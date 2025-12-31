# services/clipboard_service.py
import os
from PyQt5.QtCore import QObject, pyqtSignal, QBuffer
from PyQt5.QtGui import QImage

class ClipboardService(QObject):
    data_captured = pyqtSignal()

    def __init__(self, idea_repo, tag_repo, hash_calculator):
        super().__init__()
        self.idea_repo = idea_repo
        self.tag_repo = tag_repo
        self.hasher = hash_calculator

    def process_mime_data(self, mime_data, category_id=None):
        try:
            if mime_data.hasUrls():
                urls = mime_data.urls()
                filepaths = [url.toLocalFile() for url in urls if url.isLocalFile()]
                if filepaths:
                    content = ";".join(filepaths)
                    self._save_clipboard_item('file', content, category_id=category_id)
                    return

            if mime_data.hasImage():
                image = mime_data.imageData()
                buffer = QBuffer()
                buffer.open(QBuffer.ReadWrite)
                image.save(buffer, "PNG")
                image_bytes = buffer.data()
                self._save_clipboard_item('image', '[Image Data]', data_blob=image_bytes, category_id=category_id)
                return

            if mime_data.hasText():
                text = mime_data.text()
                if text:
                    self._save_clipboard_item('text', text, category_id=category_id)
                    return
        except Exception as e:
            # Proper logging should be added here
            print(f"Error processing clipboard data: {e}")

    def _save_clipboard_item(self, item_type, content, data_blob=None, category_id=None):
        content_hash = self.hasher.compute(content, data_blob)
        if not content_hash:
            return

        existing_idea = self.idea_repo.find_by_hash(content_hash)

        if existing_idea:
            idea_id = existing_idea[0]
            self.idea_repo.update_timestamp(idea_id)
            print(f"Clipboard content already exists, timestamp updated for ID={idea_id}")
            return idea_id
        else:
            if item_type == 'text':
                title = content.strip().split('\\n')[0][:50]
            elif item_type == 'image':
                title = "[图片]"
            elif item_type == 'file':
                title = f"[文件] {os.path.basename(content.split(';')[0])}"
            else:
                title = "未命名"
            
            idea_id = self.idea_repo.add(
                title=title,
                content=content,
                color='#696969', # Use dark gray for clipboard items
                category_id=category_id,
                item_type=item_type,
                data_blob=data_blob,
                content_hash=content_hash,
                source='clipboard'
            )
            
            # Automatically add "剪贴板" tag
            existing_tags = self.tag_repo.get_tags_for_idea(idea_id)
            if "剪贴板" not in existing_tags:
                existing_tags.append("剪贴板")
                self.tag_repo.update_tags_for_idea(idea_id, existing_tags)
            
            self.data_captured.emit()
            print(f"New clipboard item saved with ID={idea_id}")
            return idea_id
