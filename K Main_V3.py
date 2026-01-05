# K Main_V3.py (集成高清动态图标 + 多选标签逻辑)

import sys
import time
import os
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QDialog
from PyQt5.QtCore import QObject, Qt, QRectF
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QLinearGradient, 
                         QPainterPath, QPen, QBrush)
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from ui.quick_window import QuickWindow
from ui.main_window import MainWindow
from ui.ball import FloatingBall
from ui.action_popup import ActionPopup
from ui.common_tags_manager import CommonTagsManager
from ui.advanced_tag_selector import AdvancedTagSelector
from data.db_manager import DatabaseManager
from core.settings import load_setting
from core.logger import setup_logging, get_logger

SERVER_NAME = "K_KUAIJIBIJI_SINGLE_INSTANCE_SERVER"
logger = get_logger('Main')

def create_internal_icon():
    """动态绘制高清(128x128)的“笔记本+钢笔”图标"""
    size = 128
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.HighQualityAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    
    p.translate(size / 2, size / 2)
    p.scale(1.1, 1.1) 

    # 1. 笔记本
    w, h = 56, 76
    p.setBrush(QColor(192, 192, 192)) 
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(-w/2+5, -h/2+4, w, h), 3, 3)
    grad = QLinearGradient(-w, -h, w, h)
    grad.setColorAt(0, QColor(70, 40, 35))   
    grad.setColorAt(1, QColor(100, 60, 50))  
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(-w/2, -h/2, w, h), 3, 3)
    p.setBrush(QColor(160, 30, 40))
    p.drawRect(QRectF(w/2 - 14, -h/2, 8, h))

    # 2. 钢笔
    p.rotate(-45)
    p.translate(0, -8) 
    w_pen, h_pen = 14, 48 
    body_grad = QLinearGradient(-w_pen/2, 0, w_pen/2, 0)
    body_grad.setColorAt(0.0, QColor(200, 70, 80)) 
    body_grad.setColorAt(1.0, QColor(80, 10, 20)) 
    path_body = QPainterPath()
    path_body.addRoundedRect(QRectF(-w_pen/2, -h_pen/2, w_pen, h_pen), 6, 6)
    p.setBrush(body_grad)
    p.drawPath(path_body)
    path_tip = QPainterPath()
    tip_h = 16
    path_tip.moveTo(-w_pen/2 + 3, h_pen/2)
    path_tip.lineTo(w_pen/2 - 3, h_pen/2)
    path_tip.lineTo(0, h_pen/2 + tip_h)
    path_tip.closeSubpath()
    p.setBrush(QColor(255, 220, 100))
    p.drawPath(path_tip)
    p.setBrush(QColor(255, 215, 0))
    p.drawRect(QRectF(-w_pen/2, h_pen/2 - 5, w_pen, 5))
    
    p.end()
    return QIcon(pixmap)


