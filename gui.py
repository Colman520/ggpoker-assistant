import sys
import os

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
        QCheckBox,
        QDialog,
        QScrollArea,
    )
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QFont, QMouseEvent, QImage, QPixmap

    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    print("⚠️ PyQt6 未安装: pip install PyQt6")

from config import Config
from screen_capture import ScreenCapture
from card_recognition import CardRecognizer, ManualCardInput
from odds_calculator import OddsCalculator


if HAS_PYQT:

    class ImageDialog(QDialog):
        """用 PyQt6 显示截图的对话框，替代 OpenCV 弹窗"""

        def __init__(self, title, cv_img, parent=None):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog
            )

            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)

            # OpenCV BGR → Qt RGB
            import cv2
            import numpy as np

            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qt_img)

            # 缩放到合适大小（最大 900x700）
            max_w, max_h = 900, 700
            if w > max_w or h > max_h:
                pixmap = pixmap.scaled(
                    max_w, max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            img_label = QLabel()
            img_label.setPixmap(pixmap)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            scroll = QScrollArea()
            scroll.setWidget(img_label)
            scroll.setWidgetResizable(True)
            layout.addWidget(scroll)

            # 关闭按钮
            close_btn = QPushButton("关闭")
            close_btn.setStyleSheet(
                "QPushButton { background: #e74c3c; color: white; padding: 8px; "
                "font-size: 14px; font-weight: bold; border: none; }"
                "QPushButton:hover { background: #ff6b6b; }"
            )
            close_btn.clicked.connect(self.close)
            layout.addWidget(close_btn)

            self.setLayout(layout)

            # 自动调整窗口大小
            display_w = min(w + 20, max_w + 20)
            display_h = min(h + 60, max_h + 60)
            self.resize(display_w, display_h)

    class CalcWorker(QThread):
        """后台计算线程，避免UI卡死"""
        finished = pyqtSignal(list, list, dict)
        error = pyqtSignal(str)

        def __init__(self, calculator, my_cards, community_cards, num_opp):
            super().__init__()
            self.calculator = calculator
            self.my_cards = my_cards
            self.community_cards = community_cards
            self.num_opp = num_opp

        def run(self):
            try:
                result = self.calculator.calculate_odds(
                    self.my_cards, self.community_cards, self.num_opp
                )
                self.finished.emit(self.my_cards, self.community_cards, result)
            except Exception as e:
                self.error.emit(str(e))

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
            self._last_recognized = None
            self._calc_worker = None
            self._image_dialog = None  # 保持引用防止被回收

            self.init_ui()

        def init_ui(self):
            gui_config = self.config["gui"]

            self.setWindowTitle("🃏 GGPoker Assistant")
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
            )
            self.setWindowOpacity(max(gui_config["opacity"], 0.95))
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
                QPushButton:disabled { background-color: #555; color: #888; }
                QLineEdit {
                    background-color: #16213e;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 6px;
                    color: #eee;
                    font-size: 14px;
                }
                QSpinBox {
                    background-color: #16213e;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #eee;
                    font-size: 14px;
                    min-width: 50px;
                    min-height: 28px;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background-color: #2a2a4a;
                    border: 1px solid #444;
                    width: 20px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background-color: #4ecca3;
                }
                QSpinBox::up-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-bottom: 5px solid #ccc;
                    width: 0; height: 0;
                }
                QSpinBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ccc;
                    width: 0; height: 0;
                }
                QLabel { color: #ccc; }
                QCheckBox { color: #ccc; font-size: 11px; }
                QCheckBox::indicator {
                    width: 14px; height: 14px;
                    border: 1px solid #555; border-radius: 3px;
                    background: #16213e;
                }
                QCheckBox::indicator:checked { background: #4ecca3; }
            """
            )

            main_layout = QVBoxLayout()
            main_layout.setSpacing(6)
            main_layout.setContentsMargins(10, 8, 10, 8)

            # ===== 标题栏 =====
            title_bar = QHBoxLayout()
            title_label = QLabel("🃏 GGPoker Assistant")
            title_label.setStyleSheet(
                "color: #4ecca3; font-size: 18px; font-weight: bold;"
            )
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

            # ===== 手动输入区域 =====
            input_group = QGroupBox("📝 手动输入")
            input_layout = QVBoxLayout()

            hand_row = QHBoxLayout()
            hand_label = QLabel("手牌:")
            hand_label.setFixedWidth(55)
            hand_row.addWidget(hand_label)
            self.hand_input = QLineEdit()
            self.hand_input.setPlaceholderText("如: Ah Kh")
            self.hand_input.returnPressed.connect(self.manual_calculate)
            hand_row.addWidget(self.hand_input)
            input_layout.addLayout(hand_row)

            comm_row = QHBoxLayout()
            comm_label = QLabel("公共牌:")
            comm_label.setFixedWidth(55)
            comm_row.addWidget(comm_label)
            self.community_input = QLineEdit()
            self.community_input.setPlaceholderText("如: Qh Jh 3c")
            self.community_input.returnPressed.connect(self.manual_calculate)
            comm_row.addWidget(self.community_input)
            input_layout.addLayout(comm_row)

            opp_row = QHBoxLayout()
            opp_label = QLabel("对手数:")
            opp_label.setFixedWidth(55)
            opp_row.addWidget(opp_label)
            self.opponent_spin = QSpinBox()
            self.opponent_spin.setRange(1, 9)
            self.opponent_spin.setValue(self.config["default_opponents"])
            self.opponent_spin.setFixedSize(80, 32)
            opp_row.addWidget(self.opponent_spin)
            opp_row.addStretch()
            input_layout.addLayout(opp_row)

            calc_btn = QPushButton("📊 计算胜率")
            calc_btn.clicked.connect(self.manual_calculate)
            input_layout.addWidget(calc_btn)

            input_group.setLayout(input_layout)
            main_layout.addWidget(input_group)

            # ===== 结果显示区域 =====
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

            # ===== 自动识别控制 =====
            auto_group = QGroupBox("🤖 自动识别")
            auto_layout = QVBoxLayout()

            btn_row1 = QHBoxLayout()
            self.start_btn = QPushButton("▶ 开始监控")
            self.start_btn.clicked.connect(self.toggle_auto_capture)
            btn_row1.addWidget(self.start_btn)

            self.calibrate_btn = QPushButton("🎯 校准")
            self.calibrate_btn.clicked.connect(self.calibrate_regions)
            btn_row1.addWidget(self.calibrate_btn)
            auto_layout.addLayout(btn_row1)

            btn_row2 = QHBoxLayout()
            self.debug_btn = QPushButton("📸 调试截图")
            self.debug_btn.clicked.connect(self.take_debug_screenshot)
            btn_row2.addWidget(self.debug_btn)

            self.template_btn = QPushButton("📋 生成模板")
            self.template_btn.clicked.connect(self.open_template_generator)
            btn_row2.addWidget(self.template_btn)
            auto_layout.addLayout(btn_row2)

            self.debug_checkbox = QCheckBox("调试模式（保存识别过程图片）")
            self.debug_checkbox.setChecked(False)
            self.debug_checkbox.stateChanged.connect(self._toggle_debug_mode)
            auto_layout.addWidget(self.debug_checkbox)

            self.status_label = QLabel("状态: 就绪")
            self.status_label.setStyleSheet("color: #888; font-size: 11px;")
            self.status_label.setWordWrap(True)
            self.status_label.setMaximumHeight(48)
            auto_layout.addWidget(self.status_label)

            auto_group.setLayout(auto_layout)
            main_layout.addWidget(auto_group)

            main_layout.addStretch()
            self.setLayout(main_layout)

            pos = gui_config["position"]
            self.move(pos[0], pos[1])

        # ===== 用 PyQt6 对话框显示图片 =====

        def _show_image(self, title, cv_img):
            """用 PyQt6 对话框显示图片，替代 OpenCV 弹窗"""
            if cv_img is None:
                self.status_label.setText("❌ 无图片可显示")
                return

            # 关闭之前的对话框
            if self._image_dialog is not None:
                try:
                    self._image_dialog.close()
                except Exception:
                    pass

            self._image_dialog = ImageDialog(title, cv_img, parent=None)
            # 居中到屏幕
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.geometry()
                dialog_geo = self._image_dialog.geometry()
                x = (screen_geo.width() - dialog_geo.width()) // 2
                y = (screen_geo.height() - dialog_geo.height()) // 2
                self._image_dialog.move(x, y)

            self._image_dialog.show()

        # ===== 手动计算 =====

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

        # ===== 结果显示 =====

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

        # ===== 自动监控 =====

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
            self._last_recognized = None
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
            self._last_recognized = None
            self.start_btn.setText("▶ 开始监控")
            self.start_btn.setStyleSheet("")
            self.status_label.setText("⏸ 已停止")

        def update_cycle(self):
            """自动识别循环"""
            try:
                self.capture.find_ggpoker_window()

                hand_img = self.capture.capture_region("my_cards")
                my_cards = self.recognizer.recognize_cards(hand_img, max_cards=2)

                comm_img = self.capture.capture_region("community_cards")
                community_cards = self.recognizer.recognize_cards(comm_img, max_cards=5)

                if len(my_cards) == 2:
                    current_key = tuple(my_cards) + tuple(community_cards)
                    if current_key == self._last_recognized:
                        return
                    self._last_recognized = current_key

                    num_opp = self.opponent_spin.value()

                    if self._calc_worker and self._calc_worker.isRunning():
                        return

                    self._calc_worker = CalcWorker(
                        self.calculator, my_cards, community_cards, num_opp
                    )
                    self._calc_worker.finished.connect(self._on_calc_finished)
                    self._calc_worker.error.connect(self._on_calc_error)
                    self._calc_worker.start()

                    self.status_label.setText(
                        f"🔄 识别: {my_cards} | {community_cards} → 计算中..."
                    )
                else:
                    self._last_recognized = None
                    self.status_label.setText(
                        f"🔍 未识别到手牌 (检测到{len(my_cards)}张)"
                    )
            except Exception as e:
                self.status_label.setText(f"⚠️ {str(e)[:50]}")

        def _on_calc_finished(self, my_cards, community_cards, result):
            self.update_display(my_cards, community_cards, result)
            self.status_label.setText(
                f"🟢 识别: {my_cards} | {community_cards}"
            )

        def _on_calc_error(self, error_msg):
            self.status_label.setText(f"❌ 计算错误: {error_msg[:40]}")

        # ===== 调试功能 =====

        def _toggle_debug_mode(self, state):
            enabled = state == 2
            self.capture.debug_mode = enabled
            self.recognizer.debug_mode = enabled
            if enabled:
                self.status_label.setText("🔍 调试模式已开启，截图保存到 screenshots/debug/")
            else:
                self.status_label.setText("调试模式已关闭")

        def take_debug_screenshot(self):
            """保存调试截图并用 PyQt6 对话框显示"""
            try:
                if not self.capture.window_rect:
                    if not self.capture.find_ggpoker_window():
                        self.status_label.setText("❌ 未找到GGPoker窗口")
                        return

                has_debug = hasattr(self.capture, 'save_debug_screenshot')
                has_regions = hasattr(self.capture, 'capture_full_with_regions')

                # 保存截图文件
                if has_debug:
                    saved_path = self.capture.save_debug_screenshot("manual")
                    if not saved_path:
                        self.status_label.setText("❌ 截图失败")
                        return
                else:
                    full_img = self.capture.capture_full_window()
                    if full_img is None:
                        self.status_label.setText("❌ 截图失败")
                        return

                    import cv2
                    from datetime import datetime

                    debug_dir = os.path.join("screenshots", "debug")
                    os.makedirs(debug_dir, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    saved_path = os.path.join(debug_dir, f"manual_{ts}.png")
                    cv2.imwrite(saved_path, full_img)

                self.status_label.setText(f"📸 已保存: {saved_path}")

                # 用 PyQt6 对话框显示
                if has_regions:
                    img = self.capture.capture_full_with_regions()
                else:
                    img = self.capture.capture_full_window()

                if img is not None:
                    self._show_image("📸 调试截图", img)

            except Exception as e:
                self.status_label.setText(f"❌ {str(e)[:40]}")

        def open_template_generator(self):
            """打开模板生成器"""
            try:
                if not self.capture.window_rect:
                    if not self.capture.find_ggpoker_window():
                        self.status_label.setText("❌ 未找到GGPoker窗口")
                        return

                self.status_label.setText("📋 模板生成中...")
                QApplication.processEvents()

                # 先截图显示给用户看
                img = self.capture.capture_full_window()
                if img is None:
                    self.status_label.setText("❌ 截取窗口失败")
                    return

                # 显示截图
                self._show_image("📋 GGPoker 窗口截图", img)

                try:
                    from template_generator import TemplateGenerator

                    gen = TemplateGenerator()
                    gen.extract_from_screenshot(img)

                    # 重新加载模板
                    self.recognizer = CardRecognizer(self.config)
                    n_ranks = len(self.recognizer.rank_templates) if hasattr(self.recognizer, 'rank_templates') else 0
                    n_suits = len(self.recognizer.suit_templates) if hasattr(self.recognizer, 'suit_templates') else 0
                    n_total = n_ranks + n_suits
                    self.status_label.setText(f"✅ 模板已更新，共加载 {n_total} 个模板")
                except ImportError:
                    self.status_label.setText("❌ 未找到 template_generator.py")
            except Exception as e:
                self.status_label.setText(f"❌ {str(e)[:40]}")

        # ===== 区域校准 =====

        def calibrate_regions(self):
            """交互式区域校准"""
            try:
                if not self.capture.window_rect:
                    if not self.capture.find_ggpoker_window():
                        self.status_label.setText("❌ 未找到GGPoker窗口")
                        return

                self.status_label.setText("🎯 校准中...")
                QApplication.processEvents()

                try:
                    from calibration import RegionCalibrator

                    cal = RegionCalibrator(self.config)
                    cal.capture = self.capture
                    cal.img = self.capture.capture_full_window()

                    if cal.img is None:
                        self.status_label.setText("❌ 截取窗口失败")
                        return

                    cal.img_h, cal.img_w = cal.img.shape[:2]

                    for name in RegionCalibrator.REGION_NAMES:
                        cal._calibrate_one_region(name)

                    cal._save_regions()

                    self.config.load()
                    self.status_label.setText(
                        f"✅ 校准完成，已保存 {len(cal.regions)} 个区域"
                    )
                except ImportError:
                    # 降级: 用 PyQt6 对话框显示区域预览
                    has_regions = hasattr(self.capture, 'capture_full_with_regions')
                    if has_regions:
                        full_screen = self.capture.capture_full_with_regions()
                    else:
                        full_screen = self.capture.capture_full_window()

                    if full_screen is not None:
                        self._show_image("🎯 GGPoker 区域预览", full_screen)
                        self.status_label.setText(
                            "ℹ️ 已显示区域预览。安装 calibration.py 可交互校准"
                        )
            except Exception as e:
                self.status_label.setText(f"❌ {str(e)[:40]}")

        # ===== 窗口拖拽 =====

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()

        def mouseMoveEvent(self, event: QMouseEvent):
            if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_pos)

        def mouseReleaseEvent(self, event: QMouseEvent):
            self._drag_pos = None

        def closeEvent(self, event):
            """关闭时保存窗口位置"""
            pos = self.pos()
            self.config["gui"]["position"] = [pos.x(), pos.y()]
            try:
                self.config.save()
            except Exception:
                pass

            if self.is_running:
                self.stop_auto_capture()

            # 关闭图片对话框
            if self._image_dialog is not None:
                try:
                    self._image_dialog.close()
                except Exception:
                    pass

            event.accept()