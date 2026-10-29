#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyInstaller build script to create single-file executable for Codex-5H-Reset."""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def build():
    print("=" * 60)
    print("Building Codex-5H-Reset Standalone Executable")
    print("=" * 60)

    icon_ico = REPO_ROOT / "assets" / "icon.ico"
    main_py = REPO_ROOT / "main.py"
    dist_dir = REPO_ROOT / "dist"
    build_dir = REPO_ROOT / "build"

    sep = ";" if platform.system() == "Windows" else ":"
    assets_arg = f"{REPO_ROOT / 'assets'}{sep}assets"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Codex-5H-Reset",
        "--add-data", assets_arg,
    ]

    if icon_ico.exists():
        cmd.extend(["--icon", str(icon_ico)])

    # Collect submodules
    cmd.extend([
        "--hidden-import", "codex_timer",
        "--hidden-import", "codex_timer.gui",
        "--hidden-import", "codex_timer.gui.app",
        "--hidden-import", "codex_timer.gui.overlay",
        "--hidden-import", "codex_timer.gui.tray",
        "--hidden-import", "codex_timer.providers",
        "--hidden-import", "codex_timer.providers.codex",
        "--hidden-import", "codex_timer.providers.claude",
        "--hidden-import", "codex_timer.core",
        "--hidden-import", "codex_timer.config",
        "--hidden-import", "codex_timer.webhooks",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageTk",
        str(main_py)
    ])

    print(f"Executing: {' '.join(cmd)}\n")
    res = subprocess.run(cmd, cwd=str(REPO_ROOT))

    if res.returncode == 0:
        exe_name = "Codex-5H-Reset.exe" if platform.system() == "Windows" else "Codex-5H-Reset"
        target_path = dist_dir / exe_name
        if target_path.exists():
            size_mb = target_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print(f"BUILD SUCCESSFUL: {target_path} ({size_mb:.2f} MB)")
            print("=" * 60)
            return 0
        else:
            print(f"Build completed, but {target_path} was not found.")
            return 1
    else:
        print(f"Build failed with exit code {res.returncode}")
        return res.returncode


if __name__ == "__main__":
    sys.exit(build())
