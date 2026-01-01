# -*- coding: utf-8 -*-
# services/clipboard.py
import datetime
import os
import uuid
import hashlib
from PyQt5.QtCore import QObject, pyqtSignal, QBuffer
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

class ClipboardManager(QObject):
    """
    管理剪贴板数据，处理数据并将其存入数据库。
    """
    data_captured = pyqtSignal(int)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self._last_hash = None

    def _hash_data(self, data):
        """为数据创建一个简单的哈希值以检查重复。"""
        if isinstance(data, QImage):
            return hash(data.bits().tobytes())
        return hashlib.md5(str(data).encode('utf-8')).hexdigest()

    def process_clipboard(self, mime_data, category_id=None):
        """
        处理来自剪贴板的 MIME 数据。
        """
        # 1. 屏蔽内部操作
        if QApplication.activeWindow() is not None:
            return

        extra_tags = set() # 用于收集智能分析的标签

        try:
            # --- 优先处理 文件/文件夹 ---
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                
                if filepaths:
                    content = ";".join(filepaths)
                    current_hash = self._hash_data(content)
                    
                    if current_hash != self._last_hash:
                        print(f"[Clipboard] 捕获到文件/文件夹: {content}")
                        
                        # 【智能打标逻辑：文件与文件夹】
                        for path in filepaths:
                            if os.path.isdir(path):
                                extra_tags.add("文件夹")
                            elif os.path.isfile(path):
                                # 提取扩展名，转小写，去点
                                ext = os.path.splitext(path)[1].lower().lstrip('.')
                                if ext:
                                    extra_tags.add(ext)

                        result = self.db.add_clipboard_item(item_type='file', content=content, category_id=category_id)
                        self._last_hash = current_hash
                        
                        if result:
                            idea_id, is_new = result
                            if is_new:
                                # 【应用智能标签】
                                if extra_tags:
                                    self.db.add_tags_to_multiple_ideas([idea_id], list(extra_tags))
                                self.data_captured.emit(idea_id)
                        return

            # --- 处理图片 ---
            if mime_data.hasImage():
                image = mime_data.imageData()
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                image.save(buffer, "PNG")
                image_bytes = buffer.data()
                
                current_hash = hashlib.md5(image_bytes).hexdigest()
                
                if current_hash != self._last_hash:
                    print("[Clipboard] 捕获到图片。")
                    result = self.db.add_clipboard_item(item_type='image', content='[Image Data]', data_blob=image_bytes, category_id=category_id)
                    self._last_hash = current_hash
                    
                    if result:
                        idea_id, is_new = result
                        if is_new:
                            self.data_captured.emit(idea_id)
                    return

            # --- 处理文本 (含网址识别) ---
            if mime_data.hasText():
                text = mime_data.text()
                if not text.strip(): return
                
                current_hash = self._hash_data(text)
                if current_hash != self._last_hash:
                    print(f"[Clipboard] 捕获到文本: {text[:30]}...")
                    
                    # 【智能打标逻辑：网址】
                    stripped_text = text.strip()
                    if stripped_text.startswith(('http://', 'https://')):
                        extra_tags.add("网址")
                        extra_tags.add("链接")
                    
                    result = self.db.add_clipboard_item(item_type='text', content=text, category_id=category_id)
                    self._last_hash = current_hash
                    
                    if result:
                        idea_id, is_new = result
                        if is_new:
                            # 【应用智能标签】
                            if extra_tags:
                                self.db.add_tags_to_multiple_ideas([idea_id], list(extra_tags))
                            self.data_captured.emit(idea_id)
                    return

        except Exception as e:
            print(f"处理剪贴板数据时出错: {e}")