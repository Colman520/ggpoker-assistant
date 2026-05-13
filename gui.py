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
        QDoubleSpinBox,
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
from main import create_odds_calculator


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

        def __init__(
            self,
            calculator,
            my_cards,
            community_cards,
            num_opp,
            table_size,
            position,
            remaining_opponents,
            pot_size,
            call_amount,
            effective_stack_bb,
            opponent_action,
        ):
            super().__init__()
            self.calculator = calculator
            self.my_cards = my_cards
            self.community_cards = community_cards
            self.num_opp = num_opp
            
            self.table_size = table_size
            self.position = position
            self.remaining_opponents = remaining_opponents
            self.pot_size = pot_size
            self.call_amount = call_amount
            self.effective_stack_bb = effective_stack_bb
            self.opponent_action = opponent_action

        def run(self):
            try:
                result = self.calculator.calculate_odds(
                    self.my_cards, self.community_cards, self.num_opp,
                    table_size=self.table_size, 
                    position=self.position, 
                    remaining_opponents=self.remaining_opponents,
                    pot_size=self.pot_size,
                    call_amount=self.call_amount,
                    effective_stack_bb=self.effective_stack_bb,
                    opponent_action=self.opponent_action,
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
            self.calculator = create_odds_calculator(config)

            self.is_running = False
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_cycle)

            self._drag_pos = None
            self._last_recognized = None
            self._calc_worker = None
            self._image_dialog = None  # 保持引用防止被回收
            self._table_size = 9
            self._position_index = 0
            self._remaining_opponents = 8
            self._pot_size_bb = 0.0
            self._call_amount_bb = 0.0

            self.init_ui()

        def init_ui(self):
            gui_config = self.config["gui"]
            self._table_size = int(gui_config.get("table_size", 9))
            if self._table_size not in (6, 9):
                self._table_size = 9
            self._position_index = int(gui_config.get("position_index", 0))
            self._effective_stack_bb = float(gui_config.get("effective_stack_bb", 100.0))
            self._pot_size_bb = float(gui_config.get("pot_size_bb", 0.0))
            self._call_amount_bb = float(gui_config.get("call_amount_bb", 0.0))
            if "remaining_opponents" in gui_config:
                self._remaining_opponents = int(gui_config.get("remaining_opponents", self._table_size - 1))
            else:
                # 兼容旧配置 active_players(含自己)
                legacy_active = int(gui_config.get("active_players", self._table_size))
                self._remaining_opponents = max(1, legacy_active - 1)

            self.setWindowTitle("🃏 GGPoker Assistant")
            self.setWindowFlags(
                Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
            )
            self.setWindowOpacity(max(gui_config["opacity"], 0.95))
            panel_width = max(520, min(int(gui_config["width"]), 640))
            panel_height = max(620, min(int(gui_config["height"]), 860))
            self.setFixedWidth(panel_width)
            self.setMinimumHeight(panel_height)

            self.setStyleSheet(
                """
                QWidget {
                    background-color: #11131a;
                    color: #eef2ff;
                    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                }
                QGroupBox {
                    background-color: #171b24;
                    border: 1px solid #272d3b;
                    border-radius: 14px;
                    margin-top: 12px;
                    padding: 16px 14px 14px 14px;
                    font-weight: 700;
                    color: #cfd7ff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 14px;
                    padding: 0 6px;
                    color: #a7b4ff;
                }
                QPushButton {
                    background-color: #6d7cff;
                    color: #f8f9ff;
                    border: 1px solid #7f8cff;
                    padding: 9px 16px;
                    border-radius: 10px;
                    font-weight: 700;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #7d8aff;
                    border-color: #9aa5ff;
                }
                QPushButton:pressed {
                    background-color: #5b69e6;
                    border-color: #7884ff;
                }
                QPushButton:disabled {
                    background-color: #2a3142;
                    border-color: #32394c;
                    color: #7f879e;
                }
                QLineEdit {
                    background-color: #202532;
                    border: 1px solid #303748;
                    border-radius: 10px;
                    padding: 8px 10px;
                    color: #ecf1ff;
                    font-size: 14px;
                }
                QLineEdit:focus {
                    border: 1px solid #8896ff;
                }
                QComboBox, QSpinBox, QDoubleSpinBox {
                    background-color: #202532;
                    border: 1px solid #303748;
                    border-radius: 10px;
                    padding: 4px 10px;
                    color: #ecf1ff;
                    min-height: 30px;
                    font-size: 14px;
                }
                QComboBox {
                    padding-right: 10px;
                }
                QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
                    border: 1px solid #8896ff;
                }
                QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 1px solid #98a5ff;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 24px;
                }
                QSpinBox::up-button, QSpinBox::down-button,
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                    background-color: #272e3c;
                    border: 1px solid #394156;
                    width: 20px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover,
                QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                    background-color: #6c78d9;
                }
                QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-bottom: 5px solid #edf1ff;
                    width: 0; height: 0;
                }
                QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #edf1ff;
                    width: 0; height: 0;
                }
                QLabel { color: #d7dcef; }
                QCheckBox { color: #bac5e8; font-size: 11px; }
                QCheckBox::indicator {
                    width: 14px; height: 14px;
                    border: 1px solid #4f5d85; border-radius: 4px;
                    background: #202532;
                }
                QCheckBox::indicator:checked { background: #7d8aff; }
            """
            )

            main_layout = QVBoxLayout()
            main_layout.setSpacing(10)
            main_layout.setContentsMargins(14, 12, 14, 12)

            # ===== 标题栏 =====
            title_bar = QHBoxLayout()
            title_label = QLabel("GGPoker Assistant")
            title_label.setStyleSheet(
                "color: #f5f7ff; font-size: 20px; font-weight: 700; letter-spacing: 0.4px;"
            )
            title_bar.addWidget(title_label)
            title_bar.addStretch()

            close_btn = QPushButton("✕")
            close_btn.setFixedSize(24, 24)
            close_btn.setStyleSheet(
                """
                QPushButton { background: transparent; color: #98a0ba; font-size: 16px; padding: 0; border: none; }
                QPushButton:hover { color: #ffffff; background: #282e3a; border-radius: 6px; }
            """
            )
            close_btn.clicked.connect(self.close)
            title_bar.addWidget(close_btn)
            main_layout.addLayout(title_bar)

            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setStyleSheet("color: #252a35;")
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
                "background-color: #202532; color: #f4f6ff; border: 1px solid #303748; "
                "text-align: left; padding-left: 12px; border-radius: 10px; font-weight: 600;"
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
                "background-color: #202532; color: #f4f6ff; border: 1px solid #303748; "
                "text-align: left; padding-left: 12px; border-radius: 10px; font-weight: 600;"
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
            active_label = QLabel("剩余:")
            active_label.setFixedWidth(55)
            active_row.addWidget(active_label)
            self.remaining_opponents_spin = QSpinBox()
            self.remaining_opponents_spin.setFixedSize(90, 32)
            self.remaining_opponents_spin.valueChanged.connect(self._on_remaining_opponents_changed)
            active_row.addWidget(self.remaining_opponents_spin)
            active_row.addWidget(QLabel("人"))
            active_row.addStretch()
            input_layout.addLayout(active_row)
            self._sync_remaining_opponents_limit()
            
            action_row = QHBoxLayout()
            action_label = QLabel("对手动作:")
            action_label.setFixedWidth(55)
            action_row.addWidget(action_label)
            self.opponent_action_combo = QComboBox()
            self.opponent_action_combo.addItems(["Limp / Check", "Open Raise", "Call Raise", "3-Bet", "4-Bet+"])
            self.opponent_action_combo.setFixedSize(120, 32)
            self.opponent_action_combo.setCurrentIndex(1)  # 默认 Open Raise
            action_row.addWidget(self.opponent_action_combo)
            action_row.addStretch()
            input_layout.addLayout(action_row)

            pot_row = QHBoxLayout()
            pot_label = QLabel("底池:")
            pot_label.setFixedWidth(55)
            pot_row.addWidget(pot_label)
            self.pot_spin = QDoubleSpinBox()
            self.pot_spin.setFixedSize(110, 32)
            self.pot_spin.setRange(0.0, 9999.0)
            self.pot_spin.setDecimals(1)
            self.pot_spin.setSingleStep(0.5)
            self.pot_spin.setSuffix(" BB")
            self.pot_spin.setValue(max(0.0, self._pot_size_bb))
            pot_row.addWidget(self.pot_spin)
            call_label = QLabel("跟注:")
            call_label.setFixedWidth(45)
            pot_row.addWidget(call_label)
            self.call_spin = QDoubleSpinBox()
            self.call_spin.setFixedSize(110, 32)
            self.call_spin.setRange(0.0, 9999.0)
            self.call_spin.setDecimals(1)
            self.call_spin.setSingleStep(0.5)
            self.call_spin.setSuffix(" BB")
            self.call_spin.setValue(max(0.0, self._call_amount_bb))
            pot_row.addWidget(self.call_spin)
            pot_row.addStretch()
            input_layout.addLayout(pot_row)

            spr_row = QHBoxLayout()
            spr_label = QLabel("筹码:")
            spr_label.setFixedWidth(55)
            spr_row.addWidget(spr_label)
            self.effective_stack_spin = QDoubleSpinBox()
            self.effective_stack_spin.setFixedSize(110, 32)
            self.effective_stack_spin.setRange(0.0, 9999.0)
            self.effective_stack_spin.setDecimals(1)
            self.effective_stack_spin.setSingleStep(1.0)
            self.effective_stack_spin.setValue(max(0.0, self._effective_stack_bb))
            self.effective_stack_spin.setSuffix(" BB")
            spr_row.addWidget(self.effective_stack_spin)
            spr_row.addWidget(QLabel("用于SPR"))
            spr_row.addStretch()
            input_layout.addLayout(spr_row)

            calc_btn = QPushButton("📊 计算胜率")
            calc_btn.clicked.connect(self.manual_calculate)
            
            reset_btn = QPushButton("🔄 重置")
            reset_btn.setStyleSheet(
                "background-color: #4a5568; color: #f4f6ff; border: 1px solid #5a6578; "
                "border-radius: 10px; font-weight: 600;"
            )
            reset_btn.clicked.connect(self.reset_all_inputs)

            btn_layout = QHBoxLayout()
            btn_layout.addWidget(calc_btn, 3)
            btn_layout.addWidget(reset_btn, 1)
            
            input_layout.addLayout(btn_layout)

            input_group.setLayout(input_layout)
            main_layout.addWidget(input_group)

            # ===== 结果显示区域 =====
            result_group = QGroupBox("📈 计算结果")
            result_layout = QVBoxLayout()

            self.cards_label = QLabel("手牌: -- | 公共牌: --")
            self.cards_label.setStyleSheet("font-size: 13px; color: #bcc5dc;")
            result_layout.addWidget(self.cards_label)

            self.hand_type_label = QLabel("牌型: --")
            self.hand_type_label.setStyleSheet("font-size: 13px; color: #ffcc7a;")
            result_layout.addWidget(self.hand_type_label)

            self.texture_label = QLabel("牌面结构: --")
            self.texture_label.setStyleSheet("font-size: 13px; color: #a7b4ff;")
            result_layout.addWidget(self.texture_label)

            self.win_rate_label = QLabel("胜率: --%")
            self.win_rate_label.setStyleSheet(
                "color: #7d8aff; font-size: 34px; font-weight: 800;"
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
            self.outs_label.setStyleSheet("color: #b6c0d9;")
            result_layout.addWidget(self.outs_label)

            self.pot_odds_label = QLabel("底池赔率: -- | 需求胜率: --")
            self.pot_odds_label.setStyleSheet("font-size: 12px; color: #96a6cf;")
            result_layout.addWidget(self.pot_odds_label)
            self.ev_spr_label = QLabel("EV: -- | MDF: -- | SPR: -- | 弃牌率: --")
            self.ev_spr_label.setStyleSheet("font-size: 12px; color: #8ca0d0;")
            result_layout.addWidget(self.ev_spr_label)

            self.suggestion_label = QLabel("建议: --")
            self.suggestion_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.suggestion_label.setStyleSheet(
                """
                font-size: 15px; font-weight: 700; padding: 10px 12px;
                background-color: #202532; border: 1px solid #303748;
                border-radius: 10px; color: #f3f6ff;
            """
            )
            result_layout.addWidget(self.suggestion_label)

            result_group.setLayout(result_layout)
            main_layout.addWidget(result_group)

            # --- 屏蔽自动识别模块 ---
            # auto_group = QGroupBox("自动识别")
            # auto_layout = QVBoxLayout()
            # auto_layout.setSpacing(10)

            # btn_row1 = QHBoxLayout()
            # self.start_btn = QPushButton("▶ 开始监控")
            # self.start_btn.clicked.connect(self.toggle_auto_capture)
            # btn_row1.addWidget(self.start_btn)
            # self.calibrate_btn = QPushButton("🎯 校准")
            # self.calibrate_btn.clicked.connect(self.calibrate_regions)
            # btn_row1.addWidget(self.calibrate_btn)
            # auto_layout.addLayout(btn_row1)

            # btn_row2 = QHBoxLayout()
            # self.debug_btn = QPushButton("📸 调试截图")
            # self.debug_btn.clicked.connect(self.take_debug_screenshot)
            # btn_row2.addWidget(self.debug_btn)
            # self.template_btn = QPushButton("📋 生成模板")
            # self.template_btn.clicked.connect(self.open_template_generator)
            # btn_row2.addWidget(self.template_btn)
            # auto_layout.addLayout(btn_row2)

            # self.debug_checkbox = QCheckBox("调试模式（保存识别过程图片）")
            # self.debug_checkbox.setChecked(False)
            # self.debug_checkbox.stateChanged.connect(self._toggle_debug_mode)
            # auto_layout.addWidget(self.debug_checkbox)

            self.status_label = QLabel("状态: 就绪")
            self.status_label.setStyleSheet(
                "color: #8f98b0; font-size: 12px; padding: 4px 2px 0 4px;"
            )
            self.status_label.setWordWrap(True)
            self.status_label.setMaximumHeight(44)
            # auto_layout.addWidget(self.status_label)

            # auto_group.setLayout(auto_layout)
            # main_layout.addWidget(auto_group)
            
            # 将状态标签直接添加到主布局中
            main_layout.addWidget(self.status_label)

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
            
            table_size = self._table_size
            position = self._get_position_name()
            remaining_opponents = self._remaining_opponents
            pot_size, call_amount, effective_stack_bb = self._get_bet_context()
            opponent_action = self.opponent_action_combo.currentText()

            if len(my_cards) != 2:
                self.status_label.setText("⚠️ 请先选择 2 张手牌")
                return

            if self._calc_worker and self._calc_worker.isRunning():
                self.status_label.setText("🔄 正在计算中...")
                return

            self.status_label.setText("🔄 计算中...")
            self._calc_worker = CalcWorker(
                self.calculator, my_cards, community_cards, num_opp,
                table_size, position, remaining_opponents,
                pot_size, call_amount, effective_stack_bb, opponent_action
            )
            self._calc_worker.finished.connect(self._on_calc_finished)
            self._calc_worker.error.connect(self._on_calc_error)
            self._calc_worker.start()

        def reset_all_inputs(self):
            """重置所有输入选项到默认状态"""
            self._manual_my_cards = []
            self._manual_comm_cards = []
            self.hand_btn.setText("点击选择手牌")
            self.community_btn.setText("点击选择公共牌")
            
            self.pot_spin.setValue(0.0)
            self.call_spin.setValue(0.0)
            self.effective_stack_spin.setValue(100.0)
            
            self.table_size_combo.setCurrentIndex(1) # 默认9人桌
            self._table_size = 9
            self._refresh_position_options()
            self.position_combo.setCurrentIndex(0) # 默认UTG
            
            self.remaining_opponents_spin.setValue(8)
            self.opponent_action_combo.setCurrentIndex(1) # 默认Open Raise
            
            self.cards_label.setText("手牌: -- | 公共牌: --")
            self.hand_type_label.setText("牌型: --")
            self.texture_label.setText("牌面结构: --")
            self.win_rate_label.setText("胜率: --%")
            self.win_rate_label.setStyleSheet("color: #7d8aff; font-size: 34px; font-weight: 800;")
            self.tie_label.setText("⚖️ 平局: --%")
            self.lose_label.setText("❌ 败率: --%")
            self.outs_label.setText("补牌(Outs): -- | 中牌率: --%")
            self.pot_odds_label.setText("底池赔率: -- | 需求胜率: --")
            self.ev_spr_label.setText("EV: -- | MDF: -- | SPR: -- | 弃牌率: --")
            
            self.suggestion_label.setText("建议: --")
            self.suggestion_label.setStyleSheet(
                """
                font-size: 15px; font-weight: 700; padding: 10px 12px;
                background-color: #202532; border: 1px solid #303748;
                border-radius: 10px; color: #f3f6ff;
            """
            )
            self.status_label.setText("状态: 已重置")

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
                f"手牌: {hand_str}  |  公共牌: {comm_str}  |  {self._table_size}人桌 | {self._get_position_name()} | 剩余{self._remaining_opponents}人"
            )
            self.hand_type_label.setText(f"牌型: {result['hand_name']}")
            
            texture = result.get("texture")
            if texture and len(community_cards) >= 3:
                wetness = texture.get('wetness', 0)
                desc = "干燥" if wetness < 0.3 else "中等" if wetness < 0.6 else "湿润"
                traits = []
                if texture.get("monotone"): traits.append("同花面")
                if texture.get("paired"): traits.append("公对面")
                if traits:
                    desc += f" ({', '.join(traits)})"
                self.texture_label.setText(f"牌面结构: {desc} (指数: {wetness*100:.0f})")
            else:
                self.texture_label.setText("牌面结构: --")

            win_pct = result["win_rate"] * 100
            self.win_rate_label.setText(f"✅ 胜率: {win_pct:.1f}%")

            if win_pct >= 60:
                color = "#7f8dff"
            elif win_pct >= 40:
                color = "#f6c56f"
            else:
                color = "#ff7c8f"

            self.win_rate_label.setStyleSheet(
                f"color: {color}; font-size: 34px; font-weight: 800;"
            )

            self.tie_label.setText(f"⚖️ 平局: {result['tie_rate']*100:.1f}%")
            self.lose_label.setText(f"❌ 败率: {result['lose_rate']*100:.1f}%")

            outs = result["outs"]
            outs_prob = result["outs_probability"] * 100
            self.outs_label.setText(f"补牌(Outs): {outs} | 中牌率: {outs_prob:.1f}%")

            pot_info = result.get("pot_odds")
            if pot_info:
                self.pot_odds_label.setText(
                    f"底池赔率: {pot_info['pot_odds_str']} | 需求胜率: {pot_info['required_equity_pct']}"
                )
            else:
                self.pot_odds_label.setText("底池赔率: -- | 需求胜率: --")

            call_ev_bb = result.get("call_ev_bb")
            mdf_text = pot_info["mdf_pct"] if pot_info and "mdf_pct" in pot_info else "--"
            spr_text = f"{result['spr']:.2f}" if "spr" in result else "--"
            ev_text = f"{call_ev_bb:+.2f}bb" if call_ev_bb is not None else "--"
            fold_equity = result.get("fold_equity")
            fe_text = f"{fold_equity*100:.1f}%" if fold_equity is not None else "--"
            
            # 优先显示下注(诈唬)EV或跟注EV
            bluff_ev_bb = result.get("bluff_ev_bb")
            if bluff_ev_bb is not None and call_amount == 0:
                ev_text = f"Bet(诈唬)EV: {bluff_ev_bb:+.2f}bb"
            else:
                ev_text = f"Call EV: {ev_text}"
                
            self.ev_spr_label.setText(f"{ev_text} | MDF: {mdf_text} | SPR: {spr_text} | 弃牌率(FE): {fe_text}")

            self.suggestion_label.setText(result["suggestion"])

            if any(word in result["suggestion"] for word in ("RAISE", "BET", "VALUE")) and "🔥" in result["suggestion"]:
                bg = "#22283b"
                border = "#7d8aff"
            elif any(word in result["suggestion"] for word in ("CALL", "CHECK", "控池")):
                bg = "#27262d"
                border = "#c7a763"
            else:
                bg = "#2d2329"
                border = "#d87384"

            self.suggestion_label.setStyleSheet(
                f"""
                font-size: 15px; font-weight: 700; padding: 10px 12px;
                background-color: {bg}; border: 1px solid {border};
                border-radius: 10px; color: #f4f6ff;
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
                    
                    table_size = self._table_size
                    position = self._get_position_name()
                    remaining_opponents = self._remaining_opponents
                    pot_size, call_amount, effective_stack_bb = self._get_bet_context()
                    opponent_action = self.opponent_action_combo.currentText()

                    if self._calc_worker and self._calc_worker.isRunning():
                        return

                    self._calc_worker = CalcWorker(
                        self.calculator, my_cards, community_cards, num_opp,
                        table_size, position, remaining_opponents, pot_size, call_amount, effective_stack_bb, opponent_action
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
                f"✅ 计算完成 ({result['simulations']}次模拟)"
            )

        def _on_calc_error(self, error_msg):
            self.status_label.setText(f"❌ 计算错误: {error_msg[:40]}")

        def _on_table_size_changed(self, text):
            self._table_size = 6 if text.startswith("6") else 9
            self._refresh_position_options()
            self._sync_remaining_opponents_limit()
            self.status_label.setText(
                f"ℹ️ 已切换为{self._table_size}人桌（剩余人数=除自己未弃牌人数）"
            )

        def _on_position_changed(self, index):
            if index >= 0:
                self._position_index = index

        def _on_remaining_opponents_changed(self, value):
            self._remaining_opponents = int(value)

        def _sync_remaining_opponents_limit(self):
            self._remaining_opponents = min(max(self._remaining_opponents, 1), self._table_size - 1)
            self.remaining_opponents_spin.setRange(1, self._table_size - 1)
            self.remaining_opponents_spin.setValue(self._remaining_opponents)

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
            return max(1, self._remaining_opponents)

        def _get_bet_context(self):
            pot_size = float(self.pot_spin.value())
            call_amount = float(self.call_spin.value())
            effective_stack_bb = float(self.effective_stack_spin.value())
            if pot_size > 0 or call_amount > 0:
                return pot_size, call_amount, effective_stack_bb if effective_stack_bb > 0 else None
            return None, None, None

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
            self.config["gui"]["remaining_opponents"] = self._remaining_opponents
            self.config["gui"]["pot_size_bb"] = float(self.pot_spin.value())
            self.config["gui"]["call_amount_bb"] = float(self.call_spin.value())
            self.config["gui"]["effective_stack_bb"] = float(self.effective_stack_spin.value())
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
