# core/keyboard_helper.py

import time
import keyboard
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QCheckBox)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QPainterPath
from core.settings import load_setting, save_setting

class HotkeyManager(QObject):
    status_changed = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.feature_enabled = {
            'shift_space': load_setting('hotkey_shift_space', True),
            'ctrl_shift_space': load_setting('hotkey_ctrl_shift_space', True),
            'capslock': load_setting('hotkey_capslock', True),
            'backtick_backspace': load_setting('hotkey_backtick_backspace', True)
        }
        # 使用更稳健的 add_hotkey 处理组合键, 避免与输入法冲突
        self._hotkey_map = {
            'shift_space': ('shift+space', self._handle_shift_space),
            'ctrl_shift_space': ('ctrl+shift+space', self._handle_ctrl_shift_space)
        }
        # 低级 hook 只用于处理单键替换
        self.hook = None

    def _handle_shift_space(self):
        keyboard.send('shift+enter')

    def _handle_ctrl_shift_space(self):
        keyboard.send('ctrl+a')
        time.sleep(0.01)
        keyboard.send('delete')

    def start(self):
        # 1. 注册组合键
        for feature, (hotkey_str, callback) in self._hotkey_map.items():
            if self.feature_enabled.get(feature):
                try:
                    keyboard.add_hotkey(hotkey_str, callback, suppress=True)
                except Exception as e:
                    # 在某些环境下可能会失败, 打印日志
                    print(f"无法注册热键 {hotkey_str}: {e}")

        # 2. 仅为单键替换启动低级 hook
        if self.hook is None:
            self.hook = keyboard.hook(self._key_handler, suppress=True)

    def stop(self):
        # 1. 移除低级 hook
        if self.hook:
            keyboard.unhook(self.hook)
            self.hook = None

        # 2. 清理所有已注册的组合键
        for feature in self._hotkey_map:
            hotkey_str, _ = self._hotkey_map[feature]
            try:
                keyboard.remove_hotkey(hotkey_str)
            except KeyError:
                pass

    def toggle_feature(self, feature, enabled):
        if feature not in self.feature_enabled:
            return
            
        self.feature_enabled[feature] = enabled
        save_setting(f'hotkey_{feature}', enabled)

        # 对于组合键, 动态添加/移除
        if feature in self._hotkey_map:
            hotkey_str, callback = self._hotkey_map[feature]
            try:
                keyboard.remove_hotkey(hotkey_str)
            except KeyError:
                pass
            
            if enabled:
                try:
                    keyboard.add_hotkey(hotkey_str, callback, suppress=True)
                except Exception as e:
                    print(f"无法在切换时注册热键 {hotkey_str}: {e}")

        # 对于使用 hook 的单键, 无需操作, _key_handler 会自动检查标志位
        self.status_changed.emit(feature, enabled)

    def _key_handler(self, event):
        # hook 处理器现在大大简化, 只处理单键替换, 不再干扰空格键
        if event.event_type != 'down':
            return True

        # CapsLock -> Enter
        if event.name == 'caps lock':
            if keyboard.is_pressed('shift') or keyboard.is_pressed('ctrl'):
                return True
            
            if not self.feature_enabled.get('capslock'):
                return True

            keyboard.send('enter')
            return False
        
        # ` (Backtick) -> Backspace
        if event.name == '`':
            if keyboard.is_pressed('shift'):
                return True
            
            if not self.feature_enabled.get('backtick_backspace'):
                return True
            
            keyboard.send('backspace')
            return False

        return True

class HotkeySettingsWindow(QWidget):
    def __init__(self, manager: HotkeyManager):
        super().__init__()
        self.manager = manager
        self.drag_position = QPoint()
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("键盘增强工具")
        
        self.setStyleSheet("font-family: 'Microsoft YaHei';")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = self._create_title_bar()
        main_layout.addWidget(title_bar)
        
        content = self._create_content()
        main_layout.addWidget(content)
        
        self.setLayout(main_layout)
        self.setFixedSize(420, 340)
    
    def _create_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(35)
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(15, 5, 10, 5)
        
        title_label = QLabel("键盘增强工具")
        title_label.setStyleSheet("color: #B0B0B0; font-size: 13px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        btn_min = QPushButton("—")
        btn_min.setFixedSize(30, 25)
        btn_min.setStyleSheet("QPushButton { background: transparent; color: #B0B0B0; border: none; font-size: 16px; font-weight: bold; } QPushButton:hover { background: #404040; color: #FFFFFF; border-radius: 3px; }")
        btn_min.clicked.connect(self.showMinimized)
        title_layout.addWidget(btn_min)
        
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 25)
        btn_close.setStyleSheet("QPushButton { background: transparent; color: #B0B0B0; border: none; font-size: 16px; } QPushButton:hover { background: #E81123; color: #FFFFFF; border-radius: 3px; }")
        btn_close.clicked.connect(self.hide)
        title_layout.addWidget(btn_close)
        
        title_bar.setLayout(title_layout)
        return title_bar
    
    def _create_content(self):
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 15, 25, 20)
        layout.setSpacing(12)
        
        header = QLabel("快捷键设置")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #E0E0E0; font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(header)
        
        features = {
            'shift_space': "Shift + Space → 换行 (Shift+Enter)",
            'ctrl_shift_space': "Ctrl + Shift + Space → 清空输入框",
            'capslock': "CapsLock → 回车 (Shift+Caps 切换锁定)",
            'backtick_backspace': "` (反引号) → 退格 (Shift+` 输入 ~)"
        }
        
        for key, text in features.items():
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.manager.feature_enabled[key])
            checkbox.setStyleSheet(self._get_checkbox_style())
            checkbox.stateChanged.connect(lambda state, k=key: self.manager.toggle_feature(k, state == Qt.Checked))
            layout.addWidget(checkbox)
        
        tip = QLabel("提示：取消勾选即可恢复按键默认功能")
        tip.setAlignment(Qt.AlignCenter)
        tip.setStyleSheet("color: #666666; font-size: 12px; padding: 10px 5px 5px 5px;")
        layout.addWidget(tip)
        
        layout.addStretch()
        content.setLayout(layout)
        return content
    
    def _get_checkbox_style(self):
        return """
            QCheckBox { color: #E0E0E0; font-size: 14px; padding: 5px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 2px solid #555555; background: #2A2A2A; }
            QCheckBox::indicator:checked { background: #4A9EFF; border: 2px solid #4A9EFF; image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTMgNEw2IDExIDMgOCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBmaWxsPSJub25lIi8+PC9zdmc+); }
            QCheckBox::indicator:hover { border: 2px solid #4A9EFF; }
        """
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 15, 15)
        painter.fillPath(path, QColor(30, 30, 30, 250))
        painter.setPen(QColor(60, 60, 60))
        painter.drawPath(path)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.pos().y() <= 35:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPos() - self.drag_position)
    
    def mouseReleaseEvent(self, event):
        self.drag_position = QPoint()

    def showEvent(self, event):
        # Reload settings when shown, in case they were changed elsewhere
        for child in self.findChildren(QCheckBox):
            key = next((k for k, v in {
                'shift_space': "Shift + Space → 换行 (Shift+Enter)",
                'ctrl_shift_space': "Ctrl + Shift + Space → 清空输入框",
                'capslock': "CapsLock → 回车 (Shift+Caps 切换锁定)",
                'backtick_backspace': "` (反引号) → 退格 (Shift+` 输入 ~)"
            }.items() if v == child.text()), None)
            if key:
                child.setChecked(self.manager.feature_enabled[key])
        super().showEvent(event)
