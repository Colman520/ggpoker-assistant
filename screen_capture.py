import numpy as np

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    print("⚠️ mss 未安装: pip install mss")

try:
    import win32gui
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("⚠️ pywin32 未安装: pip install pywin32")

from config import Config


class ScreenCapture:
    """屏幕捕获模块 - 定位GGPoker窗口并截取关键区域"""

    def __init__(self, config: Config):
        self.config = config
        self.window_rect = None
        self.sct = mss.mss() if HAS_MSS else None

    def find_ggpoker_window(self) -> bool:
        """查找GGPoker窗口位置"""
        if not HAS_WIN32:
            print("⚠️ pywin32 未安装，无法自动查找窗口")
            return False

        keyword = self.config["window_title_keyword"]
        target_hwnd = None

        def enum_callback(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if keyword.lower() in title.lower():
                    target_hwnd = hwnd

        win32gui.EnumWindows(enum_callback, None)

        if target_hwnd:
            rect = win32gui.GetWindowRect(target_hwnd)
            self.window_rect = rect
            print(f"✅ 找到GGPoker窗口: 位置={rect}")
            return True
        else:
            print("❌ 未找到GGPoker窗口，请确认GGPoker已打开")
            return False

    def set_window_rect(self, left, top, right, bottom):
        """手动设置窗口区域"""
        self.window_rect = (left, top, right, bottom)
        print(f"✅ 手动设置窗口区域: {self.window_rect}")

    def capture_region(self, region_name: str) -> np.ndarray:
        """截取指定区域"""
        if not self.window_rect:
            raise RuntimeError("未找到窗口，请先调用 find_ggpoker_window()")
        if not self.sct:
            raise RuntimeError("mss 未安装")

        wl, wt, wr, wb = self.window_rect
        win_w = wr - wl
        win_h = wb - wt

        rx, ry, rw, rh = self.config["regions"][region_name]

        abs_left = int(wl + rx * win_w)
        abs_top = int(wt + ry * win_h)
        abs_width = int(rw * win_w)
        abs_height = int(rh * win_h)

        monitor = {
            "left": abs_left,
            "top": abs_top,
            "width": abs_width,
            "height": abs_height,
        }

        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        img = img[:, :, :3]  # BGRA -> BGR
        return img

    def capture_full_window(self) -> np.ndarray:
        """截取整个GGPoker窗口"""
        if not self.window_rect:
            raise RuntimeError("未找到窗口")

        wl, wt, wr, wb = self.window_rect
        monitor = {
            "left": wl,
            "top": wt,
            "width": wr - wl,
            "height": wb - wt,
        }

        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)[:, :, :3]
        return img
