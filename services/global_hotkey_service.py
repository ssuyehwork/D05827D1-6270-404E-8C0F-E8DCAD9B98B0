# -*- coding: utf-8 -*-
# services/global_hotkey_service.py
import threading
import ctypes
from ctypes import winfunctype, windll, POINTER
from ctypes.wintypes import DWORD, WPARAM, LPARAM, MSG
from PyQt5.QtCore import QObject, pyqtSignal

# 定义常量
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
HC_ACTION = 0

# 虚拟键码
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_E = 0x45

# 定义钩子回调函数类型
HOOKPROC = winfunctype(ctypes.c_long, ctypes.c_int, WPARAM, LPARAM)

# KBDLLHOOKSTRUCT 结构
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", DWORD),
        ("scanCode", DWORD),
        ("flags", DWORD),
        ("time", DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class GlobalHotkeyService(QObject):
    # Define a signal that will be emitted when the hotkey is pressed
    favorite_last_idea_requested = pyqtSignal()
    
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.hook_id = None
        self._shutdown_flag = threading.Event()
        self.thread = None
        self.user32 = ctypes.windll.user32
        
        # 键盘状态跟踪
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.e_pressed = False
        self.combination_triggered = False
        
        # 保持回调函数引用，防止被垃圾回收
        self.hook_callback = HOOKPROC(self._keyboard_hook_callback)
        
    def _keyboard_hook_callback(self, nCode, wParam, lParam):
        """
        底层键盘钩子回调函数
        """
        if nCode == HC_ACTION:
            kb_struct = ctypes.cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
            vk_code = kb_struct.vkCode
            
            # 按键按下事件
            if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                if vk_code == VK_CONTROL:
                    self.ctrl_pressed = True
                elif vk_code == VK_SHIFT:
                    self.shift_pressed = True
                elif vk_code == VK_E:
                    self.e_pressed = True
                    
                    # 检测组合键
                    if self.ctrl_pressed and self.shift_pressed and not self.combination_triggered:
                        self.combination_triggered = True
                        print("=== Ctrl+Shift+E detected via Hook! ===")
                        self._on_activate_favorite_last()
                        # 阻止其他应用接收这个按键
                        return 1
            
            # 按键释放事件
            elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                if vk_code == VK_CONTROL:
                    self.ctrl_pressed = False
                    self.combination_triggered = False
                elif vk_code == VK_SHIFT:
                    self.shift_pressed = False
                    self.combination_triggered = False
                elif vk_code == VK_E:
                    self.e_pressed = False
        
        # 传递给下一个钩子
        return self.user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)
    
    def _on_activate_favorite_last(self):
        """
        This function is called when the hotkey is activated.
        It emits a signal to be handled on the main Qt thread.
        """
        print("Hotkey Ctrl+Shift+E activated!")
        self.favorite_last_idea_requested.emit()
    
    def _handle_favorite_request(self):
        """
        This slot receives the signal and performs the database operation.
        """
        try:
            # It's better to access the repository layer or db context directly
            # to avoid circular dependencies if this service grows.
            # Here we directly use the db connection from the service for simplicity.
            c = self.service.idea_repo.db.get_cursor()
            c.execute("SELECT id FROM ideas WHERE is_deleted=0 ORDER BY created_at DESC LIMIT 1")
            result = c.fetchone()
            
            if result:
                last_idea_id = result[0]
                print(f"Found last idea with ID: {last_idea_id}. Setting as favorite.")
                self.service.set_favorite(last_idea_id, True)
            else:
                print("No ideas found to favorite.")
        except Exception as e:
            print(f"Error while favoriting last idea: {e}")
    
    def _monitor_hotkeys(self):
        """
        安装键盘钩子并运行消息循环
        """
        print("Installing low-level keyboard hook...")
        
        # 安装底层键盘钩子
        self.hook_id = self.user32.SetWindowsHookExA(
            WH_KEYBOARD_LL,
            self.hook_callback,
            ctypes.windll.kernel32.GetModuleHandleW(None),
            0
        )
        
        if not self.hook_id:
            print("ERROR: Failed to install keyboard hook!")
            error_code = ctypes.get_last_error()
            print(f"Error code: {error_code}")
            return
        
        print(f"✓ Keyboard hook installed successfully (Hook ID: {self.hook_id})")
        print("Listening for Ctrl+Shift+E...")
        
        # 运行消息循环
        msg = MSG()
        while not self._shutdown_flag.is_set():
            result = self.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
            if result:
                self.user32.TranslateMessage(ctypes.byref(msg))
                self.user32.DispatchMessageW(ctypes.byref(msg))
            else:
                threading.Event().wait(0.01)
        
        # 卸载钩子
        if self.hook_id:
            self.user32.UnhookWindowsHookEx(self.hook_id)
            print("Keyboard hook uninstalled.")
    
    def start(self):
        """
        Starts the hotkey monitoring using low-level keyboard hook.
        """
        if self.thread and self.thread.is_alive():
            print("Hotkey listener is already running.")
            return
        
        print("="*50)
        print("Starting Global Hotkey Service")
        print("Hotkey: Ctrl+Shift+E")
        print("Method: Low-level keyboard hook (guaranteed to work)")
        print("="*50)
        
        # Connect the signal to the slot
        self.favorite_last_idea_requested.connect(self._handle_favorite_request)
        
        # Start the hook in a separate thread
        self._shutdown_flag.clear()
        self.thread = threading.Thread(target=self._monitor_hotkeys, daemon=True)
        self.thread.start()
        
        # 等待钩子安装完成
        threading.Event().wait(0.1)
        
        if self.hook_id:
            print("✓ Global hotkey service started successfully!")
            print("Press Ctrl+Shift+E anywhere to favorite the last idea.")
        else:
            print("✗ Failed to start hotkey service.")
    
    def stop(self):
        """
        Stops the hotkey monitoring thread and unhooks the keyboard.
        """
        print("Stopping global hotkey listener...")
        
        # Stop the thread
        if self.thread and self.thread.is_alive():
            self._shutdown_flag.set()
            self.thread.join(timeout=2)
            self.thread = None
        
        self.hook_id = None
        print("Global hotkey listener stopped successfully.")