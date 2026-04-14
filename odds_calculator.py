import math
import random
from itertools import combinations
from typing import List, Tuple, Dict, Optional, Set
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

        is_straight = False
        straight_high = 0
        unique_ranks = sorted(set(ranks), reverse=True)

        if len(unique_ranks) == 5:
            if unique_ranks[0] - unique_ranks[4] == 4:
                is_straight = True
                straight_high = unique_ranks[0]

            if not is_straight and set(unique_ranks) == {14, 2, 3, 4, 5}:
                is_straight = True
                straight_high = 5

        counts = sorted(rank_counts.values(), reverse=True)
        sorted_ranks_by_count = sorted(
            rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True
        )
        kickers = [r for r, c in sorted_ranks_by_count]

        if is_flush and is_straight and straight_high == 14:
            return (9, [14])

        if is_flush and is_straight:
            return (8, [straight_high])

        if counts == [4, 1]:
            return (7, kickers)

        if counts == [3, 2]:
            return (6, kickers)

        if is_flush:
            return (5, sorted(ranks, reverse=True))

        if is_straight:
            return (4, [straight_high])

        if counts == [3, 1, 1]:
            return (3, kickers)

        if counts == [2, 2, 1]:
            return (2, kickers)

        if counts == [2, 1, 1, 1]:
            return (1, kickers)

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
    """更贴近真实牌局的 Monte Carlo 胜率模拟器"""

    FULL_DECK = [f"{r}{s}" for r in RANKS for s in SUITS]

    def __init__(self, config: Config):
        self.config = config
        self.evaluator = HandEvaluator()
        self._preflop_percentiles = self._build_preflop_percentiles()

    @staticmethod
    def _combo_key(cards: List[str]) -> Tuple[str, str]:
        return tuple(sorted(cards))

    def _hole_card_score(self, cards: List[str]) -> float:
        """给起手牌一个启发式强度分数，用于构建范围百分位。"""
        rank1 = HandEvaluator.card_rank(cards[0])
        rank2 = HandEvaluator.card_rank(cards[1])
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

    def _estimate_range_fraction(
        self,
        community_cards: List[str],
        table_size: int,
        position: str,
        active_players: int,
        opponent_action: str = "Open Raise",
    ) -> Tuple[float, float]:
        """估算对手在当前街道会继续的平均范围宽度，以及范围是否被封顶 (cap)。返回 (范围宽度, 封顶阈值)"""
        street = len(community_cards)
        
        # 基于对手翻前动作的基础范围估算
        action_base = {
            "Limp / Check": (0.35, 0.05),   # 范围宽，但没有最顶端的牌（被封顶）
            "Open Raise": (0.20, 0.00),     # 正常开池范围，不封顶
            "Call Raise": (0.15, 0.03),     # 跟注范围，通常没有AA/KK等超强牌（被封顶）
            "3-Bet": (0.07, 0.00),          # 极紧的强牌范围
            "4-Bet+": (0.025, 0.00),        # 几乎只有AA, KK, QQ, AK
        }
        
        base_range, cap_threshold = action_base.get(opponent_action, (0.20, 0.00))

        # 随着公共牌发出，范围逐渐收窄
        street_multiplier = {
            0: 1.0,
            3: 0.65,
            4: 0.45,
            5: 0.30,
        }
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

    def _range_acceptance_probability(self, percentile: float, target_range: float, cap_threshold: float = 0.0) -> float:
        """根据目标范围和封顶阈值，判断这手牌在对手范围内的概率"""
        # 如果牌太强，且对手动作是Limp或Call，这些强牌应该被剔除（封顶效应）
        if percentile < cap_threshold:
            return 0.01  # 极小概率
            
        edge = target_range - (percentile - cap_threshold)
        return self._clamp(1.0 / (1.0 + math.exp(-edge * 20.0)), 0.01, 0.98)

    def _analyze_board_texture(self, community_cards: List[str]) -> Dict[str, float]:
        """分析牌面结构 (干燥 vs 湿润)，用于实战范围推算"""
        if len(community_cards) < 3:
            return {"wetness": 0.0, "paired": False, "monotone": False}
            
        ranks = [HandEvaluator.card_rank(c) for c in community_cards]
        suits = [HandEvaluator.card_suit(c) for c in community_cards]
        
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
            wetness += 0.4  # 有同花听牌
        elif max_suit >= 3:
            wetness += 0.6  # 极度湿润（有同花面）
            
        if gaps <= 2 and len(sorted_ranks) >= 3:
            wetness += 0.5  # 顺子听牌重
        elif gaps <= 4:
            wetness += 0.2
            
        if paired:
            wetness -= 0.3  # 公对面通常较干燥（不易中听牌），除非是对大牌
            
        return {
            "wetness": self._clamp(wetness, 0.0, 1.0),
            "paired": paired,
            "monotone": max_suit >= 3,
            "high_card": max(ranks)
        }

    @staticmethod
    def _rank_set(cards: List[str]) -> Set[int]:
        ranks = {HandEvaluator.card_rank(card) for card in cards}
        if 14 in ranks:
            ranks.add(1)
        return ranks

    def _straight_completion_ranks(self, cards: List[str]) -> Set[int]:
        ranks = self._rank_set(cards)
        completions = set()
        for add_rank in range(2, 15):
            test_ranks = set(ranks)
            test_ranks.add(add_rank)
            if add_rank == 14:
                test_ranks.add(1)

            for start in range(1, 11):
                seq = set(range(start, start + 5))
                if seq.issubset(test_ranks):
                    completions.add(add_rank)
                    break
        return completions

    def _has_flush_draw(self, cards: List[str]) -> bool:
        suit_counts = Counter(HandEvaluator.card_suit(card) for card in cards)
        return max(suit_counts.values(), default=0) == 4

    def _draw_profile(self, my_cards: List[str], community_cards: List[str]) -> Dict[str, object]:
        cards = my_cards + community_cards
        straight_completion = self._straight_completion_ranks(cards)
        straight_draw_type = "none"
        if len(community_cards) < 5:
            if len(straight_completion) >= 2:
                straight_draw_type = "open_ended"
            elif len(straight_completion) == 1:
                straight_draw_type = "gutshot"

        return {
            "flush_draw": self._has_flush_draw(cards),
            "straight_draw": straight_draw_type,
            "straight_draw_cards": len(straight_completion),
        }

    def _hand_context(self, my_cards: List[str], community_cards: List[str]) -> Dict[str, object]:
        cards = my_cards + community_cards
        score = self.evaluator.evaluate_hand(cards)
        draw_profile = self._draw_profile(my_cards, community_cards)
        board_ranks = [HandEvaluator.card_rank(card) for card in community_cards]
        hole_ranks = [HandEvaluator.card_rank(card) for card in my_cards]

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

    def _postflop_combo_bonus(self, combo: List[str], community_cards: List[str], texture: Dict[str, float]) -> float:
        context = self._hand_context(combo, community_cards)
        level = context["hand_level"]
        bonus = 0.0
        
        wetness = texture.get("wetness", 0.0)

        if level >= 6:
            bonus += 0.50
        elif level == 5:
            bonus += 0.42
        elif level == 4:
            bonus += 0.34
        elif level == 3:
            bonus += 0.30
        elif level == 2:
            bonus += 0.24
        elif level == 1:
            bonus += 0.14 if context["top_pair"] else 0.08

        draw_profile = context["draw_profile"]
        if draw_profile["flush_draw"]:
            bonus += 0.12 + (wetness * 0.1)  # 湿润牌面同花听牌更多
        if draw_profile["straight_draw"] == "open_ended":
            bonus += 0.12 + (wetness * 0.08)
        elif draw_profile["straight_draw"] == "gutshot":
            bonus += 0.06 + (wetness * 0.04)

        if draw_profile["flush_draw"] and draw_profile["straight_draw"] != "none":
            bonus += 0.08

        return bonus

    def _opponent_combo_weight(
        self,
        combo: List[str],
        community_cards: List[str],
        target_range: float,
        cap_threshold: float,
        texture: Dict[str, float],
    ) -> float:
        percentile = self._preflop_percentile(combo)
        weight = self._range_acceptance_probability(percentile, target_range, cap_threshold)
        if community_cards:
            weight += self._postflop_combo_bonus(combo, community_cards, texture)
            if len(community_cards) == 5:
                weight -= 0.08
        return self._clamp(weight, 0.01, 0.98)

    def _pick_weighted_opponent_hand(
        self,
        available_cards: List[str],
        community_cards: List[str],
        target_range: float,
        cap_threshold: float,
        texture: Dict[str, float],
        combo_weight_cache: Dict[Tuple[str, str], float],
    ) -> List[str]:
        """用拒绝采样从可用牌中挑出更像真实继续范围的对手手牌。"""
        best_combo = None
        best_weight = -1.0
        attempts = min(12, max(4, len(available_cards) // 4))

        for _ in range(attempts):
            combo = random.sample(available_cards, 2)
            key = self._combo_key(combo)
            if key not in combo_weight_cache:
                combo_weight_cache[key] = self._opponent_combo_weight(
                    combo, community_cards, target_range, cap_threshold, texture
                )

            weight = combo_weight_cache[key]
            if weight > best_weight:
                best_weight = weight
                best_combo = combo

            if random.random() <= weight:
                return combo

        return best_combo if best_combo else random.sample(available_cards, 2)

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
    ) -> Dict:
        """计算范围感知的胜率/equity，并给出更贴近实战的建议。"""
        if community_cards is None:
            community_cards = []
        if num_opponents is None:
            num_opponents = self.config["default_opponents"]
        if num_simulations is None:
            num_simulations = self.config["simulation_count"]
        if active_players is not None:
            # 兼容旧参数：active_players(含自己) -> remaining_opponents(除自己)
            remaining_opponents = max(1, int(active_players) - 1)

        remaining_opponents = max(1, int(remaining_opponents))
        players_in_hand = min(table_size, remaining_opponents + 1)

        all_known = my_cards + community_cards
        assert len(my_cards) == 2, "手牌必须是2张"
        assert len(community_cards) <= 5, "公共牌最多5张"
        assert len(set(all_known)) == len(all_known), "牌面有重复！"

        remaining_deck = [c for c in self.FULL_DECK if c not in all_known]
        cards_to_deal = 5 - len(community_cards)
        required_cards = cards_to_deal + 2 * num_opponents
        assert required_cards <= len(remaining_deck), "剩余牌不足以完成模拟"

        wins = 0
        ties = 0
        losses = 0
        equity_sum = 0.0

        target_range, cap_threshold = self._estimate_range_fraction(
            community_cards, table_size, position, players_in_hand, opponent_action
        )
        texture = self._analyze_board_texture(community_cards)
        combo_weight_cache = {}

        for _ in range(num_simulations):
            available_cards = remaining_deck[:]

            opponent_hands = []
            for _ in range(num_opponents):
                combo = self._pick_weighted_opponent_hand(
                    available_cards, community_cards, target_range, cap_threshold, texture, combo_weight_cache
                )
                opponent_hands.append(combo)
                for card in combo:
                    available_cards.remove(card)

            sim_community = community_cards[:]
            if cards_to_deal > 0:
                sim_community.extend(random.sample(available_cards, cards_to_deal))

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

        total = num_simulations
        win_rate = wins / total
        tie_rate = ties / total
        lose_rate = losses / total
        equity = equity_sum / total

        hand_context = self._hand_context(my_cards, community_cards) if community_cards else None
        if community_cards:
            hand_name = hand_context["hand_name"]
        else:
            hand_name = "待翻牌"

        outs = self._calculate_outs(
            my_cards, community_cards, remaining_deck, num_opponents, target_range
        )
        outs_probability = self._outs_to_probability(outs, community_cards)

        result = {
            "win_rate": round(win_rate, 4),
            "tie_rate": round(tie_rate, 4),
            "lose_rate": round(lose_rate, 4),
            "equity": round(equity, 4),
            "hand_name": hand_name,
            "outs": outs,
            "outs_probability": outs_probability,
            "simulations": num_simulations,
            "range_fraction": round(target_range, 4),
            "cap_threshold": round(cap_threshold, 4),
            "street": self._street_name(community_cards),
            "texture": texture,
        }

        if community_cards:
            result["draw_profile"] = hand_context["draw_profile"]
            result["hand_level"] = hand_context["hand_level"]
            result["top_pair"] = hand_context["top_pair"]

        if pot_size is not None and call_amount is not None:
            result["pot_odds"] = self.calculate_pot_odds(pot_size, call_amount)
            if call_amount > 0:
                # 以 BB 为单位的跟注期望值（简化模型）
                call_ev_bb = equity * (pot_size + call_amount) - call_amount
                result["call_ev_bb"] = round(call_ev_bb, 3)
                result["ev_decision_hint"] = "CALL+" if call_ev_bb >= 0 else "FOLD"
            else:
                call_ev_bb = equity * pot_size
                result["call_ev_bb"] = round(call_ev_bb, 3)
                result["ev_decision_hint"] = "BET/CHECK"
            if effective_stack_bb is not None and pot_size > 0:
                result["spr"] = round(effective_stack_bb / pot_size, 2)
            
            # 加入弃牌率(Fold Equity)的近似计算，用于推算诈唬EV
            fold_equity = self._estimate_fold_equity(texture, target_range, call_amount, pot_size, num_opponents)
            result["fold_equity"] = fold_equity
            if call_amount <= 0:
                # 假设我们主动下注半个底池的情况
                bet_amount = pot_size * 0.5
                win_by_fold = fold_equity * pot_size
                win_by_call = (1 - fold_equity) * (equity * (pot_size + bet_amount) - bet_amount)
                bluff_ev = win_by_fold + win_by_call
                result["bluff_ev_bb"] = round(bluff_ev, 3)

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
            result["suggestion"] = self._get_postflop_suggestion(
                result=result,
                my_cards=my_cards,
                community_cards=community_cards,
                num_opponents=num_opponents,
                pot_size=pot_size,
                call_amount=call_amount,
                spr=result.get("spr"),
            )

        return result

    def _estimate_fold_equity(self, texture: Dict[str, float], target_range: float, call_amount: float, pot_size: float, num_opponents: int) -> float:
        """估算我们下注时，对手弃牌的概率 (Fold Equity)"""
        # 基础弃牌率与对手范围宽度成正比（范围越宽，越容易弃牌）
        base_fe = 0.30 + (target_range * 0.5)
        
        # 多人底池弃牌率指数级下降
        multiway_penalty = max(0, num_opponents - 1) * 0.25
        base_fe -= multiway_penalty
        
        # 牌面越湿润，对手越容易找到继续的理由（听牌多），弃牌率越低
        wetness = texture.get("wetness", 0.0)
        base_fe -= wetness * 0.25
        
        # 如果是干燥牌面，且有高牌，弃牌率会升高（除非对手正好击中）
        if texture.get("high_card", 0) >= 13 and wetness < 0.3:
            base_fe += 0.1
            
        # 考虑下注尺寸 (这里假设我们下注半池到满池)
        # 如果是面临对手下注(call_amount > 0)，我们在考虑加注的弃牌率
        if call_amount > 0:
            # 面对已经下注的对手，弃牌率较低
            base_fe -= 0.2
            
        return self._clamp(base_fe, 0.05, 0.85)

    def _calculate_outs(
        self,
        my_cards: List[str],
        community: List[str],
        remaining: List[str],
        num_opponents: int,
        target_range: float,
    ) -> int:
        """
        估算更偏实战的有效补牌数：
        - turn/river 前，只统计能让英雄牌力显著提升或形成强听牌完成的牌
        - 采用折损规则，避免把所有“看起来变强”的牌都算成纯净 outs
        """
        _ = num_opponents, target_range
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
        """Outs转概率 - 使用精确计算"""
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
        """基于 equity、底池赔率和听牌强度给出更贴近实战的建议。"""
        equity = result["equity"]
        hand_level = result.get("hand_level", 0)
        top_pair = result.get("top_pair", False)
        draw_profile = result.get("draw_profile", {})
        flush_draw = draw_profile.get("flush_draw", False)
        straight_draw = draw_profile.get("straight_draw", "none")
        strong_draw = flush_draw or straight_draw == "open_ended"
        decent_draw = strong_draw or straight_draw == "gutshot"
        multiway_pressure = max(0, num_opponents - 1) * 0.025
        texture = result.get("texture", {})
        wetness = texture.get("wetness", 0.0)

        if pot_size is not None and call_amount is not None:
            pot_info = self.calculate_pot_odds(pot_size, call_amount)
            required_equity = pot_info["required_equity"]
            margin = equity - required_equity
            call_ev_bb = equity * (pot_size + call_amount) - call_amount if call_amount > 0 else equity * pot_size
            bluff_ev_bb = result.get("bluff_ev_bb", 0.0)
            fold_equity = result.get("fold_equity", 0.0)
            
            bet_ratio = pot_info.get("bet_ratio", 0.0)
            mdf = pot_info.get("mdf", 1.0)
            if bet_ratio <= 0.40:
                bet_tier = "small"
                ev_raise_threshold = 0.40
                ev_call_threshold = 0.00
            elif bet_ratio <= 0.75:
                bet_tier = "medium"
                ev_raise_threshold = 0.55
                ev_call_threshold = 0.10
            elif bet_ratio <= 1.25:
                bet_tier = "large"
                ev_raise_threshold = 0.75
                ev_call_threshold = 0.20
            else:
                bet_tier = "overbet"
                ev_raise_threshold = 0.95
                ev_call_threshold = 0.30

            spr_raise_delta = 0.0
            spr_call_delta = 0.0
            if spr is not None:
                if spr <= 3.0:
                    spr_raise_delta = -0.08
                    spr_call_delta = -0.03
                elif spr >= 8.0:
                    spr_raise_delta = 0.06
                    spr_call_delta = 0.03
            
            # 听牌在湿润面或者高FE时的加成
            draw_implied_buffer = 0.0
            if len(community_cards) < 5:
                if strong_draw:
                    draw_implied_buffer = 0.05 + (fold_equity * 0.05)
                elif decent_draw:
                    draw_implied_buffer = 0.03 + (fold_equity * 0.02)
                    
            implied_gap = required_equity - equity

            if call_amount <= 0:
                if equity >= 0.62 - multiway_pressure and hand_level >= 2:
                    return f"🔥 VALUE BET (Eq {equity*100:.1f}%，明显领先)"
                if strong_draw and bluff_ev_bb > 0:
                    return f"🔥 SEMI-BLUFF (半诈唬EV +{bluff_ev_bb:.1f}bb，弃牌率 {fold_equity*100:.0f}%)"
                if strong_draw or equity >= 0.40 - multiway_pressure:
                    return f"✅ BET/CHECK (Eq {equity*100:.1f}%，可继续施压)"
                return f"⚖️ CHECK (Eq {equity*100:.1f}%，控制底池)"

            if call_ev_bb >= (ev_raise_threshold + spr_raise_delta) and (hand_level >= 2 or strong_draw):
                return (
                    f"🔥 VALUE RAISE / 强势继续 "
                    f"(EV +{call_ev_bb:.2f}bb, {bet_tier}注)"
                )
            if call_ev_bb >= (ev_call_threshold + spr_call_delta):
                return (
                    f"✅ CALL (EV +{call_ev_bb:.2f}bb, 需求 {required_equity*100:.1f}%)"
                )
            if bet_ratio <= 0.5 and margin >= -0.02 and (hand_level >= 1 or decent_draw):
                return (
                    f"⚖️ 频率防守CALL (小注防过弃, MDF {mdf*100:.1f}%)"
                )
            if implied_gap > 0 and implied_gap <= draw_implied_buffer and len(community_cards) < 5:
                return (
                    f"⚖️ 听牌CALL (隐含赔率与弃牌率可补 {implied_gap*100:.1f}% 缺口)"
                )
            if margin >= 0.12 and (hand_level >= 2 or strong_draw):
                return (
                    f"🔥 RAISE (Eq {equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
                )
            if margin >= 0.03:
                return (
                    f"✅ CALL (Eq {equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
                )
            if decent_draw and margin >= -0.03 and len(community_cards) < 5:
                return (
                    f"⚖️ 谨慎 CALL (听牌可继续，Eq {equity*100:.1f}% 接近价格线)"
                )
            return (
                f"❌ FOLD (EV {call_ev_bb:.2f}bb, Eq {equity*100:.1f}% < 需求 {required_equity*100:.1f}%)"
            )

        raise_threshold = 0.66 + multiway_pressure
        call_threshold = 0.44 + multiway_pressure
        if spr is not None:
            if spr <= 3.0:
                raise_threshold -= 0.05
                call_threshold -= 0.02
            elif spr >= 8.0:
                raise_threshold += 0.04
                call_threshold += 0.03

        if hand_level >= 5 or (hand_level >= 2 and equity >= raise_threshold):
            return f"🔥 RAISE / BET (强成牌，Eq {equity*100:.1f}%)"
        if top_pair and equity >= raise_threshold + 0.02:
            return f"🔥 BET / VALUE (顶对价值下注，Eq {equity*100:.1f}%)"
        if strong_draw and equity >= call_threshold - 0.06:
            return f"✅ CALL / 半诈唬继续 (强听牌，Eq {equity*100:.1f}%)"
        if equity >= call_threshold or (decent_draw and equity >= call_threshold - 0.03):
            if top_pair and equity >= call_threshold + 0.10:
                return f"✅ BET / 继续榨值 (顶对优势，Eq {equity*100:.1f}%)"
            return f"⚖️ CHECK / 控池继续 (Eq {equity*100:.1f}%)"
        if len(community_cards) < 5:
            return f"⚠️ CHECK/FOLD (Eq {equity*100:.1f}%，除非价格很好)"
        return f"❌ FOLD (河牌权益不足，Eq {equity*100:.1f}%)"

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
        """翻前评估：基于范围百分位、位置、短手桌调整与价格判断。"""
        percentile = self._preflop_percentile(my_cards)
        percentile_pct = round(percentile * 100, 1)
        if active_players is not None:
            remaining_opponents = max(1, int(active_players) - 1)
        players_in_hand = min(table_size, max(1, int(remaining_opponents)) + 1)
        pos_category = self._position_category(position, players_in_hand)

        # 面对不同动作的防守/加注阈值
        action_adjust = {
            "Limp / Check": (0.0, 0.0),    # 没有特别紧缩
            "Open Raise": (-0.10, -0.05),  # 需要更强的牌来跟注和3bet
            "Call Raise": (-0.12, -0.06),  # 需要更强的牌 (Squeeze)
            "3-Bet": (-0.25, -0.15),       # 面对3-bet，范围极度收紧
            "4-Bet+": (-0.35, -0.20),      # 面对4-bet，只玩坚果
        }
        call_adj, raise_adj = action_adjust.get(opponent_action, (0.0, 0.0))

        open_thresholds = {
            "Early": 0.10,
            "Middle": 0.18,
            "Late": 0.32,
            "Blinds": 0.22,
        }
        call_thresholds = {
            "Early": 0.16,
            "Middle": 0.28,
            "Late": 0.46,
            "Blinds": 0.36,
        }
        jam_thresholds = {
            "Early": 0.04,
            "Middle": 0.065,
            "Late": 0.10,
            "Blinds": 0.08,
        }

        short_handed_adjust = max(0, 6 - players_in_hand) * 0.035
        six_max_adjust = 0.02 if table_size == 6 else 0.0
        
        # 加上对手动作的调整
        open_threshold = self._clamp(
            open_thresholds[pos_category] + short_handed_adjust + six_max_adjust, 0.10, 0.60
        )
        call_threshold = self._clamp(
            call_thresholds[pos_category] + short_handed_adjust + six_max_adjust + call_adj, 0.02, 0.75
        )
        jam_threshold = self._clamp(
            jam_thresholds[pos_category] + short_handed_adjust * 0.6 + six_max_adjust * 0.5 + raise_adj,
            0.01,
            0.18,
        )

        group = percentile_pct

        if percentile <= jam_threshold:
            default_action = "🔥 3-BET / VALUE RAISE"
            profile = "顶端范围"
        elif percentile <= open_threshold:
            default_action = "🔥 OPEN RAISE"
            profile = "强开池范围"
        elif percentile <= call_threshold:
            default_action = "✅ CALL / 低频加注"
            profile = "可防守/可跟注范围"
        else:
            default_action = "❌ FOLD"
            profile = "弃牌范围"

        action = default_action
        if pot_size is not None and call_amount is not None and call_amount > 0:
            pot_info = self.calculate_pot_odds(pot_size, call_amount)
            required_equity = pot_info["required_equity"]
            approximate_equity = max(0.20, 1.0 - percentile * 1.15)

            if percentile <= jam_threshold and approximate_equity >= required_equity + 0.10:
                action = (
                    f"🔥 3-BET / 继续加注 "
                    f"(预估Eq {approximate_equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
                )
            elif percentile <= call_threshold and approximate_equity >= required_equity + 0.02:
                action = (
                    f"✅ CALL "
                    f"(预估Eq {approximate_equity*100:.1f}% > 需求 {required_equity*100:.1f}%)"
                )
            else:
                action = (
                    f"❌ FOLD "
                    f"(预估Eq {approximate_equity*100:.1f}% < 需求 {required_equity*100:.1f}%)"
                )

        return {
            "group": group,
            "strength": pos_category + "位置",
            "percentile": percentile_pct,
            "profile": profile,
            "action": action,
        }
