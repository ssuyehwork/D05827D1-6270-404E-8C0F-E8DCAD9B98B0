# ui/dialogs.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QGridLayout, QHBoxLayout,
                              QLabel, QLineEdit, QTextEdit, QComboBox, QPushButton,
                              QProgressBar, QFrame, QApplication, QMessageBox, QShortcut,
                             QSpacerItem, QSizePolicy, QSplitter, QWidget, QScrollBar,
                             QGraphicsDropShadowEffect)
from PyQt5.QtGui import QKeySequence, QColor
from PyQt5.QtCore import Qt
from core.config import STYLES, COLORS
from .components.rich_text_edit import RichTextEdit

# 自定义深灰色滚动条样式
SCROLLBAR_STYLE = """
QScrollBar:vertical {
    border: none;
    background: #222222;
    width: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:vertical {
    background: #555555;
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #666666;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    border: none;
    background: #222222;
    height: 10px;
    margin: 0px 0px 0px 0px;
}
QScrollBar::handle:horizontal {
    background: #555555;
    min-width: 20px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #666666;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
"""

class BaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置窗口标志,支持透明背景
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建主容器
        self._setup_container()
    
    def _setup_container(self):
        """设置带阴影的主容器"""
        # 外层布局,留出阴影空间
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(15, 15, 15, 15)
        
        # 内容容器
        self.content_container = QWidget()
        self.content_container.setObjectName("DialogContainer")
        self.content_container.setStyleSheet(f"""
            #DialogContainer {{
                background-color: {COLORS['bg_dark']};
                border-radius: 12px;
            }}
        """ + STYLES['dialog'] + SCROLLBAR_STYLE)
        
        outer_layout.addWidget(self.content_container)
        
        # 添加现代化阴影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setXOffset(0)
        shadow.setYOffset(6)
        shadow.setColor(QColor(0, 0, 0, 120))
        self.content_container.setGraphicsEffect(shadow)
        
        # 返回内容容器,子类可以在其中添加布局
        return self.content_container

