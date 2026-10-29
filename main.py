#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex-5H-Reset: Automated 5-hour rate-limit reset alignment and desktop overlay for Codex CLI."""

import sys
import os

if sys.platform == 'win32':
    try:
        if len(sys.argv) > 1:
            import ctypes
            # Attach to parent console if invoked from terminal in --windowed mode
            if ctypes.windll.kernel32.AttachConsole(-1):
                sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
                sys.stderr = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure package import works when run directly as a script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "daemon", "status", "check", "send", "profile"):
        from codex_timer.cli import main as cli_main
        cli_main()
    else:
        # Default entry: start GUI application
        try:
            from codex_timer.gui.app import run_gui
            run_gui()
        except ImportError as e:
            if "_tkinter" in str(e) or "DISPLAY" in str(e) or "no display name" in str(e):
                print("Error: Graphical interface unavailable in headless environment.")
                print("Run with 'daemon' subcommand instead: python main.py daemon")
                sys.exit(1)
            raise


if __name__ == "__main__":
    main()
