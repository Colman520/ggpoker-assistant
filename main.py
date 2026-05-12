import sys
import os

# 确保能找到同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

def create_odds_calculator(config):
    """根据配置创建胜率计算器"""
    algorithm = config["algorithm"]["odds_calculator"] if "algorithm" in config.data else "hybrid"

    if algorithm == "hybrid":
        from odds_calculator_hybrid import OddsCalculatorHybrid
        return OddsCalculatorHybrid(config)
    else:
        from odds_calculator import OddsCalculator
        return OddsCalculator(config)

def create_hand_evaluator(config):
    """根据配置创建手牌评估器"""
    algorithm = config["algorithm"]["hand_evaluator"] if "algorithm" in config.data else "two_plus_two"

    if algorithm == "two_plus_two":
        from hand_evaluator_two_plus_two import HandEvaluatorTwoPlusTwo
        table_path = config["algorithm"]["table_path"] if "algorithm" in config.data else "tables/"
        return HandEvaluatorTwoPlusTwo(table_path)
    else:
        from odds_calculator import HandEvaluator
        return HandEvaluator()


def main_gui():
    """启动GUI界面"""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
        from gui import PokerAssistantGUI
    except ImportError:
        print("❌ PyQt6 未安装: pip install PyQt6")
        print("回退到命令行模式...\n")
        main_cli()
        return

    config = Config()
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    window = PokerAssistantGUI(config)
    window.show()
    print("✅ GUI 已启动！")

    sys.exit(app.exec())


def main_cli():
    """命令行模式"""
    from card_recognition import ManualCardInput
    config = Config()
    calculator = create_odds_calculator(config)

    print("=" * 50)
    print("🃏 GGPoker 胜率计算器 (命令行模式)")
    print("=" * 50)
    print()
    print("输入格式说明:")
    print("  点数: A K Q J T(10) 9 8 7 6 5 4 3 2")
    print("  花色: s(♠黑桃) h(♥红心) d(♦方块) c(♣梅花)")
    print("  示例: Ah Kh = 红心A 红心K")
    print("  输入 quit 退出")
    print("=" * 50)

    while True:
        print()
        hand_str = input("🎴 输入手牌 (2张，如 Ah Kh): ").strip()
        if hand_str.lower() in ("quit", "exit", "q"):
            print("👋 再见！")
            break

        my_cards = ManualCardInput.parse_hand(hand_str)
        if len(my_cards) != 2:
            print("❌ 手牌需要2张！格式如: Ah Kh  或  As Td")
            print("   点数: A K Q J T 9 8 7 6 5 4 3 2")
            print("   花色: s h d c")
            continue

        comm_str = input("🃏 输入公共牌 (0-5张，回车跳过): ").strip()
        community_cards = ManualCardInput.parse_hand(comm_str) if comm_str else []

        if len(community_cards) > 5:
            print("❌ 公共牌最多5张！")
            continue

        all_cards = my_cards + community_cards
        if len(set(all_cards)) != len(all_cards):
            print("❌ 有重复的牌！请检查输入")
            continue

        opp_str = input("👥 对手数量 (直接回车默认5): ").strip()
        num_opp = int(opp_str) if opp_str.isdigit() and 1 <= int(opp_str) <= 9 else 5

        sim_count = config["simulation_count"]
        print(f"\n🔄 计算中... (模拟{sim_count}次，约需2-5秒)")

        result = calculator.calculate_odds(my_cards, community_cards, num_opp)

        suit_symbols = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

        def fmt(card):
            r = "10" if card[0] == "T" else card[0]
            return f"{r}{suit_symbols[card[1]]}"

        print()
        print("┌" + "─" * 42 + "┐")
        print(f"│  手牌:   {' '.join(fmt(c) for c in my_cards):33s}│")
        if community_cards:
            print(f"│  公共牌: {' '.join(fmt(c) for c in community_cards):33s}│")
        else:
            print(f"│  公共牌: (无)                              │")
        print(f"│  牌型:   {result['hand_name']:33s}│")
        print("├" + "─" * 42 + "┤")
        print(f"│  ✅ 胜率:   {result['win_rate']*100:6.1f}%                        │")
        print(f"│  ⚖️  平局:   {result['tie_rate']*100:6.1f}%                        │")
        print(f"│  ❌ 败率:   {result['lose_rate']*100:6.1f}%                        │")
        print("├" + "─" * 42 + "┤")
        outs = result["outs"]
        outs_p = result["outs_probability"] * 100
        print(f"│  Outs: {outs:2d}  |  中牌率: {outs_p:5.1f}%                │")
        print(f"│                                          │")
        print(f"│  {result['suggestion']:40s}│")
        print("└" + "─" * 42 + "┘")

        if not community_cards:
            preflop = calculator.preflop_hand_strength(my_cards)
            print(f"\n  📊 翻牌前评估: 组{preflop['group']} - {preflop['strength']}")
            print(f"  📌 建议: {preflop['action']}")


def main():
    """主入口"""
    print()
    print("🃏 GGPoker 助手 v1.0")
    print("=" * 40)

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "--cli":
            main_cli()
            return
        elif arg == "--help" or arg == "-h":
            print("用法:")
            print("  python main.py          → GUI模式（默认）")
            print("  python main.py --cli    → 命令行模式")
            print("  python main.py --help   → 显示帮助")
            return

    # 默认尝试 GUI
    print("启动 GUI 模式...")
    print("（如果 GUI 失败，会自动回退到命令行模式）")
    print()

    try:
        main_gui()
    except Exception as e:
        print(f"\n⚠️ GUI 启动失败: {e}")
        print("自动回退到命令行模式...\n")
        main_cli()


if __name__ == "__main__":
    main()