class AppManager(QObject):

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.db_manager = None
        self.main_window = None
        self.quick_window = None
        self.ball = None
        self.popup = None 
        self.tray_icon = None
        self.tags_manager_dialog = None

    def start(self):
        logger.info("AppManager: 正在启动...")
        try:
            self.db_manager = DatabaseManager()
        except Exception as e:
            logger.critical(f"DB Error: {e}")
            sys.exit(1)

        app_icon = create_internal_icon()
        self.app.setWindowIcon(app_icon)
        
        self.app.setApplicationName("RapidNotes")
        self.app.setApplicationDisplayName("RapidNotes")

        self._init_tray_icon(app_icon)

        self.main_window = MainWindow()
        self.main_window.closing.connect(self.on_main_window_closing)

        self.ball = FloatingBall(self.main_window)
        
        self.ball.request_show_quick_window.connect(self.show_quick_window)
        self.ball.double_clicked.connect(self.show_quick_window)
        self.ball.request_show_main_window.connect(self.show_main_window)
        self.ball.request_quit_app.connect(self.quit_application)
        self.ball.request_manage_tags.connect(self._open_common_tags_manager) 
        
        ball_pos = load_setting('floating_ball_pos')
        if ball_pos and isinstance(ball_pos, dict) and 'x' in ball_pos and 'y' in ball_pos:
            self.ball.move(ball_pos['x'], ball_pos['y'])
        else:
            g = QApplication.desktop().screenGeometry()
            self.ball.move(g.width()-80, g.height()//2)
            
        self.ball.show()

        self.quick_window = QuickWindow(self.db_manager)
        self.quick_window.toggle_main_window_requested.connect(self.toggle_main_window)
        
        self.popup = ActionPopup() 
        self.popup.request_favorite.connect(self._handle_popup_favorite)
        self.popup.request_tag_toggle.connect(self._handle_popup_tag_toggle)
        self.popup.request_manager.connect(self._open_common_tags_manager)
        
        self.quick_window.cm.data_captured.connect(self._on_clipboard_data_captured)
        
        self.show_quick_window()
        logger.info("AppManager: 启动完成")

    def _init_tray_icon(self, icon):
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("快速笔记")
        
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; }
            QMenu::item { padding: 6px 24px; }
            QMenu::item:selected { background-color: #4a90e2; color: white; }
        """)
        
        action_show = menu.addAction("显示主界面")
        action_show.triggered.connect(self.show_main_window)
        
        action_quick = menu.addAction("显示快速笔记")
        action_quick.triggered.connect(self.show_quick_window)
        
        menu.addSeparator()
        
        action_quit = menu.addAction("退出程序")
        action_quit.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_quick_window()

    def _open_common_tags_manager(self):
        try:
            if self.tags_manager_dialog and self.tags_manager_dialog.isVisible():
                self._force_activate(self.tags_manager_dialog)
                return

            self.tags_manager_dialog = CommonTagsManager()
            self.tags_manager_dialog.finished.connect(self._on_tags_manager_closed)
            self.tags_manager_dialog.show()
            self._force_activate(self.tags_manager_dialog)
        except Exception as e:
            logger.error(f"TagManager Error: {e}")

    def _on_tags_manager_closed(self, result):
        if result == QDialog.Accepted:
            if self.popup:
                self.popup.common_tags_bar.reload_tags()
        self.tags_manager_dialog = None

    def _on_clipboard_data_captured(self, idea_id):
        try:
            logger.info(f"Clipboard Captured: ID {idea_id}")
            self.ball.trigger_clipboard_feedback()
            if self.popup:
                self.popup.show_at_mouse(idea_id)
        except Exception as e:
            logger.error(f"Capture Handler Error: {e}")

    def _handle_popup_favorite(self, idea_id, is_favorite):
        try:
            self.db_manager.set_favorite(idea_id, is_favorite)
            if self.main_window.isVisible():
                self.main_window._refresh_all()
            if self.quick_window.isVisible():
                self.quick_window._update_list()
        except Exception as e:
            logger.error(f"Fav Error: {e}")

    def _handle_popup_tag_toggle(self, idea_id, tag_name, checked):
        try:
            if checked:
                self.db_manager.add_tags_to_multiple_ideas([idea_id], [tag_name])
            else:
                self.db_manager.remove_tag_from_multiple_ideas([idea_id], tag_name)
                
            if self.main_window.isVisible():
                self.main_window._refresh_all()
            if self.quick_window.isVisible():
                self.quick_window._update_list()
        except Exception as e:
            logger.error(f"Tag Toggle Error: {e}")

    def _force_activate(self, window):
        if not window: return
        window.show()
        if window.isMinimized():
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            window.showNormal()
        window.raise_()
        window.activateWindow()

    def show_quick_window(self):
        self._force_activate(self.quick_window)

    def toggle_quick_window(self):
        if self.quick_window and self.quick_window.isVisible():
            self.quick_window.hide()
        else:
            self.show_quick_window()

    def show_main_window(self):
        self._force_activate(self.main_window)

    def toggle_main_window(self):
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.main_window.hide()
        else:
            self.show_main_window()

    def on_main_window_closing(self):
        if self.main_window:
            self.main_window.hide()
            
    def quit_application(self):
        logger.info("App: 准备退出...")
        if self.quick_window:
            try: self.quick_window.save_state()
            except: pass
        if self.main_window:
            try: self.main_window.save_state()
            except: pass
        self.app.quit()

def main():
    setup_logging()
    
    app = QApplication(sys.argv)
    
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(b'SHOW')
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        sys.exit(0)
    else:
        QLocalServer.removeServer(SERVER_NAME)

    server = QLocalServer()
    if not server.listen(SERVER_NAME):
        pass
    
    manager = AppManager(app)

    def handle_new_connection():
        conn = server.nextPendingConnection()
        if conn and conn.waitForReadyRead(500):
            msg = conn.readAll().data().decode()
            if msg == 'SHOW':
                manager.show_quick_window()
            elif msg == 'EXIT':
                manager.quit_application()
    server.newConnection.connect(handle_new_connection)
    
    manager.start()
    
    exit_code = app.exec_()
    logger.info(f"App: 退出码 {exit_code}")
    sys.exit(exit_code)

if __name__ == '__main__':
    main()