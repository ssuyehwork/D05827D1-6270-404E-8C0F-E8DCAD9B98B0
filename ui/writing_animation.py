# -*- coding: utf-8 -*-
# ui/writing_animation.py
import math
import random
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QLinearGradient, QPainterPath

class WritingAnimationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.is_writing = False
        self.time_step = 0.0
        self.pen_angle = -45.0
        self.pen_x = 0
        self.pen_y = 0
        self.book_y = 0
        self.particles = []
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_physics)

    def start(self):
        self.is_writing = True
        self.time_step = 0
        if not self.timer.isActive():
            self.timer.start(20)
        self.show()

    def _update_physics(self):
        self.time_step += 0.1
        
        target_pen_angle = -65
        write_speed = self.time_step * 3.0
        flow_x = math.sin(write_speed) * 4
        flow_y = math.cos(write_speed * 2) * 1
        target_pen_x = flow_x
        target_pen_y = 2 + flow_y
        target_book_y = -1

        easing = 0.1
        self.pen_angle += (target_pen_angle - self.pen_angle) * easing
        self.pen_x += (target_pen_x - self.pen_x) * easing
        self.pen_y += (target_pen_y - self.pen_y) * easing
        self.book_y += (target_book_y - self.book_y) * easing

        self._update_particles()
        self.update()

        if self.time_step > 5: # Stop after a while
            self.timer.stop()
            self.is_writing = False

    def _update_particles(self):
        if self.is_writing and len(self.particles) < 10:
            if random.random() < 0.4:
                rad = math.radians(self.pen_angle)
                tip_len = 12
                self.particles.append({
                    'x': self.width()/2 + self.pen_x - math.sin(rad)*tip_len,
                    'y': self.height()/2 + self.pen_y + math.cos(rad)*tip_len,
                    'vx': random.uniform(-0.2, 0.2),
                    'vy': random.uniform(0.2, 0.5),
                    'life': 1.0,
                    'size': random.uniform(0.5, 1.5)
                })
        
        alive = []
        for p in self.particles:
            p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 0.04; p['size'] *= 0.95
            if p['life'] > 0: alive.append(p)
        self.particles = alive

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        
        p.save()
        p.translate(cx, cy + self.book_y)
        p.scale(0.3, 0.3) # Scale down drawing
        self._draw_book_mocha(p)
        p.restore()

        p.save()
        p.translate(cx + self.pen_x, cy + self.pen_y - 5)
        p.scale(0.3, 0.3)
        p.rotate(self.pen_angle)
        self._draw_universal_pen(p)
        p.restore()
        
        for pt in self.particles:
            alpha = int(255 * pt['life'])
            c = QColor(255, 215, 0, alpha)
            p.setPen(Qt.NoPen); p.setBrush(c)
            p.drawEllipse(QRectF(pt['x']-pt['size']/2, pt['y']-pt['size']/2, pt['size'], pt['size']))

    def _draw_universal_pen(self, p):
        w_pen, h_pen = 12, 46
        c_light, c_mid, c_dark = QColor(180, 60, 70), QColor(140, 20, 30), QColor(60, 5, 10)
        body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
        body_grad.setColorAt(0.0, c_light); body_grad.setColorAt(0.5, c_mid); body_grad.setColorAt(1.0, c_dark)
        path_body = QPainterPath()
        path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 5, 5)
        p.setPen(Qt.NoPen); p.setBrush(body_grad); p.drawPath(path_body)
        path_tip = QPainterPath(); tip_h = 14
        path_tip.moveTo(-w_pen/2 + 3, h_pen/2); path_tip.lineTo(w_pen/2 - 3, h_pen/2); path_tip.lineTo(0, h_pen/2 + tip_h); path_tip.closeSubpath()
        tip_grad = QLinearGradient(-5, 0, 5, 0)
        tip_grad.setColorAt(0, QColor(240, 230, 180)); tip_grad.setColorAt(1, QColor(190, 170, 100))
        p.setBrush(tip_grad); p.drawPath(path_tip)
        p.setBrush(QColor(220, 200, 140)); p.drawRect(QRectF(-w_pen/2, h_pen/2 - 4, w_pen, 4))
        p.setBrush(QColor(210, 190, 130)); p.drawRoundedRect(QRectF(-1.5, -h_pen/2 + 6, 3, 24), 1.5, 1.5)

    def _draw_book_mocha(self, p):
        w, h = 56, 76
        p.setBrush(QColor(245, 240, 225)); p.drawRoundedRect(QRectF(-w/2+6, -h/2+6, w, h), 3, 3)
        grad = QLinearGradient(-w, -h, w, h)
        grad.setColorAt(0, QColor(90, 60, 50)); grad.setColorAt(1, QColor(50, 30, 25))
        p.setBrush(grad); p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
        p.setBrush(QColor(120, 20, 30)); p.drawRect(QRectF(w/2 - 15, -h/2, 8, h))
