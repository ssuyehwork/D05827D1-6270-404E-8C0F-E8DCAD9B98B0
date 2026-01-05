# -*- coding: utf-8 -*-
# ui/components/syntax_highlighter.py

from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt5.QtCore import QRegExp

class SimpleHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        # 1. 关键词 (蓝色)
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) 
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "def", "class", "if", "else", "elif", "try", "except", "return", 
            "import", "from", "while", "for", "in", "True", "False", "None", 
            "and", "or", "not", "lambda", "with", "as", "pass", "break",
            "print", "range", "len", "self", "super"
        ]
        for word in keywords:
            pattern = QRegExp(r"\b" + word + r"\b")
            self.highlightingRules.append((pattern, keywordFormat))

        # 2. 字符串 (橙红色)
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178"))
        self.highlightingRules.append((QRegExp(r"\".*\""), stringFormat))
        self.highlightingRules.append((QRegExp(r"'.*'"), stringFormat))

        # 3. 注释 (绿色)
        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955"))
        self.highlightingRules.append((QRegExp(r"#[^\n]*"), commentFormat))
        self.highlightingRules.append((QRegExp(r"//[^\n]*"), commentFormat))
        
        # 4. 数字 (浅绿色)
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8"))
        self.highlightingRules.append((QRegExp(r"\b[0-9]+\b"), numberFormat))
        
        # 5. 函数调用 (黄色)
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA"))
        self.highlightingRules.append((QRegExp(r"\b[A-Za-z0-9_]+(?=\()"), functionFormat))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)