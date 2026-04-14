import random
from itertools import combinations
from typing import List, Tuple, Dict
from collections import Counter

from config import Config

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]


class HandEvaluator:
    """扑克手牌评估器"""

    RANK_VALUES = {
        "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
        "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14,
    }

    @staticmethod
    def card_rank(card: str) -> int:
        return HandEvaluator.RANK_VALUES[card[0]]

    @staticmethod
    def card_suit(card: str) -> str:
        return card[1]

    @classmethod
    def evaluate_hand(cls, cards: List[str]) -> Tuple[int, List[int]]:
        """评估最佳5张牌组合，返回 (等级, 踢脚牌)"""
        if len(cards) < 5:
            # 不足5张牌时，直接评估已有的牌
            return cls._evaluate_partial(cards)

        best_score = (0, [0])

        for combo in combinations(cards, 5):
            score = cls._evaluate_five(list(combo))
            if score > best_score:
                best_score = score

        return best_score

    @classmethod
    def _evaluate_partial(cls, cards: List[str]) -> Tuple[int, List[int]]:
        """评估不足5张的牌（翻牌前等）"""
        if len(cards) == 0:
            return (0, [0])

        ranks = sorted([cls.card_rank(c) for c in cards], reverse=True)
        suits = [cls.card_suit(c) for c in cards]
        rank_counts = Counter(ranks)
        counts = sorted(rank_counts.values(), reverse=True)

        sorted_ranks_by_count = sorted(
            rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True
        )
        kickers = [r for r, c in sorted_ranks_by_count]

        # 检查是否所有花色相同（同花趋势）
        all_same_suit = len(set(suits)) == 1

        if counts[0] == 4:
            return (7, kickers)
        if len(counts) >= 2 and counts[0] == 3 and counts[1] == 2:
            return (6, kickers)
        if counts[0] == 3:
            return (3, kickers)
        if len(counts) >= 2 and counts[0] == 2 and counts[1] == 2:
            return (2, kickers)
        if counts[0] == 2:
            return (1, kickers)

        return (0, ranks)

    @classmethod
    def _evaluate_five(cls, cards: List[str]) -> Tuple[int, List[int]]:
        """评估5张牌"""
        ranks = sorted([cls.card_rank(c) for c in cards], reverse=True)
        suits = [cls.card_suit(c) for c in cards]

        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)

        is_flush = max(suit_counts.values()) == 5

        # 检查顺子
        is_straight = False
        straight_high = 0
        unique_ranks = sorted(set(ranks), reverse=True)

        if len(unique_ranks) == 5:
            if unique_ranks[0] - unique_ranks[4] == 4:
                is_straight = True
                straight_high = unique_ranks[0]

            # A-2-3-4-5 小顺子
            if not is_straight and set(unique_ranks) == {14, 2, 3, 4, 5}:
                is_straight = True
                straight_high = 5

        counts = sorted(rank_counts.values(), reverse=True)
        sorted_ranks_by_count = sorted(
            rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True
        )
        kickers = [r for r, c in sorted_ranks_by_count]

        # 皇家同花顺
        if is_flush and is_straight and straight_high == 14:
            return (9, [14])

        # 同花顺
        if is_flush and is_straight:
            return (8, [straight_high])

        # 四条
        if counts == [4, 1]:
            return (7, kickers)

        # 葫芦
        if counts == [3, 2]:
            return (6, kickers)

        # 同花
        if is_flush:
            return (5, sorted(ranks, reverse=True))

        # 顺子
        if is_straight:
            return (4, [straight_high])

        # 三条
        if counts == [3, 1, 1]:
            return (3, kickers)

        # 两对
        if counts == [2, 2, 1]:
            return (2, kickers)

        # 一对
        if counts == [2, 1, 1, 1]:
            return (1, kickers)

        # 高牌
        return (0, sorted(ranks, reverse=True))

    @classmethod
    def hand_name(cls, score: Tuple[int, List[int]]) -> str:
        names = {
            9: "皇家同花顺 👑",
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
        return names.get(score[0], "未知")


class OddsCalculator:
    """Monte Carlo 胜率模拟器"""

    FULL_DECK = [f"{r}{s}" for r in RANKS for s in SUITS]

    def __init__(self, config: Config):
        self.config = config
        self.evaluator = HandEvaluator()

    def calculate_odds(
        self,
        my_cards: List[str],
        community_cards: List[str] = None,
        num_opponents: int = None,
        num_simulations: int = None,
    ) -> Dict:
        """计算胜率"""
        if community_cards is None:
            community_cards = []
        if num_opponents is None:
            num_opponents = self.config["default_opponents"]
        if num_simulations is None:
            num_simulations = self.config["simulation_count"]

        all_known = my_cards + community_cards
        assert len(my_cards) == 2, "手牌必须是2张"
        assert len(community_cards) <= 5, "公共牌最多5张"
        assert len(set(all_known)) == len(all_known), "牌面有重复！"

        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]

        wins = 0
        ties = 0
        losses = 0
        cards_to_deal = 5 - len(community_cards)
        cards_needed = cards_to_deal + num_opponents * 2

        for _ in range(num_simulations):
            random.shuffle(remaining_deck)
            idx = 0

            # 补齐公共牌
            sim_community = community_cards + remaining_deck[idx : idx + cards_to_deal]
            idx += cards_to_deal

            # 发对手牌
            opponent_hands = []
            for _ in range(num_opponents):
                opponent_hands.append(remaining_deck[idx : idx + 2])
                idx += 2

            # 评估我的手牌（手牌 + 公共牌 = 7张取最佳5张）
            my_full = my_cards + sim_community
            my_score = self.evaluator.evaluate_hand(my_full)

            # 评估对手最佳手牌
            best_opponent_score = (0, [0])
            for opp_hand in opponent_hands:
                opp_full = opp_hand + sim_community
                opp_score = self.evaluator.evaluate_hand(opp_full)
                if opp_score > best_opponent_score:
                    best_opponent_score = opp_score

            if my_score > best_opponent_score:
                wins += 1
            elif my_score == best_opponent_score:
                ties += 1
            else:
                losses += 1

        total = num_simulations
        win_rate = wins / total
        tie_rate = ties / total
        lose_rate = losses / total

        # 当前牌型
        if community_cards:
            current_hand = my_cards + community_cards
            current_score = self.evaluator.evaluate_hand(current_hand)
            hand_name = self.evaluator.hand_name(current_score)
        else:
            hand_name = "待翻牌"

        # 计算 Outs
        outs = self._calculate_outs(my_cards, community_cards, remaining_deck)

        result = {
            "win_rate": round(win_rate, 4),
            "tie_rate": round(tie_rate, 4),
            "lose_rate": round(lose_rate, 4),
            "hand_name": hand_name,
            "outs": outs,
            "outs_probability": self._outs_to_probability(outs, community_cards),
            "simulations": num_simulations,
        }

        result["suggestion"] = self._get_suggestion(result)
        return result

    def _calculate_outs(
        self,
        my_cards: List[str],
        community_cards: List[str],
        remaining: List[str],
    ) -> int:
        """计算补牌数 - 只计算能提升牌型等级的牌"""
        if not community_cards or len(community_cards) >= 5:
            return 0

        current_full = my_cards + community_cards
        current_score = self.evaluator.evaluate_hand(current_full)
        current_level = current_score[0]  # 只看牌型等级

        outs = 0
        for card in remaining:
            test_hand = my_cards + community_cards + [card]
            new_score = self.evaluator.evaluate_hand(test_hand)
            # 只有牌型等级提升才算 out
            if new_score[0] > current_level:
                outs += 1

        return outs

    def _outs_to_probability(self, outs: int, community_cards: List[str]) -> float:
        """Outs转概率 - 使用精确计算"""
        if outs == 0:
            return 0.0

        remaining_cards = 52 - 2 - len(community_cards)
        cards_to_come = 5 - len(community_cards)

        if cards_to_come == 2:
            # Turn + River: 1 - (miss_turn * miss_river)
            miss_turn = (remaining_cards - outs) / remaining_cards
            miss_river = (remaining_cards - 1 - outs) / (remaining_cards - 1)
            prob = 1 - (miss_turn * miss_river)
        elif cards_to_come == 1:
            # River only
            prob = outs / remaining_cards
        else:
            prob = 0.0

        return round(min(prob, 1.0), 4)

    def _get_suggestion(self, result: Dict) -> str:
        """操作建议"""
        win_rate = result["win_rate"]

        if win_rate >= 0.70:
            return "🔥 RAISE (强牌，加注!)"
        elif win_rate >= 0.50:
            return "✅ CALL/RAISE (好牌，可以跟注或加注)"
        elif win_rate >= 0.35:
            return "⚖️ CALL (中等牌，可以跟注)"
        elif win_rate >= 0.20:
            return "⚠️ CHECK/FOLD (弱牌，过牌或弃牌)"
        else:
            return "❌ FOLD (很弱，建议弃牌)"

    def calculate_pot_odds(self, pot_size: float, call_amount: float) -> Dict:
        """底池赔率"""
        if call_amount <= 0:
            return {"pot_odds": float("inf"), "required_equity": 0}

        pot_odds = pot_size / call_amount
        required_equity = call_amount / (pot_size + call_amount)

        return {
            "pot_odds": round(pot_odds, 2),
            "pot_odds_str": f"{round(pot_odds, 1)}:1",
            "required_equity": round(required_equity, 4),
            "required_equity_pct": f"{round(required_equity * 100, 1)}%",
        }

    def preflop_hand_strength(self, my_cards: List[str]) -> Dict:
        """翻牌前手牌评估"""
        rank1 = HandEvaluator.card_rank(my_cards[0])
        rank2 = HandEvaluator.card_rank(my_cards[1])
        suited = my_cards[0][1] == my_cards[1][1]

        high = max(rank1, rank2)
        low = min(rank1, rank2)

        if rank1 == rank2:
            if high >= 13:
                return {"group": 1, "strength": "超强", "action": "🔥 RAISE"}
            elif high >= 10:
                return {"group": 2, "strength": "很强", "action": "🔥 RAISE"}
            elif high >= 7:
                return {"group": 4, "strength": "中等", "action": "✅ CALL/RAISE"}
            else:
                return {"group": 5, "strength": "中等偏弱", "action": "⚖️ CALL"}

        score = high + low
        if suited:
            score += 2

        if high == 14 and low == 13:
            return {"group": 1, "strength": "超强", "action": "🔥 RAISE"}
        if high == 14 and low >= 11 and suited:
            return {"group": 2, "strength": "很强", "action": "🔥 RAISE"}

        if score >= 23:
            return {"group": 3, "strength": "较强", "action": "✅ RAISE/CALL"}
        elif score >= 19:
            return {"group": 5, "strength": "中等", "action": "⚖️ CALL"}
        elif score >= 16 and suited:
            return {"group": 6, "strength": "投机牌", "action": "⚖️ CALL (位置好时)"}
        else:
            return {"group": 8, "strength": "弱", "action": "❌ FOLD"}