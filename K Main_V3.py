# K Main_V3.py (已修改为非模态)

import sys
import time
import os
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QDialog
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from ui.quick_window import QuickWindow
from ui.main_window import MainWindow
from ui.ball import FloatingBall
from ui.action_popup import ActionPopup
from ui.common_tags_manager import CommonTagsManager
from ui.advanced_tag_selector import AdvancedTagSelector
from data.db_manager import DatabaseManager
from core.settings import load_setting

SERVER_NAME = "K_KUAIJIBIJI_SINGLE_INSTANCE_SERVER"

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
        try:
            self.db_manager = DatabaseManager()
        except Exception as e:
            pass
            sys.exit(1)

        logo_path = os.path.join("assets", "logo.svg")
        if os.path.exists(logo_path):
            app_icon = QIcon(logo_path)
            self.app.setWindowIcon(app_icon)
        else:
            app_icon = QIcon()
        
        self.app.setApplicationName("")
        self.app.setApplicationDisplayName("")
        self.app.setOrganizationName("RapidNotes")
        self.app.setOrganizationDomain("rapidnotes.local")

        self._init_tray_icon(app_icon)

        self.main_window = MainWindow()
        self.main_window.closing.connect(self.on_main_window_closing)

        self.ball = FloatingBall(self.main_window)
        
        original_context_menu = self.ball.contextMenuEvent
        def new_context_menu(e):
            m = QMenu(self.ball)
            m.setStyleSheet("""
                QMenu { background-color: #1a1a1a; color: #00f3ff; border: 1px solid #333; padding: 5px; }
                QMenu::item { padding: 5px 20px; }
                QMenu::item:selected { background-color: #00f3ff; color: #000; border-radius: 2px;}
                QMenu::separator { background-color: #333; height: 1px; margin: 5px 0; }
            """)
            m.addAction('⚡ 打开快速笔记', self.ball.request_show_quick_window.emit)
            m.addAction('💻 打开主界面', self.ball.request_show_main_window.emit)
            m.addAction('➕ 新建灵感', self.main_window.new_idea)
            m.addSeparator()
            m.addAction('🏷️ 管理常用标签', self._open_common_tags_manager)
            m.addSeparator()
            m.addAction('❌ 退出', self.ball.request_quit_app.emit)
            m.exec_(e.globalPos())
        
        self.ball.contextMenuEvent = new_context_menu
        self.ball.request_show_quick_window.connect(self.show_quick_window)
        self.ball.double_clicked.connect(self.show_quick_window)
        self.ball.request_show_main_window.connect(self.show_main_window)
        self.ball.request_quit_app.connect(self.quit_application)
        
        ball_pos = load_setting('floating_ball_pos')
        if ball_pos and isinstance(ball_pos, dict) and 'x' in ball_pos and 'y' in ball_pos:
            self.ball.move(ball_pos['x'], ball_pos['y'])
        else:
            g = QApplication.desktop().screenGeometry()
            self.ball.move(g.width()-80, g.height()//2)
            
        self.ball.show()

        self.quick_window = QuickWindow(self.db_manager)
        # 连接到 toggle_main_window
        self.quick_window.toggle_main_window_requested.connect(self.toggle_main_window)
        
        self.popup = ActionPopup() 
        self.popup.request_favorite.connect(self._handle_popup_favorite)
        self.popup.request_tag_toggle.connect(self._handle_popup_tag_toggle)
        self.popup.request_manager.connect(self._open_common_tags_manager)
        
        self.quick_window.cm.data_captured.connect(self._on_clipboard_data_captured)
        
        self.show_quick_window()

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
        if self.tags_manager_dialog and self.tags_manager_dialog.isVisible():
            self._force_activate(self.tags_manager_dialog)
            return

        self.tags_manager_dialog = CommonTagsManager()
        self.tags_manager_dialog.finished.connect(self._on_tags_manager_closed)
        self.tags_manager_dialog.show()
        self._force_activate(self.tags_manager_dialog)

    def _on_tags_manager_closed(self, result):
        if result == QDialog.Accepted:
            if self.popup:
                self.popup.common_tags_bar.reload_tags()
        self.tags_manager_dialog = None

    def _on_clipboard_data_captured(self, idea_id):
        self.ball.trigger_clipboard_feedback()
        if self.popup:
            self.popup.show_at_mouse(idea_id)

    def _handle_popup_favorite(self, idea_id):
        self.db_manager.set_favorite(idea_id, True)
        if self.main_window.isVisible():
            self.main_window._load_data()
            self.main_window.sidebar.refresh()

    def _handle_popup_tag_toggle(self, idea_id, tag_name, checked):
        if checked:
            self.db_manager.add_tags_to_multiple_ideas([idea_id], [tag_name])
        else:
            self.db_manager.remove_tag_from_multiple_ideas([idea_id], tag_name)
            
        if self.main_window.isVisible():
            self.main_window._load_data()
            self.main_window._refresh_tag_panel()

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

    # 【修改】修复后的切换逻辑
    def toggle_main_window(self):
        # 1. 如果窗口可见 且 没有最小化 -> 视为"激活/开启"状态 -> 执行关闭
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.main_window.hide()
        # 2. 否则(隐藏 或 最小化) -> 执行开启并激活
        else:
            self.show_main_window()

    def on_main_window_closing(self):
        if self.main_window:
            self.main_window.hide()
            
    def quit_application(self):
        if self.quick_window:
            try:
                self.quick_window.save_state()
            except: pass
        if self.main_window:
            try:
                self.main_window.save_state()
            except: pass
        self.app.quit()

def main():
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
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
