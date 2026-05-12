"""
Two Plus Two 手牌评估器测试
"""
import sys
import os
import time
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
FULL_DECK = [f"{r}{s}" for r in RANKS for s in SUITS]

# 已知的5张牌手牌类型计数（权威数据）
EXPECTED_COUNTS = {
    9: 4,       # 皇家同花顺
    8: 36,      # 同花顺
    7: 624,     # 四条
    6: 3744,    # 葫芦
    5: 5108,    # 同花
    4: 10200,   # 顺子
    3: 54912,   # 三条
    2: 123552,  # 两对
    1: 1098240, # 一对
    0: 1302540, # 高牌
}

def test_hand_evaluator():
    """测试手牌评估器"""
    from hand_evaluator_two_plus_two import HandEvaluatorTwoPlusTwo

    print("测试Two Plus Two手牌评估器...")

    evaluator = HandEvaluatorTwoPlusTwo()

    # 测试基本功能
    test_cases = [
        (["As", "Ks", "Qs", "Js", "Ts"], 9, "皇家同花顺"),
        (["Ks", "Qs", "Js", "Ts", "9s"], 8, "同花顺"),
        (["As", "Ah", "Ad", "Ac", "Ks"], 7, "四条"),
        (["As", "Ah", "Ad", "Ks", "Kh"], 6, "葫芦"),
        (["As", "Ks", "Qs", "Js", "9s"], 5, "同花"),
        (["As", "Kd", "Qh", "Js", "Tc"], 4, "顺子"),
        (["As", "Ah", "Ad", "Ks", "Qc"], 3, "三条"),
        (["As", "Ah", "Kd", "Kh", "Qc"], 2, "两对"),
        (["As", "Ah", "Kd", "Qc", "Js"], 1, "一对"),
        (["As", "Kd", "Qh", "Js", "9c"], 0, "高牌"),
    ]

    all_pass = True
    for cards, expected_level, desc in test_cases:
        level, kickers = evaluator.evaluate_hand(cards)
        if level == expected_level:
            print(f"  [OK] {desc}: level={level}")
        else:
            print(f"  [FAIL] {desc}: 期望 level={expected_level}, 实际 level={level}")
            all_pass = False

    return all_pass

def test_exhaustive_5_card():
    """测试所有C(52,5)组合"""
    from hand_evaluator_two_plus_two import HandEvaluatorTwoPlusTwo

    print("\n测试所有C(52,5) = 2,598,960种组合...")

    evaluator = HandEvaluatorTwoPlusTwo()
    counts = {}
    errors = []
    start = time.time()

    total = 0
    for combo in combinations(FULL_DECK, 5):
        cards = list(combo)
        total += 1

        try:
            level, kickers = evaluator.evaluate_hand(cards)
        except Exception as e:
            errors.append(f"异常: {cards} -> {e}")
            continue

        if level not in range(10):
            errors.append(f"无效等级: {cards} -> level={level}")
            continue

        counts[level] = counts.get(level, 0) + 1

        # 每500,000次打印进度
        if total % 500000 == 0:
            elapsed = time.time() - start
            print(f"  已测试 {total:,} 组合 ({elapsed:.1f}s)")

    elapsed = time.time() - start
    print(f"\n测试完成: {total:,} 组合, 耗时 {elapsed:.1f}s")

    # 验证总数
    print(f"\n--- 总数验证 ---")
    if total == 2598960:
        print(f"  [OK] 总数正确: {total:,}")
    else:
        print(f"  [FAIL] 总数错误: 实际 {total:,}, 期望 2,598,960")

    # 验证各类型计数
    print(f"\n--- 手牌类型计数验证 ---")
    all_correct = True
    for level in range(10):
        actual = counts.get(level, 0)
        expected = EXPECTED_COUNTS[level]
        status = "[OK]" if actual == expected else "[FAIL]"
        if actual != expected:
            all_correct = False
        print(f"  {status} Level {level}: 实际={actual:,}, 期望={expected:,}")

    # 报告错误
    if errors:
        print(f"\n--- 错误 ({len(errors)} 个) ---")
        for err in errors[:20]:
            print(f"  [FAIL] {err}")
        if len(errors) > 20:
            print(f"  ... 还有 {len(errors) - 20} 个错误")
    else:
        print(f"\n  [OK] 无运行时错误")

    return all_correct

def main():
    print("=" * 60)
    print("Two Plus Two 手牌评估器测试")
    print("=" * 60)

    results = []

    # 基本功能测试
    results.append(("基本功能测试", test_hand_evaluator()))

    # 全面测试
    all_correct = test_exhaustive_5_card()
    results.append(("C(52,5) 全面测试", all_correct))

    # 总结
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