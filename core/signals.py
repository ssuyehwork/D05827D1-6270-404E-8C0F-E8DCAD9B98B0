# core/signals.py
from PyQt5.QtCore import QObject, pyqtSignal

class AppSignals(QObject):
    # 定义一个名为 data_changed 的信号，无参数
    data_changed = pyqtSignal()

# 创建一个全局单例，方便在应用各处统一调用
app_signals = AppSignals()
