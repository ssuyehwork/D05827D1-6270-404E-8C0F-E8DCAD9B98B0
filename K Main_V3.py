# K Main_V3.py
import sys
import time
import logging
import traceback
import keyboard
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

# 导入核心组件
from core.container import AppContainer
from core.signals import app_signals
from ui.quick_window import QuickWindow
from ui.main_window import MainWindow
from ui.toolbox_window import ToolboxWindow
from ui.ball import FloatingBall
from core.settings import load_setting
from ui.utils import create_svg_icon

SERVER_NAME = "K_KUAIJIBIJI_SINGLE_INSTANCE_SERVER"

# --- Setup Logging ---
log_format = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
logging.basicConfig(filename='app_log.txt', level=logging.DEBUG, format=log_format, filemode='w')
def excepthook(exc_type, exc_value, exc_tb):
    logging.error("Unhandled exception:", exc_info=(exc_type, exc_value, exc_tb))
    traceback.print_exception(exc_type, exc_value, exc_tb)
sys.excepthook = excepthook
# --- End Logging Setup ---

# 用于在主线程中接收全局热键信号
class HotkeySignal(QObject):
    activated = pyqtSignal()
    favorite_last_idea_activated = pyqtSignal()

class AppManager(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        
        self.container = AppContainer()
        self.service = self.container.service
        
        self.main_window = None
        self.quick_window = None
        self.toolbox_window = None
        self.ball = None
        self.tray_icon = None
        
        self.hotkey_signal = HotkeySignal()
        self.hotkey_signal.activated.connect(self.toggle_quick_window)
        self.hotkey_signal.favorite_last_idea_activated.connect(self._favorite_last_idea)

    def _favorite_last_idea(self):
        try:
            c = self.service.idea_repo.db.get_cursor()
            c.execute("SELECT id FROM ideas WHERE is_deleted=0 ORDER BY created_at DESC LIMIT 1")
            result = c.fetchone()
            
            if result:
                last_idea_id = result[0]
                self.service.set_favorite(last_idea_id, True)
                logging.info(f"Successfully favorited last idea with ID: {last_idea_id}")
            else:
                logging.info("No ideas found to favorite.")
        except Exception as e:
            logging.error(f"Error while favoriting last idea: {e}", exc_info=True)

    def start(self):
        # 注入 Service
        self.main_window = MainWindow(self.service) 
        self.main_window.closing.connect(self.on_main_window_closing)

        self.ball = FloatingBall(self.main_window)
        self._setup_ball_menu()
        self._restore_ball_position()
        self.ball.show()

        self.quick_window = QuickWindow(self.service) 
        self.quick_window.toggle_main_window_requested.connect(self.toggle_main_window)
        
        self.toolbox_window = ToolboxWindow()

        # Connect toolbox signals
        self.main_window.header.toolbox_requested.connect(self.toggle_toolbox_window)
        self.quick_window.toolbar.toolbox_requested.connect(self.toggle_toolbox_window)

        self.quick_window.cm.data_captured.connect(self._on_clipboard_data_captured)
        
        self._init_tray_icon()
        
        # --- [核心修复] 信号同步网络 ---
        # 1. 监听全局信号 -> 刷新所有窗口
        app_signals.data_changed.connect(self.main_window._refresh_all)
        app_signals.data_changed.connect(self.quick_window._update_list)
        app_signals.data_changed.connect(self.quick_window.refresh_sidebar)
        
        # 2. 监听侧边栏局部信号 -> 触发全局信号
        # 这样，当你在 MainWindow 修改分类时，QuickWindow 也会收到通知
        self.main_window.sidebar.data_changed.connect(app_signals.data_changed.emit)
        self.quick_window.sidebar.data_changed.connect(app_signals.data_changed.emit)

        # 注册全局热键 Alt+Space
        try:
            keyboard.add_hotkey('alt+space', self._on_hotkey_triggered, suppress=False)
            logging.info("Global hotkey Alt+Space registered successfully")
        except Exception as e:
            logging.error(f"Failed to register hotkey Alt+Space: {e}", exc_info=True)

        try:
            keyboard.add_hotkey('ctrl+shift+e', lambda: self.hotkey_signal.favorite_last_idea_activated.emit(), suppress=False)
            logging.info("Global hotkey Ctrl+Shift+E registered successfully")
        except Exception as e:
            logging.error(f"Failed to register hotkey Ctrl+Shift+E: {e}", exc_info=True)

        self.show_quick_window()

    def _setup_ball_menu(self):
        original_context_menu = self.ball.contextMenuEvent
        def enhanced_context_menu(e):
            m = QMenu(self.ball)
            m.setStyleSheet("""
                QMenu { 
                    background-color: #2b2b2b; 
                    color: #f0f0f0; 
                    border: 1px solid #444; 
                    border-radius: 5px; 
                    padding: 5px; 
                }
                QMenu::item { 
                    padding: 6px 15px 6px 5px; 
                    border-radius: 3px;
                }
                QMenu::item:selected { 
                    background-color: #5D4037; 
                    color: #fff; 
                }
                QMenu::separator { 
                    background-color: #444; 
                    height: 1px; 
                    margin: 4px 0; 
                }
            """)
            skin_menu = m.addMenu(create_svg_icon('display.svg'), "切换外观")
            a1 = skin_menu.addAction(create_svg_icon('coffee.svg'), "摩卡·勃艮第"); a1.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_MOCHA))
            a2 = skin_menu.addAction(create_svg_icon('grid.svg'), "经典黑金"); a2.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_CLASSIC))
            a3 = skin_menu.addAction(create_svg_icon('book.svg'), "皇家蓝"); a3.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_ROYAL))
            a4 = skin_menu.addAction(create_svg_icon('leaf.svg'), "抹茶绿"); a4.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_MATCHA))
            a5 = skin_menu.addAction(create_svg_icon('book-open.svg'), "摊开手稿"); a5.triggered.connect(lambda: self.ball.switch_skin(self.ball.SKIN_OPEN))

            m.addSeparator()
            m.addAction(create_svg_icon('zap.svg'), '打开快速笔记', self.ball.request_show_quick_window.emit)
            m.addAction(create_svg_icon('monitor.svg'), '打开主界面', self.ball.request_show_main_window.emit)
            m.addAction(create_svg_icon('action_add.svg'), '新建灵感', self.main_window.new_idea)
            m.addSeparator()
            m.addAction(create_svg_icon('power.svg'), '退出', self.ball.request_quit_app.emit)
            m.exec_(e.globalPos())

        self.ball.contextMenuEvent = enhanced_context_menu
        self.ball.request_show_quick_window.connect(self.show_quick_window)
        self.ball.double_clicked.connect(self.show_quick_window)
        self.ball.request_show_main_window.connect(self.show_main_window)
        self.ball.request_quit_app.connect(self.quit_application)

    def _restore_ball_position(self):
        ball_pos = load_setting('floating_ball_pos')
        if ball_pos and isinstance(ball_pos, dict) and 'x' in ball_pos and 'y' in ball_pos:
            self.ball.move(ball_pos['x'], ball_pos['y'])
        else:
            g = QApplication.desktop().screenGeometry()
            self.ball.move(g.width()-80, g.height()//2)

    def _on_hotkey_triggered(self):
        self.hotkey_signal.activated.emit()

    def _init_tray_icon(self):
        temp_ball = FloatingBall(None)
        temp_ball.timer.stop()
        temp_ball.is_writing = False
        temp_ball.pen_angle = -45
        temp_ball.pen_x = 0; temp_ball.pen_y = 0; temp_ball.book_y = 0
        pixmap = QPixmap(temp_ball.size()); pixmap.fill(Qt.transparent); temp_ball.render(pixmap)
        dynamic_icon = QIcon(pixmap)
        
        self.app.setWindowIcon(dynamic_icon)
        if self.main_window:
            self.main_window.refresh_logo()
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(dynamic_icon)
        self.tray_icon.setToolTip("快速笔记")
        
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #2D2D2D; color: #EEE; border: 1px solid #444; } QMenu::item { padding: 6px 24px; } QMenu::item:selected { background-color: #4a90e2; color: white; }")
        
        action_show = menu.addAction("显示主界面"); action_show.triggered.connect(self.show_main_window)
        action_quick = menu.addAction("显示快速笔记"); action_quick.triggered.connect(self.show_quick_window)
        menu.addSeparator()
        action_quit = menu.addAction("退出程序"); action_quit.triggered.connect(self.quit_application)
        
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger: self.show_quick_window()

    def _on_clipboard_data_captured(self, idea_id):
        self.ball.trigger_clipboard_feedback()

    def _force_activate(self, window):
        if not window: return
        window.show()
        if window.isMinimized(): window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        window.showNormal(); window.raise_(); window.activateWindow()

    def show_quick_window(self): self._force_activate(self.quick_window)
    def toggle_quick_window(self):
        if self.quick_window and self.quick_window.isVisible(): self.quick_window.hide()
        else: self.show_quick_window()
    def show_main_window(self): self._force_activate(self.main_window)
    def toggle_main_window(self):
        if self.main_window.isVisible() and not self.main_window.isMinimized(): self.main_window.hide()
        else: self.show_main_window()

    def toggle_toolbox_window(self):
        if self.toolbox_window.isVisible():
            self.toolbox_window.hide()
        else:
            self._force_activate(self.toolbox_window)
            # Position it near the quick window for context
            if self.quick_window.isVisible():
                quick_pos = self.quick_window.pos()
                self.toolbox_window.move(quick_pos.x() - self.toolbox_window.width() - 10, quick_pos.y())

    def on_main_window_closing(self):
        if self.main_window: self.main_window.hide()
    def quit_application(self):
        logging.info("Application quit requested")
        try: keyboard.unhook_all()
        except: pass
        
        if self.quick_window:
            try: self.quick_window.save_state()
            except: pass
        if self.main_window:
            try: self.main_window.save_state()
            except: pass
        self.app.quit()

def main():
    app = QApplication(sys.argv)
    socket = QLocalSocket(); socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(b'EXIT'); socket.flush(); socket.waitForBytesWritten(1000)
        socket.disconnectFromServer(); time.sleep(0.5)
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer(); server.listen(SERVER_NAME)
    manager = AppManager(app)
    def handle_new_connection():
        conn = server.nextPendingConnection()
        if conn and conn.waitForReadyRead(500):
            msg = conn.readAll().data().decode()
            if msg == 'SHOW': manager.show_quick_window()
            elif msg == 'EXIT': manager.quit_application()
    server.newConnection.connect(handle_new_connection)
    manager.start()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()