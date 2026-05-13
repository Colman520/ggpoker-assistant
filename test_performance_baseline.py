"""
性能基准测试 - 记录当前算法的性能
"""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from hand_evaluator_two_plus_two import HandEvaluatorTwoPlusTwo
from odds_calculator_hybrid import OddsCalculatorHybrid

def test_hand_evaluator_performance():
    """测试手牌评估器性能"""
    from itertools import combinations

    evaluator = HandEvaluatorTwoPlusTwo()
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
    suits = ["s", "h", "d", "c"]
    deck = [f"{r}{s}" for r in ranks for s in suits]

    # 测试5张牌评估
    start = time.time()
    count = 0
    for combo in combinations(deck, 5):
        cards = list(combo)
        evaluator.evaluate_hand(cards)
        count += 1
        if count >= 100000:  # 测试10万次
            break

    elapsed = time.time() - start
    print(f"5张牌评估: {count}次, 耗时{elapsed:.3f}s, 平均{elapsed/count*1000:.3f}ms/次")

    # 测试7张牌评估
    start = time.time()
    count = 0
    for combo in combinations(deck, 7):
        cards = list(combo)
        evaluator.evaluate_hand(cards)
        count += 1
        if count >= 10000:  # 测试1万次
            break

    elapsed = time.time() - start
    print(f"7张牌评估: {count}次, 耗时{elapsed:.3f}s, 平均{elapsed/count*1000:.3f}ms/次")

def test_odds_calculator_performance():
    """测试胜率计算器性能"""
    config = Config()
    config["simulation_count"] = 200
    calc = OddsCalculatorHybrid(config)

    # 测试翻前计算
    start = time.time()
    count = 5
    for _ in range(count):
        calc.calculate_odds(["Ah", "Kh"], [], 5)
    elapsed = time.time() - start
    print(f"翻前计算: {count}次, 耗时{elapsed:.3f}s, 平均{elapsed/count*1000:.1f}ms/次")

    # 测试翻后计算
    start = time.time()
    count = 5
    for _ in range(count):
        calc.calculate_odds(["Ah", "Kh"], ["Qh", "Jh", "3c"], 3)
    elapsed = time.time() - start
    print(f"翻后计算: {count}次, 耗时{elapsed:.3f}s, 平均{elapsed/count*1000:.1f}ms/次")

if __name__ == "__main__":
    print("=" * 60)
    print("GGPoker 助手 - 性能基准测试")
    print("=" * 60)

    print("\n--- 手牌评估器性能 ---")
    test_hand_evaluator_performance()

    print("\n--- 胜率计算器性能 ---")
    test_odds_calculator_performance()

    print("\n" + "=" * 60)
    print("基准测试完成")
    print("=" * 60)
