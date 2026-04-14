import os
import cv2
import numpy as np
from typing import List, Optional, Tuple, Dict

from config import Config

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
SUIT_NAMES = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

# GGPoker 花色颜色范围 (HSV) — 可通过校准工具调整
GGPOKER_SUIT_COLORS = {
    "h": {  # 红心 - 红色
        "ranges": [
            (np.array([0, 80, 80]), np.array([12, 255, 255])),
            (np.array([158, 80, 80]), np.array([180, 255, 255])),
        ]
    },
    "d": {  # 方块 - 蓝色
        "ranges": [
            (np.array([95, 60, 60]), np.array([135, 255, 255])),
        ]
    },
    "c": {  # 梅花 - 绿色
        "ranges": [
            (np.array([30, 50, 50]), np.array([90, 255, 255])),
        ]
    },
    "s": {  # 黑桃 - 黑色/深灰 (特殊处理)
        "ranges": []  # 通过亮度检测
    },
}


class CardRecognizer:
    """GGPoker 牌面识别器 - 增强版"""

    def __init__(self, config: Config):
        self.config = config
        self.rank_templates: Dict[str, np.ndarray] = {}
        self.suit_templates: Dict[str, np.ndarray] = {}
        self.template_dir = "templates"
        self.debug_mode = False
        self._load_templates()

    def _load_templates(self):
        """加载牌面模板"""
        rank_dir = os.path.join(self.template_dir, "ranks")
        suit_dir = os.path.join(self.template_dir, "suits")

        for rank in RANKS:
            path = os.path.join(rank_dir, f"{rank}.png")
            if os.path.exists(path):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.rank_templates[rank] = tpl

        for suit in SUITS:
            path = os.path.join(suit_dir, f"{suit}.png")
            if os.path.exists(path):
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self.suit_templates[suit] = tpl

        n = len(self.rank_templates) + len(self.suit_templates)
        if n > 0:
            print(f"✅ 模板: {len(self.rank_templates)}个点数 + {len(self.suit_templates)}个花色")
        else:
            print("⚠️ 无模板文件，使用颜色+轮廓识别（准确率有限）")

    def recognize_cards(self, img: np.ndarray, max_cards: int = 5) -> List[str]:
        """识别图像中的扑克牌"""
        if img is None or img.size == 0:
            return []

        # Step 1: 找到牌的区域
        card_regions = self._find_card_regions(img, max_cards)

        if not card_regions:
            return []

        cards = []
        for i, (x, y, w, h) in enumerate(card_regions):
            card_img = img[y:y+h, x:x+w]

            # Step 2: 识别花色 (颜色优先，最可靠)
            suit = self._detect_suit(card_img)

            # Step 3: 识别点数 (模板匹配)
            rank = self._detect_rank(card_img)

            if rank and suit:
                cards.append(f"{rank}{suit}")
            elif suit and not rank:
                # 花色识别到但点数没有 → 标记为未知
                cards.append(f"?{suit}")

            if self.debug_mode:
                self._save_debug_card(card_img, i, rank, suit)

        return cards

    def _find_card_regions(self, img: np.ndarray, max_cards: int) -> List[Tuple[int, int, int, int]]:
        """多策略找牌区域"""
        h, w = img.shape[:2]

        # 策略1: 自适应阈值 + 轮廓检测
        regions = self._find_by_adaptive_threshold(img, max_cards)

        # 策略2: 如果策略1失败，用边缘检测
        if not regions:
            regions = self._find_by_edges(img, max_cards)

        # 策略3: 如果都失败，等分区域
        if not regions:
            regions = self._find_by_equal_split(img, max_cards)

        return regions

    def _find_by_adaptive_threshold(self, img: np.ndarray, max_cards: int) -> List[Tuple[int, int, int, int]]:
        """自适应阈值找牌"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # 尝试多个阈值
        for thresh_val in [180, 160, 200, 140]:
            _, binary = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            regions = []
            min_area = (w * h) / (max_cards * 10)
            max_area = (w * h) / max(max_cards * 0.5, 1)

            for contour in contours:
                x, y, cw, ch = cv2.boundingRect(contour)
                area = cw * ch
                aspect = cw / ch if ch > 0 else 0

                if min_area < area < max_area and 0.45 < aspect < 1.0:
                    regions.append((x, y, cw, ch))

            if regions:
                regions.sort(key=lambda r: r[0])
                return regions[:max_cards]

        return []

    def _find_by_edges(self, img: np.ndarray, max_cards: int) -> List[Tuple[int, int, int, int]]:
        """边缘检测找牌"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = gray.shape
        regions = []
        min_area = (w * h) / (max_cards * 12)

        for contour in contours:
            x, y, cw, ch = cv2.boundingRect(contour)
            area = cw * ch
            aspect = cw / ch if ch > 0 else 0

            if area > min_area and 0.4 < aspect < 1.1:
                regions.append((x, y, cw, ch))

        regions.sort(key=lambda r: r[0])
        return regions[:max_cards]

    def _find_by_equal_split(self, img: np.ndarray, max_cards: int) -> List[Tuple[int, int, int, int]]:
        """等分法 — 最后的备选"""
        h, w = img.shape[:2]
        if max_cards <= 0:
            return []

        card_w = w // max_cards
        margin_x = int(card_w * 0.05)
        margin_y = int(h * 0.05)

        regions = []
        for i in range(max_cards):
            x = i * card_w + margin_x
            cw = card_w - 2 * margin_x
            if cw > 10 and h - 2 * margin_y > 10:
                regions.append((x, margin_y, cw, h - 2 * margin_y))

        return regions

    def _detect_suit(self, card_img: np.ndarray) -> Optional[str]:
        """通过颜色检测花色 — 增强版"""
        if card_img is None or card_img.size == 0:
            return None

        hsv = cv2.cvtColor(card_img, cv2.COLOR_BGR2HSV)
        total_pixels = card_img.shape[0] * card_img.shape[1]
        min_pixels = total_pixels * self.config["recognition"]["suit_min_pixel_ratio"]

        scores = {}
        for suit_key in ("h", "d", "c"):
            scores[suit_key] = self._count_color_pixels(
                hsv, GGPOKER_SUIT_COLORS[suit_key]["ranges"]
            )

        max_score = max(scores.values()) if scores else 0

        if max_score >= min_pixels:
            return max(scores, key=scores.get)

        # 黑桃 — 检测深色像素
        gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
        dark_mask = cv2.inRange(gray, 0, self.config["recognition"]["spade_brightness_threshold"])
        dark_pixels = cv2.countNonZero(dark_mask)

        if dark_pixels >= min_pixels:
            return "s"

        return None

    @staticmethod
    def _count_color_pixels(hsv: np.ndarray, color_ranges) -> int:
        """统计 HSV 图像中匹配指定颜色范围的像素数"""
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for low, high in color_ranges:
            mask |= cv2.inRange(hsv, low, high)
        return cv2.countNonZero(mask)

    def _detect_rank(self, card_img: np.ndarray) -> Optional[str]:
        """识别点数"""
        if not self.rank_templates:
            return self._detect_rank_by_contour(card_img)

        h, w = card_img.shape[:2]
        gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)

        # 提取左上角区域 (点数位置)
        rank_region = gray[2:int(h * 0.40), 2:int(w * 0.50)]
        if rank_region.size == 0:
            return None

        # 二值化增强对比
        _, rank_binary = cv2.threshold(rank_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        best_rank = None
        best_score = 0
        threshold = self.config["recognition"]["match_threshold"]

        for rank, template in self.rank_templates.items():
            score = self._multi_scale_match(rank_binary, template)
            if score > best_score and score > threshold:
                best_score = score
                best_rank = rank

        return best_rank

    def _multi_scale_match(self, target: np.ndarray, template: np.ndarray) -> float:
        """多尺度模板匹配"""
        if target.size == 0 or template.size == 0:
            return 0.0

        best_score = 0.0
        th, tw = template.shape[:2]
        tgt_h, tgt_w = target.shape[:2]

        # 计算合理的缩放范围
        scale_w = tgt_w / tw if tw > 0 else 1
        scale_h = tgt_h / th if th > 0 else 1
        center_scale = min(scale_w, scale_h) * 0.8

        scales = [center_scale * s for s in [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2]]

        for scale in scales:
            if scale <= 0:
                continue

            new_w = max(3, int(tw * scale))
            new_h = max(3, int(th * scale))

            if new_w > tgt_w or new_h > tgt_h:
                continue

            resized = cv2.resize(template, (new_w, new_h))
            try:
                result = cv2.matchTemplate(target, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                best_score = max(best_score, max_val)
            except cv2.error:
                continue

        return best_score

    def _detect_rank_by_contour(self, card_img: np.ndarray) -> Optional[str]:
        """无模板时通过轮廓特征猜测点数（有限能力）"""
        # 这是一个非常基础的方法，只能区分部分牌
        # 建议尽快生成模板
        return None

    def _save_debug_card(self, card_img: np.ndarray, index: int,
                         rank: Optional[str], suit: Optional[str]):
        """保存调试图"""
        debug_dir = "screenshots/debug/cards"
        os.makedirs(debug_dir, exist_ok=True)
        label = f"{rank or '?'}{suit or '?'}"
        path = os.path.join(debug_dir, f"card_{index}_{label}.png")
        cv2.imwrite(path, card_img)


class ManualCardInput:
    """手动输入牌面解析器"""

    @staticmethod
    def parse_card(card_str: str) -> Optional[str]:
        card_str = card_str.strip()

        if len(card_str) == 2:
            rank = card_str[0].upper()
            suit = card_str[1].lower()
            if rank == "0":
                rank = "T"
            if rank in RANKS and suit in SUITS:
                return f"{rank}{suit}"

        if len(card_str) == 3 and card_str[:2] == "10":
            suit = card_str[2].lower()
            if suit in SUITS:
                return f"T{suit}"

        return None

    @staticmethod
    def parse_hand(hand_str: str) -> List[str]:
        hand_str = hand_str.replace(",", " ").replace("/", " ").strip()
        if not hand_str:
            return []

        cards = []
        parts = hand_str.split()

        for part in parts:
            part = part.strip()
            if not part:
                continue

            if part.upper().startswith("10") and len(part) == 3:
                card = ManualCardInput.parse_card(part)
                if card:
                    cards.append(card)
            elif len(part) == 2:
                card = ManualCardInput.parse_card(part)
                if card:
                    cards.append(card)
            elif len(part) == 4:
                c1 = ManualCardInput.parse_card(part[:2])
                c2 = ManualCardInput.parse_card(part[2:])
                if c1:
                    cards.append(c1)
                if c2:
                    cards.append(c2)

        return cards
