import os
import time
import numpy as np

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
    print("[WARN] mss 未安装: pip install mss")

try:
    import win32gui
    import win32con
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    print("[WARN] pywin32 未安装: pip install pywin32")

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from config import Config


class ScreenCapture:
    """屏幕捕获模块 - 增强版"""

    def __init__(self, config: Config):
        self.config = config
        self.window_rect = None
        self.sct = mss.mss() if HAS_MSS else None
        self.debug_dir = "screenshots/debug"
        self.debug_mode = False
        os.makedirs(self.debug_dir, exist_ok=True)

    def find_ggpoker_window(self) -> bool:
        """查找GGPoker窗口位置"""
        if not HAS_WIN32:
            print("[WARN] pywin32 未安装，无法自动查找窗口")
            return False

        keyword = self.config["window_title_keyword"]
        candidates = []

        def enum_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if keyword.lower() in title.lower():
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    # 过滤太小的窗口(工具栏等)
                    if w > 400 and h > 300:
                        candidates.append((hwnd, title, rect, w * h))

        win32gui.EnumWindows(enum_callback, None)

        if candidates:
            # 选最大的窗口(主牌桌)
            candidates.sort(key=lambda x: x[3], reverse=True)
            hwnd, title, rect, area = candidates[0]
            self.window_rect = rect
            print(f"[OK] GGPoker窗口: {rect[2]-rect[0]}x{rect[3]-rect[1]} @ ({rect[0]},{rect[1]})")
            return True
        else:
            print("[FAIL] 未找到GGPoker窗口")
            return False

    def set_window_rect(self, left, top, right, bottom):
        """手动设置窗口区域"""
        self.window_rect = (left, top, right, bottom)
        print(f"[OK] 手动设置窗口: {right-left}x{bottom-top}")

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

        monitor = {
            "left": int(wl + rx * win_w),
            "top": int(wt + ry * win_h),
            "width": max(1, int(rw * win_w)),
            "height": max(1, int(rh * win_h)),
        }

        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)[:, :, :3]  # BGRA -> BGR

        if self.debug_mode and HAS_CV2:
            ts = int(time.time() * 1000) % 100000
            path = os.path.join(self.debug_dir, f"{region_name}_{ts}.png")
            cv2.imwrite(path, img)

        return img

    def capture_full_window(self) -> np.ndarray:
        """截取整个GGPoker窗口"""
        if not self.window_rect:
            raise RuntimeError("未找到窗口")
        if not self.sct:
            raise RuntimeError("mss 未安装")

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

    def capture_full_with_regions(self) -> np.ndarray:
        """截取窗口并标注各识别区域 (用于校准)"""
        img = self.capture_full_window()
        if not HAS_CV2:
            return img

        h, w = img.shape[:2]
        overlay = img.copy()

        colors = {
            "my_cards": (0, 255, 0),       # 绿色
            "community_cards": (255, 0, 0), # 蓝色
            "pot": (0, 255, 255),           # 黄色
            "bet_amount": (0, 165, 255),    # 橙色
        }

        for name, (rx, ry, rw, rh) in self.config["regions"].items():
            x1 = int(rx * w)
            y1 = int(ry * h)
            x2 = int((rx + rw) * w)
            y2 = int((ry + rh) * h)
            color = colors.get(name, (255, 255, 255))

            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
            cv2.putText(overlay, name, (x1 + 4, y1 + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return overlay

    def save_debug_screenshot(self, label: str = ""):
        """保存调试截图"""
        try:
            img = self.capture_full_with_regions()
            ts = time.strftime("%H%M%S")
            name = f"debug_{ts}_{label}.png" if label else f"debug_{ts}.png"
            path = os.path.join(self.debug_dir, name)
            cv2.imwrite(path, img)
            print(f"[INFO] 调试截图: {path}")
            return path
        except Exception as e:
            print(f"[FAIL] 截图失败: {e}")
            return None
