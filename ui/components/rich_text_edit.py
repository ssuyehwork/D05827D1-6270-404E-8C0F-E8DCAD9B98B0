# -*- coding: utf-8 -*-
# ui/components/rich_text_edit.py

from PyQt5.QtWidgets import QTextEdit, QRubberBand
from PyQt5.QtGui import QImage, QColor, QTextCharFormat, QTextCursor, QPainter, QTextImageFormat, QTextBlockFormat, QTextListFormat
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, QPoint, QRect
import markdown2
from .syntax_highlighter import MarkdownHighlighter

class ImageResizer(QRubberBand):
    def __init__(self, parent=None, cursor=None, image_format=None):
        super().__init__(QRubberBand.Rectangle, parent)
        self.editor = parent
        self.cursor = cursor
        self.image_format = image_format
        self.current_image_name = image_format.name()
        
        self.original_width = image_format.width()
        self.original_height = image_format.height()
        self.aspect_ratio = self.original_height / self.original_width if self.original_width > 0 else 1.0
        
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.start_rect = QRect()
        
        self.show()
        self.update_geometry()

    def update_geometry(self):
        rect = self.editor.cursorRect(self.cursor)
        w = int(self.image_format.width())
        h = int(self.image_format.height())
        self.setGeometry(rect.x(), rect.y(), w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if (self.width() - event.pos().x() < 20) and (self.height() - event.pos().y() < 20):
                self.dragging = True
                self.drag_start_pos = event.globalPos()
                self.start_rect = self.geometry()
                event.accept()
            else:
                self.editor.deselect_image()
        
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.drag_start_pos
            new_w = max(50, self.start_rect.width() + delta.x())
            new_h = int(new_w * self.aspect_ratio)
            self.resize(new_w, new_h)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            self._apply_new_size()
            
    def _apply_new_size(self):
        new_fmt = QTextImageFormat(self.image_format)
        new_fmt.setWidth(self.width())
        new_fmt.setHeight(self.height())
        new_fmt.setName(self.current_image_name)
        
        c = QTextCursor(self.cursor)
        c.setPosition(self.cursor.position())
        c.setPosition(self.cursor.position() + 1, QTextCursor.KeepAnchor)
        c.insertImage(new_fmt)
        
        image_name = new_fmt.name()
        self.editor.document().addResource(3, image_name, self.editor.document().resource(3, image_name))
        
        self.image_format = new_fmt
        self.cursor = QTextCursor(c)
        self.cursor.setPosition(c.position() - 1)
        self.update_geometry()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(Qt.blue)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, self.width()-1, self.height()-1)
        painter.setBrush(Qt.blue)
        painter.drawRect(self.width()-10, self.height()-10, 10, 10)

class RichTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_resizer = None
        
        # 初始化 Markdown 高亮器 (确保 syntax_highlighter.py 已经更新!)
        self.highlighter = MarkdownHighlighter(self.document())
        
        self.is_markdown_preview = False
        self._source_text = ""

        # 样式设置，确保背景色不干扰
        self.setStyleSheet("""
            QTextEdit { border: none; color: #dddddd; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

    # --- Markdown 增强功能 ---
    def toggle_markdown_preview(self):
        """切换 Markdown 源码编辑与 HTML 预览"""
        if not self.is_markdown_preview:
            # 进入预览模式
            self._source_text = self.toPlainText()
            try:
                # 使用 markdown2 转 HTML
                html_content = markdown2.markdown(
                    self._source_text, 
                    extras=["fenced-code-blocks", "tables", "strike", "task_list"]
                )
                
                # 预览样式 CSS
                css = """
                <style>
                    body { font-family: "Microsoft YaHei"; color: #ddd; font-size: 14px; }
                    code { background-color: #333; padding: 2px 4px; border-radius: 3px; font-family: Consolas; color: #98C379; }
                    pre { background-color: #1e1e1e; padding: 10px; border-radius: 5px; border: 1px solid #444; color: #ccc; }
                    blockquote { border-left: 4px solid #569CD6; padding-left: 10px; color: #888; background: #252526; }
                    a { color: #4a90e2; text-decoration: none; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #444; padding: 6px; }
                    th { background-color: #333; }
                </style>
                """
                self.setHtml(css + html_content)
                self.setReadOnly(True)
                self.is_markdown_preview = True
            except Exception as e:
                print(f"Markdown preview error: {e}")
        else:
            # 返回编辑模式
            self.setReadOnly(False)
            self.setPlainText(self._source_text)
            self.highlighter.setDocument(self.document()) # 重新绑定高亮器
            self.is_markdown_preview = False

    def insert_todo(self):
        """插入待办事项 Checkbox"""
        cursor = self.textCursor()
        # 如果当前行不是空的且不在开头，先换行
        if not cursor.atBlockStart():
            cursor.insertText("\n")
        cursor.insertText("- [ ] ")
        self.setTextCursor(cursor)
        self.setFocus()

    # --- 原有功能保持 ---
    def mousePressEvent(self, event):
        if self.is_markdown_preview: return 
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            image_fmt = fmt.toImageFormat()
            self.select_image(cursor, image_fmt)
            return
            
        self.deselect_image()
        super().mousePressEvent(event)

    def select_image(self, cursor, image_fmt):
        self.deselect_image()
        self.current_resizer = ImageResizer(self, cursor, image_fmt)
        self.current_resizer.show()

    def deselect_image(self):
        if self.current_resizer:
            self.current_resizer.close()
            self.current_resizer = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.current_resizer:
            self.deselect_image()
            return
        super().keyPressEvent(event)
        
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            menu.addSeparator()
            target_cursor = QTextCursor(cursor)
            target_fmt = QTextImageFormat(fmt.toImageFormat())
            restore_action = menu.addAction("还原原始大小")
            restore_action.triggered.connect(lambda checked=False, c=target_cursor, f=target_fmt: self._restore_image_size(c, f))
            
        menu.exec_(event.globalPos())
        
    def _restore_image_size(self, cursor, image_fmt):
        try:
            image_name = image_fmt.name()
            image_variant = self.document().resource(3, image_name)
            if not image_variant: return
            
            image = image_variant
            if hasattr(image, 'toImage'): image = image.toImage()
            if not isinstance(image, QImage) or image.isNull(): return
            
            new_fmt = QTextImageFormat(image_fmt)
            new_fmt.setWidth(image.width())
            new_fmt.setHeight(image.height())
            new_fmt.setName(image_name)
            
            c = QTextCursor(cursor)
            if c.position() < self.document().characterCount():
                c.setPosition(cursor.position())
                c.setPosition(cursor.position() + 1, QTextCursor.KeepAnchor)
                c.insertImage(new_fmt)
            self.deselect_image()
        except Exception: pass

    def highlight_selection(self, color_str):
        cursor = self.textCursor()
        if not cursor.hasSelection(): return
        fmt = QTextCharFormat()
        if not color_str: fmt.setBackground(Qt.transparent)
        else: fmt.setBackground(QColor(color_str))
        cursor.mergeCharFormat(fmt)
        self.setTextCursor(cursor)

    def canInsertFromMimeData(self, source):
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage):
                byte_array = QByteArray()
                buffer = QBuffer(byte_array)
                buffer.open(QIODevice.WriteOnly)
                image.save(buffer, "PNG")
                self.image_data = byte_array.data()

                cursor = self.textCursor()
                max_width = self.viewport().width() - 40
                if image.width() > max_width:
                    scale = max_width / image.width()
                    scaled_image = image.scaled(
                        int(max_width), 
                        int(image.height() * scale),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    cursor.insertImage(scaled_image)
                else:
                    cursor.insertImage(image)
                return
        super().insertFromMimeData(source)

    def get_image_data(self): return self.image_data

    def set_image_data(self, data):
        self.image_data = data
        if data:
            image = QImage()
            image.loadFromData(data)
            if not image.isNull():
                self.clear()
                cursor = self.textCursor()
                max_width = self.viewport().width() - 40
                if image.width() > max_width:
                    scale = max_width / image.width()
                    scaled_image = image.scaled(int(max_width), int(image.height() * scale), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    cursor.insertImage(scaled_image)
                else:
                    cursor.insertImage(image)

    def toggle_list(self, list_style):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        current_list = cursor.currentList()
        if current_list:
             fmt = current_list.format()
             if fmt.style() == list_style:
                 block_fmt = QTextBlockFormat()
                 block_fmt.setObjectIndex(-1)
                 cursor.setBlockFormat(block_fmt)
             else:
                 fmt.setStyle(list_style)
                 current_list.setFormat(fmt)
        else:
             list_fmt = QTextListFormat()
             list_fmt.setStyle(list_style)
             cursor.createList(list_fmt)
        cursor.endEditBlock()