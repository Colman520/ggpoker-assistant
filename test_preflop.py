import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config import Config
from odds_calculator import OddsCalculator

def test_new_preflop_logic():
    print("=" * 60)
    print("🧪 开始全面测试翻前动态逻辑 (位置、人数、牌型)")
    print("=" * 60)
    
    config = Config()
    calc = OddsCalculator(config)
    
    passed_tests = 0
    total_tests = 13

    try:
        # === 基础强牌与边缘牌测试 ===
        res1 = calc.preflop_hand_strength(["Ah", "As"], table_size=9, position="UTG", active_players=9)
        print(f"测试 1 [9人桌 UTG 拿 AA]: \n  -> {res1['action']} (分组:{res1['group']}, {res1['strength']})")
        assert "RAISE" in res1['action'] and "Early" in res1['strength']
        passed_tests += 1

        res2 = calc.preflop_hand_strength(["Kh", "Ts"], table_size=9, position="UTG", active_players=9)
        print(f"测试 2 [9人桌 UTG 拿 KTo]: \n  -> {res2['action']} (分组:{res2['group']}, {res2['strength']})")
        assert "FOLD" in res2['action'] and "Early" in res2['strength']
        passed_tests += 1

        res3 = calc.preflop_hand_strength(["Kh", "Ts"], table_size=9, position="BTN", active_players=9)
        print(f"测试 3 [9人桌 BTN 拿 KTo]: \n  -> {res3['action']} (分组:{res3['group']}, {res3['strength']})")
        assert ("RAISE" in res3['action'] or "CALL" in res3['action']) and "Late" in res3['strength']
        passed_tests += 1

        res4 = calc.preflop_hand_strength(["Jh", "Ts"], table_size=9, position="BB", active_players=9)
        print(f"测试 4 [9人桌 BB 拿 JTo]: \n  -> {res4['action']} (分组:{res4['group']}, {res4['strength']})")
        assert "Blinds" in res4['strength'] and "FOLD" not in res4['action']
        passed_tests += 1

        # === 同花 vs 非同花测试 ===
        res5_s = calc.preflop_hand_strength(["Ah", "Qh"], table_size=9, position="UTG", active_players=9)
        res5_o = calc.preflop_hand_strength(["Ah", "Qs"], table_size=9, position="UTG", active_players=9)
        print(f"测试 5 [同花 vs 非同花 AQs/AQo]: \n  -> AQs:分组{res5_s['group']} | AQo:分组{res5_o['group']}")
        # AQs(组2) 应该比 AQo(组3) 强
        assert res5_s['group'] < res5_o['group']
        passed_tests += 1

        # === 小口袋对子测试 (55) ===
        res6_early = calc.preflop_hand_strength(["5h", "5s"], table_size=9, position="UTG", active_players=9)
        print(f"测试 6 [9人桌 UTG 拿 55]: \n  -> {res6_early['action']} (分组:{res6_early['group']})")
        # 前位小对子只建议 CALL 投机
        assert "CALL" in res6_early['action'] and "RAISE" not in res6_early['action']
        passed_tests += 1

        res6_late = calc.preflop_hand_strength(["5h", "5s"], table_size=9, position="BTN", active_players=9)
        print(f"测试 7 [9人桌 BTN 拿 55]: \n  -> {res6_late['action']} (分组:{res6_late['group']})")
        # 后位小对子可以直接 RAISE 抢盲
        assert "RAISE" in res6_late['action']
        passed_tests += 1

        # === 同花连牌测试 (JTs: Jack-Ten suited) ===
        res7 = calc.preflop_hand_strength(["Jh", "Th"], table_size=9, position="HJ", active_players=9)
        print(f"测试 8 [9人桌 HJ(中位) 拿 JTs]: \n  -> {res7['action']} (分组:{res7['group']}, {res7['strength']})")
        # 中位同花连牌是可以继续的：跟注、混合频率或直接 open 都合理
        assert "CALL" in res7['action'] or "RAISE" in res7['action']
        passed_tests += 1

        # === 弱同花A测试 (A5s) ===
        res8_early = calc.preflop_hand_strength(["Ah", "5h"], table_size=9, position="UTG", active_players=9)
        print(f"测试 9 [9人桌 UTG 拿 A5s]: \n  -> {res8_early['action']} (分组:{res8_early['group']})")
        # 前位 A5s 太弱，建议 FOLD
        assert "FOLD" in res8_early['action']
        passed_tests += 1

        res8_late = calc.preflop_hand_strength(["Ah", "5h"], table_size=9, position="BTN", active_players=9)
        print(f"测试 10 [9人桌 BTN 拿 A5s]: \n  -> {res8_late['action']} (分组:{res8_late['group']})")
        # 后位 A5s 是很好的偷盲/买花牌，建议 CALL/RAISE
        assert "FOLD" not in res8_late['action']
        passed_tests += 1

        # === 残局/单挑 (Heads-up) 极端情况测试 ===
        res9 = calc.preflop_hand_strength(["Kh", "Ts"], table_size=9, position="UTG", active_players=3)
        print(f"测试 11 [残局3人 UTG 拿 KTo]: \n  -> {res9['action']} (识别位置: {res9['strength']})")
        assert "Late" in res9['strength'] and "FOLD" not in res9['action']
        passed_tests += 1

        res10 = calc.preflop_hand_strength(["Qh", "7s"], table_size=6, position="SB", active_players=2)
        print(f"测试 12 [单挑2人 拿 Q7o (中下等牌)]: \n  -> {res10['action']} (分组:{res10['group']}, {res10['strength']})")
        # 单挑时 Q7o 算是不错的牌了 (Group 6)，在 Late 位置不应该 FOLD
        assert "Late" in res10['strength'] and "FOLD" not in res10['action']
        passed_tests += 1

        res11 = calc.preflop_hand_strength(["7h", "2s"], table_size=9, position="BTN", active_players=2)
        print(f"测试 13 [单挑2人 拿 72o (最烂牌)]: \n  -> {res11['action']} (分组:{res11['group']})")
        # 即便是单挑，最烂的 72o (Group 8) 也必须 FOLD
        assert "FOLD" in res11['action']
        passed_tests += 1

    except AssertionError as e:
        import traceback
        print(f"\n❌ 测试失败！发现逻辑不符合预期。")
        traceback.print_exc()
    except Exception as e:
        print(f"\n❌ 代码运行出错: {e}")

    print("-" * 60)
    if passed_tests == total_tests:
        print(f"✅ 全部 {total_tests} 个测试完美通过！这套翻前逻辑非常扎实！")
    else:
        print(f"⚠️ 通过了 {passed_tests}/{total_tests} 个测试。")

if __name__ == "__main__":
    test_new_preflop_logic()
