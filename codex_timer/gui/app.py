"""Main GUI Window for Codex-5H-Reset (Modern Slate Theme & Fixed Dimensions)."""
import ctypes
import datetime as dt
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any, Tuple

from ..config import ConfigManager, DEFAULT_PROMPT
from ..core import SchedulerEngine, reset_target, five_hour
from .overlay import SingleLineOverlay
from .tray import TrayManager

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def create_btn(parent, text, command, bg='#2563EB', fg='#FFFFFF', hover_bg='#1D4ED8',
               font=('Microsoft YaHei UI', 9, 'bold'), padx=14, pady=6, border_color=None):
    kw = {
        'text': text,
        'command': command,
        'bg': bg,
        'fg': fg,
        'activebackground': hover_bg,
        'activeforeground': fg,
        'relief': 'flat',
        'bd': 0,
        'padx': padx,
        'pady': pady,
        'font': font,
        'cursor': 'hand2'
    }
    if border_color:
        kw['highlightthickness'] = 1
        kw['highlightbackground'] = border_color
        kw['highlightcolor'] = border_color
    else:
        kw['highlightthickness'] = 0
    btn = tk.Button(parent, **kw)
    btn.bind('<Enter>', lambda e: btn.configure(bg=hover_bg) if str(btn['state']) != 'disabled' else None)
    btn.bind('<Leave>', lambda e: btn.configure(bg=bg) if str(btn['state']) != 'disabled' else None)
    return btn


def create_card(parent, padx=16, pady=12):
    return tk.Frame(parent, bg='#FFFFFF', highlightthickness=1, highlightbackground='#E2E8F0', padx=padx, pady=pady)


