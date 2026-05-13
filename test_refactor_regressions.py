"""
重构回归测试
运行: python test_refactor_regressions.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from odds_calculator_hybrid import OddsCalculatorHybrid, RANKS, SUITS


def make_calculator(simulations=7):
    config = Config()
    config["simulation_count"] = simulations
    return OddsCalculatorHybrid(config)


def test_simulation_count_compatibility():
    calc = make_calculator(7)
    result = calc.calculate_odds(
        ["Ah", "Kh"],
        [],
        1,
        method="monte_carlo",
    )
    assert result["simulations"] == 7, result


def test_river_has_no_draw_or_semibluff_suggestion():
    calc = make_calculator(20)
    result = calc.calculate_odds(
        ["As", "Ah"],
        ["Ks", "Qs", "Js", "2c", "3d"],
        2,
        method="monte_carlo",
    )
    assert result["draw_profile"]["flush_draw"] is False, result
    assert result["draw_profile"]["straight_draw"] == "none", result
    assert result["draw_profile"]["straight_draw_cards"] == 0, result
    assert "半诈唬" not in result["suggestion"], result
    assert "SEMI-BLUFF" not in result["suggestion"], result


def test_multi_opponent_exact_enumeration_is_not_used_by_auto():
    calc = make_calculator(10)
    assert calc._choose_method(0, 2) == "monte_carlo"
    assert calc._opponent_hand_assignment_count(4, 2) == 6
    assignments = list(calc._iter_opponent_hands(["As", "Ah", "Ks", "Kh"], 2))
    assert len(assignments) == 6, assignments


def test_all_preflop_combos_share_class_percentile():
    calc = make_calculator(5)
    deck = [f"{rank}{suit}" for rank in RANKS for suit in SUITS]
    by_class = {}

    for first_index, first in enumerate(deck):
        for second in deck[first_index + 1:]:
            cards = [first, second]
            by_class.setdefault(calc._hand_class_key(cards), set()).add(calc._preflop_percentile(cards))

    assert len(by_class) == 169, len(by_class)
    mismatches = {key: values for key, values in by_class.items() if len(values) != 1}
    assert not mismatches, mismatches


def test_wheel_and_open_ended_straight_draws():
    calc = make_calculator(5)

    wheel = calc._draw_profile(["As", "2d"], ["3c", "4h", "9s"])
    assert wheel["straight_draw"] == "gutshot", wheel
    assert wheel["straight_draw_cards"] == 1, wheel

    open_ended = calc._draw_profile(["9s", "Td"], ["Jc", "Qh", "2s"])
    assert open_ended["straight_draw"] == "open_ended", open_ended
    assert open_ended["straight_draw_cards"] == 2, open_ended


def test_invalid_public_interface_inputs_fail_fast():
    calc = make_calculator(5)

    try:
        calc.calculate_odds(["Ah", "Kh"], ["Qh"], 1)
    except ValueError as exc:
        assert "公共牌数量" in str(exc), exc
    else:
        raise AssertionError("1张公共牌应该被拒绝")

    try:
        calc.calculate_odds(["Ah", "Kh"], [], 1, method="bad")
    except ValueError as exc:
        assert "计算方法" in str(exc), exc
    else:
        raise AssertionError("未知计算方法应该被拒绝")


def main():
    tests = [
        test_simulation_count_compatibility,
        test_river_has_no_draw_or_semibluff_suggestion,
        test_multi_opponent_exact_enumeration_is_not_used_by_auto,
        test_all_preflop_combos_share_class_percentile,
        test_wheel_and_open_ended_straight_draws,
        test_invalid_public_interface_inputs_fail_fast,
    ]

    for test in tests:
        test()
        print(f"[OK] {test.__name__}")

    print("\n全部重构回归测试通过")


if __name__ == "__main__":
    main()
