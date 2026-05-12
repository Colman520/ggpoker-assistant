"""
混合胜率计算器测试
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def test_odds_calculator():
    """测试胜率计算器"""
    from odds_calculator_hybrid import OddsCalculatorHybrid

    print("测试混合胜率计算器...")

    config = Config()
    config["simulation_count"] = 100
    calc = OddsCalculatorHybrid(config)

    # 测试翻前计算
    print("\n--- 翻前计算测试 ---")
    test_cases = [
        (["Ah", "Kh"], [], 5, "AKo vs 5人"),
        (["As", "Ah"], [], 1, "AA vs 1人"),
        (["2s", "3s"], [], 9, "23s vs 9人"),
    ]

    all_pass = True
    for my_cards, community, opponents, desc in test_cases:
        result = calc.calculate_odds(my_cards, community, opponents)
        win_rate = result["win_rate"]
        print(f"  {desc}: 胜率={win_rate*100:.1f}%, 方法={result['method']}")

        if not (0 <= win_rate <= 1):
            print(f"    [FAIL] 胜率超出范围")
            all_pass = False

    # 测试翻后计算
    print("\n--- 翻后计算测试 ---")
    test_cases = [
        (["Ah", "Kh"], ["Qh", "Jh", "3c"], 3, "AK + 同花听牌 vs 3人"),
        (["As", "Ah"], ["Ks", "Qs", "Js"], 2, "AA + 高牌面 vs 2人"),
    ]

    for my_cards, community, opponents, desc in test_cases:
        result = calc.calculate_odds(my_cards, community, opponents)
        win_rate = result["win_rate"]
        equity = result["equity"]
        print(f"  {desc}: 胜率={win_rate*100:.1f}%, equity={equity*100:.1f}%, 方法={result['method']}")

        if not (0 <= win_rate <= 1):
            print(f"    [FAIL] 胜率超出范围")
            all_pass = False

    return all_pass

def test_performance():
    """测试性能"""
    from odds_calculator_hybrid import OddsCalculatorHybrid

    print("\n--- 性能测试 ---")

    config = Config()
    config["simulation_count"] = 100
    calc = OddsCalculatorHybrid(config)

    # 测试翻前计算性能
    start = time.time()
    for _ in range(3):
        calc.calculate_odds(["Ah", "Kh"], [], 5)
    elapsed = time.time() - start
    print(f"  翻前计算: 3次, 耗时{elapsed:.3f}s, 平均{elapsed/3*1000:.1f}ms/次")

    # 测试翻后计算性能
    start = time.time()
    for _ in range(3):
        calc.calculate_odds(["Ah", "Kh"], ["Qh", "Jh", "3c"], 3)
    elapsed = time.time() - start
    print(f"  翻后计算: 3次, 耗时{elapsed:.3f}s, 平均{elapsed/3*1000:.1f}ms/次")

    return True

def main():
    print("=" * 60)
    print("混合胜率计算器测试")
    print("=" * 60)

    results = []

    results.append(("功能测试", test_odds_calculator()))
    results.append(("性能测试", test_performance()))

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)

    for name, ok in results:
        status = "[OK]" if ok else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\n  通过: {passed}/{len(results)}")
    if failed == 0:
        print(f"\n  所有测试通过！")
    else:
        print(f"\n  {failed} 项测试失败，需要修复")

if __name__ == "__main__":
    main()