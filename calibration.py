"""
交互式区域校准工具
使用方法: python calibration.py
"""

import cv2
import numpy as np
import json
from config import Config
from screen_capture import ScreenCapture


class RegionCalibrator:
    """交互式区域校准"""

    REGION_NAMES = ["my_cards", "community_cards", "pot", "bet_amount"]
    REGION_LABELS = {
        "my_cards": "🎴 手牌区域",
        "community_cards": "🃏 公共牌区域",
        "pot": "💰 底池区域",
        "bet_amount": "💵 下注金额区域",
    }
    COLORS = {
        "my_cards": (0, 255, 0),
        "community_cards": (255, 0, 0),
        "pot": (0, 255, 255),
        "bet_amount": (0, 165, 255),
    }

    def __init__(self, config: Config):
        self.config = config
        self.capture = ScreenCapture(config)
        self.current_region = 0
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.regions = {}

    def setup_with_capture(self, capture: ScreenCapture, img: np.ndarray):
        """用已有的 ScreenCapture 实例和截图初始化（供 GUI 调用）"""
        self.capture = capture
        self.img = img
        self.img_h, self.img_w = img.shape[:2]

    def run(self):
        """启动校准"""
        print("\n🎯 区域校准工具")
        print("=" * 40)

        if not self.capture.find_ggpoker_window():
            path = input("未找到GGPoker窗口，请输入截图路径: ").strip().strip('"')
            img = cv2.imread(path)
            if img is None:
                print("❌ 无法加载图像")
                return
        else:
            input("按 Enter 截取画面...")
            img = self.capture.capture_full_window()

        self.img = img
        self.img_h, self.img_w = img.shape[:2]

        for i, name in enumerate(self.REGION_NAMES):
            self.current_region = i
            self._calibrate_one_region(name)

        # 保存
        self._save_regions()

    def _calibrate_one_region(self, name: str):
        label = self.REGION_LABELS[name]
        color = self.COLORS[name]

        print(f"\n{label}")
        print("  用鼠标框选该区域，然后按 Enter 确认，按 R 重画")

        self.start_point = None
        self.end_point = None
        self.drawing = False

        win_name = f"Calibrate: {label}"
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(win_name, self._mouse_cb)

        while True:
            display = self.img.copy()

            # 画已确认的区域
            for rname, (rx, ry, rw, rh) in self.regions.items():
                x1 = int(rx * self.img_w)
                y1 = int(ry * self.img_h)
                x2 = int((rx + rw) * self.img_w)
                y2 = int((ry + rh) * self.img_h)
                c = self.COLORS.get(rname, (255, 255, 255))
                cv2.rectangle(display, (x1, y1), (x2, y2), c, 1)
                cv2.putText(display, rname, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1)

            # 画当前选区
            if self.start_point and self.end_point:
                cv2.rectangle(display, self.start_point, self.end_point, color, 2)

            cv2.imshow(win_name, display)
            key = cv2.waitKey(30) & 0xFF

            if key == 13:  # Enter
                if self.start_point and self.end_point:
                    x1, y1 = self.start_point
                    x2, y2 = self.end_point
                    x1, x2 = min(x1, x2), max(x1, x2)
                    y1, y2 = min(y1, y2), max(y1, y2)

                    rx = x1 / self.img_w
                    ry = y1 / self.img_h
                    rw = (x2 - x1) / self.img_w
                    rh = (y2 - y1) / self.img_h

                    self.regions[name] = [round(rx, 4), round(ry, 4),
                                          round(rw, 4), round(rh, 4)]
                    print(f"  ✅ {name}: [{rx:.4f}, {ry:.4f}, {rw:.4f}, {rh:.4f}]")
                    break

            elif key == ord("r"):
                self.start_point = None
                self.end_point = None

            elif key == 27:  # ESC skip
                print(f"  ⏭ 跳过 {name}")
                break

        cv2.destroyWindow(win_name)

    def _mouse_cb(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.start_point = (x, y)
            self.drawing = True
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.end_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.end_point = (x, y)
            self.drawing = False

    def _save_regions(self):
        if not self.regions:
            print("⚠️ 未校准任何区域")
            return

        for name, vals in self.regions.items():
            self.config["regions"][name] = vals

        self.config.save()
        print(f"\n✅ 已保存 {len(self.regions)} 个区域到 config.json")


def main():
    config = Config()
    cal = RegionCalibrator(config)
    cal.run()


if __name__ == "__main__":
    main()