# === 编辑窗口 (支持左右拉伸 & 深色滚动条 & 阴影) ===
class EditDialog(BaseDialog):
    def __init__(self, db, idea_id=None, parent=None, category_id_for_new=None):
        super().__init__(parent)
        self.db = db
        self.idea_id = idea_id
        self.selected_color = COLORS['primary']
        self.category_id = None # 用于加载已存在的数据
        self.category_id_for_new = category_id_for_new # 用于新建
        
        self._init_ui()
        if idea_id: self._load_data()
        
        # 使对话框可拖动
        self._drag_pos = None

    def _init_ui(self):
        self.setWindowTitle('✨ 记录灵感')
        self.resize(950, 650)
        
        main_layout = QVBoxLayout(self.content_container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['bg_mid']};
                width: 2px;
                margin: 0 5px;
            }}
            QSplitter::handle:hover {{
                background-color: {COLORS['primary']};
            }}
        """)
        
        # ================= 左侧容器 =================
        left_container = QWidget()
        left_panel = QVBoxLayout(left_container)
        left_panel.setContentsMargins(15, 15, 15, 15)
        left_panel.setSpacing(12)
        
        left_panel.addWidget(QLabel('📌 标题'))
        self.title_inp = QLineEdit()
        self.title_inp.setPlaceholderText("请输入灵感标题...")
        self.title_inp.setFixedHeight(40)
        left_panel.addWidget(self.title_inp)
        
        left_panel.addWidget(QLabel('🏷️ 标签'))
        self.tags_inp = QLineEdit()
        self.tags_inp.setPlaceholderText("使用逗号分隔...")
        self.tags_inp.setFixedHeight(40)
        left_panel.addWidget(self.tags_inp)
        
        left_panel.addSpacing(10)
        left_panel.addWidget(QLabel('🎨 标记颜色'))
        color_layout = QGridLayout()
        color_layout.setSpacing(10)
        
        self.color_btns = []
        colors = [COLORS['primary'], COLORS['success'], COLORS['warning'],
                  COLORS['danger'], COLORS['info'], COLORS['teal']]
                  
        for i, c in enumerate(colors):
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background-color: {c}; border-radius: 17px; border: 2px solid transparent; }}")
            btn.clicked.connect(lambda _, x=c: self._set_color(x))
            self.color_btns.append(btn)
            color_layout.addWidget(btn, i // 3, i % 3)
            
        left_panel.addLayout(color_layout)
        left_panel.addStretch()
        
        self.save_btn = QPushButton('💾 保存 (Ctrl+S)')
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(50)
        self.save_btn.setStyleSheet(STYLES['btn_primary'])
        self.save_btn.clicked.connect(self._save_data)
        left_panel.addWidget(self.save_btn)
        
        # ================= 右侧容器 =================
        right_container = QWidget()
        right_panel = QVBoxLayout(right_container)
        right_panel.setContentsMargins(15, 15, 15, 15)
        right_panel.setSpacing(10)
        
        right_panel.addWidget(QLabel('📝 详细内容'))
        self.content_inp = RichTextEdit()
        self.content_inp.setPlaceholderText("在这里记录详细内容（支持粘贴图片）...")
        self.content_inp.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                color: #eee;
            }
        """)
        right_panel.addWidget(self.content_inp)
        
        self.splitter.addWidget(left_container)
        self.splitter.addWidget(right_container)
        self.splitter.setSizes([300, 650])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(self.splitter)
        
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_data)
        QShortcut(QKeySequence("Escape"), self, self.reject)
        self._set_color(self.selected_color)

    def mousePressEvent(self, e):
        """使对话框可拖动"""
        if e.button() == Qt.LeftButton and e.pos().y() < 40:
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        """拖动对话框"""
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPos() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        """结束拖动"""
        self._drag_pos = None

    def _set_color(self, color):
        self.selected_color = color
        for btn in self.color_btns:
            style = btn.styleSheet()
            if color in style:
                new_style = f"background-color: {color}; border-radius: 17px; border: 3px solid white;"
            else:
                bg = style.split('background-color:')[1].split(';')[0].strip()
                new_style = f"background-color: {bg}; border-radius: 17px; border: 2px solid transparent;"
            btn.setStyleSheet(f"QPushButton {{ {new_style} }}")

    def _load_data(self):
        # 在编辑时,需要加载完整数据,包括二进制blob
        d = self.db.get_idea(self.idea_id, include_blob=True)
        if d:
            self.title_inp.setText(d[1])
            self.content_inp.setText(d[2])
            self._set_color(d[3])
            self.category_id = d[8]
            
            item_type = d[9]
            data_blob = d[10]
            if item_type == 'image' and data_blob:
                self.content_inp.set_image_data(data_blob)

            self.tags_inp.setText(','.join(self.db.get_tags(self.idea_id)))

    def _save_data(self):
        title = self.title_inp.text().strip()
        if not title:
            self.title_inp.setPlaceholderText("⚠️ 标题不能为空!")
            self.title_inp.setFocus()
            return

        tags = [t.strip() for t in self.tags_inp.text().split(',') if t.strip()]
        content = self.content_inp.toPlainText()
        color = self.selected_color
        
        item_type = 'text'
        data_blob = self.content_inp.get_image_data()
        if data_blob:
            item_type = 'image'

        if self.idea_id:
            # 更新模式
            self.db.update_idea(self.idea_id, title, content, color, tags, self.category_id, item_type, data_blob)
        else:
            # 新建模式
            self.db.add_idea(title, content, color, tags, self.category_id_for_new, item_type, data_blob)
        
        self.accept()

