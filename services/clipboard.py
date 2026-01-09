# -*- coding: utf-8 -*-
# services/clipboard.py
import datetime
import os
import uuid
import hashlib
import logging
from PyQt5.QtCore import QObject, pyqtSignal, QBuffer
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

class ClipboardManager(QObject):
    """
    管理剪贴板数据,处理数据并将其存入数据库。
    """
    data_captured = pyqtSignal(int)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self._last_hash = None

    def _hash_data(self, data):
        """为数据创建一个统一的哈希值以检查重复。"""
        try:
            if isinstance(data, QImage):
                # 【安全规范】禁止使用MD5,必须使用SHA256
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                data.save(buffer, "PNG")
                return hashlib.sha256(buffer.data()).hexdigest()
            return hashlib.sha256(str(data).encode('utf-8')).hexdigest()
        except Exception as e:
            logging.error(f"Failed to hash data: {e}", exc_info=True)
            return None

    def process_clipboard(self, mime_data, category_id=None):
        """
        处理来自剪贴板的 MIME 数据。
        """
        # 【关键修复】正确的逻辑:只屏蔽应用自己的窗口
        # 检查当前活动窗口是否是应用自己的窗口
        active_win = QApplication.activeWindow()
        if active_win is not None:
            # 导入窗口类进行类型检查(延迟导入避免循环依赖)
            try:
                from ui.main_window import MainWindow
                from ui.quick_window import QuickWindow
                if isinstance(active_win, (MainWindow, QuickWindow)):
                    # 是应用自己的窗口,不处理剪贴板(避免内部复制操作)
                    return
            except ImportError as e:
                logging.warning(f"Failed to import window classes for clipboard check: {e}")

        extra_tags = set() # 用于收集智能分析的标签

        try:
            # --- 优先处理 文件/文件夹 ---
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                
                if filepaths:
                    content = ";".join(filepaths)
                    current_hash = self._hash_data(content)
                    
                    if current_hash is None:
                        logging.error("Failed to hash file paths, skipping clipboard processing")
                        return
                    
                    if current_hash != self._last_hash:
                        
                        # 【优化逻辑:扩展名作为类型记录】
                        detected_type = 'file' # 默认
                        
                        # 分析文件类型
                        exts = set()
                        is_folder = False
                        for path in filepaths:
                            if os.path.isdir(path):
                                is_folder = True
                            elif os.path.isfile(path):
                                ext = os.path.splitext(path)[1].lower().lstrip('.')
                                if ext: exts.add(ext)
                        
                        # 决定最终记录的类型
                        if is_folder and not exts:
                            detected_type = 'folder'
                        elif len(exts) == 1:
                            detected_type = list(exts)[0] # 单一类型直接用扩展名
                        elif len(exts) > 1:
                            detected_type = 'files' # 多种类型混合
                        
                        try:
                            # 将 detected_type 传入 item_type
                            result = self.db.add_clipboard_item(item_type=detected_type, content=content, category_id=category_id)
                            self._last_hash = current_hash
                            
                            if result:
                                idea_id, is_new = result
                                if is_new:
                                    # 注意：不再将扩展名作为标签添加
                                    self.data_captured.emit(idea_id)
                        except Exception as e:
                            logging.error(f"Failed to save file clipboard item: {e}", exc_info=True)
                        return

            # --- 处理图片 ---
            if mime_data.hasImage():
                try:
                    image = mime_data.imageData()
                    buffer = QBuffer()
                    buffer.open(QBuffer.ReadWrite)
                    image.save(buffer, "PNG")
                    image_bytes = buffer.data()
                    
                    # 【安全规范】禁止使用MD5,必须使用SHA256
                    current_hash = hashlib.sha256(image_bytes).hexdigest()
                    
                    if current_hash != self._last_hash:
                        result = self.db.add_clipboard_item(item_type='image', content='[Image Data]', data_blob=image_bytes, category_id=category_id)
                        self._last_hash = current_hash
                        
                        if result:
                            idea_id, is_new = result
                            if is_new:
                                self.data_captured.emit(idea_id)
                        return
                except Exception as e:
                    logging.error(f"Failed to process image from clipboard: {e}", exc_info=True)
                    return

            # --- 处理文本 (含网址识别) ---
            if mime_data.hasText():
                try:
                    text = mime_data.text()
                    if not text.strip(): 
                        return
                    
                    current_hash = self._hash_data(text)
                    if current_hash is None:
                        logging.error("Failed to hash text, skipping clipboard processing")
                        return
                        
                    if current_hash != self._last_hash:
                        
                        # 【智能打标逻辑:网址】
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
                                    try:
                                        self.db.add_tags_to_multiple_ideas([idea_id], list(extra_tags))
                                    except Exception as e:
                                        logging.error(f"Failed to add tags to idea {idea_id}: {e}", exc_info=True)
                                self.data_captured.emit(idea_id)
                        return
                except Exception as e:
                    logging.error(f"Failed to process text from clipboard: {e}", exc_info=True)
                    return

        except Exception as e:
            logging.error(f"Unexpected error in clipboard processing: {e}", exc_info=True)