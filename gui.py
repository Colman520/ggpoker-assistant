import sys

try:
    from PyQt6.QtWidgets import (
        QApplication,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QGroupBox,
        QLineEdit,
        QSpinBox,
        QFrame,
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QMouseEvent

    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    print("⚠️ PyQt6 未安装: pip install PyQt6")

from config import Config
from screen_capture import ScreenCapture
from card_recognition import CardRecognizer, ManualCardInput
from odds_calculator import OddsCalculator


if HAS_PYQT:

    class PokerAssistantGUI(QWidget):
        """GGPoker 助手悬浮窗"""

        def __init__(self, config: Config):
            super().__init__()
            self.config = config
            self.capture = ScreenCapture(config)
            self.recognizer = CardRecognizer(config)
            self.calculator = OddsCalculator(config)

            self.is_running = False
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_cycle)

            self._drag_pos = None
            self.init_ui()

        def init_ui(self):
            gui_config = self.config["gui"]

            self.setWindowTitle("🃏 GGPoker Assistant")
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
            )
            self.setWindowOpacity(gui_config["opacity"])
            self.setFixedWidth(gui_config["width"])
            self.setMinimumHeight(gui_config["height"])

            self.setStyleSheet(
                """
                QWidget {
                    background-color: #1a1a2e;
                    color: #eee;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }
                QGroupBox {
                    border: 1px solid #333;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 14px;
                    font-weight: bold;
                    color: #4ecca3;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QPushButton {
                    background-color: #4ecca3;
                    color: #1a1a2e;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 13px;
                }
                QPushButton:hover { background-color: #7efcce; }
                QPushButton:pressed { background-color: #36b58e; }
                QLineEdit {
                    background-color: #16213e;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 6px;
                    color: #eee;
                    font-size: 14px;
                }
                QSpinBox {
                    background-color: #16213e;
                    border: 1px solid #333;
                    border-radius: 4px;
                    padding: 4px;
                    color: #eee;
                }
                QLabel { color: #ccc; }
            """
            )

            main_layout = QVBoxLayout()
            main_layout.setSpacing(6)
            main_layout.setContentsMargins(10, 8, 10, 8)

            # 标题栏
            title_bar = QHBoxLayout()
            title_label = QLabel("🃏 GGPoker Assistant")
            title_label.setStyleSheet("color: #4ecca3; font-size: 18px; font-weight: bold;")
            title_bar.addWidget(title_label)
            title_bar.addStretch()

            close_btn = QPushButton("✕")
            close_btn.setFixedSize(24, 24)
            close_btn.setStyleSheet(
                """
                QPushButton { background: transparent; color: #888; font-size: 16px; padding: 0; }
                QPushButton:hover { color: #e74c3c; }
            """
            )
            close_btn.clicked.connect(self.close)
            title_bar.addWidget(close_btn)
            main_layout.addLayout(title_bar)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #333;")
            main_layout.addWidget(line)

            # 手动输入区域
            input_group = QGroupBox("📝 手动输入")
            input_layout = QVBoxLayout()

            hand_row = QHBoxLayout()
            hand_row.addWidget(QLabel("手牌:"))
            self.hand_input = QLineEdit()
            self.hand_input.setPlaceholderText("如: Ah Kh")
            self.hand_input.setMaximumWidth(150)
            hand_row.addWidget(self.hand_input)
            input_layout.addLayout(hand_row)

            comm_row = QHBoxLayout()
            comm_row.addWidget(QLabel("公共牌:"))
            self.community_input = QLineEdit()
            self.community_input.setPlaceholderText("如: Qh Jh 3c")
            self.community_input.setMaximumWidth(150)
            comm_row.addWidget(self.community_input)
            input_layout.addLayout(comm_row)

            opp_row = QHBoxLayout()
            opp_row.addWidget(QLabel("对手数:"))
            self.opponent_spin = QSpinBox()
            self.opponent_spin.setRange(1, 9)
            self.opponent_spin.setValue(self.config["default_opponents"])
            self.opponent_spin.setMaximumWidth(60)
            opp_row.addWidget(self.opponent_spin)
            opp_row.addStretch()
            input_layout.addLayout(opp_row)

            calc_btn = QPushButton("📊 计算胜率")
            calc_btn.clicked.connect(self.manual_calculate)
            input_layout.addWidget(calc_btn)

            input_group.setLayout(input_layout)
            main_layout.addWidget(input_group)

            # 结果显示区域
            result_group = QGroupBox("📈 计算结果")
            result_layout = QVBoxLayout()

            self.cards_label = QLabel("手牌: -- | 公共牌: --")
            self.cards_label.setStyleSheet("font-size: 13px;")
            result_layout.addWidget(self.cards_label)

            self.hand_type_label = QLabel("牌型: --")
            self.hand_type_label.setStyleSheet("font-size: 13px; color: #f0a500;")
            result_layout.addWidget(self.hand_type_label)

            self.win_rate_label = QLabel("胜率: --%")
            self.win_rate_label.setStyleSheet(
                "color: #4ecca3; font-size: 28px; font-weight: bold;"
            )
            self.win_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            result_layout.addWidget(self.win_rate_label)

            prob_layout = QHBoxLayout()
            self.tie_label = QLabel("⚖️ 平局: --%")
            self.lose_label = QLabel("❌ 败率: --%")
            prob_layout.addWidget(self.tie_label)
            prob_layout.addWidget(self.lose_label)
            result_layout.addLayout(prob_layout)

            self.outs_label = QLabel("补牌(Outs): -- | 中牌率: --%")
            result_layout.addWidget(self.outs_label)

            self.suggestion_label = QLabel("建议: --")
            self.suggestion_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.suggestion_label.setStyleSheet(
                """
                font-size: 15px; font-weight: bold; padding: 8px;
                background-color: #16213e; border-radius: 6px;
            """
            )
            result_layout.addWidget(self.suggestion_label)

            result_group.setLayout(result_layout)
            main_layout.addWidget(result_group)

            # 自动识别控制
            auto_group = QGroupBox("🤖 自动识别")
            auto_layout = QVBoxLayout()

            btn_row = QHBoxLayout()
            self.start_btn = QPushButton("▶ 开始监控")
            self.start_btn.clicked.connect(self.toggle_auto_capture)
            btn_row.addWidget(self.start_btn)

            self.calibrate_btn = QPushButton("🎯 校准区域")
            self.calibrate_btn.clicked.connect(self.calibrate_regions)
            btn_row.addWidget(self.calibrate_btn)
            auto_layout.addLayout(btn_row)

            self.status_label = QLabel("状态: 就绪")
            self.status_label.setStyleSheet("color: #888; font-size: 11px;")
            auto_layout.addWidget(self.status_label)

            auto_group.setLayout(auto_layout)
            main_layout.addWidget(auto_group)

            main_layout.addStretch()
            self.setLayout(main_layout)

            pos = gui_config["position"]
            self.move(pos[0], pos[1])

        def manual_calculate(self):
            """手动计算胜率"""
            hand_str = self.hand_input.text().strip()
            comm_str = self.community_input.text().strip()
            num_opp = self.opponent_spin.value()

            if not hand_str:
                self.status_label.setText("⚠️ 请输入手牌")
                return

            my_cards = ManualCardInput.parse_hand(hand_str)
            if len(my_cards) != 2:
                self.status_label.setText("⚠️ 手牌格式错误，需要2张牌 (如: Ah Kh)")
                return

            community_cards = []
            if comm_str:
                community_cards = ManualCardInput.parse_hand(comm_str)
                if len(community_cards) > 5:
                    self.status_label.setText("⚠️ 公共牌最多5张")
                    return

            all_cards = my_cards + community_cards
            if len(set(all_cards)) != len(all_cards):
                self.status_label.setText("⚠️ 有重复的牌！")
                return

            self.status_label.setText("🔄 计算中...")
            QApplication.processEvents()

            try:
                result = self.calculator.calculate_odds(
                    my_cards, community_cards, num_opp
                )
                self.update_display(my_cards, community_cards, result)
                self.status_label.setText(
                    f"✅ 计算完成 ({result['simulations']}次模拟)"
                )
            except Exception as e:
                self.status_label.setText(f"❌ 错误: {str(e)}")

        def update_display(self, my_cards, community_cards, result):
            """更新显示"""
            suit_symbols = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}

            def format_card(card):
                rank = "10" if card[0] == "T" else card[0]
                return f"{rank}{suit_symbols.get(card[1], card[1])}"

            hand_str = " ".join(format_card(c) for c in my_cards)
            comm_str = (
                " ".join(format_card(c) for c in community_cards)
                if community_cards
                else "--"
            )

            self.cards_label.setText(f"手牌: {hand_str}  |  公共牌: {comm_str}")
            self.hand_type_label.setText(f"牌型: {result['hand_name']}")

            win_pct = result["win_rate"] * 100
            self.win_rate_label.setText(f"✅ 胜率: {win_pct:.1f}%")

            if win_pct >= 60:
                color = "#4ecca3"
            elif win_pct >= 40:
                color = "#f0a500"
            else:
                color = "#e74c3c"

            self.win_rate_label.setStyleSheet(
                f"color: {color}; font-size: 28px; font-weight: bold;"
            )

            self.tie_label.setText(f"⚖️ 平局: {result['tie_rate']*100:.1f}%")
            self.lose_label.setText(f"❌ 败率: {result['lose_rate']*100:.1f}%")

            outs = result["outs"]
            outs_prob = result["outs_probability"] * 100
            self.outs_label.setText(f"补牌(Outs): {outs} | 中牌率: {outs_prob:.1f}%")

            self.suggestion_label.setText(result["suggestion"])

            if "RAISE" in result["suggestion"] and "🔥" in result["suggestion"]:
                bg = "#1a4a2e"
            elif "CALL" in result["suggestion"]:
                bg = "#3a3a1e"
            else:
                bg = "#4a1a1e"

            self.suggestion_label.setStyleSheet(
                f"""
                font-size: 15px; font-weight: bold; padding: 8px;
                background-color: {bg}; border-radius: 6px;
            """
            )

        def toggle_auto_capture(self):
            if self.is_running:
                self.stop_auto_capture()
            else:
                self.start_auto_capture()

        def start_auto_capture(self):
            found = self.capture.find_ggpoker_window()
            if not found:
                self.status_label.setText("❌ 未找到GGPoker窗口！请先打开GGPoker")
                return

            self.is_running = True
            self.start_btn.setText("⏹ 停止监控")
            self.start_btn.setStyleSheet(
                """
                QPushButton { background-color: #e74c3c; color: white; border: none;
                    padding: 8px 16px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #ff6b6b; }
            """
            )

            interval = int(self.config["capture_interval"] * 1000)
            self.timer.start(interval)
            self.status_label.setText("🟢 监控中...")

        def stop_auto_capture(self):
            self.is_running = False
            self.timer.stop()
            self.start_btn.setText("▶ 开始监控")
            self.start_btn.setStyleSheet("")
            self.status_label.setText("⏸ 已停止")

        def update_cycle(self):
            try:
                self.capture.find_ggpoker_window()

                hand_img = self.capture.capture_region("my_cards")
                my_cards = self.recognizer.recognize_cards(hand_img, max_cards=2)

                comm_img = self.capture.capture_region("community_cards")
                community_cards = self.recognizer.recognize_cards(comm_img, max_cards=5)

                if len(my_cards) == 2:
                    num_opp = self.opponent_spin.value()
                    result = self.calculator.calculate_odds(
                        my_cards, community_cards, num_opp
                    )
                    self.update_display(my_cards, community_cards, result)
                    self.status_label.setText(
                        f"🟢 识别: {my_cards} | {community_cards}"
                    )
                else:
                    self.status_label.setText(
                        f"🔍 未识别到手牌 (检测到{len(my_cards)}张)"
                    )
            except Exception as e:
                self.status_label.setText(f"⚠️ {str(e)[:50]}")

        def calibrate_regions(self):
            self.status_label.setText("🎯 截取GGPoker窗口...")
            try:
                import cv2

                full_screen = self.capture.capture_full_window()
                if full_screen is not None:
                    cv2.imshow(
                        "GGPoker Window - Press any key to close", full_screen
                    )
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()
                    self.status_label.setText("✅ 校准窗口已关闭")
            except Exception as e:
                self.status_label.setText(f"❌ {str(e)[:30]}")

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()

        def mouseMoveEvent(self, event: QMouseEvent):
            if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, event: QMouseEvent):
            self._drag_pos = None
