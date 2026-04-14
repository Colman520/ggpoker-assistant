import os
import cv2
import numpy as np
from typing import List, Optional, Tuple

from config import Config

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
SUIT_NAMES = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}


class CardRecognizer:
    """GGPoker 牌面识别器"""

    def __init__(self, config: Config):
        self.config = config
        self.templates = {}
        self.template_dir = "templates"
        self._load_templates()

    def _load_templates(self):
        """加载牌面模板"""
        rank_dir = os.path.join(self.template_dir, "ranks")
        suit_dir = os.path.join(self.template_dir, "suits")

        if os.path.exists(rank_dir):
            for rank in RANKS:
                path = os.path.join(rank_dir, f"{rank}.png")
                if os.path.exists(path):
                    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self.templates[f"rank_{rank}"] = template

        if os.path.exists(suit_dir):
            for suit in SUITS:
                path = os.path.join(suit_dir, f"{suit}.png")
                if os.path.exists(path):
                    template = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        self.templates[f"suit_{suit}"] = template

        if self.templates:
            print(f"✅ 加载了 {len(self.templates)} 个模板")
        else:
            print("⚠️ 未找到模板文件，将使用颜色+轮廓识别方法")

    def recognize_cards(self, img: np.ndarray, max_cards: int = 5) -> List[str]:
        """识别图像中的扑克牌"""
        if img is None or img.size == 0:
            return []

        if self.templates:
            return self._recognize_by_template(img, max_cards)
        else:
            return self._recognize_by_color_contour(img, max_cards)

    def _recognize_by_template(self, img: np.ndarray, max_cards: int) -> List[str]:
        """模板匹配法识别"""
        cards = []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        card_regions = self._find_card_regions(img, max_cards)

        for region in card_regions:
            x, y, w, h = region
            card_img = gray[y : y + h, x : x + w]

            rank_area = card_img[2 : int(h * 0.35), 2 : int(w * 0.45)]
            suit_area = card_img[int(h * 0.25) : int(h * 0.55), 2 : int(w * 0.45)]

            rank = self._match_rank(rank_area)
            suit = self._match_suit(suit_area, img[y : y + h, x : x + w])

            if rank and suit:
                cards.append(f"{rank}{suit}")

        return cards

    def _recognize_by_color_contour(self, img: np.ndarray, max_cards: int) -> List[str]:
        """基于颜色和轮廓的识别方法（备用）"""
        cards = []
        card_regions = self._find_card_regions(img, max_cards)

        for region in card_regions:
            x, y, w, h = region
            card_img = img[y : y + h, x : x + w]
            suit = self._detect_suit_by_color(card_img)
            rank = None  # 需要模板或OCR

            if suit:
                cards.append(f"?{suit}")

        return cards

    def _find_card_regions(
        self, img: np.ndarray, max_cards: int
    ) -> List[Tuple[int, int, int, int]]:
        """在图像中找到牌的位置"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape

        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        regions = []
        min_card_area = (width * height) / (max_cards * 8)

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            aspect_ratio = w / h if h > 0 else 0

            if area > min_card_area and 0.5 < aspect_ratio < 0.9:
                regions.append((x, y, w, h))

        regions.sort(key=lambda r: r[0])
        return regions[:max_cards]

    def _match_rank(self, rank_area: np.ndarray) -> Optional[str]:
        """模板匹配点数"""
        if rank_area is None or rank_area.size == 0:
            return None

        best_match = None
        best_score = 0
        threshold = self.config["recognition"]["match_threshold"]

        for rank in RANKS:
            key = f"rank_{rank}"
            if key not in self.templates:
                continue

            template = self.templates[key]

            try:
                if (
                    rank_area.shape[0] < template.shape[0]
                    or rank_area.shape[1] < template.shape[1]
                ):
                    template = cv2.resize(
                        template, (rank_area.shape[1], rank_area.shape[0])
                    )

                result = cv2.matchTemplate(
                    rank_area, template, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > best_score and max_val > threshold:
                    best_score = max_val
                    best_match = rank
            except cv2.error:
                continue

        return best_match

    def _match_suit(
        self, suit_area: np.ndarray, card_color_img: np.ndarray
    ) -> Optional[str]:
        """匹配花色"""
        suit_by_color = self._detect_suit_by_color(card_color_img)
        if suit_by_color:
            return suit_by_color

        if suit_area is None or suit_area.size == 0:
            return None

        best_match = None
        best_score = 0
        threshold = self.config["recognition"]["match_threshold"]

        for suit in SUITS:
            key = f"suit_{suit}"
            if key not in self.templates:
                continue

            template = self.templates[key]

            try:
                if (
                    suit_area.shape[0] < template.shape[0]
                    or suit_area.shape[1] < template.shape[1]
                ):
                    template = cv2.resize(
                        suit_area, (suit_area.shape[1], suit_area.shape[0])
                    )

                result = cv2.matchTemplate(
                    suit_area, template, cv2.TM_CCOEFF_NORMED
                )
                _, max_val, _, _ = cv2.minMaxLoc(result)

                if max_val > best_score and max_val > threshold:
                    best_score = max_val
                    best_match = suit
            except cv2.error:
                continue

        return best_match

    def _detect_suit_by_color(self, card_img: np.ndarray) -> Optional[str]:
        """通过颜色检测花色 (GGPoker: 黑/红/蓝/绿)"""
        if card_img is None or card_img.size == 0:
            return None

        hsv = cv2.cvtColor(card_img, cv2.COLOR_BGR2HSV)

        color_scores = {}

        # 红色（红心 ♥）
        mask1 = cv2.inRange(hsv, np.array([0, 100, 100]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([160, 100, 100]), np.array([180, 255, 255]))
        color_scores["h"] = cv2.countNonZero(mask1 + mask2)

        # 蓝色（方块 ♦）
        mask = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255]))
        color_scores["d"] = cv2.countNonZero(mask)

        # 绿色（梅花 ♣）
        mask = cv2.inRange(hsv, np.array([35, 80, 80]), np.array([85, 255, 255]))
        color_scores["c"] = cv2.countNonZero(mask)

        total_pixels = card_img.shape[0] * card_img.shape[1]
        max_color_score = max(color_scores.values()) if color_scores else 0
        min_color_threshold = total_pixels * 0.02

        if max_color_score < min_color_threshold:
            gray = cv2.cvtColor(card_img, cv2.COLOR_BGR2GRAY)
            dark_mask = cv2.inRange(gray, 0, 80)
            dark_pixels = cv2.countNonZero(dark_mask)
            if dark_pixels > min_color_threshold:
                return "s"
            return None

        return max(color_scores, key=color_scores.get)


class ManualCardInput:
    """手动输入牌面解析器"""

    @staticmethod
    def parse_card(card_str: str) -> Optional[str]:
        """解析单张牌: 'Ah' -> 'Ah'"""
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
        """解析多张牌: 'Ah Kd Qs' -> ['Ah', 'Kd', 'Qs']"""
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
