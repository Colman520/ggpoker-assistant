"""
Two Plus Two 查表生成器
生成手牌评估所需的查表文件
"""
import os
import sys
import numpy as np
from itertools import combinations
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
FULL_DECK = [f"{r}{s}" for r in RANKS for s in SUITS]

class TableGenerator:
    """Two Plus Two 查表生成器"""

    def __init__(self, output_dir="tables"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # 点数索引映射
        self.rank_to_index = {r: i for i, r in enumerate(RANKS)}
        self.index_to_rank = {i: r for i, r in enumerate(RANKS)}

        # 花色索引映射
        self.suit_to_index = {s: i for i, s in enumerate(SUITS)}
        self.index_to_suit = {i: s for i, s in enumerate(SUITS)}

    def generate_all_tables(self):
        """生成所有查表"""
        print("开始生成Two Plus Two查表...")

        # 生成同花查表
        self.generate_flush_tables()

        # 生成非同花查表
        self.generate_non_flush_tables()

        # 生成对子、三条、四条查表
        self.generate_pair_tables()

        print(f"查表生成完成，保存到 {self.output_dir}/")

    def generate_flush_tables(self):
        """生成同花查表"""
        print("生成同花查表...")

        # 同花手牌：5张同花色的牌
        flush_lookup = {}

        # 枚举所有同花组合
        for suit in SUITS:
            suit_cards = [f"{r}{suit}" for r in RANKS]

            # 选择5张同花色的牌
            for combo in combinations(suit_cards, 5):
                cards = list(combo)
                # 计算手牌强度
                strength = self.evaluate_flush_hand(cards)
                # 存储到查表
                key = self.cards_to_key(cards)
                flush_lookup[key] = strength

        # 保存查表
        self.save_table(flush_lookup, "flush_lookup.npy")
        print(f"  同花查表: {len(flush_lookup)} 条记录")

    def generate_non_flush_tables(self):
        """生成非同花查表"""
        print("生成非同花查表...")

        # 非同花手牌：5张不同花色的牌
        non_flush_lookup = {}

        # 枚举所有非同花组合（简化版本，实际需要更复杂的逻辑）
        # 这里只是示例，实际实现需要考虑所有情况

        # 保存查表
        self.save_table(non_flush_lookup, "non_flush_lookup.npy")
        print(f"  非同花查表: {len(non_flush_lookup)} 条记录")

    def generate_pair_tables(self):
        """生成对子、三条、四条查表"""
        print("生成对子查表...")

        # 这里只是示例，实际需要实现完整的查表逻辑

        # 保存查表
        pair_lookup = {}
        self.save_table(pair_lookup, "pair_lookup.npy")
        print(f"  对子查表: {len(pair_lookup)} 条记录")

    def evaluate_flush_hand(self, cards):
        """评估同花手牌强度"""
        # 这里只是示例，实际需要实现完整的评估逻辑
        ranks = [self.rank_to_index[c[0]] for c in cards]
        ranks.sort(reverse=True)

        # 检查是否为同花顺
        if self.is_straight(ranks):
            if ranks[0] == 12:  # A高同花顺
                return (9, [14])  # 皇家同花顺
            else:
                return (8, [ranks[0] + 2])  # 同花顺

        # 普通同花
        return (5, [r + 2 for r in ranks])

    def is_straight(self, ranks):
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

    def cards_to_key(self, cards):
        """将牌组转换为查表键"""
        # 简单的键生成方法，实际可能需要更复杂的编码
        return tuple(sorted(cards))

    def save_table(self, table, filename):
        """保存查表到文件"""
        filepath = os.path.join(self.output_dir, filename)
        np.save(filepath, table)
        print(f"  保存到 {filepath}")

def main():
    """主函数"""
    generator = TableGenerator()
    generator.generate_all_tables()

if __name__ == "__main__":
    main()