class App:
    def __init__(self, root: tk.Tk, config: Optional[ConfigManager] = None):
        self.root = root
        self.config = config or ConfigManager()
        self.engine = SchedulerEngine(config=self.config, log_callback=self._on_engine_log)

        # UI State variables
        self.when = tk.StringVar(value=(dt.datetime.now() + dt.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S'))
        self.quota = tk.StringVar(value='额度状态：尚未读取')
        self.status = tk.StringVar(value='自动刷新运行中')
        self.show_overlay = tk.BooleanVar(value=self.config.get('show_overlay', False))
        self.anim_dots = 0

        # Enable high-DPI scaling on Windows if available
        if sys.platform == 'win32':
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

        # Fixed, locked window dimensions
        root.title('Codex 定时助手 v2.0')
        root.geometry('800x635')
        root.resizable(False, False)
        root.configure(bg='#F8FAFC')

        # Load and set taskbar and titlebar feather icon
        icon_png = BASE_DIR / 'assets' / 'icon.png'
        icon_ico = BASE_DIR / 'assets' / 'icon.ico'
        if icon_png.exists():
            try:
                self._app_icon_img = tk.PhotoImage(file=str(icon_png))
                root.iconphoto(False, self._app_icon_img)
            except Exception:
                pass
        if sys.platform == 'win32' and icon_ico.exists():
            try:
                root.iconbitmap(str(icon_ico))
            except Exception:
                pass

        body = tk.Frame(root, bg='#F8FAFC', padx=22, pady=16)
        body.pack(fill='both', expand=True)

        # 1. Header Frame
        header = tk.Frame(body, bg='#F8FAFC')
        header.pack(fill='x', pady=(0, 10))

        title_box = tk.Frame(header, bg='#F8FAFC')
        title_box.pack(side='left')

        title_row = tk.Frame(title_box, bg='#F8FAFC')
        title_row.pack(anchor='w')
        tk.Label(title_row, text='Codex 定时助手', font=('Microsoft YaHei UI', 16, 'bold'), bg='#F8FAFC', fg='#0F172A').pack(side='left')
        tk.Label(title_row, text=' 开源守护版', font=('Microsoft YaHei UI', 8, 'bold'), bg='#EFF6FF', fg='#2563EB', padx=6, pady=1).pack(side='left', padx=(8, 0))

        tk.Label(title_box, text='开机即用 · 额度刷新自动对齐 · 多账号守护 · 零复杂配置', font=('Microsoft YaHei UI', 9), bg='#F8FAFC', fg='#64748B').pack(anchor='w', pady=(3, 0))

        header_right = tk.Frame(header, bg='#F8FAFC')
        header_right.pack(side='right')

        # 桌面单行悬浮条开关
        cb_overlay = tk.Checkbutton(header_right, text='🖥 桌面悬浮条', variable=self.show_overlay,
                                    command=self.toggle_overlay, bg='#F8FAFC', activebackground='#F8FAFC',
                                    fg='#1E293B', font=('Microsoft YaHei UI', 8, 'bold'), selectcolor='#FFFFFF', relief='flat', bd=0)
        cb_overlay.pack(side='left', padx=(0, 4))

        btn_overlay_style = create_btn(header_right, text='🎨 外观', command=self.open_overlay_settings,
                                       bg='#F1F5F9', fg='#334155', hover_bg='#E2E8F0', border_color='#CBD5E1',
                                       padx=8, pady=3, font=('Microsoft YaHei UI', 8))
        btn_overlay_style.pack(side='left', padx=(0, 8))

        conn_box = tk.Frame(header_right, bg='#F0FDF4', highlightthickness=1, highlightbackground='#BBF7D0', padx=8, pady=4, cursor='hand2')
        conn_box.pack(side='left', padx=(0, 8))
        self.lbl_profile = tk.Label(conn_box, text=f"● 账号: {self.config.get_active_profile_name()}", font=('Microsoft YaHei UI', 8, 'bold'), bg='#F0FDF4', fg='#15803D', cursor='hand2')
        self.lbl_profile.pack()
        conn_box.bind('<Button-1>', lambda e: self.open_account_manager())
        self.lbl_profile.bind('<Button-1>', lambda e: self.open_account_manager())

        btn_login = create_btn(header_right, text='👥 多账号管理', command=self.open_account_manager, bg='#FFFFFF', fg='#475569', hover_bg='#F1F5F9', border_color='#CBD5E1', padx=10, pady=4, font=('Microsoft YaHei UI', 8, 'bold'))
        btn_login.pack(side='left')

        # 2. Quota Card
        card_quota = create_card(body, padx=16, pady=10)
        card_quota.pack(fill='x', pady=(0, 10))

        q_top = tk.Frame(card_quota, bg='#FFFFFF')
        q_top.pack(fill='x')
        tk.Label(q_top, text='📊 额度与账号状态', font=('Microsoft YaHei UI', 10, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(side='left')

        q_top_right = tk.Frame(q_top, bg='#FFFFFF')
        q_top_right.pack(side='right')
        tk.Label(q_top_right, text='自动检测：每 15 分钟', font=('Microsoft YaHei UI', 8), bg='#F1F5F9', fg='#475569', padx=6, pady=2).pack(side='left', padx=(0, 8))
        btn_refresh_q = create_btn(q_top_right, text='立即刷新额度', command=self.check, bg='#FFFFFF', fg='#2563EB', hover_bg='#EFF6FF', border_color='#BFDBFE', padx=9, pady=2, font=('Microsoft YaHei UI', 8, 'bold'))
        btn_refresh_q.pack(side='left')

        self.quota_pills_frame = tk.Frame(card_quota, bg='#FFFFFF')
        self.quota_pills_frame.pack(fill='x', pady=(8, 4))

        self.pill_pct = tk.Label(self.quota_pills_frame, text='🔋 5H额度: 尚未读取', font=('Microsoft YaHei UI', 9, 'bold'), bg='#F1F5F9', fg='#475569', padx=10, pady=4)
        self.pill_pct.pack(side='left', padx=(0, 8))

        self.pill_reset = tk.Label(self.quota_pills_frame, text='⏰ 5H刷新: 尚未读取', font=('Microsoft YaHei UI', 9), bg='#F1F5F9', fg='#475569', padx=10, pady=4)
        self.pill_reset.pack(side='left', padx=(0, 8))

        self.pill_week = tk.Label(self.quota_pills_frame, text='📅 周额度: 尚未读取', font=('Microsoft YaHei UI', 9), bg='#F1F5F9', fg='#475569', padx=10, pady=4)
        self.pill_week.pack(side='left', padx=(0, 8))

        self.pill_avail = tk.Label(self.quota_pills_frame, text='🔒 普通额度: 尚未读取', font=('Microsoft YaHei UI', 9), bg='#F1F5F9', fg='#475569', padx=10, pady=4)
        self.pill_avail.pack(side='left')

        self.quota_label = tk.Label(card_quota, textvariable=self.quota, font=('Microsoft YaHei UI', 9), bg='#FFFFFF', fg='#64748B', wraplength=740, justify='left')
        self.quota_label.pack(anchor='w', pady=(4, 2))

        # 3. Core Schedule & Control Card
        card_control = create_card(body, padx=16, pady=12)
        card_control.pack(fill='x', pady=(0, 10))

        # Live Execution & Countdown Banner
        self.banner_frame = tk.Frame(card_control, bg='#ECFDF5', highlightthickness=1, highlightbackground='#10B981', padx=14, pady=10)
        self.banner_frame.pack(fill='x', pady=(0, 10))

        self.banner_inner = tk.Frame(self.banner_frame, bg='#ECFDF5')
        self.banner_inner.pack(fill='x')

        self.banner_title = tk.Label(self.banner_inner, text='🟢 自动刷新运行中 · 待命中', font=('Microsoft YaHei UI', 12, 'bold'), bg='#ECFDF5', fg='#047857')
        self.banner_title.pack(anchor='w')

        self.banner_desc = tk.Label(self.banner_inner, text='只要软件开着就一直会自动跟随额度刷新（每 15 分钟自动检测一次）', font=('Microsoft YaHei UI', 9), bg='#ECFDF5', fg='#065F46')
        self.banner_desc.pack(anchor='w', pady=(2, 0))

        # Timing Row
        row_timing = tk.Frame(card_control, bg='#FFFFFF')
        row_timing.pack(fill='x', pady=(0, 12))

        tk.Label(row_timing, text='定时发送时间', font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(side='left', padx=(0, 8))
        self.entry_when = tk.Entry(row_timing, textvariable=self.when, width=22, font=('Consolas', 10), bg='#F8FAFC', relief='flat', highlightthickness=1, highlightbackground='#CBD5E1', highlightcolor='#2563EB')
        self.entry_when.pack(side='left', padx=(0, 8), ipady=3)

        btn_use_reset = create_btn(row_timing, text='重设为刷新时间 + 2 分钟', command=self.use_reset, bg='#F1F5F9', fg='#1E293B', hover_bg='#E2E8F0', border_color='#CBD5E1', padx=10, pady=3, font=('Microsoft YaHei UI', 8))
        btn_use_reset.pack(side='left', padx=(0, 6))

        btn_apply_time = create_btn(row_timing, text='应用自定义时间', command=self.apply_custom_time, bg='#F1F5F9', fg='#2563EB', hover_bg='#EFF6FF', border_color='#BFDBFE', padx=10, pady=3, font=('Microsoft YaHei UI', 8, 'bold'))
        btn_apply_time.pack(side='left', padx=(0, 8))

        tk.Label(row_timing, text='（默认全自动对齐，无需手动修改）', font=('Microsoft YaHei UI', 8), bg='#FFFFFF', fg='#94A3B8').pack(side='left')

        # Action Buttons
        row_actions = tk.Frame(card_control, bg='#FFFFFF')
        row_actions.pack(fill='x')

        self.btn_pause = create_btn(row_actions, text='⏸  暂停自动刷新', command=self.toggle_pause, bg='#D97706', fg='#FFFFFF', hover_bg='#B45309', font=('Microsoft YaHei UI', 10, 'bold'), padx=18, pady=8)
        self.btn_pause.pack(side='left', padx=(0, 10))

        self.btn_send_now = create_btn(row_actions, text='⚡  立即发送一次', command=self.send_now, bg='#FFFFFF', fg='#1E293B', hover_bg='#F1F5F9', border_color='#CBD5E1', font=('Microsoft YaHei UI', 9, 'bold'), padx=14, pady=8)
        self.btn_send_now.pack(side='left')

        # 4. Logs Card
        card_logs = create_card(body, padx=14, pady=8)
        card_logs.pack(fill='both', expand=True, pady=(0, 6))

        logs_header = tk.Frame(card_logs, bg='#FFFFFF')
        logs_header.pack(fill='x', pady=(0, 6))

        tk.Label(logs_header, text='📋 运行日志', font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(side='left')

        btn_clear = create_btn(logs_header, text='清空日志显示', command=self.clear_logs, bg='#FFFFFF', fg='#64748B', hover_bg='#F1F5F9', font=('Microsoft YaHei UI', 8), padx=6, pady=1)
        btn_clear.pack(side='right')

        self.logs = tk.Text(card_logs, height=6, font=('Consolas', 9), bg='#0F172A', fg='#E2E8F0', insertbackground='#38BDF8', relief='flat', padx=10, pady=8, state='disabled')
        self.logs.pack(fill='both', expand=True)

        tk.Label(body, text='💡 软件开着就会持续自动刷新。开启右上角“桌面悬浮条”可实时浮在桌面上查看。', font=('Microsoft YaHei UI', 8), bg='#F8FAFC', fg='#64748B').pack(anchor='w')

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

    # --- Properties mapped to Engine for backwards compatibility ---
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
            pct_color = '#15803D' if rem_5h > 30 else '#B45309' if rem_5h > 0 else '#B91C1C'
            pct_bg = '#F0FDF4' if rem_5h > 30 else '#FEF3C7' if rem_5h > 0 else '#FEF2F2'
            self.pill_pct.configure(text=f'🔋 5H额度: {rem_5h:g}%', bg=pct_bg, fg=pct_color)
            self.pill_reset.configure(text=f'⏰ 5H刷新: {rst_5h}', bg='#EFF6FF', fg='#1D4ED8')

        if weekly:
            rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100)))
            rst_wk = dt.datetime.fromtimestamp(weekly['resetsAt']).strftime('%m-%d %H:%M:%S') if weekly.get('resetsAt') else '无'
            parts.append(f"周额度 剩余 {rem_wk:g}%，刷新时间 {rst_wk}")
            wk_color = '#15803D' if rem_wk > 30 else '#B45309' if rem_wk > 0 else '#B91C1C'
            wk_bg = '#F0FDF4' if rem_wk > 30 else '#FEF3C7' if rem_wk > 0 else '#FEF2F2'
            self.pill_week.configure(text=f'📅 周额度: {rem_wk:g}%', bg=wk_bg, fg=wk_color)

        allowed = data.get('ordinaryUsageAllowed')
        availability = '普通额度可用' if allowed is True else '普通额度不可用' if allowed is False else '可用性未提供'
        if allowed is True:
            self.pill_avail.configure(text='✅ 普通额度: 可用', bg='#F0FDF4', fg='#15803D')
        elif allowed is False:
            self.pill_avail.configure(text='⚠️ 普通额度: 不可用', bg='#FEF2F2', fg='#B91C1C')
        else:
            self.pill_avail.configure(text='ℹ️ 普通额度: 未知', bg='#F1F5F9', fg='#64748B')

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
            self.btn_pause.configure(text='⏸  暂停自动刷新', bg='#D97706', activebackground='#B45309')
        else:
            self.btn_pause.configure(text='▶  恢复自动刷新', bg='#2563EB', activebackground='#1D4ED8')

    def update_live_banner(self, mode: str, title: str, desc: str) -> None:
        key = (mode, title, desc)
        if getattr(self, '_last_banner_key', None) == key:
            return
        self._last_banner_key = key

        configs = {
            'executing': {'bg': '#FEF3C7', 'border': '#F59E0B', 'title_fg': '#B45309', 'desc_fg': '#78350F'},
            'checking': {'bg': '#EFF6FF', 'border': '#3B82F6', 'title_fg': '#1D4ED8', 'desc_fg': '#1E40AF'},
            'scheduled': {'bg': '#ECFDF5', 'border': '#10B981', 'title_fg': '#047857', 'desc_fg': '#065F46'},
            'waiting': {'bg': '#F0FDF4', 'border': '#34D399', 'title_fg': '#047857', 'desc_fg': '#065F46'},
            'paused': {'bg': '#F1F5F9', 'border': '#CBD5E1', 'title_fg': '#475569', 'desc_fg': '#64748B'},
        }
        cfg = configs.get(mode, configs['paused'])
        self.banner_frame.configure(bg=cfg['bg'], highlightbackground=cfg['border'])
        self.banner_inner.configure(bg=cfg['bg'])
        self.banner_title.configure(text=title, bg=cfg['bg'], fg=cfg['title_fg'])
        self.banner_desc.configure(text=desc, bg=cfg['bg'], fg=cfg['desc_fg'])

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

    def login(self) -> None:
        cmd = self.engine.provider.get_cli_cmd() + self.engine.provider.get_auth_options() + ['login', '--device-auth']
        subprocess.Popen(cmd, env=self.engine.provider.get_env(), creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
        self.log('已打开现有 CLI 的登录窗口。完成后点击“立即刷新额度”。')

    def refresh_profile_ui(self) -> None:
        info = self.engine.provider.get_account_info()
        email = info.get('email')
        p_name = self.config.get_active_profile_name()
        if email:
            label = f"● 账号: {email}"
            self.lbl_profile.configure(text=label, fg='#15803D')
        elif info.get('logged_in'):
            self.lbl_profile.configure(text=f"● 账号: {p_name} (已登录)", fg='#15803D')
        else:
            self.lbl_profile.configure(text=f"● 账号: {p_name} (未登录)", fg='#DC2626')

    def open_account_manager(self) -> None:
        dlg = tk.Toplevel(self.root)
        dlg.title("👥 多账号 Profile 管理")
        dlg.geometry("520x460")
        dlg.resizable(False, False)
        dlg.configure(bg='#F8FAFC')
        dlg.attributes('-topmost', True)

        h_frame = tk.Frame(dlg, bg='#F8FAFC', padx=20, pady=16)
        h_frame.pack(fill='x')
        tk.Label(h_frame, text="👥 多账号隔离与切换", font=('Microsoft YaHei UI', 12, 'bold'), bg='#F8FAFC', fg='#0F172A').pack(anchor='w')
        tk.Label(h_frame, text="每个账号拥有独立的存储目录，登录互不冲掉，可自由切换", font=('Microsoft YaHei UI', 8), bg='#F8FAFC', fg='#64748B').pack(anchor='w', pady=(2, 0))

        content = tk.Frame(dlg, bg='#FFFFFF', padx=18, pady=14, highlightthickness=1, highlightbackground='#E2E8F0')
        content.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        tk.Label(content, text="已配置的账号列表：", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w', pady=(0, 8))

        list_frame = tk.Frame(content, bg='#FFFFFF')
        list_frame.pack(fill='both', expand=True)

        def refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            cur_active = self.config.get_active_profile_name()
            for pid, pdata in self.config.get_profiles().items():
                row = tk.Frame(list_frame, bg='#F8FAFC' if pid == cur_active else '#FFFFFF',
                               highlightthickness=1, highlightbackground='#3B82F6' if pid == cur_active else '#E2E8F0',
                               padx=10, pady=6)
                row.pack(fill='x', pady=3)

                is_cur = (pid == cur_active)
                tag_txt = "当前生效" if is_cur else "切换此账号"
                tag_bg = '#EFF6FF' if is_cur else '#F1F5F9'
                tag_fg = '#2563EB' if is_cur else '#475569'

                from ..providers.codex import CodexCLIProvider
                prov = CodexCLIProvider(codex_home=Path(pdata.get('codex_home', '')))
                info = prov.get_account_info()
                acc_email = info.get('email') or '未读取到凭证/需登录'

                info_box = tk.Frame(row, bg=row['bg'])
                info_box.pack(side='left', fill='x', expand=True)
                name_lbl = tk.Label(info_box, text=f"[{pid}] {pdata.get('name')}", font=('Microsoft YaHei UI', 9, 'bold'),
                                    bg=row['bg'], fg='#0F172A')
                name_lbl.pack(anchor='w')
                path_lbl = tk.Label(info_box, text=f"邮箱: {acc_email}  •  目录: {pdata.get('codex_home')}",
                                    font=('Consolas', 8), bg=row['bg'], fg='#64748B')
                path_lbl.pack(anchor='w')

                btn_sw = tk.Button(row, text=tag_txt, bg=tag_bg, fg=tag_fg, font=('Microsoft YaHei UI', 8, 'bold'),
                                   relief='flat', padx=8, pady=2, cursor='hand2',
                                   command=lambda p=pid: do_switch(p))
                btn_sw.pack(side='right', padx=(4, 0))

                btn_log = tk.Button(row, text="登录/重登", bg='#FFFFFF', fg='#0F172A', font=('Microsoft YaHei UI', 8),
                                    relief='flat', padx=6, pady=2, cursor='hand2',
                                    command=lambda p=pid: do_login_profile(p))
                btn_log.pack(side='right')

        def do_switch(pid: str):
            self.config.set_active_profile(pid)
            self.engine.reload_provider()
            self.refresh_profile_ui()
            self.check()
            refresh_list()
            self.log(f"已切换活跃账号为：[{pid}]")

        def do_login_profile(pid: str):
            pdata = self.config.get_profiles().get(pid, {})
            phome = Path(pdata.get('codex_home', ''))
            from ..providers.codex import CodexCLIProvider
            prov = CodexCLIProvider(codex_home=phome)
            cmd = prov.get_cli_cmd() + prov.get_auth_options() + ['login', '--device-auth']
            subprocess.Popen(cmd, env=prov.get_env(), creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0)
            self.log(f"已打开账号 [{pid}] 的独立登录窗口。完成后切换此账号并刷新额度。")

        refresh_list()

        # Add profile row
        add_frame = tk.Frame(content, bg='#FFFFFF', pady=8)
        add_frame.pack(fill='x')
        tk.Label(add_frame, text="➕ 快捷添加新独立账号：", font=('Microsoft YaHei UI', 8, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        add_input = tk.Frame(add_frame, bg='#FFFFFF')
        add_input.pack(fill='x', pady=(4, 0))

        e_id = tk.Entry(add_input, width=12, font=('Consolas', 9), bg='#F8FAFC', relief='flat', highlightthickness=1, highlightbackground='#CBD5E1')
        e_id.insert(0, 'work')
        e_id.pack(side='left', padx=(0, 6), ipady=2)

        e_name = tk.Entry(add_input, width=14, font=('Microsoft YaHei UI', 9), bg='#F8FAFC', relief='flat', highlightthickness=1, highlightbackground='#CBD5E1')
        e_name.insert(0, '工作副号')
        e_name.pack(side='left', padx=(0, 6), ipady=2)

        def add_new():
            pid = e_id.get().strip()
            name = e_name.get().strip()
            if not pid or not name:
                return
            new_home = str(Path.home() / f".codex-{pid}")
            self.config.add_profile(pid, name, new_home)
            refresh_list()
            self.log(f"已创建新账号环境 [{pid}] ({new_home})，请点击【登录/重登】完成独立认证。")

        btn_add = tk.Button(add_input, text="添加此账号", bg='#2563EB', fg='#FFFFFF', font=('Microsoft YaHei UI', 8, 'bold'),
                            relief='flat', padx=8, pady=2, cursor='hand2', command=add_new)
        btn_add.pack(side='left')

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
    root = tk.Tk()
    App(root)
    root.mainloop()
