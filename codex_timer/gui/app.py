"""Main GUI Window for Codex-5H-Reset (Windows 11 Fluent Design with CustomTkinter)."""
import ctypes
import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Dict, Any, Tuple

import customtkinter as ctk
from PIL import Image

from ..config import ConfigManager, DEFAULT_PROMPT
from ..core import SchedulerEngine, reset_target, five_hour
from ..auth_vault import AuthVault
from .overlay import SingleLineOverlay
from .tray import TrayManager

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def enable_windows_fluent_dwm(hwnd: int) -> None:
    """Enable Windows 11 rounded window corners and immersive styling via DWM API."""
    if sys.platform != 'win32' or not hwnd:
        return
    try:
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


class App:
    """Modern Windows 11 Fluent Application Window for Codex-5H-Reset."""

    def __init__(self, root: ctk.CTk, config: Optional[ConfigManager] = None):
        self.root = root
        self.config = config or ConfigManager()
        self.engine = SchedulerEngine(config=self.config, log_callback=self._on_engine_log)

        # UI State variables
        self.when = tk.StringVar(value=(dt.datetime.now() + dt.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'))
        self.quota = tk.StringVar(value='额度状态：尚未读取')
        self.status = tk.StringVar(value='自动刷新运行中')
        self.show_overlay = tk.BooleanVar(value=bool(self.config.get('show_overlay', False)))
        self.anim_dots = 0
        self._last_banner_key = None

        # High-DPI scaling on Windows
        if sys.platform == 'win32':
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

        # Window Configuration (More comfortable & spacious dimensions)
        root.title('Codex 定时助手')
        root.geometry('920x720')
        root.minsize(900, 700)
        root.resizable(True, True)

        # Apply Windows 11 DWM rounded corners
        root.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
            enable_windows_fluent_dwm(hwnd)
        except Exception:
            pass

        # Load feather quill icons
        self.icon_png = BASE_DIR / 'assets' / 'icon.png'
        self.icon_ico = BASE_DIR / 'assets' / 'icon.ico'
        self.ctk_icon_img = None
        if self.icon_png.exists():
            try:
                pil_img = Image.open(self.icon_png)
                self.ctk_icon_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(40, 40))
                self._app_icon_tk = tk.PhotoImage(file=str(self.icon_png))
                root.iconphoto(False, self._app_icon_tk)
            except Exception:
                pass
        if sys.platform == 'win32' and self.icon_ico.exists():
            try:
                root.iconbitmap(str(self.icon_ico))
            except Exception:
                pass

        # Main Scrollable / Padded Container
        self.main_container = ctk.CTkFrame(root, corner_radius=0, fg_color="transparent")
        self.main_container.pack(fill='both', expand=True, padx=24, pady=(18, 20))

        # Build Fluent UI Sections
        self._build_header()
        self._build_quota_dashboard()
        self._build_execution_card()
        self._build_logs_card()
        self._build_footer()

        # Immediate sync profile info on startup
        self.refresh_profile_ui()

        # Managers
        self.overlay_mgr = SingleLineOverlay(root=self.root, app_ref=self)
        self.tray_mgr = TrayManager(app_ref=self)

        self.load()
        self.tray_mgr.start()
        self.update_btn_state()

        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Destroy>', self.on_destroy)
        root.after(200, self.tick)
        root.after(600, self.check)

        if self.show_overlay.get():
            root.after(400, self.overlay_mgr.show)

    # =========================================================================
    # Fluent UI Construction
    # =========================================================================

    def _build_header(self) -> None:
        """Windows 11 Header bar with logo, title, account pill, and quick switches."""
        header = ctk.CTkFrame(self.main_container, corner_radius=12,
                              fg_color=("#FFFFFF", "#2B2B2B"),
                              border_width=1, border_color=("#E2E8F0", "#383838"))
        header.pack(fill='x', pady=(0, 14), ipady=4)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill='x', padx=18, pady=12)

        # Left: App Icon & Title Stack
        left_box = ctk.CTkFrame(h_inner, fg_color="transparent")
        left_box.pack(side='left', fill='y')

        if self.ctk_icon_img:
            lbl_icon = ctk.CTkLabel(left_box, image=self.ctk_icon_img, text="")
            lbl_icon.pack(side='left', padx=(0, 14))

        title_stack = ctk.CTkFrame(left_box, fg_color="transparent")
        title_stack.pack(side='left')

        row_title = ctk.CTkFrame(title_stack, fg_color="transparent")
        row_title.pack(anchor='w')

        lbl_app = ctk.CTkLabel(row_title, text="Codex 定时助手",
                               font=ctk.CTkFont(family="Microsoft YaHei UI", size=20, weight="bold"),
                               text_color=("#0F172A", "#FFFFFF"))
        lbl_app.pack(side='left', padx=(0, 10))

        # Pro / Open Source Badge
        lbl_badge = ctk.CTkLabel(row_title, text="PRO 守护版",
                                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                 fg_color=("#EFF6FF", "#1E293B"),
                                 text_color=("#2563EB", "#38BDF8"),
                                 corner_radius=8, padx=9, pady=3)
        lbl_badge.pack(side='left', padx=(0, 10))

        # Clickable Account Pill (High contrast & readable)
        self.btn_account_pill = ctk.CTkButton(
            row_title,
            text=f"🟢 {self.config.get_active_profile_name()}",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            fg_color=("#DCFCE7", "#064E3B"),
            hover_color=("#BBF7D0", "#065F46"),
            text_color=("#15803D", "#34D399"),
            corner_radius=14,
            height=28,
            command=self.open_account_manager,
            cursor="hand2"
        )
        self.btn_account_pill.pack(side='left')

        lbl_subtitle = ctk.CTkLabel(title_stack,
                                    text="开机即用 · 额度自动对齐刷新 · 多账号会话无损切换 · 零复杂配置",
                                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                                    text_color=("#334155", "#E2E8F0"))
        lbl_subtitle.pack(anchor='w', pady=(3, 0))

        # Right: Modern Fluent Controls
        right_box = ctk.CTkFrame(h_inner, fg_color="transparent")
        right_box.pack(side='right', fill='y')

        # Windows 11 style animated pill switch for desktop overlay
        self.sw_overlay = ctk.CTkSwitch(
            right_box,
            text="桌面悬浮条",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            variable=self.show_overlay,
            command=self.toggle_overlay,
            switch_width=48,
            switch_height=24,
            progress_color="#2563EB",
            text_color=("#0F172A", "#FFFFFF"),
            cursor="hand2"
        )
        self.sw_overlay.pack(side='left', padx=(0, 12))

        # Overlay Appearance Button
        btn_style = ctk.CTkButton(
            right_box,
            text="🎨 外观",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            width=70,
            height=32,
            corner_radius=8,
            fg_color=("#F1F5F9", "#334155"),
            hover_color=("#E2E8F0", "#475569"),
            text_color=("#1E293B", "#F8FAFC"),
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            command=self.open_overlay_settings,
            cursor="hand2"
        )
        btn_style.pack(side='left', padx=(0, 8))

        # Account Vault Manager Button
        btn_vault = ctk.CTkButton(
            right_box,
            text="👥 凭据库",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            width=84,
            height=32,
            corner_radius=8,
            fg_color=("#2563EB", "#1D4ED8"),
            hover_color=("#1D4ED8", "#1E40AF"),
            text_color="#FFFFFF",
            command=self.open_account_manager,
            cursor="hand2"
        )
        btn_vault.pack(side='left', padx=(0, 8))

        # Dark / Light Theme Toggle Button
        self.btn_theme = ctk.CTkButton(
            right_box,
            text="🌓",
            font=ctk.CTkFont(size=14),
            width=38,
            height=32,
            corner_radius=8,
            fg_color=("#F1F5F9", "#334155"),
            hover_color=("#E2E8F0", "#475569"),
            text_color=("#1E293B", "#F8FAFC"),
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            command=self.toggle_theme,
            cursor="hand2"
        )
        self.btn_theme.pack(side='left')

    def _build_quota_dashboard(self) -> None:
        """Fluent 2.0 Quota Dashboard with dynamic progress bars, vivid colors, and clear fonts."""
        dash_frame = ctk.CTkFrame(self.main_container, corner_radius=12,
                                  fg_color=("#FFFFFF", "#2B2B2B"),
                                  border_width=1, border_color=("#E2E8F0", "#383838"))
        dash_frame.pack(fill='x', pady=(0, 14), ipady=4)

        d_inner = ctk.CTkFrame(dash_frame, fg_color="transparent")
        d_inner.pack(fill='x', padx=18, pady=14)

        # Header of Dashboard
        d_top = ctk.CTkFrame(d_inner, fg_color="transparent")
        d_top.pack(fill='x', pady=(0, 12))

        lbl_dash_title = ctk.CTkLabel(d_top, text="📊 额度与实时看板",
                                      font=ctk.CTkFont(family="Microsoft YaHei UI", size=15, weight="bold"),
                                      text_color=("#0F172A", "#FFFFFF"))
        lbl_dash_title.pack(side='left')

        d_top_right = ctk.CTkFrame(d_top, fg_color="transparent")
        d_top_right.pack(side='right')

        lbl_poll = ctk.CTkLabel(d_top_right, text="静默轮询: 每 15 分钟",
                                font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                fg_color=("#EFF6FF", "#1E293B"),
                                text_color=("#2563EB", "#38BDF8"),
                                corner_radius=6, padx=10, pady=4)
        lbl_poll.pack(side='left', padx=(0, 10))

        btn_refresh = ctk.CTkButton(
            d_top_right,
            text="🔄 立即刷新",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            width=96,
            height=30,
            corner_radius=8,
            fg_color=("#2563EB", "#1D4ED8"),
            hover_color=("#1D4ED8", "#1E40AF"),
            text_color="#FFFFFF",
            command=self.check,
            cursor="hand2"
        )
        btn_refresh.pack(side='left')

        # Two Main Metric Cards (5H and Weekly) Side-by-Side
        grid_frame = ctk.CTkFrame(d_inner, fg_color="transparent")
        grid_frame.pack(fill='x')
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)

        # Card 1: 5-Hour Limit Card
        card_5h = ctk.CTkFrame(grid_frame, corner_radius=10,
                               fg_color=("#F8FAFC", "#1E1E1E"),
                               border_width=1, border_color=("#E2E8F0", "#333333"))
        card_5h.grid(row=0, column=0, sticky='nsew', padx=(0, 8), pady=2, ipady=6)

        card_5h_in = ctk.CTkFrame(card_5h, fg_color="transparent")
        card_5h_in.pack(fill='both', padx=14, pady=12)

        # 5H Card Header
        h_5h = ctk.CTkFrame(card_5h_in, fg_color="transparent")
        h_5h.pack(fill='x')
        ctk.CTkLabel(h_5h, text="⏳ 5小时周期额度",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                     text_color=("#0F172A", "#FFFFFF")).pack(side='left')
        self.badge_5h_status = ctk.CTkLabel(h_5h, text="正在读取",
                                            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                            fg_color=("#EFF6FF", "#1E293B"),
                                            text_color=("#2563EB", "#38BDF8"),
                                            corner_radius=6, padx=8, pady=3)
        self.badge_5h_status.pack(side='right')

        # 5H Big Value & Progress Bar
        self.lbl_5h_pct = ctk.CTkLabel(card_5h_in, text="--%",
                                      font=ctk.CTkFont(family="Segoe UI Variable Display", size=32, weight="bold"),
                                      text_color=("#2563EB", "#38BDF8"))
        self.lbl_5h_pct.pack(anchor='w', pady=(2, 4))

        self.prog_5h = ctk.CTkProgressBar(card_5h_in, height=10, corner_radius=5,
                                          fg_color=("#E2E8F0", "#3F3F46"),
                                          progress_color="#2563EB")
        self.prog_5h.set(0.0)
        self.prog_5h.pack(fill='x', pady=(2, 8))

        self.lbl_5h_meta = ctk.CTkLabel(card_5h_in, text="⏰ 刷新时间: 正在检测...",
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                                       text_color=("#1E40AF", "#60A5FA"))
        self.lbl_5h_meta.pack(anchor='w')

        # Card 2: Weekly Limit Card
        card_wk = ctk.CTkFrame(grid_frame, corner_radius=10,
                               fg_color=("#F8FAFC", "#1E1E1E"),
                               border_width=1, border_color=("#E2E8F0", "#333333"))
        card_wk.grid(row=0, column=1, sticky='nsew', padx=(8, 0), pady=2, ipady=6)

        card_wk_in = ctk.CTkFrame(card_wk, fg_color="transparent")
        card_wk_in.pack(fill='both', padx=14, pady=12)

        # Weekly Card Header
        h_wk = ctk.CTkFrame(card_wk_in, fg_color="transparent")
        h_wk.pack(fill='x')
        ctk.CTkLabel(h_wk, text="📅 每周额度总览",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                     text_color=("#0F172A", "#FFFFFF")).pack(side='left')
        self.badge_wk_status = ctk.CTkLabel(h_wk, text="普通额度可用",
                                            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                            fg_color=("#DCFCE7", "#064E3B"),
                                            text_color=("#15803D", "#34D399"),
                                            corner_radius=6, padx=8, pady=3)
        self.badge_wk_status.pack(side='right')

        # Weekly Big Value & Progress Bar
        self.lbl_wk_pct = ctk.CTkLabel(card_wk_in, text="--%",
                                      font=ctk.CTkFont(family="Segoe UI Variable Display", size=32, weight="bold"),
                                      text_color=("#10B981", "#34D399"))
        self.lbl_wk_pct.pack(anchor='w', pady=(2, 4))

        self.prog_wk = ctk.CTkProgressBar(card_wk_in, height=10, corner_radius=5,
                                          fg_color=("#E2E8F0", "#3F3F46"),
                                          progress_color="#10B981")
        self.prog_wk.set(0.0)
        self.prog_wk.pack(fill='x', pady=(2, 8))

        self.lbl_wk_meta = ctk.CTkLabel(card_wk_in, text="📅 周刷新: 正在检测...",
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                                       text_color=("#065F46", "#34D399"))
        self.lbl_wk_meta.pack(anchor='w')

    def _build_execution_card(self) -> None:
        """Fluent Hero Card displaying real-time execution status, countdown, and primary action controls."""
        self.card_hero = ctk.CTkFrame(self.main_container, corner_radius=12,
                                     fg_color=("#ECFDF5", "#064E3B"),
                                     border_width=1, border_color=("#A7F3D0", "#047857"))
        self.card_hero.pack(fill='x', pady=(0, 14), ipady=6)

        c_inner = ctk.CTkFrame(self.card_hero, fg_color="transparent")
        c_inner.pack(fill='x', padx=18, pady=14)

        # Top Status Headline & Sub-caption
        self.lbl_hero_title = ctk.CTkLabel(
            c_inner,
            text="🟢 自动刷新运行中 · 待命中",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
            text_color=("#065F46", "#A7F3D0")
        )
        self.lbl_hero_title.pack(anchor='w')

        self.lbl_hero_desc = ctk.CTkLabel(
            c_inner,
            text="已连接后台守护引擎，只要软件开着就会持续自动跟随刷新额度",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            text_color=("#047857", "#6EE7B7")
        )
        self.lbl_hero_desc.pack(anchor='w', pady=(2, 12))

        # Timing Row
        row_timing = ctk.CTkFrame(c_inner, fg_color="transparent")
        row_timing.pack(fill='x', pady=(0, 14))

        ctk.CTkLabel(row_timing, text="定时发送时间",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                     text_color=("#0F172A", "#FFFFFF")).pack(side='left', padx=(0, 10))

        self.entry_when = ctk.CTkEntry(
            row_timing,
            textvariable=self.when,
            width=230,
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            fg_color=("#FFFFFF", "#1E1E1E"),
            border_color=("#CBD5E1", "#475569")
        )
        self.entry_when.pack(side='left', padx=(0, 10))

        btn_use_reset = ctk.CTkButton(
            row_timing,
            text="对齐刷新时间 + 2分钟",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            height=36,
            corner_radius=8,
            fg_color=("#F1F5F9", "#1E1E1E"),
            hover_color=("#E2E8F0", "#333333"),
            text_color=("#0F172A", "#FFFFFF"),
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            command=self.use_reset,
            cursor="hand2"
        )
        btn_use_reset.pack(side='left', padx=(0, 8))

        btn_apply_time = ctk.CTkButton(
            row_timing,
            text="应用自定义时间",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
            height=36,
            corner_radius=8,
            fg_color=("#2563EB", "#1D4ED8"),
            hover_color=("#1D4ED8", "#1E40AF"),
            text_color="#FFFFFF",
            command=self.apply_custom_time,
            cursor="hand2"
        )
        btn_apply_time.pack(side='left', padx=(0, 10))

        ctk.CTkLabel(row_timing, text="(全自动对齐，无需手动干预)",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                     text_color=("#475569", "#CBD5E1")).pack(side='left')

        # Action Buttons Row
        row_actions = ctk.CTkFrame(c_inner, fg_color="transparent")
        row_actions.pack(fill='x')

        self.btn_pause = ctk.CTkButton(
            row_actions,
            text="⏸  暂停自动刷新",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
            height=40,
            width=170,
            corner_radius=8,
            fg_color="#D97706",
            hover_color="#B45309",
            text_color="#FFFFFF",
            command=self.toggle_pause,
            cursor="hand2"
        )
        self.btn_pause.pack(side='left', padx=(0, 12))

        self.btn_send_now = ctk.CTkButton(
            row_actions,
            text="⚡  立即发送一次",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
            height=40,
            width=170,
            corner_radius=8,
            fg_color=("#2563EB", "#1D4ED8"),
            hover_color=("#1D4ED8", "#1E40AF"),
            text_color="#FFFFFF",
            command=self.send_now,
            cursor="hand2"
        )
        self.btn_send_now.pack(side='left')

    def _build_logs_card(self) -> None:
        """Modern Terminal / Logs card with copy and clear actions."""
        card_logs = ctk.CTkFrame(self.main_container, corner_radius=12,
                                 fg_color=("#FFFFFF", "#2B2B2B"),
                                 border_width=1, border_color=("#E2E8F0", "#383838"))
        card_logs.pack(fill='both', expand=True, pady=(0, 10), ipady=2)

        l_inner = ctk.CTkFrame(card_logs, fg_color="transparent")
        l_inner.pack(fill='both', expand=True, padx=16, pady=12)

        # Logs Header
        l_top = ctk.CTkFrame(l_inner, fg_color="transparent")
        l_top.pack(fill='x', pady=(0, 8))

        ctk.CTkLabel(l_top, text="📋 调度与运行日志",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
                     text_color=("#0F172A", "#FFFFFF")).pack(side='left')

        l_top_right = ctk.CTkFrame(l_top, fg_color="transparent")
        l_top_right.pack(side='right')

        btn_copy = ctk.CTkButton(
            l_top_right,
            text="📋 复制全部",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
            width=86,
            height=28,
            corner_radius=6,
            fg_color=("#F1F5F9", "#334155"),
            hover_color=("#E2E8F0", "#475569"),
            text_color=("#0F172A", "#F8FAFC"),
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            command=self.copy_logs,
            cursor="hand2"
        )
        btn_copy.pack(side='left', padx=(0, 6))

        btn_clear = ctk.CTkButton(
            l_top_right,
            text="🗑️ 清空显示",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
            width=86,
            height=28,
            corner_radius=6,
            fg_color=("#F1F5F9", "#334155"),
            hover_color=("#E2E8F0", "#475569"),
            text_color=("#0F172A", "#F8FAFC"),
            border_width=1,
            border_color=("#CBD5E1", "#475569"),
            command=self.clear_logs,
            cursor="hand2"
        )
        btn_clear.pack(side='left')

        # Fluent Dark / Slate Monospace Text Area
        self.logs = ctk.CTkTextbox(
            l_inner,
            height=130,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=("#0F172A", "#141824"),
            text_color="#E2E8F0",
            wrap="char"
        )
        self.logs.pack(fill='both', expand=True)

    def _build_footer(self) -> None:
        """Bottom note and status indicator."""
        foot_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        foot_frame.pack(fill='x', pady=(2, 0))

        lbl_foot = ctk.CTkLabel(
            foot_frame,
            text="💡 软件开着就会持续自动刷新额度窗口。开启右上角“桌面悬浮条”可实时将极简条钉在桌面上。",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
            text_color=("#334155", "#CBD5E1")
        )
        lbl_foot.pack(anchor='w')

    # =========================================================================
    # Properties mapped to SchedulerEngine
    # =========================================================================
    @property
    def busy(self): return self.engine.busy
    @property
    def exec_state(self): return self.engine.exec_state
    @property
    def exec_detail(self): return self.engine.exec_detail
    @property
    def next_at(self): return self.engine.next_at
    @next_at.setter
    def next_at(self, val): self.engine.next_at = val
    @property
    def auto_active(self): return self.engine.auto_active
    @auto_active.setter
    def auto_active(self, val): self.engine.auto_active = val
    @property
    def handled_resets(self): return self.engine.handled_resets
    @property
    def scheduled_reset(self): return self.engine.scheduled_reset
    @scheduled_reset.setter
    def scheduled_reset(self, val): self.engine.scheduled_reset = val
    @property
    def latest(self): return self.engine.latest
    @latest.setter
    def latest(self, val): self.engine.latest = val

    # =========================================================================
    # Theme & Dialog Actions
    # =========================================================================

    def toggle_theme(self) -> None:
        """Toggle between Dark and Light mode dynamically."""
        cur = ctk.get_appearance_mode()
        new_mode = "Light" if cur.lower() == "dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        self.log(f"已切换界面主题至：{new_mode} 模式")

    def _on_engine_log(self, text: str) -> None:
        self.log(text)

    def log(self, value: str) -> None:
        ts = dt.datetime.now().strftime('%m-%d %H:%M:%S')
        line = f"[{ts}] {value}\n"
        self.logs.configure(state='normal')
        self.logs.insert('end', line)
        try:
            line_count = int(self.logs.index('end-1c').split('.')[0])
            if line_count > 200:
                self.logs.delete('1.0', f'{line_count - 180}.0')
        except Exception:
            pass
        self.logs.see('end')
        self.logs.configure(state='disabled')
        with (BASE_DIR / 'activity.log').open('a', encoding='utf-8') as f:
            f.write(line)

    def copy_logs(self) -> None:
        try:
            content = self.logs.get("1.0", "end").strip()
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.log("运行日志已全部复制到剪贴板。")
        except Exception:
            pass

    def clear_logs(self) -> None:
        self.logs.configure(state='normal')
        self.logs.delete('1.0', 'end')
        self.logs.configure(state='disabled')

    def toggle_overlay(self) -> None:
        if self.show_overlay.get():
            self.overlay_mgr.show()
        else:
            self.overlay_mgr.hide()
        self.config.set('show_overlay', self.show_overlay.get())

    def toggle_overlay_from_tray(self) -> None:
        self.show_overlay.set(not self.show_overlay.get())
        self.toggle_overlay()

    def open_overlay_settings(self) -> None:
        """Open HUD appearance, background color, and opacity settings."""
        if not self.show_overlay.get():
            self.show_overlay.set(True)
            self.toggle_overlay()
        self.overlay_mgr.open_settings_dialog()

    def open_account_manager(self) -> None:
        """Modern Fluent Dialog for multi-account Auth Vault management with 100% session preservation."""
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("👥 多账号凭据库（会话数据 100% 共享）")
        dlg.geometry("580x560")
        dlg.resizable(False, False)
        dlg.attributes('-topmost', True)

        try:
            hwnd = ctypes.windll.user32.GetParent(dlg.winfo_id()) or dlg.winfo_id()
            enable_windows_fluent_dwm(hwnd)
        except Exception:
            pass

        d_body = ctk.CTkFrame(dlg, corner_radius=0, fg_color="transparent")
        d_body.pack(fill='both', expand=True, padx=22, pady=18)

        # Header Title Stack
        h_box = ctk.CTkFrame(d_body, fg_color="transparent")
        h_box.pack(fill='x', pady=(0, 12))

        ctk.CTkLabel(h_box, text="👥 多账号凭据库 (Auth Vault)",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=16, weight="bold"),
                     text_color=("#0F172A", "#F8FAFC")).pack(anchor='w')
        ctk.CTkLabel(h_box, text="💡 换号只切换扣费额度，所有项目会话、历史聊天与技能库 100% 完整保留！",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                     text_color=("#2563EB", "#38BDF8")).pack(anchor='w', pady=(3, 0))

        # Active Account Banner
        top_banner = ctk.CTkFrame(d_body, corner_radius=10,
                                  fg_color=("#DCFCE7", "#064E3B"),
                                  border_width=1, border_color=("#86EFAC", "#047857"))
        top_banner.pack(fill='x', pady=(0, 14), ipady=6)

        lbl_active_acc = ctk.CTkLabel(top_banner, text="正在读取当前生效凭据…",
                                      font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                                      text_color=("#15803D", "#34D399"))
        lbl_active_acc.pack(anchor='w', padx=14, pady=6)

        def sync_active_banner():
            act = AuthVault.get_active_account_info()
            em = act.get('email') or '未登录'
            lbl_active_acc.configure(text=f"🟢 当前生效账号：{em} (所有工程与会话无缝续接)")

        sync_active_banner()

        # Section: Saved Accounts in Vault
        ctk.CTkLabel(d_body, text="已收录的账号列表（点击直接热切换）：",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                     text_color=("#0F172A", "#FFFFFF")).pack(anchor='w', pady=(0, 8))

        list_scroll = ctk.CTkScrollableFrame(d_body, height=230, corner_radius=10,
                                             fg_color=("#FFFFFF", "#2B2B2B"),
                                             border_width=1, border_color=("#E2E8F0", "#383838"))
        list_scroll.pack(fill='both', expand=True, pady=(0, 14))

        def refresh_accounts():
            for w in list_scroll.winfo_children():
                w.destroy()

            AuthVault.backup_current_to_vault()
            saved = AuthVault.list_saved_accounts()
            act = AuthVault.get_active_account_info()
            active_email = act.get('email')

            if not saved:
                ctk.CTkLabel(list_scroll, text="暂无保存的账号凭据。点击下方【收录刚登录的账号】即可添加。",
                             font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                             text_color=("#64748B", "#94A3B8")).pack(pady=24)
                return

            for acc in saved:
                em = acc['email']
                nm = acc.get('name') or 'Codex User'
                is_cur = (em == active_email)

                row = ctk.CTkFrame(list_scroll, corner_radius=8,
                                   fg_color=("#F0FDF4", "#064E3B") if is_cur else ("#F8FAFC", "#1E1E1E"),
                                   border_width=1,
                                   border_color=("#86EFAC", "#047857") if is_cur else ("#E2E8F0", "#333333"))
                row.pack(fill='x', pady=4, padx=4)

                r_in = ctk.CTkFrame(row, fg_color="transparent")
                r_in.pack(fill='x', padx=12, pady=10)

                col_info = ctk.CTkFrame(r_in, fg_color="transparent")
                col_info.pack(side='left')

                ctk.CTkLabel(col_info, text=f"👤 {em}",
                             font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                             text_color=("#0F172A", "#F8FAFC")).pack(anchor='w')
                ctk.CTkLabel(col_info, text=f"昵称/备注: {nm}",
                             font=ctk.CTkFont(family="Microsoft YaHei UI", size=10),
                             text_color=("#475569", "#CBD5E1")).pack(anchor='w')

                if is_cur:
                    badge = ctk.CTkLabel(r_in, text="● 当前生效中",
                                         font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                         text_color=("#15803D", "#34D399"))
                    badge.pack(side='right', padx=8)
                else:
                    btn_sw = ctk.CTkButton(r_in, text="⚡ 切为此号",
                                           font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                           width=88, height=28, corner_radius=6,
                                           fg_color=("#2563EB", "#1D4ED8"),
                                           hover_color=("#1D4ED8", "#1E40AF"),
                                           text_color="#FFFFFF",
                                           command=lambda target_em=em: do_swap(target_em))
                    btn_sw.pack(side='right', padx=4)

        def do_swap(email: str):
            if AuthVault.switch_to_account(email):
                self.engine.reload_provider()
                self.refresh_profile_ui()
                sync_active_banner()
                refresh_accounts()
                self.check()
                self.log(f"已一键热切换至账号：{email}！所有项目会话与历史数据 100% 完整保留。")

        refresh_accounts()

        # Bottom Actions Frame
        b_frame = ctk.CTkFrame(d_body, fg_color="transparent")
        b_frame.pack(fill='x')

        def do_add_new():
            AuthVault.backup_current_to_vault()
            cmd = self.engine.provider.get_cli_cmd() + self.engine.provider.get_auth_options() + ['login', '--device-auth']
            subprocess.Popen(cmd, env=self.engine.provider.get_env(), creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
            self.log("已弹出浏览器登录窗口。完成登录后，点击下方【收录刚登录的账号】按钮即可保存！")

        def do_capture_new():
            new_em = AuthVault.backup_current_to_vault()
            self.engine.reload_provider()
            self.refresh_profile_ui()
            sync_active_banner()
            refresh_accounts()
            self.check()
            messagebox.showinfo("收录成功", f"新账号凭据 [{new_em}] 已成功收录！随时可一键切换。")
            self.log(f"已收录新账号 [{new_em}] 至凭据库。")

        btn_new_login = ctk.CTkButton(b_frame, text="➕ 登录另一个新账号...",
                                      font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                      height=34, corner_radius=8,
                                      fg_color=("#F1F5F9", "#334155"),
                                      hover_color=("#E2E8F0", "#475569"),
                                      text_color=("#0F172A", "#F8FAFC"),
                                      command=do_add_new)
        btn_new_login.pack(side='left', padx=(0, 10))

        btn_capture = ctk.CTkButton(b_frame, text="📥 收录刚登录的账号",
                                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                                    height=34, corner_radius=8,
                                    fg_color=("#10B981", "#059669"),
                                    hover_color=("#059669", "#047857"),
                                    text_color="#FFFFFF",
                                    command=do_capture_new)
        btn_capture.pack(side='left')

    # =========================================================================
    # Scheduler Engine Interactions
    # =========================================================================

    def toggle_pause(self) -> None:
        if self.engine.auto_active:
            self.pause()
        else:
            self.resume()

    def pause(self) -> None:
        self.engine.pause()
        self.update_btn_state()

    def resume(self) -> None:
        self.engine.resume()
        self.update_btn_state()

    def start(self) -> None:
        self.resume()

    def check(self) -> None:
        self.engine.check()

    def send_now(self, scheduled: bool = False) -> None:
        self.engine.send_now(scheduled=scheduled)

    def show_limits(self, data: Dict[str, Any]) -> None:
        self.engine.latest = data
        self.refresh_profile_ui()
        five_h, weekly = self.get_extracted_windows()
        parts = []

        rem_5h = 0
        rst_5h = '无'
        if five_h:
            rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100)))
            if five_h.get('resetsAt'):
                rst_5h = dt.datetime.fromtimestamp(five_h['resetsAt']).strftime('%m-%d %H:%M:%S')
            parts.append(f"5H 剩余 {rem_5h:g}%，刷新时间 {rst_5h}")

            pct_color = "#16A34A" if rem_5h > 30 else "#D97706" if rem_5h > 0 else "#DC2626"
            self.lbl_5h_pct.configure(text=f"{rem_5h:g}%", text_color=pct_color)
            self.prog_5h.configure(progress_color=pct_color)
            self.prog_5h.set(rem_5h / 100.0)
            self.lbl_5h_meta.configure(text=f"⏰ 预计刷新: {rst_5h}", text_color=pct_color)
            if rem_5h > 30:
                self.badge_5h_status.configure(text="额度充沛", text_color="#15803D", fg_color=("#DCFCE7", "#064E3B"))
            elif rem_5h > 0:
                self.badge_5h_status.configure(text="额度见底", text_color="#B45309", fg_color=("#FEF3C7", "#78350F"))
            else:
                self.badge_5h_status.configure(text="已耗尽·待重置", text_color="#B91C1C", fg_color=("#FEE2E2", "#7F1D1D"))

        if weekly:
            rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100)))
            rst_wk = dt.datetime.fromtimestamp(weekly['resetsAt']).strftime('%m-%d %H:%M:%S') if weekly.get('resetsAt') else '无'
            parts.append(f"周额度 剩余 {rem_wk:g}%，刷新时间 {rst_wk}")

            wk_color = "#059669" if rem_wk > 30 else "#D97706" if rem_wk > 0 else "#DC2626"
            self.lbl_wk_pct.configure(text=f"{rem_wk:g}%", text_color=wk_color)
            self.prog_wk.configure(progress_color=wk_color)
            self.prog_wk.set(rem_wk / 100.0)
            self.lbl_wk_meta.configure(text=f"📅 周刷新: {rst_wk}", text_color=wk_color)

        allowed = data.get('ordinaryUsageAllowed')
        availability = '普通额度可用' if allowed is True else '普通额度不可用' if allowed is False else '可用性未提供'
        if allowed is True:
            self.badge_wk_status.configure(text="✅ 普通额度可用", text_color="#15803D", fg_color=("#DCFCE7", "#064E3B"))
        elif allowed is False:
            self.badge_wk_status.configure(text="⚠️ 普通额度不可用", text_color="#B91C1C", fg_color=("#FEE2E2", "#7F1D1D"))
        else:
            self.badge_wk_status.configure(text="额度状态正常", text_color="#2563EB", fg_color=("#EFF6FF", "#1E293B"))

        self.quota.set('额度：' + ('；'.join(parts) if parts else '未返回 5 小时窗口') + '。' + availability)
        self.log(self.quota.get())
        self.engine.sync_reset()
        self.overlay_mgr.update()

    def get_extracted_windows(self) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        return self.engine.provider.extract_windows(self.engine.latest)

    def get_5h_tooltip(self) -> str:
        five_h, _ = self.get_extracted_windows()
        if five_h and five_h.get('resetsAt'):
            rst = dt.datetime.fromtimestamp(five_h['resetsAt']).strftime('%Y-%m-%d %H:%M:%S')
            return f"5小时额度刷新时间：{rst}"
        return "5小时额度刷新时间：尚未获取"

    def get_wk_tooltip(self) -> str:
        _, weekly = self.get_extracted_windows()
        if weekly and weekly.get('resetsAt'):
            rst = dt.datetime.fromtimestamp(weekly['resetsAt']).strftime('%Y-%m-%d %H:%M:%S')
            return f"每周额度刷新时间：{rst}"
        return "每周额度刷新时间：尚未获取"

    def apply_custom_time(self) -> None:
        try:
            target_str = self.when.get().strip()
            stamp = dt.datetime.strptime(target_str, '%Y-%m-%d %H:%M:%S').timestamp()
            if stamp <= time.time():
                messagebox.showerror('时间有误', '请设置未来的时间。')
                return
            self.engine.generation += 1
            self.engine.next_at = stamp
            self.config.set('next_at', stamp)
            self.config.set('when', target_str)
            self.log(f'已手动设定定时发送时间：{target_str}')
        except ValueError:
            messagebox.showerror('格式有误', '请使用正确的日期时间格式：YYYY-MM-DD HH:MM:SS')

    def use_reset(self) -> None:
        resets = [w['resetsAt'] for w in five_hour(self.engine.latest).values() if w.get('resetsAt')]
        if not resets:
            messagebox.showinfo('暂无时间', '尚未获取到 5 小时窗口，请先检查额度，或手动设定时间。')
            return
        stamp = max(time.time() + 5, min(resets) + 120)
        self.when.set(dt.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S'))
        self.engine.next_at = stamp
        self.config.set('next_at', stamp)
        self.config.set('when', self.when.get())
        self.log(f'已对齐刷新时间 + 2 分钟：{self.when.get()}')

    def update_btn_state(self) -> None:
        if self.engine.auto_active:
            self.btn_pause.configure(text='⏸  暂停自动刷新', fg_color='#D97706', hover_color='#B45309')
        else:
            self.btn_pause.configure(text='▶  恢复自动刷新', fg_color=('#2563EB', '#1D4ED8'), hover_color=('#1D4ED8', '#1E40AF'))

    def update_live_banner(self, mode: str, title: str, desc: str) -> None:
        key = (mode, title, desc)
        if getattr(self, '_last_banner_key', None) == key:
            return
        self._last_banner_key = key

        configs = {
            'executing': {
                'card_fg': ("#FEF3C7", "#78350F"),
                'card_border': ("#F59E0B", "#B45309"),
                'title_fg': ("#B45309", "#FDE68A"),
                'desc_fg': ("#92400E", "#FCD34D")
            },
            'checking': {
                'card_fg': ("#EFF6FF", "#1E3A8A"),
                'card_border': ("#3B82F6", "#2563EB"),
                'title_fg': ("#1D4ED8", "#BFDBFE"),
                'desc_fg': ("#1E40AF", "#93C5FD")
            },
            'scheduled': {
                'card_fg': ("#ECFDF5", "#064E3B"),
                'card_border': ("#10B981", "#059669"),
                'title_fg': ("#047857", "#A7F3D0"),
                'desc_fg': ("#065F46", "#6EE7B7")
            },
            'waiting': {
                'card_fg': ("#F0FDF4", "#064E3B"),
                'card_border': ("#34D399", "#059669"),
                'title_fg': ("#047857", "#A7F3D0"),
                'desc_fg': ("#065F46", "#6EE7B7")
            },
            'paused': {
                'card_fg': ("#F1F5F9", "#27272A"),
                'card_border': ("#CBD5E1", "#3F3F46"),
                'title_fg': ("#475569", "#D4D4D8"),
                'desc_fg': ("#64748B", "#A1A1AA")
            },
        }
        cfg = configs.get(mode, configs['paused'])
        self.card_hero.configure(fg_color=cfg['card_fg'], border_color=cfg['card_border'])
        self.lbl_hero_title.configure(text=title, text_color=cfg['title_fg'])
        self.lbl_hero_desc.configure(text=desc, text_color=cfg['desc_fg'])

    def tick(self) -> None:
        self.engine.process_bus_events()

        if self.engine.next_at and not self.engine.busy and time.time() >= self.engine.next_at:
            self.engine.send_now(scheduled=True)
        elif self.engine.auto_active and not self.engine.busy and time.time() >= self.engine.poll_at:
            self.engine.check()

        self.anim_dots = (self.anim_dots + 1) % 4
        dots = '.' * self.anim_dots

        if self.engine.busy or self.engine.exec_state != 'idle':
            if self.engine.exec_state == 'sending':
                state_title = '⚡ 正在即时执行中'
                state_desc = (self.engine.exec_detail or '正在向 Codex CLI 发送消息并等待回复…') + dots
                self.update_live_banner('executing', state_title, state_desc)
                self.status.set(f'正在即时执行中：{state_desc}')
            elif self.engine.exec_state == 'checking':
                state_title = '🔄 正在即时检查额度'
                state_desc = (self.engine.exec_detail or '正在读取最新额度状态…') + dots
                self.update_live_banner('checking', state_title, state_desc)
                self.status.set(f'正在即时检查额度：{state_desc}')
            else:
                self.update_live_banner('executing', '⚡ 正在即时处理中', '请稍候…' + dots)
                self.status.set('正在处理，请稍候…')
        elif self.engine.next_at:
            secs = max(0, int(self.engine.next_at - time.time()))
            countdown_str = f'{secs//3600:02d}:{secs%3600//60:02d}:{secs%60:02d}'
            target_str = dt.datetime.fromtimestamp(self.engine.next_at).strftime('%m-%d %H:%M:%S')
            retry_hint = f' (重试中 {self.engine.retry_count}/{self.engine.max_retries})' if self.engine.retry_count > 0 else ''
            state_title = f'🟢 自动刷新运行中 · 距离下次发送 {countdown_str}{retry_hint}'
            state_desc = f'预定发送时间：{target_str} （到达后将自动触发执行）'
            self.update_live_banner('scheduled', state_title, state_desc)
            self.status.set(f'距离发送 {countdown_str}  ·  {target_str}')
        elif self.engine.auto_active:
            state_title = '🟢 自动刷新运行中 · 监听中'
            state_desc = '已开启自动跟随，等待服务端返回下一次 5 小时刷新窗口（每 15 分钟自动检测一次）'
            self.update_live_banner('waiting', state_title, state_desc)
            self.status.set('自动模式已开启 · 等待服务端返回下一次刷新时间')
        else:
            state_title = '⏸ 自动刷新已暂停'
            state_desc = '当前定时发送已暂停。点击下方“恢复自动刷新”即可继续后台守护。'
            self.update_live_banner('paused', state_title, state_desc)
            self.status.set('已暂停')

        self.overlay_mgr.update()
        self.root.after(500, self.tick)

    def refresh_profile_ui(self) -> None:
        # Check active account info in AuthVault first for instantaneous display
        vault_info = AuthVault.get_active_account_info()
        email = vault_info.get('email')
        if not email:
            cli_info = self.engine.provider.get_account_info()
            email = cli_info.get('email')
        
        p_name = self.config.get_active_profile_name()
        if email:
            txt = f"🟢 {email}"
            self.btn_account_pill.configure(
                text=txt,
                fg_color=("#DCFCE7", "#064E3B"),
                text_color=("#15803D", "#34D399")
            )
        elif vault_info.get('logged_in'):
            self.btn_account_pill.configure(
                text=f"🟢 {p_name} (已登录)",
                fg_color=("#DCFCE7", "#064E3B"),
                text_color=("#15803D", "#34D399")
            )
        else:
            self.btn_account_pill.configure(
                text=f"🔴 {p_name} (未登录)",
                fg_color=("#FEE2E2", "#7F1D1D"),
                text_color=("#DC2626", "#FCA5A5")
            )

    def restore_from_tray(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def close(self) -> None:
        if self.tray_mgr.tray_icon:
            self.root.withdraw()
            self.log('已隐藏至系统托盘，后台持续运行。双击托盘图标可重新打开。')
        elif self.engine.next_at or self.engine.busy or self.engine.auto_active:
            self.root.iconify()
            self.log('已最小化，自动刷新继续运行。')
        else:
            self.quit_app()

    def quit_app(self) -> None:
        self.overlay_mgr.hide()
        self.tray_mgr.stop()
        self.config.save()
        self.root.destroy()

    def on_destroy(self, event=None) -> None:
        if event and event.widget == self.root:
            self.overlay_mgr.hide()
            self.tray_mgr.stop()

    def load(self) -> None:
        when_saved = self.config.get('when')
        if when_saved:
            self.when.set(when_saved)
        if self.engine.next_at and self.engine.auto_active:
            self.log('已恢复定时任务；过期任务将在启动后自动补发一次。')


def run_gui():
    ctk.set_appearance_mode("System")  # Automatically matches Windows 11 Light/Dark theme!
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    App(root)
    root.mainloop()
