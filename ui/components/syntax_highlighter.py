# -*- coding: utf-8 -*-
# ui/components/syntax_highlighter.py

import re
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        # --- 1. 标题 (Headers) ---
        # 匹配 # 开头，蓝色，加粗
        headerFormat = QTextCharFormat()
        headerFormat.setForeground(QColor("#569CD6")) 
        headerFormat.setFontWeight(QFont.Bold)
        self.rules.append((re.compile(r"^#{1,6}\s.*"), headerFormat))

        # --- 2. 粗体 (**bold**) ---
        # 匹配 **中间的内容**，红色，加粗
        boldFormat = QTextCharFormat()
        boldFormat.setFontWeight(QFont.Bold)
        boldFormat.setForeground(QColor("#E06C75")) 
        self.rules.append((re.compile(r"\*\*.*?\*\*"), boldFormat))

        # --- 3. 待办事项 ([ ] [x]) ---
        # 未完成，黄色
        uncheckedFormat = QTextCharFormat()
        uncheckedFormat.setForeground(QColor("#E5C07B")) 
        self.rules.append((re.compile(r"-\s\[\s\]"), uncheckedFormat))
        
        # 已完成，绿色
        checkedFormat = QTextCharFormat()
        checkedFormat.setForeground(QColor("#6A9955")) 
        self.rules.append((re.compile(r"-\s\[x\]"), checkedFormat))

        # --- 4. 代码块 (``` ... ```) ---
        # 绿色，等宽字体
        codeFormat = QTextCharFormat()
        codeFormat.setForeground(QColor("#98C379")) 
        codeFormat.setFontFamily("Consolas") 
        # 注意：这里处理简单的多行代码块会有局限，但在 QSyntaxHighlighter 中
        # 使用多行正则比较复杂，这里先确保单行 ``` 和行内 `code` 能亮
        self.rules.append((re.compile(r"`[^`]+`"), codeFormat)) 
        self.rules.append((re.compile(r"```.*"), codeFormat)) # 简单的代码块头

        # --- 5. 引用 (> Quote) ---
        # 灰色，斜体
        quoteFormat = QTextCharFormat()
        quoteFormat.setForeground(QColor("#808080")) 
        quoteFormat.setFontItalic(True)
        self.rules.append((re.compile(r"^\s*>.*"), quoteFormat))
        
        # --- 6. 列表项 (- item) ---
        # 紫色
        listFormat = QTextCharFormat()
        listFormat.setForeground(QColor("#C678DD")) 
        self.rules.append((re.compile(r"^\s*[\-\*]\s"), listFormat))

    def highlightBlock(self, text):
        """
        使用 Python 的 re 模块进行匹配，速度快且语法支持全。
        """
        for pattern, format in self.rules:
            # 使用 finditer 查找所有匹配项
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, format)