# === 看板窗口 ===
class StatsDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📊 数据看板')
        self.resize(550, 450)
        
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        counts = db.get_counts()
        grid = QGridLayout()
        grid.setSpacing(15)
        grid.addWidget(self._box("📚 总灵感", counts['all'], COLORS['primary']), 0, 0)
        grid.addWidget(self._box("📅 今日新增", counts['today'], COLORS['success']), 0, 1)
        grid.addWidget(self._box("⭐ 我的收藏", counts['favorite'], COLORS['warning']), 1, 0)
        grid.addWidget(self._box("🏷️ 待整理", counts['untagged'], COLORS['danger']), 1, 1)
        layout.addLayout(grid)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("🔥 热门标签 Top 5"))
        
        stats = db.get_top_tags()
        if not stats:
            layout.addWidget(QLabel("暂无标签数据", styleSheet="color:#666; font-style:italic; font-weight:normal;"))
        else:
            max_val = stats[0][1]
            for name, cnt in stats:
                h = QHBoxLayout()
                lbl = QLabel(f"#{name}")
                lbl.setFixedWidth(80)
                lbl.setStyleSheet("color:#eee; font-weight:bold; margin:0;")
                h.addWidget(lbl)
                
                p = QProgressBar()
                p.setMaximum(max_val)
                p.setValue(cnt)
                p.setFixedHeight(18)
                p.setFormat(f" {cnt}")
                p.setStyleSheet(f"""
                    QProgressBar {{
                        background-color: {COLORS['bg_mid']};
                        border: none;
                        border-radius: 9px;
                        color: white;
                        text-align: center;
                    }}
                    QProgressBar::chunk {{
                        background-color: {COLORS['primary']};
                        border-radius: 9px;
                    }}
                """)
                h.addWidget(p)
                layout.addLayout(h)
                
        layout.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(40)
        close_btn.setStyleSheet(f"background-color:{COLORS['bg_mid']}; border:1px solid #444; color:#ccc; border-radius:5px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _box(self, t, v, c):
        f = QFrame()
        f.setStyleSheet(f"QFrame {{ background-color: {c}15; border: 1px solid {c}40; border-radius: 10px; }}")
        vl = QVBoxLayout(f)
        vl.setContentsMargins(15, 15, 15, 15)
        lbl_title = QLabel(t)
        lbl_title.setStyleSheet(f"color:{c}; font-size:13px; font-weight:bold; border:none; margin:0;")
        lbl_val = QLabel(str(v))
        lbl_val.setStyleSheet(f"color:{c}; font-size:28px; font-weight:bold; border:none; margin-top:5px;")
        vl.addWidget(lbl_title)
        vl.addWidget(lbl_val)
        return f

# === 提取窗口 ===
class ExtractDialog(BaseDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle('📋 提取内容')
        self.resize(700, 600)
        
        layout = QVBoxLayout(self.content_container)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setPlaceholderText("暂无数据...")
        layout.addWidget(self.txt)
        
        data = db.get_ideas('', 'all', None)
        text = '\n' + '-'*60 + '\n'
        text += '\n'.join([f"【{d[1]}】\n{d[2]}\n" + '-'*60 for d in data])
        self.txt.setText(text)
        
        layout.addSpacing(10)
        btn = QPushButton('📋 复制全部到剪贴板')
        btn.setFixedHeight(45)
        btn.setStyleSheet(STYLES['btn_primary'])
        btn.clicked.connect(lambda: (QApplication.clipboard().setText(text), QMessageBox.information(self,'成功','✅ 内容已复制')))
        layout.addWidget(btn)

# === 预览窗口 ===
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import QDesktopWidget

class PreviewDialog(QDialog):
    def __init__(self, item_type, data, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.Popup)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self._init_ui(item_type, data)

        # 添加关闭快捷键
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.close)
        QShortcut(QKeySequence(Qt.Key_Space), self, self.close)

    def _init_ui(self, item_type, data):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_dark']};
                border: 2px solid {COLORS['bg_mid']};
                border-radius: 12px;
            }}
        """)
        container_layout = QVBoxLayout(container)
        main_layout.addWidget(container)

        if item_type == 'text':
            self._setup_text_preview(container_layout, data)
        elif item_type == 'image':
            self._setup_image_preview(container_layout, data)

    def _setup_text_preview(self, layout, text_data):
        self.resize(600, 500)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText(text_data)
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: transparent;
                border: none;
                padding: 15px;
                color: #ddd;
                font-size: 14px;
            }}
            {SCROLLBAR_STYLE}
        """)
        layout.addWidget(text_edit)

    def _setup_image_preview(self, layout, image_data):
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        if pixmap.isNull():
            # 如果图片加载失败,显示错误信息
            label = QLabel("无法加载图片")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #E81123; font-size: 16px;")
            layout.addWidget(label)
            self.resize(300, 200)
            return
            
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # 智能缩放
        screen_geo = QDesktopWidget().availableGeometry(self)
        max_width = screen_geo.width() * 0.8
        max_height = screen_geo.height() * 0.8

        scaled_pixmap = pixmap.scaled(int(max_width), int(max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
        
        # 调整窗口大小以适应图片
        self.resize(scaled_pixmap.width() + 20, scaled_pixmap.height() + 20)

    def mousePressEvent(self, event):
        # 点击任何地方都关闭
        self.close()