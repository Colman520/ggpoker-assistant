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
        QGridLayout,
        QComboBox,
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


    class CardSelectorDialog(QDialog):
        """扑克牌可视化选择器 - 精美版"""
        def __init__(self, title, max_cards, current_selection, disabled_cards, parent=None):
            super().__init__(parent)
            self.setWindowTitle(title)
            self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
            self.max_cards = max_cards
            self.selected_cards = list(current_selection)
            self.disabled_cards = disabled_cards

            layout = QVBoxLayout()
            layout.setContentsMargins(20, 20, 20, 20)  # 增加外边距，让界面透气
            layout.setSpacing(15)

            # 顶部提示文字
            self.info_label = QLabel(f"请选择 {max_cards} 张牌 ({len(self.selected_cards)}/{max_cards})")
            self.info_label.setStyleSheet("color: #4ecca3; font-weight: bold; font-size: 16px; letter-spacing: 1px;")
            layout.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)

            # 扑克牌网格
            grid = QGridLayout()
            grid.setSpacing(8)  # 卡片之间的间距
            
            ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]
            # 优化颜色：黑桃/梅花用亮白色，红心/方块用鲜红色
            suits = [
                ("s", "♠", "#ffffff"), 
                ("h", "♥", "#ff4757"), 
                ("c", "♣", "#ffffff"),
                ("d", "♦", "#ff4757")
            ]

            self.buttons = {}
            for row, (suit_code, suit_sym, base_color) in enumerate(suits):
                for col, rank in enumerate(ranks):
                    card_str = f"{rank}{suit_code}"
                    display_rank = "10" if rank == "T" else rank
                    
                    # 使用 \n 换行，把点数和花色分开，呈现真实扑克牌的视觉效果
                    btn = QPushButton(f"{display_rank}\n{suit_sym}")
                    btn.setFixedSize(46, 68)  # 调整为扑克牌的长宽比
                    btn.setFont(QFont("Arial", 13, QFont.Weight.Bold))
                    
                    if card_str in self.disabled_cards:
                        btn.setEnabled(False)
                    else:
                        btn.clicked.connect(lambda checked, c=card_str: self.toggle_card(c))
                        
                    grid.addWidget(btn, row, col)
                    self.buttons[card_str] = {"btn": btn, "color": base_color}

            layout.addLayout(grid)

            # 底部按钮区域 (居中且固定大小)
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()  # 左侧弹簧
            
            clear_btn = QPushButton("清空")
            clear_btn.setFixedSize(120, 36)
            clear_btn.setStyleSheet("""
                QPushButton { background-color: #e74c3c; color: white; border-radius: 18px; font-weight: bold; font-size: 14px; }
                QPushButton:hover { background-color: #ff6b6b; }
            """)
            clear_btn.clicked.connect(self.clear_selection)
            
            confirm_btn = QPushButton("确定")
            confirm_btn.setFixedSize(120, 36)
            confirm_btn.setStyleSheet("""
                QPushButton { background-color: #4ecca3; color: #1a1a2e; border-radius: 18px; font-weight: bold; font-size: 14px; }
                QPushButton:hover { background-color: #7efcce; }
            """)
            confirm_btn.clicked.connect(self.accept)
            
            btn_layout.addWidget(clear_btn)
            btn_layout.addSpacing(20) # 两个按钮中间的间距
            btn_layout.addWidget(confirm_btn)
            btn_layout.addStretch()  # 右侧弹簧
            
            layout.addLayout(btn_layout)

            self.setLayout(layout)
            self.setStyleSheet("QDialog { background-color: #1a1a2e; }")
            self.update_buttons()

        def toggle_card(self, card_str):
            if card_str in self.selected_cards:
                self.selected_cards.remove(card_str)
            else:
                if len(self.selected_cards) >= self.max_cards:
                    return
                self.selected_cards.append(card_str)
            self.info_label.setText(f"请选择 {self.max_cards} 张牌 ({len(self.selected_cards)}/{self.max_cards})")
            self.update_buttons()

        def clear_selection(self):
            self.selected_cards.clear()
            self.info_label.setText(f"请选择 {self.max_cards} 张牌 (0/{self.max_cards})")
            self.update_buttons()

        def update_buttons(self):
            """统一管理按钮的样式"""
            for card_str, data in self.buttons.items():
                btn = data["btn"]
                if not btn.isEnabled():
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #161622;
                            color: #333333;
                            border: 1px solid #222;
                            border-radius: 6px;
                        }
                    """)
                    continue
                    
                if card_str in self.selected_cards:
                    # 选中状态：主色调背景，深色文字，发光边框
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #4ecca3;
                            color: #1a1a2e;
                            border: 2px solid #ffffff;
                            border-radius: 6px;
                            font-weight: bold;
                        }
                    """)
                else:
                    # 正常状态：深色背景，对应花色文字，支持鼠标悬浮效果
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: #26263a;
                            color: {data['color']};
                            border: 1px solid #3f3f5a;
                            border-radius: 6px;
                        }}
                        QPushButton:hover {{
                            background-color: #32324a;
                            border: 1px solid #4ecca3;
                        }}
                    """)

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
            self._table_size = 9
            self._position_index = 0
            self._active_players = 9

            self.init_ui()

        def init_ui(self):
            gui_config = self.config["gui"]
            self._table_size = int(gui_config.get("table_size", 9))
            if self._table_size not in (6, 9):
                self._table_size = 9
            self._position_index = int(gui_config.get("position_index", 0))
            self._active_players = int(gui_config.get("active_players", self._table_size))

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
                    background-color: #0f1220;
                    color: #e8ecff;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }
                QGroupBox {
                    background-color: #141a2d;
                    border: 1px solid #2a3558;
                    border-radius: 10px;
                    margin-top: 12px;
                    padding: 14px 12px 12px 12px;
                    font-weight: 600;
                    color: #74e7ca;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 6px;
                    color: #7ef2d4;
                }
                QPushButton {
                    background-color: #43d3ad;
                    color: #102136;
                    border: 1px solid #57e9c1;
                    padding: 9px 16px;
                    border-radius: 8px;
                    font-weight: 700;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #5be8c3;
                    border-color: #7ef8d7;
                }
                QPushButton:pressed {
                    background-color: #2cb48f;
                    border-color: #3fc8a1;
                }
                QPushButton:disabled {
                    background-color: #2d3550;
                    border-color: #3b4568;
                    color: #7e89af;
                }
                QLineEdit {
                    background-color: #1a2442;
                    border: 1px solid #344166;
                    border-radius: 8px;
                    padding: 8px 10px;
                    color: #ecf1ff;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #63e8c5;
                }
                QComboBox {
                    background-color: #1a2442;
                    border: 1px solid #344166;
                    border-radius: 8px;
                    padding: 4px 10px;
                    color: #ecf1ff;
                    min-height: 28px;
                }
                QComboBox:hover {
                    border: 1px solid #63e8c5;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QSpinBox {
                    background-color: #1a2442;
                    border: 1px solid #344166;
                    border-radius: 8px;
                    padding: 4px 8px;
                    color: #ecf1ff;
                    font-size: 14px;
                    min-width: 50px;
                    min-height: 28px;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background-color: #263153;
                    border: 1px solid #3a4770;
                    width: 20px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background-color: #57dcb9;
                }
                QSpinBox::up-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-bottom: 5px solid #e6f2ff;
                    width: 0; height: 0;
                }
                QSpinBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #e6f2ff;
                    width: 0; height: 0;
                }
                QLabel { color: #d4dbf3; }
                QCheckBox { color: #bac5e8; font-size: 11px; }
                QCheckBox::indicator {
                    width: 14px; height: 14px;
                    border: 1px solid #4f5d85; border-radius: 4px;
                    background: #1a2442;
                }
                QCheckBox::indicator:checked { background: #4fd9b4; }
            """
            )

            main_layout = QVBoxLayout()
            main_layout.setSpacing(10)
            main_layout.setContentsMargins(14, 12, 14, 12)

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
                QPushButton { background: transparent; color: #8fa0d2; font-size: 16px; padding: 0; border: none; }
                QPushButton:hover { color: #ff6c7c; background: #1f2742; border-radius: 6px; }
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

            self._manual_my_cards = []         # 保存手动选择的手牌
            self._manual_comm_cards = []       # 保存手动选择的公共牌

            hand_row = QHBoxLayout()
            hand_label = QLabel("手牌:")
            hand_label.setFixedWidth(55)
            hand_row.addWidget(hand_label)
            self.hand_btn = QPushButton("点击选择手牌")
            self.hand_btn.setStyleSheet(
                "background-color: #1a2442; color: #ecf1ff; border: 1px solid #344166; "
                "text-align: left; padding-left: 12px; border-radius: 8px;"
            )
            self.hand_btn.clicked.connect(self.open_hand_selector)
            hand_row.addWidget(self.hand_btn)
            input_layout.addLayout(hand_row)

            comm_row = QHBoxLayout()
            comm_label = QLabel("公共牌:")
            comm_label.setFixedWidth(55)
            comm_row.addWidget(comm_label)
            self.community_btn = QPushButton("点击选择公共牌")
            self.community_btn.setStyleSheet(
                "background-color: #1a2442; color: #ecf1ff; border: 1px solid #344166; "
                "text-align: left; padding-left: 12px; border-radius: 8px;"
            )
            self.community_btn.clicked.connect(self.open_community_selector)
            comm_row.addWidget(self.community_btn)
            input_layout.addLayout(comm_row)

            table_row = QHBoxLayout()
            table_label = QLabel("人数:")
            table_label.setFixedWidth(55)
            table_row.addWidget(table_label)
            self.table_size_combo = QComboBox()
            self.table_size_combo.addItems(["6人桌", "9人桌"])
            self.table_size_combo.setFixedSize(120, 32)
            self.table_size_combo.setCurrentIndex(0 if self._table_size == 6 else 1)
            self.table_size_combo.currentTextChanged.connect(self._on_table_size_changed)
            table_row.addWidget(self.table_size_combo)
            table_row.addStretch()
            input_layout.addLayout(table_row)

            pos_row = QHBoxLayout()
            pos_label = QLabel("位置:")
            pos_label.setFixedWidth(55)
            pos_row.addWidget(pos_label)
            self.position_combo = QComboBox()
            self.position_combo.setFixedSize(180, 32)
            self._refresh_position_options()
            self.position_combo.currentIndexChanged.connect(self._on_position_changed)
            pos_row.addWidget(self.position_combo)
            pos_row.addStretch()
            input_layout.addLayout(pos_row)

            active_row = QHBoxLayout()
            active_label = QLabel("在局:")
            active_label.setFixedWidth(55)
            active_row.addWidget(active_label)
            self.active_players_spin = QSpinBox()
            self.active_players_spin.setFixedSize(90, 32)
            self.active_players_spin.valueChanged.connect(self._on_active_players_changed)
            active_row.addWidget(self.active_players_spin)
            active_row.addWidget(QLabel("人"))
            active_row.addStretch()
            input_layout.addLayout(active_row)
            self._sync_active_players_limit()

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
                background-color: #1a2442; border-radius: 8px; color: #e9efff;
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

        def _format_cards_for_btn(self, cards):
            if not cards:
                return ""
            suit_symbols = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
            res = []
            for c in cards:
                rank = "10" if c[0] == "T" else c[0]
                res.append(f"{rank}{suit_symbols.get(c[1], c[1])}")
            return " ".join(res)

        def open_hand_selector(self):
            dialog = CardSelectorDialog("选择手牌 (2张)", 2, self._manual_my_cards, self._manual_comm_cards, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._manual_my_cards = dialog.selected_cards
                text = self._format_cards_for_btn(self._manual_my_cards)
                self.hand_btn.setText(text if text else "点击选择手牌")

        def open_community_selector(self):
            dialog = CardSelectorDialog("选择公共牌 (最多5张)", 5, self._manual_comm_cards, self._manual_my_cards, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._manual_comm_cards = dialog.selected_cards
                text = self._format_cards_for_btn(self._manual_comm_cards)
                self.community_btn.setText(text if text else "点击选择公共牌")

        def manual_calculate(self):
            """手动计算胜率"""
            num_opp = self._get_num_opponents()
            my_cards = self._manual_my_cards
            community_cards = self._manual_comm_cards

            if len(my_cards) != 2:
                self.status_label.setText("⚠️ 请先选择 2 张手牌")
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

            self.cards_label.setText(
                f"手牌: {hand_str}  |  公共牌: {comm_str}  |  {self._table_size}人桌 | {self._get_position_name()} | 在局{self._active_players}人"
            )
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

                    num_opp = self._get_num_opponents()

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

        def _on_table_size_changed(self, text):
            self._table_size = 6 if text.startswith("6") else 9
            self._refresh_position_options()
            self._sync_active_players_limit()
            self.status_label.setText(
                f"ℹ️ 已切换为{self._table_size}人桌（对手数: {self._get_num_opponents()}）"
            )

        def _on_position_changed(self, index):
            if index >= 0:
                self._position_index = index

        def _on_active_players_changed(self, value):
            self._active_players = int(value)

        def _sync_active_players_limit(self):
            self._active_players = min(max(self._active_players, 2), self._table_size)
            self.active_players_spin.setRange(2, self._table_size)
            self.active_players_spin.setValue(self._active_players)

        def _refresh_position_options(self):
            current_names = self._position_names()
            self.position_combo.blockSignals(True)
            self.position_combo.clear()
            self.position_combo.addItems(current_names)
            self._position_index = min(max(self._position_index, 0), len(current_names) - 1)
            self.position_combo.setCurrentIndex(self._position_index)
            self.position_combo.blockSignals(False)

        def _position_names(self):
            if self._table_size == 6:
                return ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
            return ["UTG", "UTG+1", "UTG+2", "LJ", "HJ", "CO", "BTN", "SB", "BB"]

        def _get_position_name(self):
            names = self._position_names()
            return names[self._position_index]

        def _get_num_opponents(self):
            return max(1, self._active_players - 1)

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
            self.config["gui"]["table_size"] = self._table_size
            self.config["gui"]["position_index"] = self._position_index
            self.config["gui"]["active_players"] = self._active_players
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