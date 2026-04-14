"""
GGPoker 助手 - 模块测试脚本
运行: python test_all.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"

results = []


def test(name, func):
    """运行单个测试"""
    try:
        msg = func()
        status = PASS
        results.append((status, name, msg or "OK"))
        print(f"  {status} {name}: {msg or 'OK'}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")


def test_imports():
    """测试所有依赖能否导入"""
    print("\n" + "=" * 50)
    print("📦 Step 1: 检查依赖库")
    print("=" * 50)

    def check_pyqt6():
        from PyQt6.QtWidgets import QApplication
        return "PyQt6 可用"

    def check_cv2():
        import cv2
        return f"OpenCV {cv2.__version__}"

    def check_numpy():
        import numpy as np
        return f"NumPy {np.__version__}"

    def check_mss():
        import mss
        return "mss 可用"

    def check_pillow():
        from PIL import Image
        import PIL
        return f"Pillow {PIL.__version__}"

    def check_win32():
        import win32gui
        return "pywin32 可用"

    test("PyQt6", check_pyqt6)
    test("OpenCV", check_cv2)
    test("NumPy", check_numpy)
    test("mss", check_mss)
    test("Pillow", check_pillow)
    test("pywin32 (Windows)", check_win32)


def test_modules():
    """测试项目模块能否导入"""
    print("\n" + "=" * 50)
    print("📂 Step 2: 检查项目文件")
    print("=" * 50)

    files = [
        "config.py",
        "card_recognition.py",
        "screen_capture.py",
        "odds_calculator.py",
        "gui.py",
        "main.py",
    ]

    for f in files:
        exists = os.path.exists(f)
        status = PASS if exists else FAIL
        size = f"{os.path.getsize(f)} bytes" if exists else "文件不存在！"
        results.append((status, f"文件 {f}", size))
        print(f"  {status} {f}: {size}")

    optional_files = ["calibration.py", "template_generator.py"]
    for f in optional_files:
        exists = os.path.exists(f)
        status = PASS if exists else WARN
        size = f"{os.path.getsize(f)} bytes" if exists else "未创建（可选）"
        results.append((status, f"文件 {f}", size))
        print(f"  {status} {f}: {size}")

    print("\n  --- 导入测试 ---")

    def import_config():
        from config import Config
        c = Config()
        return f"配置加载成功，{len(c.data)} 个顶级配置项"

    def import_card_recognition():
        from card_recognition import CardRecognizer, ManualCardInput
        return "CardRecognizer, ManualCardInput 可用"

    def import_screen_capture():
        from screen_capture import ScreenCapture
        return "ScreenCapture 可用"

    def import_odds_calculator():
        from odds_calculator import OddsCalculator
        return "OddsCalculator 可用"

    def import_gui():
        from gui import HAS_PYQT
        if HAS_PYQT:
            from gui import PokerAssistantGUI
            return "PokerAssistantGUI 可用"
        else:
            return "PyQt6 未安装，GUI 不可用"

    test("导入 config", import_config)
    test("导入 card_recognition", import_card_recognition)
    test("导入 screen_capture", import_screen_capture)
    test("导入 odds_calculator", import_odds_calculator)
    test("导入 gui", import_gui)


def test_config():
    """测试配置系统"""
    print("\n" + "=" * 50)
    print("⚙️ Step 3: 测试配置系统")
    print("=" * 50)

    def test_config_default():
        from config import Config
        c = Config()
        assert "regions" in c.data, "缺少 regions 配置"
        assert "my_cards" in c["regions"], "缺少 my_cards 区域"
        assert "community_cards" in c["regions"], "缺少 community_cards 区域"
        return f"regions: {list(c['regions'].keys())}"

    def test_config_save_load():
        from config import Config
        test_path = "_test_config.json"
        try:
            c = Config(test_path)
            c["test_key"] = "test_value"
            c.save()
            c2 = Config(test_path)
            assert c2["test_key"] == "test_value", "保存/加载不一致"
            return "保存和加载正常"
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)

    test("默认配置", test_config_default)
    test("保存/加载", test_config_save_load)


def test_card_input():
    """测试手动输入解析"""
    print("\n" + "=" * 50)
    print("🎴 Step 4: 测试牌面输入解析")
    print("=" * 50)

    from card_recognition import ManualCardInput

    def test_single_card():
        cases = [
            ("Ah", "Ah"),
            ("kd", "Kd"),
            ("Ts", "Ts"),
            ("10h", "Th"),
            ("2c", "2c"),
        ]
        for inp, expected in cases:
            result = ManualCardInput.parse_card(inp)
            assert result == expected, f"parse_card('{inp}') = '{result}', 期望 '{expected}'"
        return f"测试 {len(cases)} 个用例全部通过"

    def test_hand_parse():
        cases = [
            ("Ah Kh", ["Ah", "Kh"]),
            ("Ts Jd Qc", ["Ts", "Jd", "Qc"]),
            ("2c, 3d, 4h", ["2c", "3d", "4h"]),
            ("AhKh", ["Ah", "Kh"]),
            ("", []),
        ]
        for inp, expected in cases:
            result = ManualCardInput.parse_hand(inp)
            assert result == expected, f"parse_hand('{inp}') = {result}, 期望 {expected}"
        return f"测试 {len(cases)} 个用例全部通过"

    def test_invalid_input():
        invalid = ["XY", "1z", "AA", "hello", "ZZ"]
        for inp in invalid:
            result = ManualCardInput.parse_card(inp)
            assert result is None, f"parse_card('{inp}') 应返回 None, 实际返回 '{result}'"
        return f"测试 {len(invalid)} 个无效输入全部正确拒绝"

    test("单张牌解析", test_single_card)
    test("多张牌解析", test_hand_parse)
    test("无效输入拒绝", test_invalid_input)


def test_odds_calculator():
    """测试胜率计算器"""
    print("\n" + "=" * 50)
    print("📊 Step 5: 测试胜率计算器")
    print("=" * 50)

    def test_basic_calc():
        from config import Config
        from odds_calculator import OddsCalculator

        config = Config()
        # 减少模拟次数加快测试
        original = config["simulation_count"]
        config["simulation_count"] = 2000

        calc = OddsCalculator(config)

        result = calc.calculate_odds(["Ah", "Kh"], [], 5)

        config["simulation_count"] = original

        assert "win_rate" in result, "结果缺少 win_rate"
        assert "tie_rate" in result, "结果缺少 tie_rate"
        assert "lose_rate" in result, "结果缺少 lose_rate"
        assert "suggestion" in result, "结果缺少 suggestion"
        assert "hand_name" in result, "结果缺少 hand_name"
        assert "outs" in result, "结果缺少 outs"
        assert "equity" in result, "结果缺少 equity"

        win = result["win_rate"]
        assert 0 <= win <= 1, f"胜率 {win} 超出范围"
        assert 0 <= result["equity"] <= 1, f"equity {result['equity']} 超出范围"

        total = result["win_rate"] + result["tie_rate"] + result["lose_rate"]
        assert abs(total - 1.0) < 0.05, f"胜/平/负之和 = {total}，应接近 1.0"

        return (
            f"Ah Kh vs 5人: 胜率={win*100:.1f}% "
            f"建议={result['suggestion'][:20]}"
        )

    def test_with_community():
        from config import Config
        from odds_calculator import OddsCalculator

        config = Config()
        config["simulation_count"] = 2000
        calc = OddsCalculator(config)

        result = calc.calculate_odds(["Ah", "Kh"], ["Qh", "Jh", "3c"], 3)

        win = result["win_rate"]
        return (
            f"Ah Kh + Qh Jh 3c vs 3人: 胜率={win*100:.1f}% "
            f"牌型={result['hand_name']}"
        )

    def test_pocket_aces():
        from config import Config
        from odds_calculator import OddsCalculator

        config = Config()
        config["simulation_count"] = 3000
        calc = OddsCalculator(config)

        result = calc.calculate_odds(["As", "Ah"], [], 1)
        win = result["win_rate"]
        assert win > 0.7, f"AA vs 1人胜率应 > 70%，实际 {win*100:.1f}%"
        return f"AA vs 1人: 胜率={win*100:.1f}% (应 > 70%)"

    test("基础计算 (Ah Kh)", test_basic_calc)
    test("带公共牌计算", test_with_community)
    test("AA 胜率验证", test_pocket_aces)


def test_screen_capture():
    """测试屏幕捕获（不需要GGPoker运行）"""
    print("\n" + "=" * 50)
    print("📷 Step 6: 测试屏幕捕获模块")
    print("=" * 50)

    def test_capture_init():
        from config import Config
        from screen_capture import ScreenCapture
        config = Config()
        cap = ScreenCapture(config)
        return f"ScreenCapture 初始化成功"

    def test_find_window():
        from config import Config
        from screen_capture import ScreenCapture
        config = Config()
        cap = ScreenCapture(config)
        found = cap.find_ggpoker_window()
        if found:
            rect = cap.window_rect
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            return f"找到GGPoker窗口: {w}x{h}"
        else:
            return "GGPoker未运行（正常，不影响手动输入功能）"

    test("初始化", test_capture_init)
    test("查找GGPoker窗口", test_find_window)


def test_card_recognizer():
    """测试牌面识别器"""
    print("\n" + "=" * 50)
    print("🔍 Step 7: 测试牌面识别器")
    print("=" * 50)

    def test_recognizer_init():
        from config import Config
        from card_recognition import CardRecognizer
        config = Config()
        rec = CardRecognizer(config)
        n_templates = len(rec.templates) if hasattr(rec, 'templates') else 0
        n_ranks = len(rec.rank_templates) if hasattr(rec, 'rank_templates') else 0
        n_suits = len(rec.suit_templates) if hasattr(rec, 'suit_templates') else 0

        if n_templates > 0:
            return f"加载 {n_templates} 个模板"
        elif n_ranks > 0 or n_suits > 0:
            return f"加载 {n_ranks} 个点数 + {n_suits} 个花色模板"
        else:
            return "无模板（需要运行模板生成工具，手动输入不受影响）"

    def test_empty_image():
        import numpy as np
        from config import Config
        from card_recognition import CardRecognizer
        config = Config()
        rec = CardRecognizer(config)

        result = rec.recognize_cards(None)
        assert result == [], f"None输入应返回[], 实际返回 {result}"

        result = rec.recognize_cards(np.array([]))
        assert result == [], f"空数组应返回[], 实际返回 {result}"
        return "空图像处理正常"

    def test_template_dirs():
        rank_dir = os.path.join("templates", "ranks")
        suit_dir = os.path.join("templates", "suits")
        rank_exists = os.path.exists(rank_dir)
        suit_exists = os.path.exists(suit_dir)

        n_ranks = len([f for f in os.listdir(rank_dir) if f.endswith('.png')]) if rank_exists else 0
        n_suits = len([f for f in os.listdir(suit_dir) if f.endswith('.png')]) if suit_exists else 0

        if n_ranks == 0 and n_suits == 0:
            return "模板目录为空 → 运行 template_generator.py 生成模板"
        return f"点数模板: {n_ranks}/13, 花色模板: {n_suits}/4"

    test("识别器初始化", test_recognizer_init)
    test("空图像处理", test_empty_image)
    test("模板文件检查", test_template_dirs)


def test_gui_launch():
    """测试GUI能否启动（只创建不显示）"""
    print("\n" + "=" * 50)
    print("🖥️ Step 8: 测试GUI创建")
    print("=" * 50)

    def test_gui_create():
        try:
            from PyQt6.QtWidgets import QApplication
            from gui import PokerAssistantGUI, HAS_PYQT
        except ImportError:
            return "PyQt6 不可用，跳过GUI测试"

        if not HAS_PYQT:
            return "HAS_PYQT = False，跳过"

        from config import Config

        # 创建 QApplication（如果还没有）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        config = Config()
        try:
            window = PokerAssistantGUI(config)
            return f"GUI创建成功: {window.width()}x{window.minimumHeight()}"
        except Exception as e:
            raise RuntimeError(f"GUI创建失败: {e}")

    test("创建GUI窗口", test_gui_create)


def print_summary():
    """打印测试总结"""
    print("\n" + "=" * 50)
    print("📋 测试总结")
    print("=" * 50)

    passed = sum(1 for s, _, _ in results if s == PASS)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    warned = sum(1 for s, _, _ in results if s == WARN)

    print(f"\n  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  ⚠️ 警告: {warned}")
    print(f"  总计: {len(results)}")

    if failed > 0:
        print(f"\n  --- 失败项 ---")
        for s, name, msg in results:
            if s == FAIL:
                print(f"  {FAIL} {name}: {msg}")

    if failed == 0:
        print(f"\n  🎉 所有核心测试通过！")
        print(f"\n  下一步:")
        print(f"    1. 运行: python main.py           → 启动GUI")
        print(f"    2. 运行: python main.py --cli      → 命令行模式")
        print(f"    3. 在GUI中手动输入 'Ah Kh' 测试计算")
    else:
        print(f"\n  🔧 请先修复失败项再启动程序")
        print(f"  常见问题:")
        print(f"    - 缺少依赖: pip install -r requirements.txt")
        print(f"    - 缺少文件: 检查 screen_capture.py / odds_calculator.py")


def main():
    print()
    print("🃏 GGPoker 助手 - 模块测试")
    print("=" * 50)

    test_imports()
    test_modules()
    test_config()
    test_card_input()

    # 只在 odds_calculator 存在时测试
    if os.path.exists("odds_calculator.py"):
        test_odds_calculator()
    else:
        print(f"\n  {FAIL} odds_calculator.py 不存在！")
        results.append((FAIL, "odds_calculator.py", "文件不存在"))

    test_screen_capture()
    test_card_recognizer()
    test_gui_launch()
    print_summary()


if __name__ == "__main__":
    main()
