"""CLI Entrypoint for Codex-5H-Reset (Headless Daemon & Terminal Commands)."""
import argparse
import datetime as dt
import json
import sys
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from .config import ConfigManager
from .core import SchedulerEngine
from .providers.codex import CodexCLIProvider


def cmd_status(config: ConfigManager) -> None:
    provider = CodexCLIProvider(codex_home=config.get_active_codex_home())
    print("\n=== Codex-5H-Reset 状态概览 ===")
    print(f"当前生效账号 Profile: {config.get_active_profile_name()}")
    print(f"CLI 认证目录: {provider.codex_home}")
    info = provider.get_account_info()
    if info.get('email'):
        print(f"登录账号: {info['email']}" + (f" ({info['name']})" if info.get('name') else ""))
    else:
        print(f"登录状态: {'已登录' if provider.is_logged_in() else '未登录'}")

    try:
        data = provider.read_limits(timeout=15)
        five_h, weekly = provider.extract_windows(data)

        if five_h:
            rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100)))
            rst_5h = dt.datetime.fromtimestamp(five_h['resetsAt']).strftime('%Y-%m-%d %H:%M:%S') if five_h.get('resetsAt') else '无'
            print(f"5小时额度: 剩余 {rem_5h:g}% | 下次刷新: {rst_5h}")

        if weekly:
            rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100)))
            rst_wk = dt.datetime.fromtimestamp(weekly['resetsAt']).strftime('%Y-%m-%d %H:%M:%S') if weekly.get('resetsAt') else '无'
            print(f"每周额度: 剩余 {rem_wk:g}% | 下次刷新: {rst_wk}")

        allowed = data.get('ordinaryUsageAllowed')
        print(f"普通额度可用性: {'可用' if allowed is True else '不可用' if allowed is False else '未知'}")

    except Exception as exc:
        print(f"读取额度失败: {exc}")

    next_at = config.get('next_at')
    if next_at:
        nxt_str = dt.datetime.fromtimestamp(next_at).strftime('%Y-%m-%d %H:%M:%S')
        print(f"下次计划自动发送时间: {nxt_str}")
    else:
        print("下次计划自动发送时间: 待定/监听中")
    print("===============================\n")


def cmd_check(config: ConfigManager, raw: bool = False) -> None:
    provider = CodexCLIProvider(codex_home=config.get_active_codex_home())
    try:
        data = provider.read_limits(timeout=20)
        if raw:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            cmd_status(config)
    except Exception as exc:
        print(f"检查失败: {exc}")
        sys.exit(1)


def cmd_send(config: ConfigManager) -> None:
    provider = CodexCLIProvider(codex_home=config.get_active_codex_home())
    print("正在发送测试心跳消息…")
    prompt = config.get('prompt', 'Reply with exactly OK.')
    try:
        reply = provider.send_heartbeat(prompt)
        print(f"发送成功！Codex 回复: {reply}")
    except Exception as exc:
        print(f"发送失败: {exc}")
        sys.exit(1)


def cmd_daemon(config: ConfigManager) -> None:
    engine = SchedulerEngine(config=config)
    engine.run_headless_daemon()


def main(args: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(description="Codex-5H-Reset: AI CLI 额度守护与5小时自动对齐工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("daemon", help="启动无头后台守护进程 (适合 Linux/VPS/NAS)")
    subparsers.add_parser("status", help="查看当前额度状态与倒计时")
    chk_p = subparsers.add_parser("check", help="从 CLI 刷新并读取最新额度")
    chk_p.add_argument("--raw", action="store_true", help="输出完整原始 JSON")
    subparsers.add_parser("send", help="立即手动发送一次心跳请求")

    prof_p = subparsers.add_parser("profile", help="多账号配置管理")
    prof_p.add_argument("--list", action="store_true", help="列出所有账号 Profile")
    prof_p.add_argument("--switch", type=str, help="切换当前活跃账号 Profile")
    prof_p.add_argument("--add", nargs=3, metavar=("ID", "NAME", "PATH"), help="添加新账号 Profile (ID 名称 目录)")

    parsed = parser.parse_args(args)
    config = ConfigManager()

    if parsed.command == "daemon":
        cmd_daemon(config)
    elif parsed.command == "status":
        cmd_status(config)
    elif parsed.command == "check":
        cmd_check(config, raw=parsed.raw)
    elif parsed.command == "send":
        cmd_send(config)
    elif parsed.command == "profile":
        if parsed.list:
            print("已配置账号 Profiles:")
            active = config.get_active_profile_name()
            for pid, pdata in config.get_profiles().items():
                cur = "*" if pid == active else " "
                print(f" {cur} [{pid}] {pdata.get('name')} -> {pdata.get('codex_home')}")
        elif parsed.switch:
            config.set_active_profile(parsed.switch)
            print(f"已切换为账号 Profile: {parsed.switch}")
        elif parsed.add:
            pid, name, ppath = parsed.add
            config.add_profile(pid, name, ppath)
            print(f"已添加账号 Profile [{pid}]: {name} ({ppath})")
        else:
            parser.print_help()
    else:
        # If no arguments provided, launch GUI by default
        from .gui.app import run_gui
        run_gui()


if __name__ == '__main__':
    main()
