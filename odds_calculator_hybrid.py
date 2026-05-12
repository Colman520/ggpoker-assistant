"""
混合胜率计算器
结合精确计算和蒙特卡洛模拟
"""
import math
import random
import time
from itertools import combinations
from typing import List, Tuple, Dict, Optional, Set
from collections import Counter

from config import Config
from hand_evaluator_two_plus_two import HandEvaluatorTwoPlusTwo

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]

class OddsCalculatorHybrid:
    """混合胜率计算器"""

    FULL_DECK = [f"{r}{s}" for r in RANKS for s in SUITS]

    def __init__(self, config: Config):
        self.config = config
        self.evaluator = HandEvaluatorTwoPlusTwo()
        self._preflop_percentiles = self._build_preflop_percentiles()

        # 配置参数
        algorithm = config["algorithm"] if "algorithm" in config.data else {}
        self.exact_threshold = algorithm.get("exact_calculation_threshold", 1000000)
        self.default_simulations = algorithm.get("monte_carlo_simulations", 10000)

    @staticmethod
    def _combo_key(cards: List[str]) -> Tuple[str, str]:
        return tuple(sorted(cards))

    def _hole_card_score(self, cards: List[str]) -> float:
        """给起手牌一个启发式强度分数"""
        rank1 = self.evaluator.RANK_TO_INDEX[cards[0][0]]
        rank2 = self.evaluator.RANK_TO_INDEX[cards[1][0]]
        high = max(rank1, rank2)
        low = min(rank1, rank2)
        suited = cards[0][1] == cards[1][1]
        pair = rank1 == rank2
        gap = high - low - 1

        if pair:
            score = 44 + high * 5.6
        else:
            score = high * 4.0 + low * 2.1
            if suited:
                score += 4.8
            else:
                score -= 1.6
            if high >= 14:
                score += 2.5
            if high >= 13 and low >= 10:
                score += 3.2 if suited else 1.0
            elif high >= 12 and low >= 10:
                score += 1.8 if suited else 0.2

            if gap <= 0:
                score += 4.8 if suited else 2.0
            elif gap == 1:
                score += 3.2 if suited else 0.8
            elif gap == 2:
                score += 1.2 if suited else -1.1
            elif gap == 3:
                score += 0.4 if suited else -2.0
            elif gap >= 4:
                score -= min(8.0, gap * 1.3)

            if suited and high == 14 and low <= 5:
                score += 3.0
            if not suited and high >= 13 and low <= 10:
                score -= 3.0
            if not suited and high >= 12 and low <= 9:
                score -= 1.6

        return score

    def _build_preflop_percentiles(self) -> Dict[Tuple[str, str], float]:
        ranked = []
        for combo in combinations(self.FULL_DECK, 2):
            cards = list(combo)
            ranked.append((self._combo_key(cards), self._hole_card_score(cards)))

        ranked.sort(key=lambda item: item[1], reverse=True)
        total = max(len(ranked) - 1, 1)
        percentiles = {}
        for index, (key, _) in enumerate(ranked):
            percentiles[key] = index / total
        return percentiles

    def _preflop_percentile(self, cards: List[str]) -> float:
        return self._preflop_percentiles.get(self._combo_key(cards), 1.0)

    def calculate_odds(
        self,
        my_cards: List[str],
        community_cards: List[str] = None,
        num_opponents: int = None,
        method: str = "auto",
        num_simulations: int = None,
        **kwargs
    ) -> Dict:
        """计算胜率和equity"""
        if community_cards is None:
            community_cards = []
        if num_opponents is None:
            num_opponents = self.config["default_opponents"]
        if num_simulations is None:
            num_simulations = self.default_simulations

        # 验证输入
        assert len(my_cards) == 2, "手牌必须是2张"
        assert len(community_cards) <= 5, "公共牌最多5张"

        all_known = my_cards + community_cards
        assert len(set(all_known)) == len(all_known), "牌面有重复！"

        # 动态选择计算方法
        if method == "auto":
            remaining_cards = 5 - len(community_cards)
            method = self._choose_method(remaining_cards, num_opponents)

        if method == "exact":
            return self.calculate_exact_odds(my_cards, community_cards, num_opponents)
        else:
            return self.calculate_monte_carlo_odds(my_cards, community_cards, num_opponents, num_simulations)

    def _choose_method(self, remaining_cards: int, num_opponents: int) -> str:
        """动态选择计算方法"""
        if remaining_cards <= 2 and num_opponents <= 2:
            return "exact"
        # 精确计算的组合数 = C(remaining_deck, cards_to_deal) * C(remaining, 2*opponents)
        # 简化估算
        if remaining_cards == 0 and num_opponents <= 3:
            return "exact"
        return "monte_carlo"

    def calculate_exact_odds(
        self,
        my_cards: List[str],
        community_cards: List[str],
        num_opponents: int
    ) -> Dict:
        """精确计算胜率"""
        start_time = time.time()

        all_known = my_cards + community_cards
        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]
        cards_to_deal = 5 - len(community_cards)

        total_combinations = 0
        wins = 0
        ties = 0
        losses = 0
        equity_sum = 0.0

        if cards_to_deal == 0:
            # 公共牌已知，只枚举对手手牌
            for opponent_combo in combinations(remaining_deck, 2 * num_opponents):
                opponent_hands = []
                for i in range(num_opponents):
                    hand = list(opponent_combo[i*2:(i+1)*2])
                    opponent_hands.append(hand)

                my_full = my_cards + community_cards
                my_score = self.evaluator.evaluate_hand(my_full)

                all_scores = [my_score]
                for opp_hand in opponent_hands:
                    opp_full = opp_hand + community_cards
                    opp_score = self.evaluator.evaluate_hand(opp_full)
                    all_scores.append(opp_score)

                best_score = max(all_scores)
                winners = [idx for idx, score in enumerate(all_scores) if score == best_score]

                if 0 in winners:
                    share = 1.0 / len(winners)
                    equity_sum += share
                    if len(winners) == 1:
                        wins += 1
                    else:
                        ties += 1
                else:
                    losses += 1

                total_combinations += 1
        else:
            # 枚举所有可能的公共牌组合
            for community_combo in combinations(remaining_deck, cards_to_deal):
                full_community = community_cards + list(community_combo)
                remaining_after_community = [c for c in remaining_deck if c not in community_combo]

                for opponent_combo in combinations(remaining_after_community, 2 * num_opponents):
                    opponent_hands = []
                    for i in range(num_opponents):
                        hand = list(opponent_combo[i*2:(i+1)*2])
                        opponent_hands.append(hand)

                    my_full = my_cards + full_community
                    my_score = self.evaluator.evaluate_hand(my_full)

                    all_scores = [my_score]
                    for opp_hand in opponent_hands:
                        opp_full = opp_hand + full_community
                        opp_score = self.evaluator.evaluate_hand(opp_full)
                        all_scores.append(opp_score)

                    best_score = max(all_scores)
                    winners = [idx for idx, score in enumerate(all_scores) if score == best_score]

                    if 0 in winners:
                        share = 1.0 / len(winners)
                        equity_sum += share
                        if len(winners) == 1:
                            wins += 1
                        else:
                            ties += 1
                    else:
                        losses += 1

                    total_combinations += 1

        elapsed = time.time() - start_time

        win_rate = wins / total_combinations if total_combinations > 0 else 0
        tie_rate = ties / total_combinations if total_combinations > 0 else 0
        lose_rate = losses / total_combinations if total_combinations > 0 else 0
        equity = equity_sum / total_combinations if total_combinations > 0 else 0

        if community_cards:
            hand_name = self.evaluator.hand_name(self.evaluator.evaluate_hand(my_cards + community_cards))
        else:
            hand_name = "待翻牌"

        return {
            "win_rate": round(win_rate, 4),
            "tie_rate": round(tie_rate, 4),
            "lose_rate": round(lose_rate, 4),
            "equity": round(equity, 4),
            "hand_name": hand_name,
            "method": "exact",
            "combinations": total_combinations,
            "elapsed_time": round(elapsed, 3),
        }

    def calculate_monte_carlo_odds(
        self,
        my_cards: List[str],
        community_cards: List[str],
        num_opponents: int,
        num_simulations: int = None
    ) -> Dict:
        """蒙特卡洛模拟胜率"""
        start_time = time.time()

        if num_simulations is None:
            num_simulations = self.default_simulations

        all_known = my_cards + community_cards
        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]
        cards_to_deal = 5 - len(community_cards)

        wins = 0
        ties = 0
        losses = 0
        equity_sum = 0.0

        for _ in range(num_simulations):
            available = remaining_deck[:]

            # 随机选择公共牌
            if cards_to_deal > 0:
                sim_community = community_cards + random.sample(available, cards_to_deal)
                for c in sim_community:
                    if c in available:
                        available.remove(c)
            else:
                sim_community = community_cards[:]

            # 随机选择对手手牌
            opponent_hands = []
            for _ in range(num_opponents):
                hand = random.sample(available, 2)
                opponent_hands.append(hand)
                for card in hand:
                    available.remove(card)

            # 评估手牌
            my_full = my_cards + sim_community
            my_score = self.evaluator.evaluate_hand(my_full)

            all_scores = [my_score]
            for opp_hand in opponent_hands:
                opp_full = opp_hand + sim_community
                opp_score = self.evaluator.evaluate_hand(opp_full)
                all_scores.append(opp_score)

            best_score = max(all_scores)
            winners = [idx for idx, score in enumerate(all_scores) if score == best_score]

            if 0 in winners:
                share = 1.0 / len(winners)
                equity_sum += share
                if len(winners) == 1:
                    wins += 1
                else:
                    ties += 1
            else:
                losses += 1

        elapsed = time.time() - start_time

        win_rate = wins / num_simulations
        tie_rate = ties / num_simulations
        lose_rate = losses / num_simulations
        equity = equity_sum / num_simulations

        if community_cards:
            hand_name = self.evaluator.hand_name(self.evaluator.evaluate_hand(my_cards + community_cards))
        else:
            hand_name = "待翻牌"

        return {
            "win_rate": round(win_rate, 4),
            "tie_rate": round(tie_rate, 4),
            "lose_rate": round(lose_rate, 4),
            "equity": round(equity, 4),
            "hand_name": hand_name,
            "method": "monte_carlo",
            "simulations": num_simulations,
            "elapsed_time": round(elapsed, 3),
        }

    def estimate_range(
        self,
        position: str,
        action: str,
        table_size: int
    ) -> Dict:
        """估算对手范围"""
        base_range = {
            "UTG": 0.15, "UTG+1": 0.18, "UTG+2": 0.20,
            "LJ": 0.25, "HJ": 0.30, "CO": 0.35,
            "BTN": 0.45, "SB": 0.30, "BB": 0.25,
        }

        action_adjust = {
            "Limp / Check": 1.0, "Open Raise": 0.8,
            "Call Raise": 0.7, "3-Bet": 0.5, "4-Bet+": 0.3,
        }

        base = base_range.get(position, 0.25)
        adjust = action_adjust.get(action, 1.0)
        range_fraction = base * adjust

        return {
            "range_fraction": round(range_fraction, 4),
            "position": position,
            "action": action,
            "table_size": table_size,
        }

# 为了兼容性，创建别名
OddsCalculator = OddsCalculatorHybrid