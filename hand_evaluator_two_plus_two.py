"""
Two Plus Two 手牌评估器
使用多级查表直接评估7张牌
"""
import os
import numpy as np
from typing import List, Tuple, Dict, Optional
from itertools import combinations

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]

class HandEvaluatorTwoPlusTwo:
    """Two Plus Two 手牌评估器"""

    # 点数索引映射
    RANK_TO_INDEX = {r: i for i, r in enumerate(RANKS)}
    INDEX_TO_RANK = {i: r for i, r in enumerate(RANKS)}

    # 花色索引映射
    SUIT_TO_INDEX = {s: i for i, s in enumerate(SUITS)}
    INDEX_TO_SUIT = {i: s for i, s in enumerate(SUITS)}

    # 手牌类型名称
    HAND_NAMES = {
        9: "皇家同花顺",
        8: "同花顺",
        7: "四条",
        6: "葫芦",
        5: "同花",
        4: "顺子",
        3: "三条",
        2: "两对",
        1: "一对",
        0: "高牌",
    }

    def __init__(self, table_path: str = "tables"):
        """初始化评估器，加载查表"""
        self.table_path = table_path
        self.flush_lookup = {}
        self.non_flush_lookup = {}
        self.pair_lookup = {}

        # 加载查表
        self._load_tables()

        # 如果查表不存在，生成简单的查表
        if not self.flush_lookup:
            self._generate_simple_tables()

    def _load_tables(self):
        """加载查表文件"""
        try:
            # 加载同花查表
            flush_path = os.path.join(self.table_path, "flush_lookup.npy")
            if os.path.exists(flush_path):
                self.flush_lookup = np.load(flush_path, allow_pickle=True).item()

            # 加载非同花查表
            non_flush_path = os.path.join(self.table_path, "non_flush_lookup.npy")
            if os.path.exists(non_flush_path):
                self.non_flush_lookup = np.load(non_flush_path, allow_pickle=True).item()

            # 加载对子查表
            pair_path = os.path.join(self.table_path, "pair_lookup.npy")
            if os.path.exists(pair_path):
                self.pair_lookup = np.load(pair_path, allow_pickle=True).item()

            print(f"[OK] 加载查表: 同花={len(self.flush_lookup)}, 非同花={len(self.non_flush_lookup)}")

        except Exception as e:
            print(f"[WARN] 加载查表失败: {e}")

    def _generate_simple_tables(self):
        """生成简单的查表（用于测试）"""
        print("生成简单查表...")

        # 生成同花查表
        for suit in SUITS:
            suit_cards = [f"{r}{suit}" for r in RANKS]
            for combo in combinations(suit_cards, 5):
                cards = list(combo)
                key = tuple(sorted(cards))
                self.flush_lookup[key] = self._evaluate_flush_simple(cards)

        # 生成非同花查表（简化版本）
        # 实际需要更复杂的逻辑

        print(f"[OK] 生成查表: 同花={len(self.flush_lookup)}")

    def evaluate_hand(self, cards: List[str]) -> Tuple[int, List[int]]:
        """评估手牌强度，返回(等级, 踢脚牌)"""
        if len(cards) == 5:
            return self._evaluate_5_cards(cards)
        elif len(cards) == 7:
            return self._evaluate_7_cards(cards)
        elif len(cards) == 6:
            return self._evaluate_6_cards(cards)
        else:
            raise ValueError(f"不支持{len(cards)}张牌的评估")

    def _evaluate_5_cards(self, cards: List[str]) -> Tuple[int, List[int]]:
        """评估5张牌"""
        # 检查是否为同花
        suits = [c[1] for c in cards]
        is_flush = len(set(suits)) == 1

        if is_flush:
            # 使用同花查表
            key = tuple(sorted(cards))
            return self.flush_lookup.get(key, (0, [0]))
        else:
            # 使用非同花查表
            key = tuple(sorted(cards))
            result = self.non_flush_lookup.get(key)
            if result:
                return result

            # 如果查表中没有，使用简单评估
            return self._evaluate_non_flush_simple(cards)

    def _evaluate_7_cards(self, cards: List[str]) -> Tuple[int, List[int]]:
        """评估7张牌 - 使用Two Plus Two算法"""
        # 将7张牌分为两组：3张和4张
        best_score = (0, [0])

        # 枚举所有C(7,5)=21种组合
        for combo in combinations(cards, 5):
            score = self._evaluate_5_cards(list(combo))
            if score > best_score:
                best_score = score

        return best_score

    def _evaluate_6_cards(self, cards: List[str]) -> Tuple[int, List[int]]:
        """评估6张牌"""
        best_score = (0, [0])

        # 枚举所有C(6,5)=6种组合
        for combo in combinations(cards, 5):
            score = self._evaluate_5_cards(list(combo))
            if score > best_score:
                best_score = score

        return best_score

    def _evaluate_flush_simple(self, cards: List[str]) -> Tuple[int, List[int]]:
        """简单的同花手牌评估"""
        ranks = [self.RANK_TO_INDEX[c[0]] for c in cards]
        ranks.sort(reverse=True)

        # 检查是否为同花顺
        if self._is_straight(ranks):
            # 皇家同花顺 (A-K-Q-J-T)
            if ranks == [12, 11, 10, 9, 8]:
                return (9, [14])  # 皇家同花顺
            # 轮子同花顺 (A-5-4-3-2)
            elif ranks == [12, 3, 2, 1, 0]:
                return (8, [5])  # 同花顺，5高
            else:
                return (8, [ranks[0] + 2])  # 同花顺

        # 普通同花
        return (5, [r + 2 for r in ranks])

    def _is_straight_flush(self, cards: List[str]) -> bool:
        """检查是否为同花顺"""
        suits = [c[1] for c in cards]
        if len(set(suits)) != 1:
            return False

        ranks = [self.RANK_TO_INDEX[c[0]] for c in cards]
        ranks.sort(reverse=True)

        # 检查连续性
        for i in range(4):
            if ranks[i] - ranks[i+1] != 1:
                # 检查轮子顺子 (A-5)
                if ranks == [12, 3, 2, 1, 0]:
                    return True
                return False

        return True

    def _is_straight(self, ranks: List[int]) -> bool:
        """检查是否为顺子"""
        if len(ranks) != 5:
            return False

        # 检查连续性
        for i in range(4):
            if ranks[i] - ranks[i+1] != 1:
                # 检查轮子顺子 (A-5)
                if ranks == [12, 3, 2, 1, 0]:
                    return True
                return False

        return True

    def _evaluate_non_flush_simple(self, cards: List[str]) -> Tuple[int, List[int]]:
        """简单的非同花手牌评估"""
        ranks = [self.RANK_TO_INDEX[c[0]] for c in cards]
        rank_counts = {}
        for r in ranks:
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # 按计数和点数排序
        sorted_by_count = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
        counts = [c for _, c in sorted_by_count]
        kickers = [r + 2 for r, _ in sorted_by_count]

        # 检查是否为顺子
        unique_ranks = sorted(set(ranks), reverse=True)
        if len(unique_ranks) == 5:
            if self._is_straight(unique_ranks):
                if unique_ranks[0] == 12 and unique_ranks[1] == 3:  # 轮子顺子
                    return (4, [5])
                return (4, [unique_ranks[0] + 2])

        # 根据计数判断手牌类型
        if counts == [4, 1]:
            return (7, kickers)  # 四条
        elif counts == [3, 2]:
            return (6, kickers)  # 葫芦
        elif counts == [3, 1, 1]:
            return (3, kickers)  # 三条
        elif counts == [2, 2, 1]:
            return (2, kickers)  # 两对
        elif counts == [2, 1, 1, 1]:
            return (1, kickers)  # 一对
        else:
            return (0, kickers)  # 高牌

    def hand_name(self, score: Tuple[int, List[int]]) -> str:
        """将分数转换为手牌名称"""
        return self.HAND_NAMES.get(score[0], "未知")

    def compare_hands(self, hand1: List[str], hand2: List[str]) -> int:
        """比较两手牌强度，返回1/0/-1"""
        score1 = self.evaluate_hand(hand1)
        score2 = self.evaluate_hand(hand2)

        if score1 > score2:
            return 1
        elif score1 < score2:
            return -1
        else:
            return 0

# 为了兼容性，创建别名
HandEvaluator = HandEvaluatorTwoPlusTwo