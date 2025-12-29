# -*- coding: utf-8 -*-
# ui/ball.py
import math
from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt5.QtGui import QPainter, QRadialGradient, QColor, QFont
from core.settings import save_setting

class FloatingBall(QWidget):
    double_clicked = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(60, 60)

        self.setAcceptDrops(True)

        self.dragging = False
        self.offset = QPoint()
        # --- 动画相关初始化 ---
        self.step = 0.0 # 动画步进 (0 ~ 2π)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_animation)

        # 默认启动呼吸动画 (40ms 刷新一次，约 25帧，省资源且流畅)
        self.timer.start(40) 

    def _update_animation(self):
        """定时器槽函数：更新呼吸状态"""
        self.step += 0.1
        if self.step > math.pi * 2:
            self.step = 0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # --- 计算呼吸因子 ---
        # sin 值域为 -1 到 1，将其映射到 0 到 1 之间
        # breath_factor: 0.0 (最弱) -> 1.0 (最强)
        breath_factor = (math.sin(self.step) + 1) / 2

        # --- 效果 1: 忽大忽小 (半径变化) ---
        # 基础半径 22，最大增加 6 (即 22 ~ 28 像素)
        base_radius = 22
        current_radius = base_radius + (6 * breath_factor)

        # --- 效果 2: 发光 (颜色/透明度变化) ---
        # 核心颜色: 越亮越偏向亮蓝/白色
        # Alpha: 保持较高不透明度
        r_val = 74 + (40 * breath_factor) # R: 变大时红分量增加(变白)
        g_val = 144 + (40 * breath_factor) # G: 变大时绿分量增加
        b_val = 226 # B: 保持高位
        alpha_val = 200 + (55 * breath_factor) # Alpha: 200 ~ 255

        center_color = QColor(int(r_val), int(g_val), int(b_val), int(alpha_val))
        edge_color = QColor(52, 100, 158, 200) # 边缘保持深蓝

        # --- 绘制球体 ---
        # 径向渐变，光源在中心
        g = QRadialGradient(30, 30, current_radius)
        g.setColorAt(0, center_color)
        g.setColorAt(1, edge_color)

        p.setBrush(g)
        p.setPen(Qt.NoPen)

        # 绘制同心圆 (中心点 30,30)
        p.drawEllipse(QPoint(30, 30), current_radius, current_radius)

        # --- 绘制图标/文字 (始终居中，不旋转) ---
        p.setPen(Qt.white)
        # 字体大小也可以随呼吸微调，增加动感 (可选，这里设为固定或微动)
        font_size = 20 + (2 * breath_factor) 
        p.setFont(QFont('Arial', int(font_size), QFont.Bold))

        p.drawText(self.rect(), Qt.AlignCenter, '💡')

    # --- 拖拽接收逻辑 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.accept()
            # 拖拽进来时，可以瞬间变大以提示用户
            self.step = math.pi / 2 # 设置到波峰
            self.update()
        else:
            e.ignore()

    def dropEvent(self, e):
        text = e.mimeData().text()
        if text.strip():
            self.mw.quick_add_idea(text)
            e.acceptProposedAction()

    # --- 鼠标交互逻辑 ---
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = e.pos()
            # 按下时可以缩小一点，产生按压感
            self.timer.stop()
            self.update()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.move(self.mapToGlobal(e.pos() - self.offset))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            # 保存当前位置
            pos = self.pos()
            save_setting('floating_ball_pos', {'x': pos.x(), 'y': pos.y()})
        # 松开后恢复呼吸
        if not self.timer.isActive():
            self.timer.start(40)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            # 双击打开主窗口
            self.mw.show_main_window()
            self.double_clicked.emit()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet("background:#2d2d2d;color:white;border:1px solid #333")
        m.addAction('📖 打开主窗口', self.mw.show_main_window)
        m.addAction('➕ 新建灵感', self.mw.new_idea)
        m.addSeparator()
        m.addAction('❌ 退出', self.mw.quit_app)
        m.exec_(e.globalPos())
