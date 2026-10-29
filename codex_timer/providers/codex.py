"""OpenAI Codex CLI Rate Limit Provider."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, Any, Tuple, Optional, List

from .base import BaseRateLimitProvider

CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0


class CodexCLIProvider(BaseRateLimitProvider):
    def __init__(self, codex_home: Optional[Path] = None, base_dir: Optional[Path] = None):
        self.codex_home = codex_home or (Path.home() / '.codex')
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent.parent

    @property
    def provider_id(self) -> str:
        return 'codex'

    @property
    def display_name(self) -> str:
        return 'OpenAI Codex CLI'

    def get_env(self) -> Dict[str, str]:
        self.codex_home.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env['CODEX_HOME'] = str(self.codex_home)
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'OPENAI_BASE_URL'):
            env.pop(key, None)
        return env

    def get_auth_options(self) -> List[str]:
        return ['-c', 'cli_auth_credentials_store="file"', '-c', 'forced_login_method="chatgpt"']

    def is_available(self) -> bool:
        try:
            self.get_cli_cmd()
            return True
        except Exception:
            return False

    def is_logged_in(self) -> bool:
        return (self.codex_home / 'auth.json').exists()

    def get_account_info(self) -> Dict[str, str]:
        """Extract user email and display name from auth tokens without exposing secrets."""
        auth_file = self.codex_home / 'auth.json'
        info = {'email': '', 'name': '', 'logged_in': False}
        if not auth_file.exists():
            return info
        info['logged_in'] = True
        try:
            import base64
            data = json.loads(auth_file.read_text(encoding='utf-8'))
            id_tok = data.get('tokens', {}).get('id_token')
            if id_tok and '.' in id_tok:
                payload_b64 = id_tok.split('.')[1]
                payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
                info['email'] = payload.get('email', '')
                info['name'] = payload.get('name', '')
        except Exception:
            pass
        return info

    def get_cli_cmd(self) -> List[str]:
        # Cross-platform CLI resolution
        node = shutil.which('node')
        if sys.platform == 'win32':
            script = Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/@openai/codex/bin/codex.js'
            if script.exists() and node:
                return [node, str(script)]
            exe = shutil.which('codex.exe')
            if exe:
                return [exe]
        else:
            # macOS / Linux paths
            for p in [
                Path.home() / '.nvm/versions/node',
                Path('/usr/local/lib/node_modules/@openai/codex/bin/codex.js'),
                Path('/usr/lib/node_modules/@openai/codex/bin/codex.js')
            ]:
                if p.exists() and node:
                    return [node, str(p)]
            binary = shutil.which('codex')
            if binary:
                return [binary]
        raise RuntimeError('未找到 Codex CLI，请全局安装后重试：npm i -g @openai/codex')

    def read_limits(self, timeout: int = 35) -> Dict[str, Any]:
        if not self.is_logged_in():
            raise RuntimeError('Codex CLI 尚未登录。请先在终端运行 codex 进行 ChatGPT 账号登录。')

        cmd = self.get_cli_cmd() + self.get_auth_options() + ['app-server', '--stdio']
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                encoding='utf-8', creationflags=CREATE_NO_WINDOW, env=self.get_env())
        lines = queue.Queue()

        def reader():
            for line in proc.stdout:
                try:
                    lines.put(json.loads(line))
                except ValueError:
                    pass
            lines.put({'error': {'message': '额度服务已退出'}})

        threading.Thread(target=reader, daemon=True).start()

        def send(val):
            proc.stdin.write(json.dumps(val) + '\n')
            proc.stdin.flush()

        def receive(ident):
            end = time.monotonic() + timeout
            while True:
                try:
                    msg = lines.get(timeout=max(0.01, end - time.monotonic()))
                except queue.Empty:
                    raise TimeoutError('额度读取超时，请检查网络或重新登录 CLI。') from None
                if msg.get('id') == ident or ('error' in msg and 'id' not in msg):
                    if 'error' in msg:
                        raise RuntimeError(msg['error'].get('message', '额度读取失败'))
                    return msg.get('result', {})
                if time.monotonic() >= end:
                    raise TimeoutError('额度读取超时')

        try:
            send({'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'codex_timer', 'version': '2.0.0'}, 'capabilities': None}})
            receive(1)
            send({'method': 'initialized', 'params': {}})
            send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
            return receive(2)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    def extract_windows(self, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        snapshots = data.get('rateLimitsByLimitId') or {'codex': data.get('rateLimits', {})}
        five_h, weekly = None, None
        for name, snap in snapshots.items():
            if not snap:
                continue
            for slot in ('primary', 'secondary'):
                w = snap.get(slot)
                if not w:
                    continue
                mins = w.get('windowDurationMins', 0)
                if mins == 300 and five_h is None:
                    five_h = w
                elif mins >= 10000 and weekly is None:
                    weekly = w
        if five_h is None and snapshots.get('codex', {}).get('primary'):
            five_h = snapshots['codex']['primary']
        if weekly is None and snapshots.get('codex', {}).get('secondary'):
            weekly = snapshots['codex']['secondary']
        return five_h, weekly

    def send_heartbeat(self, prompt: str) -> str:
        if not self.is_logged_in():
            raise RuntimeError('Codex CLI 尚未登录。')
        workspace = self.base_dir / 'empty-workspace'
        workspace.mkdir(exist_ok=True)

        args = self.get_cli_cmd() + self.get_auth_options() + [
            'exec', '--skip-git-repo-check', '--ephemeral', '--ignore-user-config',
            '--sandbox', 'read-only', '-C', str(workspace), '--json', '-'
        ]
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding='utf-8', errors='replace',
                                creationflags=CREATE_NO_WINDOW, env=self.get_env())
        try:
            output, error = proc.communicate(prompt, timeout=180)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError('发送超过 180 秒，已强制终止请求。')

        events = []
        for line in output.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass

        if proc.returncode or not any(e.get('type') == 'turn.completed' for e in events):
            errors = [e.get('message') or str(e.get('error', '')) for e in events
                      if e.get('type') in ('error', 'turn.failed')]
            raise RuntimeError(('\n'.join(errors) or error or output or '心跳请求未完成')[-1800:])

        return next((e['item'].get('text', '') for e in reversed(events)
                     if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message'), '完成')
