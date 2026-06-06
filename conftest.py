#!/usr/bin/env python3
"""
pytest設定ファイル
PyQt5テスト環境設定（ヘッドレス対応）
"""

import os
import sys
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# ヘッドレス環境での PyQt5 設定
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

@pytest.fixture(scope="session", autouse=True)
def qapp():
    """
    PyQt5アプリケーション初期化（セッション全体で共有）
    ヘッドレス環境対応
    """
    if not QApplication.instance():
        app = QApplication(sys.argv)
        app.setAttribute(Qt.AA_Use96Dpi, True)
        app.processEvents()
        yield app
        app.quit()
    else:
        yield QApplication.instance()

@pytest.fixture(autouse=True)
def qt_cleanup():
    """各テスト後のQt クリーンアップ"""
    yield
    if QApplication.instance():
        QApplication.instance().processEvents()