# -*- coding: utf-8 -*-
# ui/platform_utils.py

import sys
import ctypes
from ctypes import wintypes
import time

# --- Platform-specific setup for Windows ---
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    KEYEVENTF_KEYUP = 0x0002
    VK_CONTROL = 0x11
    VK_V = 0x56
    
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010
    SWP_FLAGS = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),      
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT)
        ]
    
    user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.SetFocus.argtypes = [wintypes.HWND]
    user32.SetFocus.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]

else:
    # Define dummy objects for non-Windows platforms to prevent crashes
    user32 = None
    kernel32 = None

class PlatformUtils:
    """
    Encapsulates platform-specific code, primarily for Windows.
    This includes monitoring active windows, simulating paste operations,
    and controlling window flags like 'stay on top'.
    """
    def __init__(self):
        self.is_windows = sys.platform == "win32"
        self.my_hwnd = None
        self.last_active_hwnd = None
        self.last_focus_hwnd = None
        self.last_thread_id = None

    def set_my_hwnd(self, hwnd):
        """Sets the window handle of the application's own window."""
        self.my_hwnd = hwnd

    def monitor_foreground_window(self):
        """
        Monitors the foreground window to capture the context for the paste operation.
        """
        if not self.is_windows: return
        
        current_hwnd = user32.GetForegroundWindow()
        # Ignore if no window is in foreground or if it's our own window
        if current_hwnd == 0 or current_hwnd == self.my_hwnd: return
        
        if current_hwnd != self.last_active_hwnd:
            self.last_active_hwnd = current_hwnd
            self.last_thread_id = user32.GetWindowThreadProcessId(current_hwnd, None)
            self.last_focus_hwnd = None 

    def paste_in_previous_window(self):
        """
        Activates the last-focused external window and sends a Ctrl+V command.
        This simulates a 'Ditto-style' paste.
        """
        if not self.is_windows: return

        target_win = self.last_active_hwnd
        target_focus = self.last_focus_hwnd
        target_thread = self.last_thread_id
        
        if not target_win or not user32.IsWindow(target_win): return
        
        curr_thread = kernel32.GetCurrentThreadId()
        attached = False
        # Attach to the target window's thread to send input
        if target_thread and curr_thread != target_thread:
            attached = user32.AttachThreadInput(curr_thread, target_thread, True)
        
        try:
            # Restore the window if it's minimized
            if user32.IsIconic(target_win): 
                user32.ShowWindow(target_win, 9) # SW_RESTORE
            # Bring the window to the foreground
            user32.SetForegroundWindow(target_win)
            
            if target_focus and user32.IsWindow(target_focus):
                user32.SetFocus(target_focus)
            
            # Simulate Ctrl+V keypress
            time.sleep(0.1) # A small delay to ensure the window is ready
            user32.keybd_event(VK_CONTROL, 0, 0, 0)
            user32.keybd_event(VK_V, 0, 0, 0)
            user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
        except Exception as e:
            # In a real app, you might want to log this
            print(f"❌ Paste operation failed: {e}")
        finally:
            # Detach the thread input
            if attached:
                user32.AttachThreadInput(curr_thread, target_thread, False)

    def set_window_topmost(self, hwnd, is_topmost):
        """
        Sets the window's 'stay on top' property.
        """
        if not self.is_windows: return
        
        flag = HWND_TOPMOST if is_topmost else HWND_NOTOPMOST
        user32.SetWindowPos(hwnd, flag, 0, 0, 0, 0, SWP_FLAGS)
