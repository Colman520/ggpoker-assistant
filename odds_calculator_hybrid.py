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
        self.default_simulations = self._configured_simulation_count()

    def _configured_simulation_count(self) -> int:
        """读取兼容旧配置的模拟次数。"""
        if "simulation_count" in self.config.data:
            return int(self.config["simulation_count"])

        algorithm = self.config["algorithm"] if "algorithm" in self.config.data else {}
        return int(algorithm.get("monte_carlo_simulations", 10000))

    @staticmethod
    def _combo_key(cards: List[str]) -> Tuple[str, str]:
        return tuple(sorted(cards))

    def _hand_class_key(self, cards: List[str]) -> Tuple[int, int, bool]:
        rank1 = self.evaluator.RANK_TO_INDEX[cards[0][0]]
        rank2 = self.evaluator.RANK_TO_INDEX[cards[1][0]]
        return max(rank1, rank2), min(rank1, rank2), cards[0][1] == cards[1][1]

    def _hole_card_score(self, cards: List[str]) -> float:
        """给起手牌一个启发式强度分数"""
        rank1 = self.evaluator.RANK_TO_INDEX[cards[0][0]] + 2
        rank2 = self.evaluator.RANK_TO_INDEX[cards[1][0]] + 2
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
        index = 0
        while index < len(ranked):
            score = ranked[index][1]
            group_start = index
            while index < len(ranked) and ranked[index][1] == score:
                index += 1

            percentile = group_start / total
            for key, _ in ranked[group_start:index]:
                percentiles[key] = percentile
        return percentiles

    def _preflop_percentile(self, cards: List[str]) -> float:
        return self._preflop_percentiles.get(self._combo_key(cards), 1.0)

    @staticmethod
    def _street_name(community_cards: List[str]) -> str:
        street_map = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}
        return street_map.get(len(community_cards), "unknown")

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _position_category(self, position: str, active_players: int) -> str:
        if active_players <= 3:
            return "Late"
        if position in ["UTG", "UTG+1", "UTG+2", "LJ"]:
            return "Early"
        if position in ["HJ", "CO"]:
            return "Middle"
        if position in ["BTN"]:
            return "Late"
        return "Blinds"

    def _analyze_board_texture(self, community_cards: List[str]) -> Dict[str, float]:
        """分析牌面结构 (干燥 vs 湿润)"""
        if len(community_cards) < 3:
            return {"wetness": 0.0, "paired": False, "monotone": False}

        ranks = [self.evaluator.RANK_TO_INDEX[c[0]] for c in community_cards]
        suits = [c[1] for c in community_cards]

        suit_counts = Counter(suits)
        rank_counts = Counter(ranks)

        max_suit = max(suit_counts.values())
        max_rank = max(rank_counts.values())

        monotone = max_suit >= 3
        paired = max_rank >= 2

        # 连牌性 (Connectedness)
        sorted_ranks = sorted(set(ranks))
        gaps = sum(sorted_ranks[i+1] - sorted_ranks[i] - 1 for i in range(len(sorted_ranks)-1))

        wetness = 0.0
        if max_suit == 2:
            wetness += 0.4
        elif max_suit >= 3:
            wetness += 0.6

        if gaps <= 2 and len(sorted_ranks) >= 3:
            wetness += 0.5
        elif gaps <= 4:
            wetness += 0.2

        if paired:
            wetness -= 0.3

        return {
            "wetness": self._clamp(wetness, 0.0, 1.0),
            "paired": paired,
            "monotone": max_suit >= 3,
            "high_card": max(ranks) + 2
        }

    @staticmethod
    def _rank_set(cards: List[str]) -> Set[int]:
        ranks = {HandEvaluatorTwoPlusTwo.RANK_TO_INDEX[c[0]] for c in cards}
        if 12 in ranks:  # A
            ranks.add(-1)  # A可以作为1
        return ranks

    def _straight_completion_ranks(self, cards: List[str]) -> Set[int]:
        ranks = self._rank_set(cards)
        present_ranks = {HandEvaluatorTwoPlusTwo.RANK_TO_INDEX[c[0]] for c in cards}
        straight_sequences = [set(range(start, start + 5)) for start in range(9)]
        straight_sequences.append({-1, 0, 1, 2, 3})  # A-2-3-4-5
        completions = set()
        for add_rank in range(13):
            if add_rank in present_ranks:
                continue

            test_ranks = set(ranks)
            test_ranks.add(add_rank)
            if add_rank == 12:
                test_ranks.add(-1)

            for seq in straight_sequences:
                if seq.issubset(test_ranks):
                    completions.add(add_rank)
                    break
        return completions

    def _has_flush_draw(self, cards: List[str]) -> bool:
        suit_counts = Counter(c[1] for c in cards)
        return max(suit_counts.values(), default=0) == 4

    def _draw_profile(self, my_cards: List[str], community_cards: List[str]) -> Dict[str, object]:
        cards = my_cards + community_cards
        straight_completion = set()
        straight_draw_type = "none"
        if len(community_cards) < 5:
            straight_completion = self._straight_completion_ranks(cards)
            if len(straight_completion) >= 2:
                straight_draw_type = "open_ended"
            elif len(straight_completion) == 1:
                straight_draw_type = "gutshot"

        return {
            "flush_draw": len(community_cards) < 5 and self._has_flush_draw(cards),
            "straight_draw": straight_draw_type,
            "straight_draw_cards": len(straight_completion),
        }

    def _hand_context(self, my_cards: List[str], community_cards: List[str]) -> Dict[str, object]:
        cards = my_cards + community_cards
        score = self.evaluator.evaluate_hand(cards)
        draw_profile = self._draw_profile(my_cards, community_cards)
        board_ranks = [self.evaluator.RANK_TO_INDEX[c[0]] for c in community_cards]
        hole_ranks = [self.evaluator.RANK_TO_INDEX[c[0]] for c in my_cards]

        pair_rank = None
        if score[0] == 1 and board_ranks:
            shared = set(board_ranks) & set(hole_ranks)
            if shared:
                pair_rank = max(shared)

        top_pair = bool(board_ranks and pair_rank is not None and pair_rank == max(board_ranks))

        return {
            "score": score,
            "hand_level": score[0],
            "hand_name": self.evaluator.hand_name(score),
            "top_pair": top_pair,
            "draw_profile": draw_profile,
        }

    @staticmethod
    def _estimate_fold_equity(texture: Dict[str, float], target_range: float, call_amount: float, pot_size: float, num_opponents: int) -> float:
        """估算弃牌率"""
        base_fe = 0.30 + (target_range * 0.5)
        multiway_penalty = max(0, num_opponents - 1) * 0.25
        base_fe -= multiway_penalty
        wetness = texture.get("wetness", 0.0)
        base_fe -= wetness * 0.25
        if texture.get("high_card", 0) >= 13 and wetness < 0.3:
            base_fe += 0.1
        if call_amount > 0:
            base_fe -= 0.2
        return max(0.05, min(0.85, base_fe))

    def _calculate_outs(
        self,
        my_cards: List[str],
        community: List[str],
        remaining: List[str],
        num_opponents: int,
        target_range: float,
    ) -> int:
        """估算有效补牌数"""
        if len(community) not in (3, 4):
            return 0

        current_context = self._hand_context(my_cards, community)
        current_level = current_context["hand_level"]
        effective_outs = 0

        for card in remaining:
            future_board = community + [card]
            future_context = self._hand_context(my_cards, future_board)
            future_level = future_context["hand_level"]

            clean_improvement = future_level > current_level and future_level >= 2
            premium_improvement = future_level >= 4 or (
                future_level >= 2 and future_context["top_pair"]
            )
            draw_completion = (
                future_context["draw_profile"]["flush_draw"] is False
                and current_context["draw_profile"]["flush_draw"]
                and future_level >= 5
            )
            straight_completion = (
                current_context["draw_profile"]["straight_draw"] != "none"
                and future_level >= 4
            )

            if premium_improvement or draw_completion or straight_completion:
                effective_outs += 1
                continue

            if clean_improvement and current_level <= 1:
                effective_outs += 1

        return effective_outs

    def _outs_to_probability(self, outs: int, community_cards: List[str]) -> float:
        """Outs转概率"""
        if outs == 0:
            return 0.0

        remaining_cards = 52 - 2 - len(community_cards)
        cards_to_come = 5 - len(community_cards)

        if cards_to_come == 2:
            miss_turn = (remaining_cards - outs) / remaining_cards
            miss_river = (remaining_cards - 1 - outs) / (remaining_cards - 1)
            prob = 1 - (miss_turn * miss_river)
        elif cards_to_come == 1:
            prob = outs / remaining_cards
        else:
            prob = 0.0

        return round(min(prob, 1.0), 4)

    def _estimate_range_fraction(
        self,
        community_cards: List[str],
        table_size: int,
        position: str,
        active_players: int,
        opponent_action: str = "Open Raise",
    ) -> Tuple[float, float]:
        """估算对手范围宽度"""
        street = len(community_cards)

        action_base = {
            "Limp / Check": (0.35, 0.05),
            "Open Raise": (0.20, 0.00),
            "Call Raise": (0.15, 0.03),
            "3-Bet": (0.07, 0.00),
            "4-Bet+": (0.025, 0.00),
        }

        base_range, cap_threshold = action_base.get(opponent_action, (0.20, 0.00))

        street_multiplier = {0: 1.0, 3: 0.65, 4: 0.45, 5: 0.30}
        multiplier = street_multiplier.get(street, 1.0)

        short_handed_bonus = max(0, 6 - active_players) * 0.03
        six_max_bonus = 0.02 if table_size == 6 else 0.0

        pos_category = self._position_category(position, active_players)
        if pos_category == "Late":
            position_bonus = 0.05
        elif pos_category == "Blinds":
            position_bonus = 0.02
        else:
            position_bonus = -0.02

        range_fraction = (base_range + short_handed_bonus + six_max_bonus + position_bonus) * multiplier
        return self._clamp(range_fraction, 0.02, 0.60), cap_threshold

    def calculate_pot_odds(self, pot_size: float, call_amount: float) -> Dict:
        """底池赔率"""
        if call_amount <= 0:
            return {
                "pot_odds": float("inf"),
                "required_equity": 0,
                "mdf": 1.0,
                "mdf_pct": "100.0%",
                "bet_ratio": 0.0,
            }

        pot_odds = pot_size / call_amount
        required_equity = call_amount / (pot_size + call_amount)
        mdf = pot_size / (pot_size + call_amount)
        bet_ratio = call_amount / pot_size if pot_size > 0 else float("inf")

        return {
            "pot_odds": round(pot_odds, 2),
            "pot_odds_str": f"{round(pot_odds, 1)}:1",
            "required_equity": round(required_equity, 4),
            "required_equity_pct": f"{round(required_equity * 100, 1)}%",
            "mdf": round(mdf, 4),
            "mdf_pct": f"{round(mdf * 100, 1)}%",
            "bet_ratio": round(bet_ratio, 3) if bet_ratio != float("inf") else float("inf"),
        }

    def preflop_hand_strength(
        self,
        my_cards: List[str],
        table_size: int = 9,
        position: str = "UTG",
        remaining_opponents: int = 8,
        active_players: Optional[int] = None,
        pot_size: Optional[float] = None,
        call_amount: Optional[float] = None,
        opponent_action: str = "Limp / Check",
    ) -> Dict:
        """翻前评估"""
        percentile = self._preflop_percentile(my_cards)
        percentile_pct = round(percentile * 100, 1)
        if active_players is not None:
            remaining_opponents = max(1, int(active_players) - 1)
        players_in_hand = min(table_size, max(1, int(remaining_opponents)) + 1)
        pos_category = self._position_category(position, players_in_hand)

        action_adjust = {
            "Limp / Check": (0.0, 0.0),
            "Open Raise": (-0.10, -0.05),
            "Call Raise": (-0.12, -0.06),
            "3-Bet": (-0.25, -0.15),
            "4-Bet+": (-0.35, -0.20),
        }
        call_adj, raise_adj = action_adjust.get(opponent_action, (0.0, 0.0))

        open_thresholds = {"Early": 0.10, "Middle": 0.18, "Late": 0.32, "Blinds": 0.22}
        call_thresholds = {"Early": 0.16, "Middle": 0.28, "Late": 0.46, "Blinds": 0.36}
        jam_thresholds = {"Early": 0.04, "Middle": 0.065, "Late": 0.10, "Blinds": 0.08}

        short_handed_adjust = max(0, 6 - players_in_hand) * 0.035
        six_max_adjust = 0.02 if table_size == 6 else 0.0

        open_threshold = self._clamp(
            open_thresholds[pos_category] + short_handed_adjust + six_max_adjust, 0.10, 0.60
        )
        call_threshold = self._clamp(
            call_thresholds[pos_category] + short_handed_adjust + six_max_adjust + call_adj, 0.02, 0.75
        )
        jam_threshold = self._clamp(
            jam_thresholds[pos_category] + short_handed_adjust * 0.6 + six_max_adjust * 0.5 + raise_adj,
            0.01, 0.18,
        )

        if percentile <= jam_threshold:
            default_action = "3-BET / VALUE RAISE"
            profile = "顶端范围"
        elif percentile <= open_threshold:
            default_action = "OPEN RAISE"
            profile = "强开池范围"
        elif percentile <= call_threshold:
            default_action = "CALL / 低频加注"
            profile = "可防守/可跟注范围"
        else:
            default_action = "FOLD"
            profile = "弃牌范围"

        action = default_action
        if pot_size is not None and call_amount is not None and call_amount > 0:
            pot_info = self.calculate_pot_odds(pot_size, call_amount)
            required_equity = pot_info["required_equity"]
            approximate_equity = max(0.20, 1.0 - percentile * 1.15)

            if percentile <= jam_threshold and approximate_equity >= required_equity + 0.10:
                action = f"3-BET / 继续加注 (预估Eq {approximate_equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
            elif percentile <= call_threshold and approximate_equity >= required_equity + 0.02:
                action = f"CALL (预估Eq {approximate_equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
            else:
                action = f"FOLD (预估Eq {approximate_equity*100:.1f}% < 需求 {required_equity*100:.1f}%)"

        return {
            "group": percentile_pct,
            "strength": pos_category + "位置",
            "percentile": percentile_pct,
            "profile": profile,
            "action": action,
        }

    def _choose_method(self, remaining_cards: int, num_opponents: int) -> str:
        """动态选择计算方法"""
        if num_opponents > 1:
            return "monte_carlo"

        deck_size = 52 - 2 - (5 - remaining_cards)
        if remaining_cards > 0:
            community_combos = math.comb(deck_size, remaining_cards)
            remaining_after = deck_size - remaining_cards
            opponent_combos = self._opponent_hand_assignment_count(remaining_after, num_opponents)
            total_combos = community_combos * opponent_combos
        else:
            total_combos = self._opponent_hand_assignment_count(deck_size, num_opponents)

        if total_combos <= self.exact_threshold:
            return "exact"
        return "monte_carlo"

    @staticmethod
    def _opponent_hand_assignment_count(deck_size: int, num_opponents: int) -> int:
        """对固定座位的对手发牌组合数。"""
        total = 1
        for index in range(num_opponents):
            total *= math.comb(deck_size - index * 2, 2)
        return total

    def _iter_opponent_hands(self, available: List[str], num_opponents: int):
        """枚举固定座位对手的所有不重叠两张手牌。"""
        if num_opponents == 0:
            yield []
            return

        for hand in combinations(available, 2):
            hand_set = set(hand)
            remaining = [card for card in available if card not in hand_set]
            for rest in self._iter_opponent_hands(remaining, num_opponents - 1):
                yield [list(hand)] + rest

    def calculate_odds(
        self,
        my_cards: List[str],
        community_cards: List[str] = None,
        num_opponents: int = None,
        num_simulations: int = None,
        table_size: int = 9,
        position: str = "UTG",
        remaining_opponents: int = 8,
        active_players: Optional[int] = None,
        pot_size: Optional[float] = None,
        call_amount: Optional[float] = None,
        effective_stack_bb: Optional[float] = None,
        opponent_action: str = "Open Raise",
        method: str = "auto",
    ) -> Dict:
        """计算范围感知的胜率/equity"""
        if community_cards is None:
            community_cards = []
        if num_opponents is None:
            num_opponents = self.config["default_opponents"]
        if num_simulations is None:
            num_simulations = self._configured_simulation_count()
        num_simulations = int(num_simulations)
        if active_players is not None:
            remaining_opponents = max(1, int(active_players) - 1)

        remaining_opponents = max(1, int(remaining_opponents))
        players_in_hand = min(table_size, remaining_opponents + 1)

        all_known = my_cards + community_cards
        if len(my_cards) != 2:
            raise ValueError("手牌必须是2张")
        if len(community_cards) not in (0, 3, 4, 5):
            raise ValueError("公共牌数量必须是0、3、4或5张")
        if len(community_cards) > 5:
            raise ValueError("公共牌最多5张")
        if len(set(all_known)) != len(all_known):
            raise ValueError("牌面有重复！")
        if method not in ("auto", "exact", "monte_carlo"):
            raise ValueError("计算方法必须是auto、exact或monte_carlo")

        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]
        cards_to_deal = 5 - len(community_cards)
        cards_needed = cards_to_deal + 2 * num_opponents
        if cards_needed > len(remaining_deck):
            raise ValueError("对手数量过多，剩余牌不足")
        if num_simulations <= 0:
            raise ValueError("模拟次数必须大于0")

        # 动态选择计算方法
        if method == "auto":
            method = self._choose_method(cards_to_deal, num_opponents)

        # 执行计算
        if method == "exact":
            result = self._run_exact_calculation(my_cards, community_cards, num_opponents, num_simulations)
        else:
            result = self._run_monte_carlo_calculation(my_cards, community_cards, num_opponents, num_simulations)

        # 计算额外信息
        target_range, cap_threshold = self._estimate_range_fraction(
            community_cards, table_size, position, players_in_hand, opponent_action
        )
        texture = self._analyze_board_texture(community_cards)

        result["range_fraction"] = round(target_range, 4)
        result["cap_threshold"] = round(cap_threshold, 4)
        result["street"] = self._street_name(community_cards)
        result["texture"] = texture

        # 计算outs
        outs = self._calculate_outs(my_cards, community_cards, remaining_deck, num_opponents, target_range)
        outs_probability = self._outs_to_probability(outs, community_cards)
        result["outs"] = outs
        result["outs_probability"] = outs_probability

        # 手牌上下文
        hand_context = self._hand_context(my_cards, community_cards) if community_cards else None
        if community_cards:
            result["draw_profile"] = hand_context["draw_profile"]
            result["hand_level"] = hand_context["hand_level"]
            result["top_pair"] = hand_context["top_pair"]

        # 底池赔率和EV
        if pot_size is not None and call_amount is not None:
            result["pot_odds"] = self.calculate_pot_odds(pot_size, call_amount)
            equity = result["equity"]
            if call_amount > 0:
                call_ev_bb = equity * (pot_size + call_amount) - call_amount
                result["call_ev_bb"] = round(call_ev_bb, 3)
                result["ev_decision_hint"] = "CALL+" if call_ev_bb >= 0 else "FOLD"
            else:
                call_ev_bb = equity * pot_size
                result["call_ev_bb"] = round(call_ev_bb, 3)
                result["ev_decision_hint"] = "BET/CHECK"
            if effective_stack_bb is not None and pot_size > 0:
                result["spr"] = round(effective_stack_bb / pot_size, 2)

            fold_equity = self._estimate_fold_equity(texture, target_range, call_amount, pot_size, num_opponents)
            result["fold_equity"] = fold_equity
            if call_amount <= 0:
                bet_amount = pot_size * 0.5
                win_by_fold = fold_equity * pot_size
                win_by_call = (1 - fold_equity) * (equity * (pot_size + bet_amount) - bet_amount)
                bluff_ev = win_by_fold + win_by_call
                result["bluff_ev_bb"] = round(bluff_ev, 3)

        # 建议
        if not community_cards:
            preflop = self.preflop_hand_strength(
                my_cards,
                table_size=table_size,
                position=position,
                remaining_opponents=remaining_opponents,
                pot_size=pot_size,
                call_amount=call_amount,
                opponent_action=opponent_action,
            )
            result["suggestion"] = preflop["action"]
            result["preflop_percentile"] = preflop["percentile"]
            result["preflop_profile"] = preflop["profile"]
        else:
            result["suggestion"] = self._get_postflop_suggestion(result, my_cards, community_cards, num_opponents, pot_size, call_amount, result.get("spr"))

        return result

    def _run_exact_calculation(
        self,
        my_cards: List[str],
        community_cards: List[str],
        num_opponents: int,
        num_simulations: int,
    ) -> Dict:
        """精确计算"""
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
            my_full = my_cards + community_cards
            my_score = self.evaluator.evaluate_hand(my_full)
            for opponent_hands in self._iter_opponent_hands(remaining_deck, num_opponents):
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
            for community_combo in combinations(remaining_deck, cards_to_deal):
                full_community = community_cards + list(community_combo)
                remaining_after_community = [c for c in remaining_deck if c not in community_combo]
                my_full = my_cards + full_community
                my_score = self.evaluator.evaluate_hand(my_full)

                for opponent_hands in self._iter_opponent_hands(remaining_after_community, num_opponents):
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
            "simulations": total_combinations,
            "elapsed_time": round(elapsed, 3),
        }

    def _run_monte_carlo_calculation(
        self,
        my_cards: List[str],
        community_cards: List[str],
        num_opponents: int,
        num_simulations: int,
    ) -> Dict:
        """蒙特卡洛模拟"""
        start_time = time.time()

        all_known = my_cards + community_cards
        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]
        cards_to_deal = 5 - len(community_cards)

        wins = 0
        ties = 0
        losses = 0
        equity_sum = 0.0

        cards_needed = cards_to_deal + 2 * num_opponents

        for _ in range(num_simulations):
            deal = random.sample(remaining_deck, cards_needed)
            sim_community = community_cards + deal[:cards_to_deal]

            opponent_hands = []
            offset = cards_to_deal
            for opponent_index in range(num_opponents):
                start = offset + opponent_index * 2
                opponent_hands.append(deal[start:start + 2])

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

    def _get_postflop_suggestion(
        self,
        result: Dict,
        my_cards: List[str],
        community_cards: List[str],
        num_opponents: int,
        pot_size: Optional[float],
        call_amount: Optional[float],
        spr: Optional[float] = None,
    ) -> str:
        """翻后建议"""
        equity = result["equity"]
        hand_level = result.get("hand_level", 0)
        top_pair = result.get("top_pair", False)
        draw_profile = result.get("draw_profile", {})
        flush_draw = draw_profile.get("flush_draw", False)
        straight_draw = draw_profile.get("straight_draw", "none")
        strong_draw = flush_draw or straight_draw == "open_ended"
        decent_draw = strong_draw or straight_draw == "gutshot"
        multiway_pressure = max(0, num_opponents - 1) * 0.025

        if pot_size is not None and call_amount is not None:
            pot_info = self.calculate_pot_odds(pot_size, call_amount)
            required_equity = pot_info["required_equity"]
            margin = equity - required_equity
            call_ev_bb = equity * (pot_size + call_amount) - call_amount if call_amount > 0 else equity * pot_size

            if call_amount <= 0:
                if equity >= 0.62 - multiway_pressure and hand_level >= 2:
                    return f"VALUE BET (Eq {equity*100:.1f}%)"
                if strong_draw:
                    return f"SEMI-BLUFF (Eq {equity*100:.1f}%)"
                if strong_draw or equity >= 0.40 - multiway_pressure:
                    return f"BET/CHECK (Eq {equity*100:.1f}%)"
                return f"CHECK (Eq {equity*100:.1f}%)"

            if call_ev_bb >= 0.5 and (hand_level >= 2 or strong_draw):
                return f"VALUE RAISE (EV +{call_ev_bb:.2f}bb)"
            if call_ev_bb >= 0:
                return f"CALL (EV +{call_ev_bb:.2f}bb)"
            if margin >= -0.02 and (hand_level >= 1 or decent_draw):
                return f"频率防守CALL (MDF {pot_info['mdf']*100:.1f}%)"
            return f"FOLD (EV {call_ev_bb:.2f}bb)"

        raise_threshold = 0.66 + multiway_pressure
        call_threshold = 0.44 + multiway_pressure

        if hand_level >= 5 or (hand_level >= 2 and equity >= raise_threshold):
            return f"RAISE / BET (强成牌，Eq {equity*100:.1f}%)"
        if top_pair and equity >= raise_threshold + 0.02:
            return f"BET / VALUE (顶对，Eq {equity*100:.1f}%)"
        if strong_draw and equity >= call_threshold - 0.06:
            return f"CALL / 半诈唬 (Eq {equity*100:.1f}%)"
        if equity >= call_threshold:
            return f"CHECK / 控池 (Eq {equity*100:.1f}%)"
        if len(community_cards) < 5:
            return f"CHECK/FOLD (Eq {equity*100:.1f}%)"
        return f"FOLD (Eq {equity*100:.1f}%)"

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
