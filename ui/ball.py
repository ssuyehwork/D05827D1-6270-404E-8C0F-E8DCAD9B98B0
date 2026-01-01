# -*- coding: utf-8 -*-
# ui/ball.py
import math
import random
from PyQt5.QtWidgets import QWidget, QMenu
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush
from core.settings import save_setting

class FloatingBall(QWidget):
    request_show_quick_window = pyqtSignal()
    request_show_main_window = pyqtSignal()
    request_quit_app = pyqtSignal()
    double_clicked = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window 
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(64, 64) 
        self.setAcceptDrops(True)

        self.dragging = False
        self.is_hovering = False 
        self.offset = QPoint()
        self.hue = 0  # 色相 (0-359)

        # --- 动能参数 ---
        self.angle_outer = 0  # 外环角度
        self.angle_inner = 0  # 内环角度
        self.rotation_speed_base = 2.0 # 基础转速
        self.current_speed = self.rotation_speed_base
        
        # 粒子系统
        self.particles = [] 

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)
        self.timer.start(16) # ~60FPS

    def _update_physics(self):
        """物理帧更新"""
        # 1. 色相更新 (彩虹呼吸效果)
        self.hue = (self.hue + 0.5) % 360

        # 2. 目标速度控制 (惯性平滑处理)
        target_speed = 15.0 if self.is_hovering else 2.0
        self.current_speed += (target_speed - self.current_speed) * 0.1
        
        # 3. 更新角度
        self.angle_outer += self.current_speed
        self.angle_inner -= self.current_speed * 1.5 # 内环反向旋转
        
        # 归一化
        self.angle_outer %= 360
        self.angle_inner %= 360

        # 4. 粒子更新
        if self.is_hovering:
            self._update_particles()
            
        self.update()

    def _update_particles(self):
        # 随机生成指向圆心的粒子
        if len(self.particles) < 10:
            angle = random.uniform(0, 6.28)
            dist = 30
            self.particles.append({'a': angle, 'd': dist, 's': random.uniform(2, 4)})
        
        # 更新粒子位置
        alive_particles = []
        for p in self.particles:
            p['d'] -= p['s'] # 向圆心吸入
            if p['d'] > 0:
                alive_particles.append(p)
        self.particles = alive_particles

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        cx, cy = 32, 32
        
        # === 赛博配色 (Cyber Palette) ===
        if self.is_hovering:
            # 高能状态: 金/橙
            main_color = QColor(255, 215, 0)      # Gold
            glow_color = QColor(255, 69, 0, 150)  # Orange Glow
            bg_color = QColor(20, 0, 0, 200)      
        else:
            # 常态: 彩虹呼吸
            main_color = QColor.fromHsvF(self.hue / 360.0, 0.9, 1.0)
            glow_color = QColor.fromHsvF(self.hue / 360.0, 0.7, 1.0, 0.4) # Alpha=100/255
            bg_color = QColor(0, 15, 30, 180)

        # 1. 绘制核心背景
        p.setPen(Qt.NoPen)
        p.setBrush(bg_color)
        p.drawEllipse(4, 4, 56, 56)

        # 2. 绘制粒子流
        if self.is_hovering:
            p.setPen(QPen(QColor(255, 255, 255, 180), 1.5))
            for pt in self.particles:
                px = cx + math.cos(pt['a']) * pt['d']
                py = cy + math.sin(pt['a']) * pt['d']
                p.drawPoint(QPoint(int(px), int(py)))

        # 3. 绘制外环 (三段不对称，模拟HUD)
        pen_outer = QPen(main_color)
        pen_outer.setWidth(3)
        pen_outer.setCapStyle(Qt.RoundCap)
        p.setPen(pen_outer)
        p.setBrush(Qt.NoBrush)
        
        rect_outer = QRectF(6, 6, 52, 52)
        start_angle = int(self.angle_outer * 16)
        # 1度 = 16 units
        p.drawArc(rect_outer, start_angle, 16 * 60)          # 60度长弧
        p.drawArc(rect_outer, start_angle + 16*120, 16 * 30) # 30度短弧
        p.drawArc(rect_outer, start_angle + 16*200, 16 * 100)# 100度大弧

        # 4. 绘制内环 (三段对称，模拟机械锁扣) -- [这里是修改后的部分]
        pen_inner = QPen(main_color)
        pen_inner.setWidth(2) # 稍微细一点，但比之前清晰
        pen_inner.setCapStyle(Qt.FlatCap) # 内环用平头，更有机械感
        p.setPen(pen_inner)
        
        rect_inner = QRectF(14, 14, 36, 36)
        start_angle_in = int(self.angle_inner * 16)
        
        # 绘制三个均匀分布的弧 (每个80度，间隔40度)
        # 0度偏移
        p.drawArc(rect_inner, start_angle_in, 16 * 80)
        # 120度偏移
        p.drawArc(rect_inner, start_angle_in + 16 * 120, 16 * 80)
        # 240度偏移
        p.drawArc(rect_inner, start_angle_in + 16 * 240, 16 * 80)

        # 5. 绘制中心闪电图标
        font = QFont('Arial', 18, QFont.Bold)
        p.setFont(font)
        
        # 辉光层
        p.setPen(glow_color)
        p.drawText(self.rect().adjusted(1,1,1,1), Qt.AlignCenter, '⚡')
        
        # 实体层
        p.setPen(QColor(255, 255, 255))
        p.drawText(self.rect(), Qt.AlignCenter, '⚡')

    # --- 交互逻辑 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.accept()
            self.is_hovering = True
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.is_hovering = False

    def dropEvent(self, e):
        self.is_hovering = False
        text = e.mimeData().text()
        if text.strip():
            self.mw.quick_add_idea(text)
            e.acceptProposedAction()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = e.pos()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.move(self.mapToGlobal(e.pos() - self.offset))

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            pos = self.pos()
            save_setting('floating_ball_pos', {'x': pos.x(), 'y': pos.y()})

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.double_clicked.emit()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        m.setStyleSheet("""
            QMenu { background-color: #1a1a1a; color: #00f3ff; border: 1px solid #333; padding: 5px; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #00f3ff; color: #000; border-radius: 2px;}
            QMenu::separator { background-color: #333; height: 1px; margin: 5px 0; }
        """)
        m.addAction('⚡ 打开快速笔记', self.request_show_quick_window.emit)
        m.addAction('💻 打开主界面', self.request_show_main_window.emit)
        m.addAction('➕ 新建灵感', self.mw.new_idea)
        m.addSeparator()
        m.addAction('❌ 退出', self.request_quit_app.emit)
        m.exec_(e.globalPos())