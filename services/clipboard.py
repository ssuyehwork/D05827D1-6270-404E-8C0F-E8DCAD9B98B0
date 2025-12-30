# services/clipboard.py
import datetime
import os
import uuid
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QImage
# from data.db_manager import DatabaseManager # 假设的导入

class ClipboardManager(QObject):
    """
    管理剪贴板数据，处理数据并将其存入数据库。
    """
    data_captured = pyqtSignal()

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        # 使用一个简单的哈希值来避免在内存中存储大的剪贴板内容
        self._last_hash = None

    def _hash_data(self, data):
        """为数据创建一个简单的哈希值以检查重复。"""
        if isinstance(data, QImage):
            # 对图片，哈希其原始字节数据
            return hash(data.bits().tobytes())
        return hash(str(data))

    def process_clipboard(self, mime_data, category_id=None):
        """
        处理来自剪贴板的 MIME 数据。
        """
        current_hash = None

        try:
            # 优先处理 URL，因为它们也可能包含文本
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                
                if filepaths:
                    content = ";".join(filepaths)
                    current_hash = self._hash_data(content)
                    if current_hash != self._last_hash:
                        print(f"[Clipboard] 捕获到文件: {content}")
                        # self.db.add_item(item_type='file', content=content, category_id=category_id)
                        self._last_hash = current_hash
                        self.data_captured.emit()
                        return # 在此停止处理

            # 处理图片
            if mime_data.hasImage():
                image = mime_data.imageData()
                current_hash = self._hash_data(image)
                if current_hash != self._last_hash:
                    print("[Clipboard] 捕获到图片。")
                    # 实际应用中，我们会将图片保存到文件并存储路径，
                    # 或者直接将 blob 存入数据库。
                    # self.db.add_item(item_type='image', image_data=image.bits().tobytes(), category_id=category_id)
                    self._last_hash = current_hash
                    self.data_captured.emit()
                    return

            # 处理文本 (如果不是文件路径)
            if mime_data.hasText():
                text = mime_data.text()
                current_hash = self._hash_data(text)
                if text and current_hash != self._last_hash:
                    print(f"[Clipboard] 捕获到文本: {text[:70]}...")
                    # self.db.add_item(item_type='text', content=text, category_id=category_id)
                    self._last_hash = current_hash
                    self.data_captured.emit()
                    return

        except Exception as e:
            print(f"处理剪贴板数据时出错: {e}")
