"""System Tray Manager using pystray."""
import pystray
from PIL import Image, ImageDraw
from typing import Any, Optional


def make_tray_icon() -> Image.Image:
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill='#2563EB')
    d.ellipse((8, 8, 56, 56), outline='#93C5FD', width=2)
    d.arc((20, 20, 44, 44), start=45, end=315, fill='white', width=5)
    return img


class TrayManager:
    """Thread-safe background system tray integration."""

    def __init__(self, app_ref: Any):
        self.app = app_ref
        self.tray_icon: Optional[pystray.Icon] = None

    def start(self) -> None:
        try:
            menu = pystray.Menu(
                pystray.MenuItem('打开主界面', lambda: self.app.root.after(0, self.app.restore_from_tray), default=True),
                pystray.MenuItem(lambda item: '隐藏桌面悬浮窗' if self.app.overlay_mgr.is_visible() else '显示桌面悬浮窗',
                                 lambda: self.app.root.after(0, self.app.toggle_overlay_from_tray)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('立即刷新额度', lambda: self.app.root.after(0, self.app.check)),
                pystray.MenuItem('立即发送一次', lambda: self.app.root.after(0, self.app.send_now)),
                pystray.MenuItem(lambda item: '暂停自动刷新' if self.app.auto_active else '恢复自动刷新',
                                 lambda: self.app.root.after(0, self.app.toggle_pause)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('彻底退出', lambda: self.app.root.after(0, self.app.quit_app)),
            )
            self.tray_icon = pystray.Icon('codex_timer', make_tray_icon(), 'Codex 定时助手', menu=menu)
            self.tray_icon.run_detached()
        except Exception:
            self.tray_icon = None

    def notify(self, title: str, text: str) -> bool:
        if self.tray_icon:
            try:
                self.tray_icon.notify(text, title)
                return True
            except Exception:
                pass
        return False

    def stop(self) -> None:
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
