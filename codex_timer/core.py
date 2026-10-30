"""Core Scheduling and Rate Limit Management Engine (Headless / Decoupled)."""
import datetime as dt
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Callable

from .config import ConfigManager, DEFAULT_PROMPT
from .providers.codex import CodexCLIProvider
from .webhooks import WebhookDispatcher

logger = logging.getLogger('codex_timer.core')


def five_hour(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility helper to extract 5-hour rate limit windows."""
    snapshots = data.get('rateLimitsByLimitId') or {'codex': data.get('rateLimits', {})}
    result = {}
    for name, snapshot in snapshots.items():
        if not snapshot:
            continue
        for slot in ('primary', 'secondary'):
            window = snapshot.get(slot)
            if window and window.get('windowDurationMins') == 300:
                result[f'{name}/{slot}'] = window
    return result


def reset_target(data: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """Determine target identifier and scheduled timestamp (stamp + 30s)."""
    windows = five_hour(data)
    key = 'codex/primary' if 'codex/primary' in windows else next(iter(windows), None)
    if key is None or not windows[key].get('resetsAt'):
        return None
    stamp = windows[key]['resetsAt']
    return f'{key}:{stamp}', stamp + 30


def refresh_evidence(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """Analyze whether 5-hour window or ordinary usage changed after a message."""
    old, new = five_hour(before), five_hour(after)
    changed = any(key in old and old[key].get('resetsAt') and w.get('resetsAt')
                  and w['resetsAt'] > old[key]['resetsAt'] for key, w in new.items())
    if changed:
        return '服务端已返回新的 5 小时窗口。' + (
            '普通额度可用。' if after.get('ordinaryUsageAllowed') is True else '当前可用性请查看 Codex。')
    if before.get('ordinaryUsageAllowed') is False and after.get('ordinaryUsageAllowed') is True:
        return '服务端已确认普通额度恢复可用。'
    return '消息已成功完成；尚未确认 5 小时窗口刷新。'


class SchedulerEngine:
    """Decoupled Core Scheduling Engine for Headless CLI Daemon and GUI alike."""

    def __init__(self, config: Optional[ConfigManager] = None,
                 log_callback: Optional[Callable[[str], None]] = None,
                 limits_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
                 error_callback: Optional[Callable[[str], None]] = None):
        self.config = config or ConfigManager()
        self.log_callback = log_callback or self._default_log
        self.limits_callback = limits_callback
        self.error_callback = error_callback
        self.provider = CodexCLIProvider(codex_home=self.config.get_active_codex_home())

        self.bus = queue.Queue()
        self.busy = False
        self.exec_state = 'idle'
        self.exec_detail = ''
        self.next_at = self.config.get('next_at')
        self.latest: Dict[str, Any] = {}
        self.auto_active = self.config.get('auto_active', True)
        self.handled_resets = self.config.get('handled_resets', [])
        self.scheduled_reset = self.config.get('scheduled_reset')
        self.poll_at = 0
        self.retry_count = 0
        self.max_retries = 2
        self.generation = 0
        self.running = False

    def _default_log(self, text: str) -> None:
        ts = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] {text}")

    def log(self, text: str) -> None:
        self.log_callback(text)

    def reload_provider(self) -> None:
        """Switch to active profile's codex_home."""
        self.provider = CodexCLIProvider(codex_home=self.config.get_active_codex_home())

    def pause(self) -> None:
        self.generation += 1
        self.auto_active = False
        self.next_at = None
        self.retry_count = 0
        self.config.set('auto_active', False)
        self.config.set('next_at', None)
        self.log('已暂停自动刷新；正在执行中的请求会正常完成。')

    def resume(self) -> None:
        self.generation += 1
        self.auto_active = True
        self.retry_count = 0
        self.config.set('auto_active', True)
        self.log('已恢复自动刷新：按服务端刷新时间 + 30 秒自动对齐。')
        self.sync_reset()
        self.check()

    def start(self) -> None:
        self.resume()

    def sync_reset(self) -> None:
        if not self.auto_active:
            return
        target = reset_target(self.latest)
        if not target:
            return
        ident, stamp = target
        if ident in self.handled_resets:
            return
        if self.scheduled_reset == ident and self.next_at == stamp:
            return

        self.scheduled_reset = ident
        self.next_at = stamp
        target_str = dt.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S')
        self.config.set('scheduled_reset', ident, auto_save=False)
        self.config.set('next_at', stamp, auto_save=False)
        self.config.set('when', target_str, auto_save=True)
        self.log(f'已按刷新时间安排发送：{target_str}')

    def check(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.exec_state = 'checking'
        self.exec_detail = '正在读取最新额度状态…'
        poll_interval = self.config.get('poll_interval_seconds', 900)
        self.poll_at = time.time() + poll_interval

        def _work():
            try:
                data = self.provider.read_limits()
                self.bus.put(('limits', data))
            except Exception as exc:
                self.bus.put(('error', f'额度读取失败：{exc}'))
            finally:
                self.bus.put(('idle', None))

        threading.Thread(target=_work, daemon=True).start()

    def send_now(self, scheduled: bool = False) -> None:
        if self.busy:
            return
        self.busy = True
        self.exec_state = 'sending'
        self.exec_detail = '正在向 Codex 发送心跳并验证额度…'
        generation = self.generation

        if scheduled:
            if self.auto_active and self.scheduled_reset:
                self.handled_resets.append(self.scheduled_reset)
                self.config.set('handled_resets', self.handled_resets[-100:], auto_save=False)
                self.scheduled_reset = None
                self.config.set('scheduled_reset', None, auto_save=False)
            self.next_at = None
            self.config.set('next_at', None, auto_save=True)

        self.log('正在发送消息…')
        prompt = self.config.get('prompt', DEFAULT_PROMPT)

        def _work():
            before = {}
            try:
                try:
                    self.bus.put(('detail', '正在读取发送前额度…'))
                    before = self.provider.read_limits()
                    self.bus.put(('limits', before))
                except Exception as exc:
                    self.bus.put(('log', f'发送前额度读取失败：{exc}'))

                self.bus.put(('detail', '正在向 Codex 发送消息 (请稍候)…'))
                reply = self.provider.send_heartbeat(prompt)
                self.bus.put(('log', f'Codex 回复：{reply[:400]}'))

                try:
                    self.bus.put(('detail', '正在读取发送后额度…'))
                    after = self.provider.read_limits()
                    self.bus.put(('limits', after))
                    summary = refresh_evidence(before, after)
                except Exception:
                    summary = '消息已成功完成；额度读取失败，无法确认刷新。'

                self.bus.put(('notice', ('Codex 定时消息完成', summary)))
                self.bus.put(('success_scheduled', None))

                # Webhook alert
                wh_cfg = self.config.get('webhooks', {})
                if wh_cfg.get('notify_on_success'):
                    WebhookDispatcher.send(wh_cfg, 'Codex 额度已自动对齐', f"{summary}\n回复: {reply[:200]}")

            except Exception as exc:
                err_msg = str(exc)
                self.bus.put(('notice', ('Codex 发送失败', err_msg)))
                if scheduled:
                    self.bus.put(('retry', (generation, err_msg)))

                wh_cfg = self.config.get('webhooks', {})
                if wh_cfg.get('notify_on_failure'):
                    WebhookDispatcher.send(wh_cfg, 'Codex 定时发送失败', f"错误信息: {err_msg}")
            finally:
                self.bus.put(('done', (scheduled, generation)))

        threading.Thread(target=_work, daemon=True).start()

    def process_bus_events(self) -> None:
        try:
            while True:
                kind, val = self.bus.get_nowait()
                if kind == 'limits':
                    self.latest = val
                    self.sync_reset()
                    if self.limits_callback:
                        try:
                            self.limits_callback(val)
                        except Exception as e:
                            logger.exception("limits_callback error: %s", e)
                    wh_cfg = self.config.get('webhooks', {})
                    if wh_cfg.get('notify_on_refresh'):
                        # Trigger webhook if quota is reset
                        pass
                elif kind == 'detail':
                    self.exec_detail = val
                elif kind in ('error', 'log'):
                    self.log(str(val))
                    if kind == 'error' and self.error_callback:
                        try:
                            self.error_callback(str(val))
                        except Exception as e:
                            logger.exception("error_callback error: %s", e)
                elif kind == 'notice':
                    self.log(f"{val[0]}：{val[1]}")
                elif kind == 'success_scheduled':
                    self.retry_count = 0
                elif kind == 'retry':
                    gen, err = val
                    if gen == self.generation and self.retry_count < self.max_retries:
                        self.retry_count += 1
                        self.next_at = time.time() + 120
                        self.config.set('next_at', self.next_at)
                        self.log(f'【自动重试】将在 2 分钟后重试（第 {self.retry_count}/{self.max_retries} 次）。错误：{err[:100]}')
                elif kind == 'idle':
                    self.busy = False
                    self.exec_state = 'idle'
                    self.exec_detail = ''
                elif kind == 'done':
                    self.busy = False
                    self.exec_state = 'idle'
                    self.exec_detail = ''
                    scheduled, gen = val
                    if self.auto_active and gen == self.generation:
                        self.sync_reset()
        except queue.Empty:
            pass

    def run_headless_daemon(self) -> None:
        """Runs the scheduler continuously in headless terminal mode (for Linux/VPS/NAS)."""
        self.running = True
        self.log('Codex-5H-Reset 无头守护进程已启动。按 Ctrl+C 退出。')
        self.check()

        try:
            while self.running:
                self.process_bus_events()
                now = time.time()

                if self.next_at and not self.busy and now >= self.next_at:
                    self.send_now(scheduled=True)
                elif self.auto_active and not self.busy and now >= self.poll_at:
                    self.check()

                time.sleep(0.5)
        except KeyboardInterrupt:
            self.log('接收到中断信号，正在退出守护进程…')
            self.running = False
