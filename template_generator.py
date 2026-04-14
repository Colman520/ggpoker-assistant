"""
模板生成工具 — 从GGPoker截图中提取牌面模板
使用方法:
  1. 打开GGPoker，确保桌面上有牌
  2. 运行: python template_generator.py
  3. 按提示截取并标注每张牌
"""

import os
import cv2
import numpy as np
from typing import Optional, Tuple

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
SUIT_NAMES = {"s": "spade", "h": "heart", "d": "diamond", "c": "club"}


class TemplateGenerator:
    """从GGPoker截图自动生成识别模板"""

    def __init__(self):
        self.rank_dir = "templates/ranks"
        self.suit_dir = "templates/suits"
        os.makedirs(self.rank_dir, exist_ok=True)
        os.makedirs(self.suit_dir, exist_ok=True)

    def extract_from_screenshot(self, img: np.ndarray):
        """交互式从截图中提取模板"""
        print("\n🎯 模板提取工具")
        print("=" * 40)
        print("操作说明:")
        print("  1. 用鼠标框选一张牌的【点数区域】(左上角的数字)")
        print("  2. 按对应按键标注: 2-9, t=10, j=J, q=Q, k=K, a=A")
        print("  3. 框选【花色图标】并标注: s=♠ h=♥ d=♦ c=♣")
        print("  4. 按 ESC 完成")
        print()

        clone = img.copy()
        self._current_img = clone
        self._roi_start = None
        self._roi_end = None
        self._selecting = False

        cv2.namedWindow("Template Extractor", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Template Extractor", self._mouse_callback)

        while True:
            display = self._current_img.copy()

            if self._roi_start and self._roi_end:
                cv2.rectangle(display, self._roi_start, self._roi_end, (0, 255, 0), 2)

            cv2.imshow("Template Extractor", display)
            key = cv2.waitKey(50) & 0xFF

            if key == 27:  # ESC
                break

            if key == 255 or key == 0:
                continue

            if self._roi_start and self._roi_end:
                self._handle_key(key, img)

        cv2.destroyAllWindows()
        self._print_summary()

    def _mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self._roi_start = (x, y)
            self._selecting = True
        elif event == cv2.EVENT_MOUSEMOVE and self._selecting:
            self._roi_end = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self._roi_end = (x, y)
            self._selecting = False

    def _handle_key(self, key, img):
        x1, y1 = self._roi_start
        x2, y2 = self._roi_end
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        if x2 - x1 < 5 or y2 - y1 < 5:
            return

        roi = img[y1:y2, x1:x2]
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        char = chr(key).upper()

        # 点数标注
        rank_map = {
            "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
            "7": "7", "8": "8", "9": "9", "T": "T", "0": "T",
            "J": "J", "Q": "Q", "K": "K", "A": "A",
        }

        if char in rank_map:
            rank = rank_map[char]
            path = os.path.join(self.rank_dir, f"{rank}.png")
            cv2.imwrite(path, gray_roi)
            print(f"  ✅ 保存点数模板: {rank} → {path}")
            self._roi_start = None
            self._roi_end = None

        # 花色标注
        elif char in ("S", "H", "D", "C"):
            suit = char.lower()
            path = os.path.join(self.suit_dir, f"{suit}.png")
            cv2.imwrite(path, gray_roi)
            print(f"  ✅ 保存花色模板: {SUIT_NAMES[suit]} → {path}")
            self._roi_start = None
            self._roi_end = None

    def _print_summary(self):
        ranks = len([f for f in os.listdir(self.rank_dir) if f.endswith(".png")])
        suits = len([f for f in os.listdir(self.suit_dir) if f.endswith(".png")])
        print(f"\n📊 模板总结: {ranks}个点数 + {suits}个花色")

        if ranks < 13:
            missing = [r for r in RANKS if not os.path.exists(os.path.join(self.rank_dir, f"{r}.png"))]
            print(f"  ⚠️ 缺少点数: {', '.join(missing)}")
        if suits < 4:
            missing = [s for s in SUITS if not os.path.exists(os.path.join(self.suit_dir, f"{s}.png"))]
            print(f"  ⚠️ 缺少花色: {', '.join(missing)}")

    def auto_extract_from_card(self, card_img: np.ndarray, rank: str, suit: str):
        """自动提取 — 已知牌面时直接保存模板"""
        h, w = card_img.shape[:2]
        gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)

        # 点数: 左上角
        rank_roi = gray[2:int(h * 0.35), 2:int(w * 0.45)]
        if rank_roi.size > 0:
            path = os.path.join(self.rank_dir, f"{rank}.png")
            cv2.imwrite(path, rank_roi)

        # 花色: 左上角下方
        suit_roi = gray[int(h * 0.28):int(h * 0.52), 2:int(w * 0.40)]
        if suit_roi.size > 0:
            path = os.path.join(self.suit_dir, f"{suit}.png")
            cv2.imwrite(path, suit_roi)


def main():
    """独立运行: 从截图文件提取模板"""
    import sys
    from config import Config
    from screen_capture import ScreenCapture

    config = Config()
    capture = ScreenCapture(config)
    gen = TemplateGenerator()

    print("🃏 GGPoker 模板生成器")
    print("=" * 40)

    # 尝试截取GGPoker窗口
    if capture.find_ggpoker_window():
        print("按 Enter 截取GGPoker画面...")
        input()
        img = capture.capture_full_window()
    else:
        # 从文件加载
        path = input("请输入截图文件路径: ").strip().strip('"')
        if not os.path.exists(path):
            print("❌ 文件不存在")
            return
        img = cv2.imread(path)

    if img is None:
        print("❌ 无法加载图像")
        return

    gen.extract_from_screenshot(img)


if __name__ == "__main__":
    main()