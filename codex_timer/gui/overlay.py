"""Single-line compact desktop floating overlay (HUD Widget) with Pin-Lock, Faint Transparency, and Appearance Settings."""
import datetime as dt
import time
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Callable, Optional, Dict, Any, Tuple


def adjust_color_hex(hex_color: str, factor: float = 1.35) -> str:
    """Helper to derive border color from background color."""
    try:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = min(255, max(0, int(r * factor + 15)))
        g = min(255, max(0, int(g * factor + 15)))
        b = min(255, max(0, int(b * factor + 15)))
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return '#2F333A'


class SingleLineOverlay:
    """Ultra-compact single-line desktop HUD with lock-in-place, faint pinned background, and hover controls."""

    def __init__(self, root: tk.Tk, app_ref: Any):
        self.root = root
        self.app = app_ref
        self.overlay: Optional[tk.Toplevel] = None
        self.pinned = bool(self.app.config.get('overlay_pinned', True))

        # Color & Depth / Transparency
        self.normal_alpha = float(self.app.config.get('overlay_normal_alpha', self.app.config.get('overlay_alpha', 0.94)))
        self.pinned_alpha = float(self.app.config.get('overlay_pinned_alpha', 0.38))
        self.bg_color = self.app.config.get('overlay_bg_color', '#181A1D')
        self.border_color = self.app.config.get('overlay_border_color', adjust_color_hex(self.bg_color))

        self.pos_x = self.app.config.get('overlay_x', 120)
        self.pos_y = self.app.config.get('overlay_y', 120)
        self.drag_x = 0
        self.drag_y = 0

        self._is_hovered = False
        self._settings_dlg: Optional[tk.Toplevel] = None

    def _clamp_and_snap(self, x: int, y: int, snap_dist: int = 16) -> Tuple[int, int]:
        """Keep overlay within screen boundaries and apply edge snapping."""
        if not self.overlay:
            return x, y
        screen_w = self.overlay.winfo_screenwidth()
        screen_h = self.overlay.winfo_screenheight()
        w, h = 380, 36
        max_x = max(0, screen_w - w)
        max_y = max(0, screen_h - h - 48)  # Leave room for Windows taskbar

        # Magnetic edge snapping
        if abs(x) < snap_dist:
            x = 0
        elif abs(x - max_x) < snap_dist:
            x = max_x

        if abs(y) < snap_dist:
            y = 0
        elif abs(y - max_y) < snap_dist:
            y = max_y

        x = max(0, min(max_x, x))
        y = max(0, min(max_y, y))
        return x, y

    def show(self) -> None:
        if self.overlay:
            try:
                self.overlay.deiconify()
                self.overlay.lift()
                self._apply_visual_state()
                return
            except Exception:
                self.overlay = None

        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-topmost', True)
        self.overlay.configure(bg=self.bg_color)
        self.pos_x, self.pos_y = self._clamp_and_snap(self.pos_x, self.pos_y)
        self.overlay.geometry(f'380x36+{self.pos_x}+{self.pos_y}')

        self.border_frame = tk.Frame(self.overlay, bg=self.border_color, padx=1, pady=1)
        self.border_frame.pack(fill='both', expand=True)

        self.main_f = tk.Frame(self.border_frame, bg=self.bg_color, padx=8, pady=2)
        self.main_f.pack(fill='both', expand=True)

        # 拖拽手柄 / 锁定标识
        self.lbl_drag = tk.Label(self.main_f, text='🔒' if self.pinned else '⋮⋮',
                                 font=('Segoe UI', 9), bg=self.bg_color,
                                 fg='#475569' if self.pinned else '#6B7280',
                                 cursor='arrow' if self.pinned else 'fleur')
        self.lbl_drag.pack(side='left', padx=(0, 6))

        # 1. 倒计时
        self.lbl_cd = tk.Label(self.main_f, text='⏳ --', font=('Consolas', 10, 'bold'),
                               bg=self.bg_color, fg='#38BDF8',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_cd.pack(side='left', padx=(0, 6))

        self.sep1 = tk.Label(self.main_f, text='│', font=('Consolas', 9), bg=self.bg_color, fg='#374151')
        self.sep1.pack(side='left', padx=(0, 6))

        # 2. 短周期额度 (5H / 2H)
        self.lbl_5h = tk.Label(self.main_f, text='5H: --', font=('Microsoft YaHei UI', 9, 'bold'),
                               bg=self.bg_color, fg='#EF4444',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_5h.pack(side='left', padx=(0, 6))

        self.sep2 = tk.Label(self.main_f, text='│', font=('Consolas', 9), bg=self.bg_color, fg='#374151')
        self.sep2.pack(side='left', padx=(0, 6))

        # 3. 周额度 (Week)
        self.lbl_wk = tk.Label(self.main_f, text='Week: --', font=('Microsoft YaHei UI', 9, 'bold'),
                               bg=self.bg_color, fg='#10B981',
                               cursor='arrow' if self.pinned else 'fleur')
        self.lbl_wk.pack(side='left', padx=(0, 6))

        # ✕ 关闭按钮 (仅在 hover 或未固定时展示)
        self.btn_close = tk.Label(self.main_f, text='✕', font=('Microsoft YaHei UI', 9),
                                  bg=self.bg_color, fg='#9CA3AF', cursor='hand2')
        self.btn_close.bind('<Button-1>', lambda e: self.close())

        # 📌 固定/置顶切换按钮 (Hover 时展示)
        self.btn_pin = tk.Label(self.main_f, text='📌', font=('Segoe UI Emoji', 9),
                                bg=self.bg_color, fg='#38BDF8' if self.pinned else '#64748B', cursor='hand2')
        self.btn_pin.bind('<Button-1>', lambda e: self.toggle_pin())

        # 绑定通用事件（拖拽、右键菜单、鼠标滚轮、悬停进出）
        all_widgets = [self.border_frame, self.main_f, self.lbl_drag, self.lbl_cd,
                       self.sep1, self.lbl_5h, self.sep2, self.lbl_wk, self.btn_close, self.btn_pin]
        for w in all_widgets:
            w.bind('<Button-1>', self._start_move)
            w.bind('<B1-Motion>', self._do_move)
            w.bind('<Button-3>', self._show_context_menu)
            w.bind('<MouseWheel>', self._on_mouse_wheel)
            w.bind('<Enter>', self._on_mouse_enter, add='+')
            w.bind('<Leave>', self._on_mouse_leave, add='+')

        # 悬停详细提示 (Tooltips)
        self._bind_tooltip(self.lbl_cd, lambda: f"下次发送时间：{self.app.when.get()} (右键可唤起外观菜单)")
        self._bind_tooltip(self.lbl_5h, self.app.get_5h_tooltip)
        self._bind_tooltip(self.lbl_wk, self.app.get_wk_tooltip)
        self._bind_tooltip(self.lbl_drag, lambda: "🔒 已固定（不可移动，移开鼠标淡化）" if self.pinned else "⋮⋮ 自由拖拽模式")

        self._apply_visual_state()
        self.update()

    def _apply_visual_state(self) -> None:
        """Apply lock, faint background opacity, and hover controls."""
        if not self.overlay:
            return

        # 1. Cursor & Drag Handle
        cursor = 'arrow' if self.pinned else 'fleur'
        for w in (self.main_f, self.lbl_drag, self.lbl_cd, self.lbl_5h, self.lbl_wk):
            w.configure(cursor=cursor)

        self.lbl_drag.configure(text='🔒' if self.pinned else '⋮⋮',
                                fg='#38BDF8' if (self.pinned and self._is_hovered) else '#475569' if self.pinned else '#6B7280')

        # 2. Pinned & Hover Visibility for Pin / Close buttons
        if self.pinned:
            if self._is_hovered:
                # Hovered while pinned: light up to normal opacity, show pin & close buttons
                self.overlay.attributes('-alpha', self.normal_alpha)
                self.btn_close.pack(side='right', padx=(4, 0))
                self.btn_pin.pack(side='right', padx=(2, 0))
                self.btn_pin.configure(fg='#38BDF8')  # Cyan active
            else:
                # Idle while pinned: faint background depth, hide pin & close buttons
                self.overlay.attributes('-alpha', self.pinned_alpha)
                self.btn_pin.pack_forget()
                self.btn_close.pack_forget()
        else:
            # Unpinned: always full normal opacity, pin icon visible in inactive color
            self.overlay.attributes('-alpha', self.normal_alpha)
            self.btn_close.pack(side='right', padx=(4, 0))
            self.btn_pin.pack(side='right', padx=(2, 0))
            self.btn_pin.configure(fg='#64748B')  # Inactive gray

    def _on_mouse_enter(self, e) -> None:
        self._is_hovered = True
        self._apply_visual_state()

    def _on_mouse_leave(self, e) -> None:
        # Delay check to confirm pointer really left the whole overlay window
        if self.overlay:
            self.overlay.after(35, self._check_leave)

    def _check_leave(self) -> None:
        if not self.overlay:
            return
        try:
            x, y = self.overlay.winfo_pointerxy()
            rx, ry = self.overlay.winfo_rootx(), self.overlay.winfo_rooty()
            rw, rh = self.overlay.winfo_width(), self.overlay.winfo_height()
            if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                self._is_hovered = False
                self._apply_visual_state()
        except Exception:
            pass

    def apply_style(self, bg_color: str, pinned_alpha: float, normal_alpha: float, border_color: Optional[str] = None) -> None:
        """Update colors and depths dynamically in real-time."""
        self.bg_color = bg_color
        self.border_color = border_color or adjust_color_hex(bg_color)
        self.pinned_alpha = max(0.15, min(0.90, round(pinned_alpha, 2)))
        self.normal_alpha = max(0.40, min(1.00, round(normal_alpha, 2)))

        # Save to config
        self.app.config.set('overlay_bg_color', self.bg_color, auto_save=False)
        self.app.config.set('overlay_border_color', self.border_color, auto_save=False)
        self.app.config.set('overlay_pinned_alpha', self.pinned_alpha, auto_save=False)
        self.app.config.set('overlay_normal_alpha', self.normal_alpha, auto_save=False)
        self.app.config.set('overlay_alpha', self.normal_alpha, auto_save=True)

        if self.overlay:
            self.overlay.configure(bg=self.bg_color)
            self.border_frame.configure(bg=self.border_color)
            self.main_f.configure(bg=self.bg_color)
            for w in (self.lbl_drag, self.lbl_cd, self.sep1, self.lbl_5h, self.sep2,
                      self.lbl_wk, self.btn_close, self.btn_pin):
                w.configure(bg=self.bg_color)
            self._apply_visual_state()

    def toggle_pin(self) -> None:
        if not self.overlay:
            return
        self.pinned = not self.pinned
        self.overlay.attributes('-topmost', True)  # Always keep on top
        self.app.config.set('overlay_pinned', self.pinned)
        self._apply_visual_state()
        status_txt = "已固定（不可移动，移开鼠标背景极淡，hover 显示图钉）" if self.pinned else "已取消固定（可自由拖拽）"
        self.app.log(f"悬浮窗{status_txt}")

    def _start_move(self, e) -> None:
        if self.pinned:
            return  # Locked! Do not allow movement when pinned
        if self.overlay:
            self.drag_x = e.x_root - self.overlay.winfo_x()
            self.drag_y = e.y_root - self.overlay.winfo_y()

    def _do_move(self, e) -> None:
        if self.pinned:
            return  # Locked! Do not allow movement when pinned
        if self.overlay:
            raw_x = e.x_root - self.drag_x
            raw_y = e.y_root - self.drag_y
            x, y = self._clamp_and_snap(raw_x, raw_y)
            self.overlay.geometry(f'+{x}+{y}')
            self.pos_x, self.pos_y = x, y
            self.app.config.set('overlay_x', x, auto_save=False)
            self.app.config.set('overlay_y', y, auto_save=True)

    def _on_mouse_wheel(self, e) -> None:
        """Wheel adjusts opacity: pinned faintness if pinned, or normal opacity if unpinned."""
        if not self.overlay:
            return
        delta = 0.03 if e.delta > 0 else -0.03
        if self.pinned:
            self.pinned_alpha = max(0.15, min(0.85, round(self.pinned_alpha + delta, 2)))
            self.app.config.set('overlay_pinned_alpha', self.pinned_alpha)
            if not self._is_hovered:
                self.overlay.attributes('-alpha', self.pinned_alpha)
        else:
            self.normal_alpha = max(0.40, min(1.00, round(self.normal_alpha + delta, 2)))
            self.app.config.set('overlay_normal_alpha', self.normal_alpha)
            self.overlay.attributes('-alpha', self.normal_alpha)

    def open_settings_dialog(self) -> None:
        """Open Appearance & Transparency Settings Modal."""
        if self._settings_dlg:
            try:
                self._settings_dlg.lift()
                self._settings_dlg.focus_force()
                return
            except Exception:
                self._settings_dlg = None

        dlg = tk.Toplevel(self.root)
        dlg.title("🎨 悬浮窗外观与颜色设置")
        dlg.geometry("420x460")
        dlg.resizable(False, False)
        dlg.configure(bg='#F8FAFC')
        dlg.attributes('-topmost', True)
        self._settings_dlg = dlg

        # Header
        h_frame = tk.Frame(dlg, bg='#F8FAFC', padx=20, pady=16)
        h_frame.pack(fill='x')
        tk.Label(h_frame, text="🎨 悬浮窗外观与透明度", font=('Microsoft YaHei UI', 12, 'bold'), bg='#F8FAFC', fg='#0F172A').pack(anchor='w')
        tk.Label(h_frame, text="自定义悬浮条背景颜色、固定时淡化深度与日常透明度", font=('Microsoft YaHei UI', 8), bg='#F8FAFC', fg='#64748B').pack(anchor='w', pady=(2, 0))

        content = tk.Frame(dlg, bg='#FFFFFF', padx=20, pady=16, highlightthickness=1, highlightbackground='#E2E8F0')
        content.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        # 1. Color Presets
        tk.Label(content, text="背景颜色预设", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        color_row = tk.Frame(content, bg='#FFFFFF')
        color_row.pack(fill='x', pady=(6, 12))

        presets = [
            ("经典冷灰", "#181A1D"),
            ("纯黑曜石", "#0D0F12"),
            ("极夜深蓝", "#0F172A"),
            ("赛博暗绿", "#052217"),
            ("极简全黑", "#000000"),
        ]

        color_var = tk.StringVar(value=self.bg_color)
        preview_box = tk.Frame(content, bg=self.bg_color, width=32, height=18, highlightthickness=1, highlightbackground='#94A3B8')

        def set_color(c: str):
            color_var.set(c)
            preview_box.configure(bg=c)
            self.apply_style(c, scale_pinned.get(), scale_normal.get())

        for name, col in presets:
            btn = tk.Button(color_row, text=name, bg=col, fg='#FFFFFF',
                            font=('Microsoft YaHei UI', 8), padx=6, pady=3, relief='flat', bd=0,
                            command=lambda c=col: set_color(c), cursor='hand2')
            btn.pack(side='left', padx=(0, 5))

        # Custom Color Picker Row
        custom_row = tk.Frame(content, bg='#FFFFFF')
        custom_row.pack(fill='x', pady=(0, 16))

        def pick_custom_color():
            picked = colorchooser.askcolor(color=color_var.get(), title="选择悬浮条背景颜色")
            if picked and picked[1]:
                set_color(picked[1])

        btn_pick = tk.Button(custom_row, text="🌈 自定义颜色...", bg='#F1F5F9', fg='#1E293B',
                             font=('Microsoft YaHei UI', 8, 'bold'), padx=8, pady=3, relief='flat',
                             command=pick_custom_color, cursor='hand2')
        btn_pick.pack(side='left', padx=(0, 10))

        tk.Label(custom_row, text="当前颜色: ", font=('Microsoft YaHei UI', 8), bg='#FFFFFF', fg='#64748B').pack(side='left')
        preview_box.pack(side='left', padx=(4, 6))
        lbl_hex = tk.Label(custom_row, textvariable=color_var, font=('Consolas', 9), bg='#FFFFFF', fg='#0F172A')
        lbl_hex.pack(side='left')

        # 2. Pinned Faintness Slider
        pinned_row = tk.Frame(content, bg='#FFFFFF')
        pinned_row.pack(fill='x', pady=(0, 12))

        lbl_pinned_val = tk.Label(pinned_row, text=f"{int(self.pinned_alpha * 100)}%", font=('Consolas', 9, 'bold'), bg='#FFFFFF', fg='#2563EB')
        lbl_pinned_val.pack(side='right')
        tk.Label(pinned_row, text="📌 固定时背景淡化深度 (很淡/防遮挡)", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        def on_pinned_slider(val):
            v = float(val)
            lbl_pinned_val.configure(text=f"{int(v * 100)}%")
            self.apply_style(color_var.get(), v, scale_normal.get())

        scale_pinned = ttk.Scale(content, from_=0.15, to=0.80, value=self.pinned_alpha, command=on_pinned_slider)
        scale_pinned.pack(fill='x', pady=(0, 16))

        # 3. Normal / Active Opacity Slider
        normal_row = tk.Frame(content, bg='#FFFFFF')
        normal_row.pack(fill='x', pady=(0, 12))

        lbl_normal_val = tk.Label(normal_row, text=f"{int(self.normal_alpha * 100)}%", font=('Consolas', 9, 'bold'), bg='#FFFFFF', fg='#2563EB')
        lbl_normal_val.pack(side='right')
        tk.Label(normal_row, text="✨ 未固定/悬停时透明度 (正常清晰)", font=('Microsoft YaHei UI', 9, 'bold'), bg='#FFFFFF', fg='#1E293B').pack(anchor='w')

        def on_normal_slider(val):
            v = float(val)
            lbl_normal_val.configure(text=f"{int(v * 100)}%")
            self.apply_style(color_var.get(), scale_pinned.get(), v)

        scale_normal = ttk.Scale(content, from_=0.40, to=1.00, value=self.normal_alpha, command=on_normal_slider)
        scale_normal.pack(fill='x', pady=(0, 16))

        # Bottom Actions
        b_frame = tk.Frame(dlg, bg='#F8FAFC', padx=20, pady=8)
        b_frame.pack(fill='x')

        def reset_defaults():
            set_color('#181A1D')
            scale_pinned.set(0.38)
            scale_normal.set(0.94)
            lbl_pinned_val.configure(text="38%")
            lbl_normal_val.configure(text="94%")
            self.apply_style('#181A1D', 0.38, 0.94)

        btn_rst = tk.Button(b_frame, text="恢复默认", bg='#FFFFFF', fg='#64748B', font=('Microsoft YaHei UI', 8),
                            relief='flat', padx=10, pady=4, cursor='hand2', command=reset_defaults)
        btn_rst.pack(side='left')

        btn_ok = tk.Button(b_frame, text="完成并关闭", bg='#2563EB', fg='#FFFFFF', font=('Microsoft YaHei UI', 8, 'bold'),
                           relief='flat', padx=14, pady=4, cursor='hand2', command=dlg.destroy)
        btn_ok.pack(side='right')

    def hide(self) -> None:
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None

    def close(self) -> None:
        self.app.show_overlay.set(False)
        self.hide()
        self.app.config.set('show_overlay', False)

    def is_visible(self) -> bool:
        return self.overlay is not None

    def _show_context_menu(self, e) -> None:
        """Right-click context menu."""
        menu = tk.Menu(self.overlay, tearoff=0, font=('Microsoft YaHei UI', 9))
        menu.add_command(label="⚡ 立即刷新额度", command=self.app.check)
        menu.add_command(label="📋 复制当前额度", command=self._copy_quota_summary)
        menu.add_separator()
        pin_label = "🔓 取消固定 (解锁为可拖拽)" if self.pinned else "📌 固定悬浮条 (锁定防误触+移开淡化)"
        menu.add_command(label=pin_label, command=self.toggle_pin)
        menu.add_command(label="🎨 悬浮窗外观与颜色...", command=self.open_settings_dialog)
        menu.add_separator()
        menu.add_command(label="🪟 打开主界面", command=self.app.restore_from_tray)
        menu.add_command(label="📦 隐藏悬浮窗", command=self.close)
        menu.add_separator()
        menu.add_command(label="❌ 彻底退出", command=self.app.quit_app)
        menu.tk_popup(e.x_root, e.y_root)

    def _copy_quota_summary(self) -> None:
        five_h, weekly = self.app.get_extracted_windows()
        rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100))) if five_h else 0
        rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100))) if weekly else 0
        txt = f"Codex 额度: 5H剩余 {rem_5h:g}%, 周额度剩余 {rem_wk:g}%, 下次自动发送: {self.app.when.get()}"
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self.app.log("已复制额度概要到剪贴板。")

    def _bind_tooltip(self, widget, text_func: Callable[[], str]) -> None:
        tip_ref = [None]

        def enter(e):
            if tip_ref[0] or not self.overlay:
                return
            txt = text_func() if callable(text_func) else str(text_func)
            if not txt:
                return
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 5
            tw = tk.Toplevel(self.overlay)
            tw.wm_overrideredirect(True)
            tw.attributes('-topmost', True)
            tw.attributes('-alpha', 0.95)
            tw.wm_geometry(f"+{x}+{y}")
            tk.Label(tw, text=txt, font=('Microsoft YaHei UI', 8), bg='#202227', fg='#E5E7EB',
                     padx=8, pady=4, relief='flat', highlightthickness=1, highlightbackground='#374151').pack()
            tip_ref[0] = tw

        def leave(e):
            if tip_ref[0]:
                try:
                    tip_ref[0].destroy()
                except Exception:
                    pass
                tip_ref[0] = None

        widget.bind('<Enter>', enter, add='+')
        widget.bind('<Leave>', leave, add='+')

    def update(self) -> None:
        if not self.overlay:
            return

        five_h, weekly = self.app.get_extracted_windows()

        rem_5h = 0
        hours = 5
        if five_h:
            rem_5h = max(0, min(100, 100 - five_h.get('usedPercent', 100)))
            mins = five_h.get('windowDurationMins', 300)
            hours = mins // 60 if mins >= 60 else 5

        rem_wk = 0
        if weekly:
            rem_wk = max(0, min(100, 100 - weekly.get('usedPercent', 100)))

        if self.app.busy and self.app.exec_state == 'sending':
            cd_text = '⚡ 发送中'
            cd_fg = '#F59E0B'
        elif self.app.next_at:
            secs = max(0, int(self.app.next_at - time.time()))
            if secs >= 3600:
                cd_text = f'⏳ {secs//3600:02d}:{secs%3600//60:02d}:{secs%60:02d}'
            else:
                cd_text = f'⏳ {secs//60:02d}m{secs%60:02d}s'
            cd_fg = '#38BDF8'
        elif self.app.auto_active:
            cd_text = '🟢 待命中'
            cd_fg = '#10B981'
        else:
            cd_text = '⏸ 已暂停'
            cd_fg = '#9CA3AF'

        self.lbl_cd.configure(text=cd_text, fg=cd_fg)

        fg_5h = '#10B981' if rem_5h > 30 else '#F59E0B' if rem_5h > 0 else '#EF4444'
        self.lbl_5h.configure(text=f'{hours}H: {rem_5h:g}%', fg=fg_5h)

        fg_wk = '#10B981' if rem_wk > 30 else '#F59E0B' if rem_wk > 0 else '#EF4444'
        self.lbl_wk.configure(text=f'Week: {rem_wk:g}%', fg=fg_wk)
