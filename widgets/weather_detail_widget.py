#!/usr/bin/env python3
"""
Weather Detail Widget - 天気詳細ページUI

5日間×8時間の詳細天気情報を表示するQWidget
QStackedWidget統合用のページウィジェット

機能:
- 5日間の詳細天気予報表示（40データポイント）
- スクロール対応レイアウト
- 戻るボタンでメインダッシュボードに復帰
- Weather Iconsフォント統合
"""

import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor
from logging_system import get_logger


class WeatherDetailWidget(QWidget):
    """天気詳細ページウィジェット"""
    
    # シグナル定義
    back_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # ログシステム初期化
        self.logger = get_logger("weather_detail_widget")
        
        # UI初期化
        self.init_ui()
        self.setup_styles()
        
        self.logger.info("WeatherDetailWidget初期化完了")
    
    def init_ui(self):
        """UI初期化 - 1画面固定レイアウト（スクロールなし）"""
        # メインレイアウト
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # ヘッダー作成
        header = self.create_header()
        main_layout.addWidget(header)
        
        # 固定コンテンツエリア（スクロールなし）
        self.content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.content_widget)
        self.scroll_layout.setContentsMargins(10, 5, 10, 5)  # コンパクトマージン
        self.scroll_layout.setSpacing(5)  # コンパクトスペース
        
        # メインレイアウトに追加
        main_layout.addWidget(self.content_widget)
    
    def create_header(self) -> QWidget:
        """ヘッダー作成 - タイトル・戻るボタン"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setObjectName("weather_detail_header")
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)
        
        # 戻るボタン
        self.back_button = QPushButton("← 戻る")
        self.back_button.setFixedSize(120, 50)
        self.back_button.setObjectName("back_button")
        self.back_button.clicked.connect(self.on_back_clicked)
        layout.addWidget(self.back_button)
        
        # タイトル
        title_label = QLabel("天気詳細 - 3日間予報 - 降水確率,気温,風速")
        title_label.setObjectName("detail_title")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 更新時刻表示（右側）
        self.update_time_label = QLabel("--:--")
        self.update_time_label.setObjectName("header_update_time")
        self.update_time_label.setAlignment(Qt.AlignCenter)
        self.update_time_label.setFixedWidth(80)
        layout.addWidget(self.update_time_label)
        
        return header
    
    
    def setup_styles(self):
        """スタイル設定"""
        self.setStyleSheet("""
            /* メインウィジェット */
            WeatherDetailWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1a1a1a,
                    stop:1 #2d2d2d
                );
                color: #FFFFFF;
            }
            
            /* ヘッダー */
            QFrame#weather_detail_header {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #333333,
                    stop:1 #1a1a1a
                );
                border-bottom: 2px solid #444444;
            }
            
            /* タイトル */
            QLabel#detail_title {
                font-size: 24px;
                font-weight: bold;
                color: #FFFFFF;
            }
            
            /* ヘッダー更新時刻 */
            QLabel#header_update_time {
                font-size: 14px;
                color: #CCCCCC;
                font-weight: normal;
            }
            
            /* 戻るボタン */
            QPushButton#back_button {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a90e2,
                    stop:1 #357abd
                );
                border: 2px solid #2968a3;
                border-radius: 25px;
                color: #FFFFFF;
                font-size: 16px;
                font-weight: bold;
            }
            
            QPushButton#back_button:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5ba0f2,
                    stop:1 #4a90e2
                );
            }
            
            QPushButton#back_button:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #357abd,
                    stop:1 #2968a3
                );
            }
            
            /* スクロールエリア */
            QScrollArea {
                border: none;
                background: transparent;
            }
            
        """)
    
    def on_back_clicked(self):
        """戻るボタンクリック処理"""
        self.logger.info("戻るボタンがクリックされました")
        self.back_requested.emit()
    
    def clear_scroll_content(self):
        """スクロールコンテンツクリア"""
        try:
            # 既存のウィジェットを削除
            while self.scroll_layout.count():
                child = self.scroll_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            self.logger.debug("スクロールコンテンツクリア完了")
        except Exception as e:
            self.logger.error(f"スクロールコンテンツクリアエラー: {e}")
    
    def show_loading_message(self):
        """ローディングメッセージ表示"""
        self.clear_scroll_content()
        
        loading_label = QLabel("天気データを読み込み中...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("""
            font-size: 18px;
            color: #CCCCCC;
            padding: 50px;
        """)
        
        self.scroll_layout.addWidget(loading_label)
        self.scroll_layout.addStretch()
        
    
    def show_error_message(self, error_msg: str):
        """エラーメッセージ表示"""
        self.clear_scroll_content()
        
        error_label = QLabel(f"エラー: {error_msg}")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet("""
            font-size: 16px;
            color: #FF6B6B;
            padding: 50px;
        """)
        
        self.scroll_layout.addWidget(error_label)
        self.scroll_layout.addStretch()
        
    
    def update_footer_status(self, data_source: str, update_time: str):
        """ヘッダー更新時刻表示更新"""
        self.update_time_label.setText(update_time)