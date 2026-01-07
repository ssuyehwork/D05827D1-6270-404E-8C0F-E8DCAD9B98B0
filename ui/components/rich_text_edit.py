from PyQt5.QtWidgets import QTextEdit, QRubberBand, QMenu, QAction
from PyQt5.QtGui import QImage, QColor, QTextCharFormat, QTextCursor, QPainter, QMouseEvent, QTextImageFormat, QTextListFormat, QTextBlockFormat
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QIODevice, QSize, QPoint, QRect

class ImageResizer(QRubberBand):
    def __init__(self, parent=None, cursor=None, image_format=None):
        super().__init__(QRubberBand.Rectangle, parent)
        self.editor = parent
        self.cursor = cursor  # 指向图片的 TextCursor
        self.image_format = image_format
        self.current_image_name = image_format.name()
        
        # 初始尺寸
        self.original_width = image_format.width()
        self.original_height = image_format.height()
        self.aspect_ratio = self.original_height / self.original_width if self.original_width > 0 else 1.0
        
        # 拖拽状态
        self.dragging = False
        self.drag_start_pos = QPoint()
        self.start_rect = QRect()
        
        self.show()
        self.update_geometry()

    def update_geometry(self):
        # 根据 cursor 计算图片在 viewport 中的位置
        rect = self.editor.cursorRect(self.cursor)
        # cursorRect 返回的是光标位置（一条线），我们需要图片的实际矩形
        # 实际上对于 ImageResource，我们需要更复杂的计算，或者利用 cursorRect 的位置
        # 这里简化：假设我们已知宽高
        w = int(self.image_format.width())
        h = int(self.image_format.height())
        # cursorRect 通常在图片的右侧，我们需要调整
        # 但对于 Block 中的 Image，cursorRect 可能就是图片区域？
        # 不，QTextEdit 中图片通常是一个字符。
        
        # 更准确的方法是：
        # 使用 editor.cursorRect(cursor) 得到位置，然后结合 width/height
        self.setGeometry(rect.x(), rect.y(), w, h)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 简单实现：点击右下角区域作为调整大小
            if (self.width() - event.pos().x() < 20) and (self.height() - event.pos().y() < 20):
                self.dragging = True
                self.drag_start_pos = event.globalPos()
                self.start_rect = self.geometry()
                event.accept()
            else:
                # 点击其他地方，可能是想取消选中或移动
                self.editor.deselect_image()
                # 转发事件给 editor? 其实不需要，并在点击外部时由 editor 处理
        
    def mouseMoveEvent(self, event):
        if self.dragging:
            delta = event.globalPos() - self.drag_start_pos
            new_w = max(50, self.start_rect.width() + delta.x())
            new_h = int(new_w * self.aspect_ratio) # 保持比例
            
            self.resize(new_w, new_h)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.dragging = False
            # 应用新的尺寸到文档
            self._apply_new_size()
            
    def _apply_new_size(self):
        # 更新 ImageFormat
        new_fmt = QTextImageFormat(self.image_format)
        new_fmt.setWidth(self.width())
        new_fmt.setHeight(self.height())
        new_fmt.setName(self.current_image_name) # 保持名字很重要
        
        # 我们必须操作 document
        # 使用 cursor 选中该图片字符，然后 setCharFormat (其实是 mergeCharFormat 不适用 ImageFormat 的属性更新?)
        # 实际上更新图片大小比较 tricky，最稳妥是替换
        c = QTextCursor(self.cursor)
        c.setPosition(self.cursor.position()) # 确保位置正确
        c.setPosition(self.cursor.position() + 1, QTextCursor.KeepAnchor) # 选中图片字符
        c.setCharFormat(new_fmt) # 这里可能不管用，对于 ImageFormat 需要用 mergeBlockCharFormat? 不，直接替换更好?
        
        # 更好的方法: 替换图片
        # 但为了避免重新加载闪烁，PyQt 的 QTextImageFormat 属性修改后，如果不重新 insert 可能不刷新。
        # 试试最直接的: insertImage 替换
        # c.insertImage(new_fmt) 
        # 但这样会导致 cursor 丢失。
        
        # 正确做法：
        image_name = new_fmt.name()
        self.editor.document().addResource(3, image_name, self.editor.document().resource(3, image_name)) # 刷新资源? 不
        
        c.insertImage(new_fmt)
        
        # 更新内部状态
        self.image_format = new_fmt
        self.cursor = QTextCursor(c) # 更新 cursor 位置（因为它动了）
        self.cursor.setPosition(c.position() - 1) # 回退到图片前
        
        # 重新定位 Resizer
        self.update_geometry()

    def paintEvent(self, event):
        # 绘制边框和手柄
        painter = QPainter(self)
        painter.setPen(Qt.blue)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, self.width()-1, self.height()-1)
        
        # 右下角手柄
        painter.setBrush(Qt.blue)
        painter.drawRect(self.width()-10, self.height()-10, 10, 10)

class RichTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_data = None
        self.current_resizer = None
        
        # 添加滚动条样式
        self.setStyleSheet("""
            QTextEdit {
                border: none;
            }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #444; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

    def mousePressEvent(self, event):
        # 检测点击图片
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            image_fmt = fmt.toImageFormat()
            # 选中图片
            self.select_image(cursor, image_fmt)
            return # 吞掉事件，防止光标移动导致取消选中? 
            # 或者我们只在点击确切是图片时拦截。
            
        # 点击非图片区域，取消选中
        self.deselect_image()
        super().mousePressEvent(event)

    def select_image(self, cursor, image_fmt):
        self.deselect_image()
        
        # 创建调整器
        # 注意: cursor 位置是在图片字符之前还是之后? need careful handling
        # cursorForPosition 返回的 cursor 通常在字符之间。
        # 我们需要确保 cursor 指向图片字符的开始。
        
        # 简单处理: 我们假设 clicked on image implies that the char to the right (or left) is the image.
        # But cursorForPosition is precise.
        
        # 调整 cursor 选中该图片
        # 如果是点在图片上，cursor通常在图片后面？
        # 让我们获取确切的 ImageFormat
        
        self.current_resizer = ImageResizer(self, cursor, image_fmt)
        self.current_resizer.show()

    def deselect_image(self):
        if self.current_resizer:
            self.current_resizer.close()
            self.current_resizer = None

    def keyPressEvent(self, event):
         # ESC 取消选中
        if event.key() == Qt.Key_Escape and self.current_resizer:
            self.deselect_image()
            return
        super().keyPressEvent(event)
        
    def contextMenuEvent(self, event):
        # 增强右键菜单
        menu = self.createStandardContextMenu()
        
        # 检查是否点击了图片
        cursor = self.cursorForPosition(event.pos())
        fmt = cursor.charFormat()
        
        if fmt.isImageFormat():
            menu.addSeparator()
            # 显式拷贝对象，防止 C++ 对象释放导致的野指针崩溃
            target_cursor = QTextCursor(cursor)
            target_fmt = QTextImageFormat(fmt.toImageFormat())
            
            restore_action = menu.addAction("还原原始大小")
            # lambda 接收 checked 参数，并使用默认参数锁定对象副本
            restore_action.triggered.connect(lambda checked=False, c=target_cursor, f=target_fmt: self._restore_image_size(c, f))
            
        menu.exec_(event.globalPos())
        
    def _restore_image_size(self, cursor, image_fmt):
        try:
            image_name = image_fmt.name()
            # 3 = QTextDocument.ImageResource
            image_variant = self.document().resource(3, image_name)
            
            if not image_variant:
                return
                
            # PyQt5 中 resource 可能返回 QVariant，需要解包
            image = image_variant
            if hasattr(image, 'toImage'): # 如果是 QVariant
                image = image.toImage()
                
            # 再次检查
            if not isinstance(image, QImage) or image.isNull():
                return
            
            new_fmt = QTextImageFormat(image_fmt)
            new_fmt.setWidth(image.width())
            new_fmt.setHeight(image.height())
            new_fmt.setName(image_name) # 确保名字一致
            
            c = QTextCursor(cursor)
            # 确保光标位置有效
            if c.position() < self.document().characterCount():
                c.setPosition(cursor.position())
                c.setPosition(cursor.position() + 1, QTextCursor.KeepAnchor)
                c.insertImage(new_fmt)
                
            self.deselect_image()
        except Exception as e:
            pass

    def highlight_selection(self, color_str):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
            
        fmt = QTextCharFormat()
        if not color_str:
            fmt.setBackground(Qt.transparent)
        else:
            fmt.setBackground(QColor(color_str))
            
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

    def get_image_data(self):
        return self.image_data

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
                    scaled_image = image.scaled(
                        int(max_width),
                        int(image.height() * scale),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
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
                 # 取消列表: 将当前块格式重置
                 # 实际上比较复杂，简单做法是创建一个新的 BlockFormat
                 block_fmt = QTextBlockFormat()
                 block_fmt.setObjectIndex(-1) # 移除列表关联
                 cursor.setBlockFormat(block_fmt)
             else:
                 fmt.setStyle(list_style)
                 current_list.setFormat(fmt)
        else:
             list_fmt = QTextListFormat()
             list_fmt.setStyle(list_style)
             cursor.createList(list_fmt)
             
        cursor.endEditBlock()

