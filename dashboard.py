#!/usr/bin/env python3
"""
Raspberry Pi ダッシュボード - 正しい時刻部分と動作するセンサー部分の組み合わせ
品質改善プロジェクト Phase 1.1.1 対応 - 構造化ログ統合
"""

import sys
import json
import os
import requests
from datetime import datetime
from calendar import Calendar
from logging_system import get_logger
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGridLayout, QFrame, QPushButton, QSizePolicy, QSpacerItem,
    QScrollArea
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
# Logic分離統一: Bridge importは削除、Logic classesを直接使用
from logic.data_transformation_logic import DataTransformationLogic
from logic.calculation_logic import CalculationLogic
from logic.file_processing_logic import FileProcessingLogic

class SensorDataThread(QThread):
    """センサーデータ取得用スレッド（Web監視グラフ統一方式）"""
    data_updated = pyqtSignal(dict)
    date_changed = pyqtSignal()  # 日付変更時のシグナルを追加
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger("webexactdashboard")
        self.logger = get_logger("calendardatathread")
        self.logger = get_logger("sensordatathread")
        self.running = True
        self.logger = get_logger("sensor_thread")
        self.last_check_date = datetime.now().date()  # 前回チェック日を記録
        # Logic分離統一: DataTransformationLogic 初期化
        self.data_transformation_logic = DataTransformationLogic()
        # Logic分離統一 Phase5: FileProcessingLogic 初期化
        self.file_processing_logic = FileProcessingLogic()
        
    def run(self):
        while self.running:
            try:
                # Web監視グラフと同じ統一JSONファイルから最新センサーデータを取得
                # この方式により、Web・Dashboard・将来のモバイルアプリが同じデータソースを利用
                
                # Logic分離統一 Phase5: FileProcessingLogicによる安全なmetrics.json読み込み
                metrics_data = self.file_processing_logic.load_metrics_json()
                
                if metrics_data:
                    latest_metric = metrics_data['metrics'][-1] if metrics_data.get('metrics') else {}
                else:
                    latest_metric = {}
                
                # DashboardのAPIレスポンス形式に変換
                temp = latest_metric.get('room_temperature')
                humidity = latest_metric.get('humidity')
                co2_ppm = latest_metric.get('co2_ppm')
                
                # Logic分離統一: 不快度指数計算をDataTransformationLogicに委譲
                discomfort_result = self.data_transformation_logic.calculate_discomfort_index(temp, humidity)
                discomfort_index = discomfort_result['discomfort_index']
                comfort_level = discomfort_result['comfort_level']
                
                # Logic分離統一: CO2レベル分類をDataTransformationLogicに委譲
                co2_result = self.data_transformation_logic.classify_co2_level(co2_ppm)
                co2_level = co2_result['co2_level']
                co2_color = co2_result['co2_color']
                co2_message = co2_result['co2_message']
                
                # JSONデータから直接Dashboard用データを構築
                dashboard_data = {
                    'status': 'success',
                    'data': {
                        'temperature': temp,
                        'humidity': humidity,
                        'discomfort_index': discomfort_index,
                        'comfort_level': comfort_level,
                        'co2_ppm': co2_ppm,
                        'co2_level': co2_level,
                        'co2_color': co2_color,
                        'co2_message': co2_message,
                        'timestamp': latest_metric.get('timestamp')
                    }
                }
                
                # 日付変更チェックをセンサーデータ更新時に追加
                current_date = datetime.now().date()
                if current_date != self.last_check_date:
                    self.logger.info(f"📅 日付変更検出 (センサー更新時): {self.last_check_date} → {current_date}")
                    self.last_check_date = current_date
                    self.date_changed.emit()  # 日付変更シグナルを送信
                
                self.data_updated.emit(dashboard_data)
                
                if latest_metric:
                    self.logger.info("統一JSONファイルからセンサーデータ取得",
                                    temperature=temp, humidity=humidity, co2_ppm=co2_ppm)
                else:
                    self.logger.warning("メトリクスデータが空です")
                    
            except Exception as e:
                self.logger.error(f"センサーデータ取得エラー: {e}")
            
            self.msleep(120000)  # 2分間隔（負荷軽減・適切な応答性確保）
    
    def stop(self):
        self.running = False

class CalendarDataThread(QThread):
    """カレンダーデータ取得用スレッド"""
    calendar_updated = pyqtSignal(dict)
    
    def __init__(self, year, month):
        super().__init__()
        self.year = year
        self.month = month
        self.logger = get_logger("calendar_thread")

        
    def generate_basic_calendar(self):
        """キャッシュなしでも即座に表示可能な基本カレンダー構造を生成"""
        try:
            import calendar
            from datetime import datetime, date
            
            # 月の基本情報を計算
            days_in_month = calendar.monthrange(self.year, self.month)[1]
            first_weekday = calendar.monthrange(self.year, self.month)[0]
            
            # 今日の情報
            today = datetime.now()
            today_year = today.year
            today_month = today.month
            today_day = today.day
            
            # 基本カレンダー構造
            calendar_data = {
                'year': self.year,
                'month': self.month,
                'days_in_month': days_in_month,
                'first_day_weekday': first_weekday,
                'days': {},
                'offline_mode': True,  # オフラインモードフラグ
                'calendar_data': {}  # 互換性のため
            }
            
            # 各日の基本情報を生成
            for day in range(1, days_in_month + 1):
                date_obj = date(self.year, self.month, day)
                weekday = date_obj.weekday()  # 0=月曜日, 6=日曜日
                
                # 今日かどうかをチェック
                is_today = (self.year == today_year and 
                           self.month == today_month and 
                           day == today_day)
                
                # 週末かどうかをチェック
                is_weekend = weekday >= 5  # 土曜日(5)、日曜日(6)
                
                day_data = {
                    'date': date_obj.strftime('%Y-%m-%d'),
                    'day': day,
                    'weekday': weekday,
                    'is_today': is_today,
                    'is_weekend': is_weekend,
                    'events': [],  # 空のイベントリスト
                    'holidays': [],  # 空の祝日リスト
                    'is_holiday': False,
                    'day_type': 'holiday' if is_weekend else 'weekday'
                }
                
                calendar_data['days'][day] = day_data
                calendar_data['calendar_data'][day] = day_data  # 互換性のため
            
            # 今日が含まれているかをチェック（ログ出力用）
            has_today = any(d['is_today'] for d in calendar_data['days'].values())
            
            # ログ出力（辞書のキーは文字列のみ）
            self.logger.info("基本カレンダー生成完了", 
                           calendar_year=self.year, 
                           calendar_month=self.month, 
                           total_days=days_in_month, 
                           includes_today=has_today)
            
            return calendar_data
            
        except Exception as e:
            self.logger.error("基本カレンダー生成エラー", 
                            calendar_year=self.year, 
                            calendar_month=self.month,
                            error_message=str(e))
            return None
        
    def run(self):
        try:
            self.logger.info("Calendar 先行表示開始", year=self.year, month=self.month)
            
            # ステップ1: 基本カレンダー構造を即座に表示（キャッシュなしでも表示）
            try:
                basic_calendar = self.generate_basic_calendar()
                if basic_calendar:
                    from datetime import datetime
                    api_format = {
                        'status': 'success',
                        'data': basic_calendar,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.calendar_updated.emit(api_format)
                    self.logger.info("基本カレンダー即座表示完了", year=self.year, month=self.month)
            except Exception as e:
                self.logger.warning("基本カレンダー表示エラー", error=str(e), year=self.year, month=self.month)
            
            # ステップ2: キャッシュ優先システムで拡張表示
            try:
                import sys
                sys.path.append('.')
                from calendar_cache_priority import get_calendar_cache_priority
                from datetime import datetime
                
                cache_priority = get_calendar_cache_priority()
                cache_result = cache_priority.get_calendar_with_cache_priority(self.year, self.month)
                
                if cache_result and cache_result.get('status') in ['success', 'fallback']:
                    self.logger.success("キャッシュ優先表示", 
                                      display_source=cache_result.get('cache_priority_status', {}).get('display_source', 'unknown'),
                                      year=self.year, month=self.month)
                    # キャッシュデータでカレンダー表示を更新
                    api_format = {
                        'status': 'success',
                        'data': cache_result,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.calendar_updated.emit(api_format)
                    return  # キャッシュ表示で完了
                else:
                    self.logger.info("キャッシュなし、API取得を試行", year=self.year, month=self.month)
            except Exception as e:
                self.logger.warning("キャッシュ優先表示エラー、API取得にフォールバック", error=str(e), year=self.year, month=self.month)
            
            # ステップ3: キャッシュなし時のAPI呼び出し（バックグラウンド）
            try:
                self.logger.info("Calendar API開始", year=self.year, month=self.month)
                params = {'year': self.year, 'month': self.month}
                response = requests.get('http://localhost:5000/api/calendar', params=params, timeout=5)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # APIレスポンス形式の検証
                        if 'status' in data and data['status'] == 'success' and 'data' in data:
                            self.logger.success("Calendar API成功", year=self.year, month=self.month)
                            self.calendar_updated.emit(data)
                        else:
                            self.logger.warning("Calendar APIレスポンス形式エラー", response_data=data, year=self.year, month=self.month)
                            # 基本カレンダーが既に表示されているのでエラー通知のみ
                    except json.JSONDecodeError as e:
                        self.logger.error("Calendar API JSON解析エラー", error=str(e), year=self.year, month=self.month)
                        # 基本カレンダーが既に表示されているのでエラー通知のみ
                else:
                    self.logger.error("Calendar APIエラー", 
                                    http_status=response.status_code, 
                                    response_preview=response.text[:200],
                                    year=self.year, month=self.month)
                    # 基本カレンダーが既に表示されているのでエラー通知のみ
            except requests.exceptions.Timeout:
                self.logger.warning("Calendar APIタイムアウト", year=self.year, month=self.month)
                # 基本カレンダーが既に表示されているのでエラー通知のみ
            except requests.exceptions.ConnectionError:
                self.logger.error("Calendar API接続エラー", year=self.year, month=self.month)
                # 基本カレンダーが既に表示されているのでエラー通知のみ
                
        except Exception as e:
            self.logger.exception("Calendar API例外エラー", error=str(e), year=self.year, month=self.month)
            # 最終フォールバック：基本カレンダーを表示
            try:
                basic_calendar = self.generate_basic_calendar()
                if basic_calendar:
                    from datetime import datetime
                    api_format = {
                        'status': 'success',
                        'data': basic_calendar,
                        'timestamp': datetime.now().isoformat()
                    }
                    self.calendar_updated.emit(api_format)
            except Exception:
                pass

class ClickableDayCell(QFrame):
    """タップ可能なカレンダー日付セル"""
    clicked = pyqtSignal(int, int, int)  # year, month, day

    def __init__(self, year, month, day, parent=None):
        super().__init__(parent)
        self._year = year
        self._month = month
        self._day = day

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._year, self._month, self._day)
        event.accept()


class EventPopupOverlay(QWidget):
    """メインウィンドウの子ウィジェットとして表示するオーバーレイ。
    別ウィンドウを作らないのでタッチ入力グラブが発生しない。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        # カード内のコンテンツを差し替えるためのコンテナ
        self._content_layout = None
        self._build_skeleton()

    def _build_skeleton(self):
        """固定レイアウト骨格を構築（コンテンツは show_for_day で差し替え）"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignCenter)

        self._card = QFrame(self)
        self._card.setFixedWidth(420)
        self._card.setStyleSheet(
            "QFrame { background: #1e2a3a; border-radius: 16px;"
            " border: 1px solid rgba(255,255,255,0.15); }"
        )
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(14)

        # タイトル行
        title_row = QHBoxLayout()
        self._title_label = QLabel()
        self._title_label.setStyleSheet(
            "color: white; font-size: 24px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        title_row.addWidget(self._title_label)
        title_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.1); color: white;"
            " border-radius: 18px; font-size: 18px; border: none; }"
            "QPushButton:pressed { background: rgba(255,255,255,0.3); }"
        )
        close_btn.clicked.connect(self._close)
        title_row.addWidget(close_btn)
        card_layout.addLayout(title_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(
            "background: rgba(255,255,255,0.2); border: none; max-height: 1px;"
        )
        card_layout.addWidget(sep)

        # イベントリスト用スクロールエリア
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll.setMaximumHeight(420)
        card_layout.addWidget(self._scroll)

        outer.addWidget(self._card)

    def show_for_day(self, year, month, day, events):
        """表示内容を更新して表示する"""
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        import calendar as cal_mod
        weekday = weekday_names[cal_mod.weekday(year, month, day)]
        self._title_label.setText(f"{month}月{day}日（{weekday}）")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 4, 0, 4)
        inner_layout.setSpacing(8)

        for ev in events:
            ev_title = ev['title'] if isinstance(ev, dict) else str(ev)
            time_str = ev.get('time_str') if isinstance(ev, dict) else None
            is_holiday = ev.get('is_holiday', False) if isinstance(ev, dict) else False

            title_color = "#ff9f9f" if is_holiday else "rgba(255,255,255,0.9)"
            title_lbl = QLabel(f"• {ev_title}")
            title_lbl.setStyleSheet(
                f"color: {title_color}; font-size: 20px;"
                " background: transparent; border: none;"
            )
            title_lbl.setWordWrap(True)
            inner_layout.addWidget(title_lbl)

            if time_str:
                time_lbl = QLabel(f"   {time_str}")
                time_lbl.setStyleSheet(
                    "color: rgba(255,255,255,0.55); font-size: 17px;"
                    " background: transparent; border: none;"
                )
                inner_layout.addWidget(time_lbl)

        inner_layout.addStretch()
        self._scroll.setWidget(inner)

        # 親サイズに合わせてオーバーレイを広げ、最前面に出す
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()
        self.setVisible(True)

    def _close(self):
        self.setVisible(False)

    def mousePressEvent(self, event):
        """カード外タップで閉じる"""
        if not self._card.geometry().contains(event.pos()):
            self._close()
        event.accept()


class WebExactDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 構造化ログシステム初期化
        self.logger = get_logger("dashboard")
        
        # フルスクリーン表示設定
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)
        
        # Logic分離統一: ビジネスロジッククラス初期化（init_ui前に必須）
        from logic.calendar_logic import CalendarLogic
        from logic.sensor_logic import SensorLogic
        from logic.style_logic import StyleLogic
        self.calendar_logic = CalendarLogic()
        self.sensor_logic = SensorLogic()
        self.data_transformation_logic = DataTransformationLogic()
        self.calculation_logic = CalculationLogic()
        self.style_logic = StyleLogic()
        # Logic分離統一 Phase5: FileProcessingLogic 初期化
        self.file_processing_logic = FileProcessingLogic()
        
        # UI状態管理（Logic分離統一後、直接のholidays管理は削除）
        self.current_date = datetime.now()  # 現在の日付を管理
        self.personal_events = {}  # API から取得した個人予定データ
        self.calendar_thread = None  # カレンダーAPIスレッド管理
        self.api_loading = False  # API読み込み中フラグ
        self.api_holidays = {}  # Logic分離統一: 互換性維持のため残存
        
        # StyleLogic統合: フォント・Material Icons初期化（init_uiより前に必須）
        self.style_logic.setup_fonts()  # 日本語フォント設定
        self.material_font = self.style_logic.get_material_font()  # Material Iconsフォント取得
        self.material_icons = {}  # デフォルト値設定（互換性維持）
        self.load_material_icons()  # Material Iconsアイコン設定
        
        # 初期化完了前にキャッシュから祝日を即座に読み込み（Logic経由）
        self.cached_holidays = self.calendar_logic.cached_holidays
        
        # QStackedWidget統合: WeatherDetailWidget ナビゲーション用
        self.stacked_widget = None
        self.main_page = None
        self.weather_detail_page = None
        
        self.init_ui()
        self.setup_styles()  # StyleLogic統合: 元のメソッド名を維持
        self.setup_fixed_weather_display()  # 固定配置天気バー初期化
        self.setup_stacked_navigation()  # QStackedWidget ナビゲーション初期化
        # 予定ポップアップオーバーレイ（子ウィジェット・別ウィンドウなし）
        self._popup_overlay = EventPopupOverlay(parent=self)
        self.start_updates()
        self.load_calendar_data()  # 初回カレンダーデータ読み込み  # 初回カレンダーデータ読み込み  # 初回カレンダーデータ読み込み  # 初回カレンダーデータ読み込み  # 初回カレンダーデータ読み込み

    
    def setup_stacked_navigation(self):
        """QStackedWidget ナビゲーション設定"""
        try:
            # QStackedWidget作成
            from PyQt5.QtWidgets import QStackedWidget
            self.stacked_widget = QStackedWidget(self)
            self.stacked_widget.setGeometry(0, 0, 1024, 630)
            
            # メインページ作成（既存のcentralWidget）
            self.main_page = self.centralWidget()
            
            # 天気詳細ページ作成
            from widgets.weather_detail_widget import WeatherDetailWidget
            self.weather_detail_page = WeatherDetailWidget()
            self.weather_detail_page.back_requested.connect(self.show_main_page)
            
            # StackedWidgetにページ追加
            self.stacked_widget.addWidget(self.main_page)
            self.stacked_widget.addWidget(self.weather_detail_page)
            
            # StackedWidgetをメインウィジェットに設定
            self.setCentralWidget(self.stacked_widget)
            
            # 初期ページ：メインダッシュボード
            self.stacked_widget.setCurrentWidget(self.main_page)
            
            # 🔧 重要：天気バーを最前面に再配置（QStackedWidget統合後）
            if hasattr(self, 'weather_bar'):
                self.weather_bar.raise_()  # Z-order最前面
                self.weather_bar.show()
                # さらに確実にするためにウィンドウフラグ設定
                self.weather_bar.setWindowFlags(self.weather_bar.windowFlags() | Qt.WindowStaysOnTopHint)
            
            # 天気バークリックイベント設定（天気バー最前面化後に実行）
            self.setup_weather_click_event()
            
            self.logger.info("QStackedWidget ナビゲーション初期化完了")
            
        except Exception as e:
            self.logger.error(f"QStackedWidget ナビゲーション設定エラー: {e}")
    
    def setup_weather_click_event(self):
        """天気バークリック設定（透明オーバーレイボタン）"""
        try:
            # 天気バーが存在することを確認
            if not hasattr(self, 'weather_bar') or not self.weather_bar:
                self.logger.warning("天気バーが存在しないため、クリックイベント設定をスキップ")
                return
            
            # 透明なクリック可能ボタンを天気バー上にオーバーレイ
            from PyQt5.QtWidgets import QPushButton
            self.weather_click_button = QPushButton(self.weather_bar)
            self.weather_click_button.setGeometry(0, 0, 1008, 75)  # 天気バー全体をカバー
            self.weather_click_button.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
            """)
            self.weather_click_button.clicked.connect(self.show_weather_detail_page)
            
            # クリックボタンを確実に最前面に配置
            self.weather_click_button.raise_()
            self.weather_click_button.show()
            
            self.logger.info("天気バークリックイベント設定完了")
            
        except Exception as e:
            self.logger.error(f"天気バークリックイベント設定エラー: {e}")
    
    def show_weather_detail_page(self):
        """天気詳細ページ表示"""
        try:
            self.logger.info("天気詳細ページへ移動中...")
            
            # 天気バーを隠してから詳細ページ表示
            self.weather_bar.hide()
            
            # 詳細データ準備・表示
            from logic.weather_detail_logic import WeatherDetailLogic
            weather_detail_logic = WeatherDetailLogic()
            detail_data = weather_detail_logic.prepare_detail_data()
            data_source_info = weather_detail_logic.get_data_source_info()
            
            # 詳細ページにデータ設定
            self.weather_detail_page.clear_scroll_content()
            if detail_data and detail_data.get('days'):
                self.populate_weather_detail_content(detail_data)
                self.weather_detail_page.update_footer_status(
                    data_source_info['source'], 
                    data_source_info['update_time']
                )
            else:
                self.weather_detail_page.show_error_message("天気データの取得に失敗しました")
            
            # 詳細ページに切り替え
            self.stacked_widget.setCurrentWidget(self.weather_detail_page)
            
            self.logger.info("天気詳細ページ表示完了")
            
        except Exception as e:
            self.logger.error(f"天気詳細ページ表示エラー: {e}")
    
    def show_main_page(self):
        """メインダッシュボードページ表示"""
        try:
            self.logger.info("メインダッシュボードに復帰中...")
            
            # メインページに切り替え
            self.stacked_widget.setCurrentWidget(self.main_page)
            
            # 天気バーを再表示
            self.weather_bar.show()
            self.weather_bar.raise_()  # Z-order確保
            
            self.logger.info("メインダッシュボード復帰完了")
            
        except Exception as e:
            self.logger.error(f"メインダッシュボード復帰エラー: {e}")
    
    def populate_weather_detail_content(self, detail_data):
        """天気詳細ページのコンテンツを生成"""
        try:
            # 既存コンテンツをクリア
            while self.weather_detail_page.scroll_layout.count():
                child = self.weather_detail_page.scroll_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            # 場所情報（アイコンを削除）
            location_name = detail_data.get('location', {}).get('name', '不明な場所')
            location_label = QLabel(f"{location_name}")
            location_label.setStyleSheet("""
                font-size: 20px; 
                color: #FFFFFF; 
                font-weight: bold; 
                padding: 12px; 
                background: rgba(0, 0, 0, 0.3); 
                border-radius: 8px;
            """)
            location_label.setAlignment(Qt.AlignCenter)
            self.weather_detail_page.scroll_layout.addWidget(location_label)
            
            # 拡張テーブル形式のメイングリッド
            table_widget = QWidget()
            table_layout = QGridLayout(table_widget)
            table_layout.setContentsMargins(0, -15, 0, 5)
            table_layout.setSpacing(1)
            
            # 今日の日付を取得
            today = datetime.now().date()
            
            # 今日から3日間のデータを選択
            days_data = []
            for date_key, day_data in detail_data['days'].items():
                if not day_data.get('forecasts'):
                    continue
                # 日付キーを日付オブジェクトに変換
                data_date = datetime.strptime(date_key, '%Y-%m-%d').date()
                # 今日以降のデータのみ選択
                if data_date >= today and len(days_data) < 3:
                    actual_date = data_date.strftime("%m/%d")
                    days_data.append({
                        'date': actual_date,
                        'forecasts': day_data['forecasts']
                    })
            
            # ヘッダー行
            header_label = QLabel("")
            header_label.setFixedSize(80, 35)
            table_layout.addWidget(header_label, 0, 0)
            
            for col, day_info in enumerate(days_data):
                day_header = QLabel(f"{day_info['date']}")
                day_header.setStyleSheet("""
                    font-size: 18px; 
                    color: #FFFFFF; 
                    font-weight: bold; 
                    padding: 8px;
                    background: transparent;
                    border: none;
                """)
                day_header.setAlignment(Qt.AlignCenter)
                day_header.setFixedSize(320, 35)
                table_layout.addWidget(day_header, 0, col + 1)
            
            # 8つの時間スロット（3時間おき）を作成
            time_slots = ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00"]
            
            for row in range(8):
                time_str = time_slots[row]
                
                # 時間ラベル
                time_container = QWidget()
                time_container.setFixedSize(80, 90)
                time_container_layout = QVBoxLayout(time_container)
                time_container_layout.setContentsMargins(0, 8, 0, 0)
                time_container_layout.setSpacing(0)
                time_container_layout.setAlignment(Qt.AlignTop)
                
                time_label = QLabel(time_str)
                time_label.setStyleSheet("""
                    font-size: 18px; 
                    color: #E0E0E0; 
                    font-weight: bold;
                    padding: 0px 5px 0px 5px;
                    background: transparent;
                    border: none;
                """)
                time_label.setAlignment(Qt.AlignCenter)
                time_container_layout.addWidget(time_label)
                table_layout.addWidget(time_container, row + 1, 0)
                
                # 各日のデータセル
                for col, day_info in enumerate(days_data):
                    # 該当時刻のデータを検索
                    forecast_cell = None
                    for forecast in day_info['forecasts']:
                        forecast_time = forecast['time']
                        if ' ' in forecast_time:
                            actual_time = forecast_time.split(' ')[1]
                            if actual_time == time_str:
                                forecast_cell = self.create_expanded_forecast_cell(forecast)
                                break
                    
                    # データが見つからない場合は空セル
                    if not forecast_cell:
                        forecast_cell = QLabel("--")
                        forecast_cell.setStyleSheet("background: transparent; border: none; color: #666666;")
                        forecast_cell.setFixedSize(320, 90)
                        forecast_cell.setAlignment(Qt.AlignCenter)
                    
                    table_layout.addWidget(forecast_cell, row + 1, col + 1)
            
            # 列の配置設定
            table_layout.setColumnStretch(0, 0)
            for i in range(len(days_data)):
                table_layout.setColumnStretch(i + 1, 0)
            
            self.weather_detail_page.scroll_layout.addWidget(table_widget)
            
            spacer = QSpacerItem(0, 50, QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.weather_detail_page.scroll_layout.addItem(spacer)
            
            self.logger.info("天気詳細ページ更新完了")
        
        except Exception as e:
            self.logger.error(f"天気詳細コンテンツ生成エラー: {e}")
            
            error_label = QLabel("天気詳細データの読み込みに失敗しました")
            error_label.setStyleSheet("color: #FF6B6B; font-size: 16px; padding: 20px;")
            error_label.setAlignment(Qt.AlignCenter)
            self.weather_detail_page.scroll_layout.addWidget(error_label)
    
    def create_expanded_forecast_cell(self, forecast):
        """拡張予報セル作成（降水確率・天気・気温・風速を横並び）"""
        try:
            from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget
            from PyQt5.QtCore import Qt
            
            # 拡張セルサイズ（完全透明背景）
            cell = QFrame()
            cell.setFixedSize(320, 90)  # 一日あたり幅をさらに拡大：280→320px
            cell.setStyleSheet("""
                background: transparent;
                border: none;
            """)
            
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(8, 2, 8, 8)  # 上マージン8→2で上に移動
            layout.setSpacing(4)
            layout.setAlignment(Qt.AlignTop)  # センター→上寄せでデータを上に
            
            # 横並び情報レイアウト（固定幅でズレ防止）
            info_layout = QHBoxLayout()
            info_layout.setSpacing(8)  # スペース調整
            info_layout.setAlignment(Qt.AlignLeft)  # 降水確率を左に移動するため左寄せ
            
            # 1. 降水確率（気温と同じ大きさ）
            pop_value = forecast.get('pop', 0)
            pop_container = QWidget()
            pop_container.setFixedWidth(80)  # 降水確率幅を大幅拡大：60→80px
            pop_layout = QHBoxLayout(pop_container)
            pop_layout.setContentsMargins(0, 0, 10, 0)  # 右マージン増やして左寄せ強化
            pop_layout.setSpacing(2)  # スペーシング縮小
            pop_layout.setAlignment(Qt.AlignLeft)  # 100%見切れ修正のため左寄せ
            
            # 降水アイコン（気温サイズに合わせて拡大）
            rain_icon = QLabel("☔")
            rain_icon.setStyleSheet("""
                font-size: 24px; 
                color: #00BFFF; 
                font-weight: bold;
            """)
            rain_icon.setAlignment(Qt.AlignCenter)
            pop_layout.addWidget(rain_icon)
            
            # 降水確率数字（気温と同じサイズ）
            rain_percent = QLabel(f"{pop_value:.0f}%")
            rain_percent.setFixedWidth(45)  # 100%表示のため幅を大幅拡大
            rain_percent.setStyleSheet("""
                font-size: 16px; 
                color: #00BFFF; 
                font-weight: bold;
            """)
            rain_percent.setAlignment(Qt.AlignCenter)
            pop_layout.addWidget(rain_percent)
            
            info_layout.addWidget(pop_container)
            
            # 2. 天気アイコン（固定幅）
            icon_container = QWidget()
            icon_container.setFixedWidth(40)
            icon_layout = QHBoxLayout(icon_container)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            icon_layout.setAlignment(Qt.AlignCenter)
            
            icon_label = QLabel(forecast['weather_icon'])
            icon_label.setStyleSheet("""
                font-size: 28px; 
                color: #FFD700;
                font-family: 'WeatherIcons-Regular';
            """)
            icon_label.setAlignment(Qt.AlignCenter)
            icon_layout.addWidget(icon_label)
            info_layout.addWidget(icon_container)
            
            # 3. 気温（固定幅）
            temp_container = QWidget()
            temp_container.setFixedWidth(55)
            temp_layout = QHBoxLayout(temp_container)
            temp_layout.setContentsMargins(0, 0, 0, 0)
            temp_layout.setAlignment(Qt.AlignCenter)
            
            temp_label = QLabel(f"{forecast['temperature']:.0f}°C")
            temp_label.setStyleSheet("""
                font-size: 16px; 
                color: #FFFFFF; 
                font-weight: bold;
            """)
            temp_label.setAlignment(Qt.AlignCenter)
            temp_layout.addWidget(temp_label)
            info_layout.addWidget(temp_container)
            
            # 4. 風速（大きめサイズ・WeatherIconsフォント使用）
            wind_speed = forecast.get('wind_speed', 0)
            wind_container = QWidget()
            wind_container.setFixedWidth(60)  # 風速コンテナ幅拡大
            wind_layout = QHBoxLayout(wind_container)
            wind_layout.setContentsMargins(0, 0, 0, 0)
            wind_layout.setSpacing(3)
            wind_layout.setAlignment(Qt.AlignCenter)
            
            # 風速アイコン（WeatherIconsのwi-strong-wind f050使用）
            wind_icon = QLabel("\uf050")  # wi-strong-wind
            wind_icon.setStyleSheet("""
                font-size: 20px; 
                color: #CCCCCC;
                font-family: 'WeatherIcons-Regular';
                font-weight: bold;
            """)
            wind_icon.setAlignment(Qt.AlignCenter)
            wind_layout.addWidget(wind_icon)
            
            # 風速数値（大きめサイズ）
            wind_value = QLabel(f"{wind_speed:.1f}")
            wind_value.setStyleSheet("""
                font-size: 16px; 
                color: #CCCCCC;
                font-weight: bold;
            """)
            wind_value.setAlignment(Qt.AlignCenter)
            wind_layout.addWidget(wind_value)
            
            info_layout.addWidget(wind_container)
            
            layout.addLayout(info_layout)
            
            return cell
            
        except Exception as e:
            self.logger.error(f"拡張予報セル作成エラー: {e}")
            # エラー時は透明なセルを返す
            error_cell = QFrame()
            error_cell.setFixedSize(320, 90)
            error_cell.setStyleSheet("background: transparent; border: none;")
            return error_cell
        
    def setup_fonts(self):
        """StyleLogic統合: フォント設定はStyleLogicに委譲"""
        # StyleLogic統合により、このメソッドは互換性維持のためのラッパーとして残存
        self.logger.info("フォント設定: StyleLogic経由で処理完了")
    
    def load_material_icons(self):
        """Material Iconsフォントをロード（Logic分離統一 Phase5）"""
        
        # Logic分離統一 Phase5: FileProcessingLogicによる安全なフォント読み込み
        success, font_id, font_family = self.file_processing_logic.load_material_icons_font()
        
        if success and font_family:
            self.material_font = QFont(font_family, 48)  # 36→48に拡大
            self.logger.success("Material Iconsフォントをロード: {font_family}")
        else:
            self.logger.info("Material Iconsフォント取得失敗、デフォルトフォント使用")
            self.material_font = QFont("Arial", 48)  # 36→48に拡大
        
        # Logic分離統一 Phase5: FileProcessingLogicによるアイコンマッピングロード
        self.material_icons = self.file_processing_logic.load_icon_mappings()
        if not self.material_icons:
            self.material_icons = {}  # デフォルト値設定
    
    def get_sensor_icon(self, sensor_type, value=None):
        """Logic分離統一: センサーアイコン計算をCalculationLogicに委譲"""
        return self.calculation_logic.get_sensor_icon_with_fallback(sensor_type, value, self.material_icons)
        
    def init_ui(self):
        """UI初期化 - Web版完全再現"""
        self.setWindowTitle("Raspberry Pi Dashboard - Web完全再現")
        self.setGeometry(0, 0, 1024, 630)  # 高さを600→630に拡大
        self.setFixedSize(1024, 630)  # 高さを600→630に拡大
        
        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Web版と同じレイアウト: dashboard-container
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Web版と同じ: dashboard-main (grid-template-columns: 2fr 1fr)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # 左カラム: カレンダーセクション (4fr - さらに大きく)
        left_widget = QWidget()
        left_widget.setFixedWidth(780)  # 750→780に拡大
        left_widget.setMaximumHeight(590)  # 550→590に拡大
        self.create_calendar_section(left_widget)
        
        # 右カラム: センサーセクション (1fr - もっと右寄せ) 
        right_widget = QWidget()
        right_widget.setFixedWidth(220)  # 250→220に縮小（さらに右寄せ）
        right_widget.setMaximumHeight(590)  # 550→590に拡大
        self.create_sensor_section(right_widget)
        
        content_layout.addWidget(left_widget)
        content_layout.addStretch()  # センサー部分を右端に寄せるためのストレッチ
        content_layout.addWidget(right_widget)
        main_layout.addLayout(content_layout)
    
    def create_calendar_section(self, parent):
        """カレンダーセクション - Logic分離統一処理"""
        parent.setObjectName("calendar_section")
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)
        
        # Web版 calendar-header
        self.create_calendar_header(layout)
        
        # Web版 calendar-grid
        self.create_calendar_grid(layout)

    
    def _original_create_calendar_section(self, parent):
        """Logic分離統一完了: 重複削除済み"""
        pass
    
    def create_calendar_header(self, layout):
        """カレンダーヘッダー - Web版完全再現"""
        header = QFrame()
        header.setObjectName("calendar_header")
        header.setFixedHeight(45)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 0, 20, 40)
        header_layout.setAlignment(Qt.AlignBottom)
        header_layout.setSpacing(0)
        
        # 前月ボタン
        self.prev_button = QPushButton("‹")
        self.prev_button.setObjectName("nav_button")
        self.prev_button.setFixedSize(40, 40)
        self.prev_button.clicked.connect(self.prev_month)
        header_layout.addWidget(self.prev_button)
        
        # カレンダータイトル部分（水平レイアウトに変更）
        title_container = QWidget()
        title_container.setFixedWidth(420)  # 幅を拡張してセンサー警告用スペース確保
        title_layout = QHBoxLayout(title_container)  # VBoxLayout → HBoxLayoutに変更
        title_layout.setAlignment(Qt.AlignLeft)  # シンプルな左寄せに戻す
        title_layout.setSpacing(15)  # タイトルとセンサー警告の間隔
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左側：カレンダータイトルのみ
        self.calendar_title = QLabel(f"{self.current_date.year}年{self.current_date.month}月")
        self.calendar_title.setObjectName("calendar_title")
        self.calendar_title.setAlignment(Qt.AlignLeft)
        self.calendar_title.setContentsMargins(20, 0, 0, 0)
        title_layout.addWidget(self.calendar_title)
        
        # 中央：ステータス表示（カレンダータイトルの右側）
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setAlignment(Qt.AlignCenter)  # Bottomを削除してセンター配置に戻す
        status_layout.setSpacing(6)
        status_layout.setContentsMargins(20, 0, 0, 0)  # 左マージンを10pxに設定
        
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("status_dot")
        self.status_dot.setStyleSheet("color: #38a169; font-size: 8px;")
        self.status_dot.setAlignment(Qt.AlignCenter)  # センター配置に戻す
        status_layout.addWidget(self.status_dot)
        
        self.status_text = QLabel("システム正常")
        self.status_text.setObjectName("status_text")
        self.status_text.setAlignment(Qt.AlignCenter)  # センター配置に戻す
        status_layout.addWidget(self.status_text)
        
        title_layout.addWidget(status_container)
        
        # 右側：センサー警告表示（センサーセクションから移動）
        self.header_co2_message = QLabel("")
        self.header_co2_message.setObjectName("header_co2_message")
        self.header_co2_message.setAlignment(Qt.AlignCenter)
        self.header_co2_message.setVisible(False)
        self.header_co2_message.setFixedWidth(150)  # 幅制限
        title_layout.addWidget(self.header_co2_message)
        
        header_layout.addWidget(title_container)
        
        # 時刻表示 - Web版のcurrent-time-display（影なし）
        time_container = QWidget()
        time_container.setObjectName("current_time_display")
        time_container.setFixedWidth(200)
        time_layout = QVBoxLayout(time_container)
        time_layout.setAlignment(Qt.AlignTop)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(0)
        
        self.time_label = QLabel("--:--")
        self.time_label.setObjectName("time_main")
        self.time_label.setAlignment(Qt.AlignCenter)
        
        time_layout.addWidget(self.time_label)
        
        header_layout.addWidget(time_container)
        
        # 次月ボタン
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("nav_button")
        self.next_button.setFixedSize(40, 40)
        self.next_button.clicked.connect(self.next_month)
        header_layout.addWidget(self.next_button)
        
        layout.addWidget(header)
    
    def create_calendar_grid(self, layout):
        """カレンダーグリッド - Web版完全再現"""
        self.grid_container = QFrame()
        self.grid_container.setObjectName("calendar_grid_container")
        
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(10, 0, 10, 0)
        self.grid_layout.setAlignment(Qt.AlignBottom)
        self.grid_layout.setSpacing(2)
        
        # 曜日ヘッダー（Web版と同じ日曜日始まり）
        weekdays = ['日', '月', '火', '水', '木', '金', '土']
        for i, day in enumerate(weekdays):
            label = QLabel(day)
            if i == 0:  # 日曜日
                label.setObjectName("weekday_sunday")
            elif i == 6:  # 土曜日
                label.setObjectName("weekday_saturday")
            else:
                label.setObjectName("weekday_normal")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedHeight(30)
            self.grid_layout.addWidget(label, 0, i)
        
        # カレンダー日付表示
        self.update_calendar_display()
        
        layout.addWidget(self.grid_container)
    
    def _get_day_events(self, year, month, day):
        """指定日の全予定リストを返す（祝日名 + 個人予定）
        各要素は {'title': str, 'time_str': str|None, 'is_holiday': bool} の dict。
        """
        events = []
        holiday_name = self.calendar_logic.get_holiday_name(year, month, day)
        if holiday_name:
            events.append({'title': holiday_name, 'time_str': None, 'is_holiday': True})
        personal = self.personal_events.get((year, month, day))
        if personal:
            if isinstance(personal, list):
                for ev in personal:
                    if isinstance(ev, dict):
                        title = ev.get('title', '予定')
                        time_str = self._format_event_time(ev)
                    else:
                        title = str(ev)
                        time_str = None
                    events.append({'title': title, 'time_str': time_str, 'is_holiday': False})
            else:
                events.append({'title': str(personal), 'time_str': None, 'is_holiday': False})
        return events

    def _format_event_time(self, ev):
        """イベント dict から表示用の時間文字列を返す。終日なら None。"""
        if ev.get('all_day'):
            return None
        start = ev.get('start_datetime')
        end = ev.get('end_datetime')
        if start is None:
            return None
        # start_datetime は datetime オブジェクトまたは ISO 文字列の両方に対応
        if isinstance(start, str):
            try:
                start = datetime.fromisoformat(start)
            except ValueError:
                return None
        if isinstance(end, str):
            try:
                end = datetime.fromisoformat(end)
            except ValueError:
                end = None
        start_str = start.strftime('%H:%M')
        if end:
            end_str = end.strftime('%H:%M')
            return f"{start_str}〜{end_str}"
        return start_str

    def show_day_popup(self, year, month, day):
        """日付タップ時に全予定オーバーレイを表示"""
        events = self._get_day_events(year, month, day)
        if not events:
            return
        self._popup_overlay.show_for_day(year, month, day, events)

    def update_calendar_display(self):
        """カレンダー表示更新"""
        # 既存の日付セルを削除（曜日ヘッダー行=0 は残す）
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                row, col, _, _ = self.grid_layout.getItemPosition(i)
                if row > 0:
                    item.widget().setParent(None)

        now = datetime.now()
        cal = Calendar(firstweekday=6)  # 日曜日始まり
        year = self.current_date.year
        month = self.current_date.month
        month_days = cal.monthdayscalendar(year, month)

        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        prev_month_days = cal.monthdayscalendar(prev_year, prev_month)

        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        next_month_days = cal.monthdayscalendar(next_year, next_month)

        for week_num, week in enumerate(month_days, 1):
            for day_num, day in enumerate(week):
                if day == 0:
                    # 前月・次月の薄い日付表示（クリック不可）
                    day_widget = QFrame()
                    day_widget.setFixedSize(110, 100)
                    day_widget.setObjectName("calendar_day_empty")
                    day_layout = QVBoxLayout(day_widget)
                    day_layout.setContentsMargins(5, 5, 5, 5)
                    day_layout.setAlignment(Qt.AlignTop)
                    day_layout.setSpacing(2)

                    other_day = None
                    if week_num == 1 and prev_month_days:
                        prev_week = prev_month_days[-1]
                        if day_num < len(prev_week) and prev_week[day_num] > 0:
                            other_day = prev_week[day_num]
                    elif week_num > 1 and next_month_days:
                        next_week = next_month_days[0]
                        if day_num < len(next_week) and next_week[day_num] > 0:
                            other_day = next_week[day_num]

                    if other_day:
                        lbl = QLabel(str(other_day))
                        lbl.setAlignment(Qt.AlignCenter)
                        lbl.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: rgba(255, 255, 255, 0.6); font-size: 16px; font-weight: bold;")
                        day_layout.addWidget(lbl)
                else:
                    # 七夕のデバッグ出力
                    if month == 7 and day == 7:
                        is_holiday_debug = self.calendar_logic.is_holiday(year, month, day)
                        self.logger.info("🎋 七夕チェック: is_holiday=", is_holiday=is_holiday_debug)

                    is_today = (day == now.day and month == now.month and year == now.year)
                    is_holiday = self.calendar_logic.is_holiday(year, month, day)

                    day_widget = ClickableDayCell(year, month, day)
                    day_widget.setFixedSize(110, 100)
                    day_layout = QVBoxLayout(day_widget)
                    day_layout.setContentsMargins(5, 5, 5, 5)
                    day_layout.setAlignment(Qt.AlignTop)
                    day_layout.setSpacing(2)

                    # 日付ラベルのスタイルを種別で切り替え
                    day_label = QLabel(str(day))
                    day_label.setAlignment(Qt.AlignCenter)
                    day_label.setFixedHeight(25)

                    if is_today:
                        day_widget.setObjectName("calendar_day_today")
                        day_label.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: white; font-weight: bold; font-size: 24px; background: #4299e1; border-radius: 12px; padding: 3px 8px;")
                    elif is_holiday:
                        day_widget.setObjectName("calendar_day_holiday")
                        day_label.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: #ff7675; font-weight: bold; font-size: 24px;")
                    elif day_num == 0:
                        day_widget.setObjectName("calendar_day_sunday")
                        day_label.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: #ff7675; font-weight: bold; font-size: 24px;")
                    elif day_num == 6:
                        day_widget.setObjectName("calendar_day_saturday")
                        day_label.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: #74b9ff; font-weight: bold; font-size: 24px;")
                    else:
                        day_widget.setObjectName("calendar_day_normal")
                        day_label.setStyleSheet("font-family: 'Comfortaa', 'Quicksand', sans-serif; color: rgba(255, 255, 255, 0.9); font-size: 24px; font-weight: bold;")

                    day_layout.addWidget(day_label)

                    # 全予定取得 → 1件目を表示、2件以上なら「•」
                    all_events = self._get_day_events(year, month, day)
                    if all_events:
                        first_ev = all_events[0]
                        first_title = first_ev['title'] if isinstance(first_ev, dict) else str(first_ev)
                        ev_color = '#ff7675' if (isinstance(first_ev, dict) and first_ev.get('is_holiday')) else 'white'
                        ev_label = QLabel(first_title)
                        ev_label.setStyleSheet(
                            f"font-family: 'Quicksand', 'Noto Sans JP', sans-serif; "
                            f"color: {ev_color}; font-size: 12px; font-weight: bold; margin-top: 5px;"
                        )
                        ev_label.setAlignment(Qt.AlignCenter)
                        ev_label.setWordWrap(True)
                        ev_label.setFixedHeight(20)
                        day_layout.addWidget(ev_label)

                        if len(all_events) > 1:
                            dot_label = QLabel("•")
                            dot_label.setStyleSheet(
                                "color: rgba(255,255,255,0.55); font-size: 14px; font-weight: bold;"
                            )
                            dot_label.setAlignment(Qt.AlignCenter)
                            dot_label.setFixedHeight(16)
                            day_layout.addWidget(dot_label)

                    day_widget.clicked.connect(self.show_day_popup)

                self.grid_layout.addWidget(day_widget, week_num, day_num)

        self.setStyleSheet(self.styleSheet())
    
    def create_sensor_section(self, parent):
        """センサーセクション - Logic分離統一処理"""
        # Logic分離統一: 直接UIコードを統合（重複削除）
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(15, 80, 15, 15)  # 上マージンを30→80に（50px下に移動）
        layout.setSpacing(25)
        layout.setAlignment(Qt.AlignTop)
        
        # 温度表示 - 横レイアウト（アイコン左、テキスト右）
        temp_layout = QHBoxLayout()  # 縦から横に変更
        temp_layout.setSpacing(15)  # アイコンとテキストの間隔
        
        # 温度アイコン（左側）
        temp_icon = self.get_sensor_icon("temperature")
        self.temp_icon_label = QLabel(temp_icon)
        self.temp_icon_label.setAlignment(Qt.AlignCenter)
        self.temp_icon_label.setFont(self.material_font)
        self.temp_icon_label.setObjectName("sensor_icon_temperature")
        self.temp_icon_label.setFixedSize(60, 60)  # 正方形に固定
        temp_layout.addWidget(self.temp_icon_label)
        
        # テキスト部分（右側）
        temp_text_layout = QVBoxLayout()
        temp_text_layout.setSpacing(2)
        
        temp_label = QLabel("温度")
        temp_label.setObjectName("sensor_simple_label")
        temp_label.setAlignment(Qt.AlignLeft)  # 左揃え
        temp_text_layout.addWidget(temp_label)
        
        self.temp_value = QLabel("28.7°C")
        self.temp_value.setObjectName("sensor_simple_value")
        self.temp_value.setAlignment(Qt.AlignLeft)  # 左揃え
        temp_text_layout.addWidget(self.temp_value)
        
        temp_layout.addLayout(temp_text_layout)
        temp_layout.addStretch()  # 右側に余白を作る
        layout.addLayout(temp_layout)
        
        # 湿度表示 - 横レイアウト（アイコン左、テキスト右）
        humidity_layout = QHBoxLayout()  # 縦から横に変更
        humidity_layout.setSpacing(15)  # アイコンとテキストの間隔
        
        # 湿度アイコン（左側）
        humidity_icon = self.get_sensor_icon("humidity")
        self.humidity_icon_label = QLabel(humidity_icon)
        self.humidity_icon_label.setAlignment(Qt.AlignCenter)
        self.humidity_icon_label.setFont(self.material_font)
        self.humidity_icon_label.setObjectName("sensor_icon_humidity")
        self.humidity_icon_label.setFixedSize(60, 60)  # 正方形に固定
        humidity_layout.addWidget(self.humidity_icon_label)
        
        # テキスト部分（右側）
        humidity_text_layout = QVBoxLayout()
        humidity_text_layout.setSpacing(2)
        
        humidity_label = QLabel("湿度")
        humidity_label.setObjectName("sensor_simple_label")
        humidity_label.setAlignment(Qt.AlignLeft)  # 左揃え
        humidity_text_layout.addWidget(humidity_label)
        
        self.humidity_value = QLabel("64.1%")
        self.humidity_value.setObjectName("sensor_simple_value")
        self.humidity_value.setAlignment(Qt.AlignLeft)  # 左揃え
        humidity_text_layout.addWidget(self.humidity_value)
        
        humidity_layout.addLayout(humidity_text_layout)
        humidity_layout.addStretch()  # 右側に余白を作る
        layout.addLayout(humidity_layout)
        
        # 不快度指数表示 - 横レイアウト（アイコン左、テキスト右）
        discomfort_layout = QHBoxLayout()  # 縦から横に変更
        discomfort_layout.setSpacing(15)  # アイコンとテキストの間隔
        
        # 不快度アイコン（左側）
        discomfort_icon = self.get_sensor_icon("discomfort")
        self.discomfort_icon_label = QLabel(discomfort_icon)
        self.discomfort_icon_label.setAlignment(Qt.AlignCenter)
        self.discomfort_icon_label.setFont(self.material_font)
        self.discomfort_icon_label.setObjectName("sensor_icon_discomfort")
        self.discomfort_icon_label.setFixedSize(60, 60)  # 正方形に固定
        discomfort_layout.addWidget(self.discomfort_icon_label)
        
        # テキスト部分（右側）
        discomfort_text_layout = QVBoxLayout()
        discomfort_text_layout.setSpacing(2)
        
        discomfort_label = QLabel("不快度指数")
        discomfort_label.setObjectName("sensor_simple_label")
        discomfort_label.setAlignment(Qt.AlignLeft)  # 左揃え
        discomfort_text_layout.addWidget(discomfort_label)
        
        self.discomfort_value = QLabel("78.6")
        self.discomfort_value.setObjectName("sensor_simple_value")
        self.discomfort_value.setAlignment(Qt.AlignLeft)  # 左揃え
        discomfort_text_layout.addWidget(self.discomfort_value)
        
        self.discomfort_level = QLabel("不快")
        self.discomfort_level.setObjectName("sensor_simple_level")
        self.discomfort_level.setAlignment(Qt.AlignLeft)  # 左揃え
        discomfort_text_layout.addWidget(self.discomfort_level)
        
        discomfort_layout.addLayout(discomfort_text_layout)
        discomfort_layout.addStretch()  # 右側に余白を作る
        layout.addLayout(discomfort_layout)
        
        # CO2濃度表示 - 横レイアウト（アイコン左、テキスト右）
        co2_layout = QHBoxLayout()
        co2_layout.setSpacing(15)
        
        # CO2アイコン（左側）- Material Icons使用
        self.co2_icon = QLabel("air")
        self.co2_icon.setObjectName("sensor_co2_icon")
        self.co2_icon.setAlignment(Qt.AlignCenter)
        self.co2_icon.setFixedSize(60, 60)
        co2_layout.addWidget(self.co2_icon)
        
        # CO2テキスト（右側）
        co2_text_layout = QVBoxLayout()
        co2_text_layout.setSpacing(0)
        
        co2_label = QLabel("CO2濃度")
        co2_label.setObjectName("sensor_simple_label")
        co2_label.setAlignment(Qt.AlignLeft)
        co2_text_layout.addWidget(co2_label)
        
        # CO2値を数字とppmに分離
        co2_value_layout = QHBoxLayout()
        co2_value_layout.setSpacing(5)
        co2_value_layout.setContentsMargins(0, 0, 0, 0)
        
        self.co2_value = QLabel("850")
        self.co2_value.setObjectName("sensor_co2_value")
        self.co2_value.setAlignment(Qt.AlignLeft)
        co2_value_layout.addWidget(self.co2_value)
        
        self.co2_unit = QLabel("ppm")
        self.co2_unit.setObjectName("sensor_co2_unit")
        self.co2_unit.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        co2_value_layout.addWidget(self.co2_unit)
        
        co2_value_layout.addStretch()
        co2_text_layout.addLayout(co2_value_layout)
        
        self.co2_level = QLabel("正常")
        self.co2_level.setObjectName("sensor_co2_level")
        self.co2_level.setAlignment(Qt.AlignLeft)
        co2_text_layout.addWidget(self.co2_level)
        
        co2_layout.addLayout(co2_text_layout)
        co2_layout.addStretch()
        layout.addLayout(co2_layout)
        
        # CO2警告メッセージ（カレンダーヘッダーに移動済み、この部分は削除）
        # 最終更新時刻とシステム情報は天気予報スペース確保のため削除

    
    def _original_create_sensor_section(self, parent):
        """Logic分離統一により削除 - create_sensor_sectionに統合済み"""
        # Logic分離統一: この170行メソッドは不要、create_sensor_sectionに統合済み
        pass
    
    
    def setup_styles(self):
        """StyleLogic統合: 元のスタイル定義を完全保持した分離"""
        # StyleLogicに委譲し、元のスタイル定義をそのまま適用
        self.setStyleSheet(self.style_logic.get_main_stylesheet())

    def setup_fixed_weather_display(self):
        """固定配置天気バー初期化（3時間後天気追加版）"""
        try:
            # WeatherLogic初期化
            from logic.weather_logic import WeatherLogic
            self.weather_logic = WeatherLogic()
            
            # 天気バーコンテナ作成（固定配置）
            self.weather_bar = QWidget(self)
            self.weather_bar.setGeometry(8, 8, 1008, 75)  # 上部70-80px空間に固定配置
            self.weather_bar.setStyleSheet("background: transparent; border: none;")
            
            # 天気バーレイアウト（横並び版）
            weather_layout = QHBoxLayout(self.weather_bar)
            weather_layout.setContentsMargins(15, 8, 15, 8)
            weather_layout.setSpacing(25)  # 間隔調整（5ブロックになるため縮める）
            
            # 現在天気エリア（背景なし）
            current_widget = QWidget()
            current_widget.setStyleSheet("background: transparent;")
            current_layout = QHBoxLayout(current_widget)
            current_layout.setContentsMargins(0, 0, 0, 0)
            current_layout.setSpacing(15)
            
            # 天気アイコン（特大）
            self.weather_icon = QLabel()
            self.weather_icon.setStyleSheet("font-size: 42px; color: #FFD700; background: transparent; font-family: 'WeatherIcons-Regular';")
            self.weather_icon.setFixedSize(60, 60)
            self.weather_icon.setAlignment(Qt.AlignCenter)
            current_layout.addWidget(self.weather_icon)
            
            # 現在温度（特大・明るい白）
            self.weather_temp = QLabel()
            self.weather_temp.setStyleSheet("font-size: 36px; color: #FFFFFF; font-weight: bold; background: transparent;")
            current_layout.addWidget(self.weather_temp)
            
            weather_layout.addWidget(current_widget)
            
            # 場所表示（アイコンなし）
            location_widget = QWidget()
            location_widget.setStyleSheet("background: transparent;")
            location_layout = QVBoxLayout(location_widget)
            location_layout.setContentsMargins(0, 0, 0, 0)
            location_layout.setSpacing(0)
            location_layout.setAlignment(Qt.AlignCenter)
            
            self.weather_location = QLabel()
            self.weather_location.setStyleSheet("font-size: 16px; color: #FFFFFF; font-weight: bold; background: transparent;")
            self.weather_location.setAlignment(Qt.AlignCenter)
            location_layout.addWidget(self.weather_location)
            
            weather_layout.addWidget(location_widget)
            
            # 3時間後予報（今日・明日と同じ横レイアウト）
            next3h_widget = QWidget()
            next3h_widget.setStyleSheet("background: transparent;")
            next3h_layout = QHBoxLayout(next3h_widget)
            next3h_layout.setContentsMargins(0, 0, 0, 0)
            next3h_layout.setSpacing(6)
            
            self.next3h_time_label = QLabel()
            self.next3h_time_label.setStyleSheet("font-size: 16px; color: #E0E0E0; font-weight: bold; background: transparent;")
            next3h_layout.addWidget(self.next3h_time_label)
            
            self.next3h_icon = QLabel()
            self.next3h_icon.setStyleSheet("font-size: 24px; color: #FFD700; background: transparent; font-family: 'WeatherIcons-Regular';")
            next3h_layout.addWidget(self.next3h_icon)
            
            self.next3h_temp = QLabel()
            self.next3h_temp.setStyleSheet("font-size: 18px; color: #FFFFFF; font-weight: bold; background: transparent;")
            next3h_layout.addWidget(self.next3h_temp)
            
            self.next3h_rain = QLabel()
            self.next3h_rain.setStyleSheet("font-size: 16px; color: #00BFFF; font-weight: bold; background: transparent;")
            next3h_layout.addWidget(self.next3h_rain)
            
            weather_layout.addWidget(next3h_widget)
            
            # 今日予報（背景なし・明るい色）
            today_widget = QWidget()
            today_widget.setStyleSheet("background: transparent;")
            today_layout = QHBoxLayout(today_widget)
            today_layout.setContentsMargins(0, 0, 0, 0)
            today_layout.setSpacing(6)
            
            today_label = QLabel("今日")
            today_label.setStyleSheet("font-size: 16px; color: #E0E0E0; font-weight: bold; background: transparent;")
            today_layout.addWidget(today_label)
            
            self.today_icon = QLabel()
            self.today_icon.setStyleSheet("font-size: 24px; color: #FFD700; background: transparent; font-family: 'WeatherIcons-Regular';")
            today_layout.addWidget(self.today_icon)
            
            self.today_temp = QLabel()
            self.today_temp.setStyleSheet("font-size: 18px; color: #FFFFFF; font-weight: bold; background: transparent;")
            today_layout.addWidget(self.today_temp)
            
            self.today_rain = QLabel()
            self.today_rain.setStyleSheet("font-size: 16px; color: #00BFFF; font-weight: bold; background: transparent;")
            today_layout.addWidget(self.today_rain)
            
            weather_layout.addWidget(today_widget)
            
            # 明日予報（背景なし・明るい色）
            tomorrow_widget = QWidget()
            tomorrow_widget.setStyleSheet("background: transparent;")
            tomorrow_layout = QHBoxLayout(tomorrow_widget)
            tomorrow_layout.setContentsMargins(0, 0, 0, 0)
            tomorrow_layout.setSpacing(6)
            
            tomorrow_label = QLabel("明日")
            tomorrow_label.setStyleSheet("font-size: 16px; color: #E0E0E0; font-weight: bold; background: transparent;")
            tomorrow_layout.addWidget(tomorrow_label)
            
            self.tomorrow_icon = QLabel()
            self.tomorrow_icon.setStyleSheet("font-size: 24px; color: #FFD700; background: transparent; font-family: 'WeatherIcons-Regular';")
            tomorrow_layout.addWidget(self.tomorrow_icon)
            
            self.tomorrow_temp = QLabel()
            self.tomorrow_temp.setStyleSheet("font-size: 18px; color: #FFFFFF; font-weight: bold; background: transparent;")
            tomorrow_layout.addWidget(self.tomorrow_temp)
            
            self.tomorrow_rain = QLabel()
            self.tomorrow_rain.setStyleSheet("font-size: 16px; color: #00BFFF; font-weight: bold; background: transparent;")
            tomorrow_layout.addWidget(self.tomorrow_rain)
            
            weather_layout.addWidget(tomorrow_widget)
            
            # スペーサーを追加して右寄せ効果を作る
            weather_layout.addStretch()
            
            # 更新時刻表示
            self.weather_update_time = QLabel()
            self.weather_update_time.setStyleSheet("font-size: 12px; color: #CCCCCC; background: transparent;")
            weather_layout.addWidget(self.weather_update_time)
            
            # 初期データ表示（JSONから読み込み - 3時間毎Cron更新）
            self.update_weather_display()
            
            # 注記: 天気JSONは既存の時刻更新システムで効率的にチェック
            #       Cronが毎3時間の05分にJSONを更新するため、
            #       06分に時刻ベースでJSON再読み込み（タイマー不要）
            
            # 天気バー表示
            self.weather_bar.show()
            
            self.logger.info("3時間後天気追加版天気バー初期化完了")
            
        except Exception as e:
            self.logger.error(f"天気バー初期化エラー: {e}")
    
    def update_weather_display(self):
        """天気表示更新（JSON読み込みのみ・6分オフセット同期）"""
        weather_file = f"{os.path.dirname(__file__)}/cache/weather/weather_data.json"
        
        try:
            # JSONファイル読み込み
            if os.path.exists(weather_file):
                with open(weather_file, 'r', encoding='utf-8') as f:
                    weather_data = json.load(f)
                
                if weather_data.get('forecast_list'):
                    # JSONデータから天気バー更新
                    current = weather_data['forecast_list'][0]
                    self._update_weather_from_json(current, weather_data)
                    self.logger.info("天気データをJSONから読み込み完了")
                    return
            
            # JSONが読めない場合はエラーログのみ（API呼び出しなし）
            self.logger.error("天気JSONファイルが見つからないか読み込めません")
            self._show_weather_fallback_display()
            
        except Exception as e:
            self.logger.error(f"天気表示更新エラー: {e}")
            self._show_weather_fallback_display()

    def _show_weather_fallback_display(self):
        """JSON読み込み失敗時のフォールバック表示（APIなし）"""
        self.weather_icon.setText('☀')
        self.weather_location.setText('東京')
        self.weather_temp.setText('--°C')
        
        self.next3h_time_label.setText('--:--')
        self.next3h_icon.setText('☀')
        self.next3h_temp.setText('--°C')
        self.next3h_rain.setText('☔--%')
        
        self.today_icon.setText('☀')
        self.today_temp.setText('--/--')
        self.today_rain.setText('☔ --%')
        
        self.tomorrow_icon.setText('☀')
        self.tomorrow_temp.setText('--/--')
        self.tomorrow_rain.setText('☔ --%')
        
        self.weather_update_time.setText('--:--')

    def _update_weather_from_json(self, current_data, full_weather_data):
        """JSONデータから天気バー更新"""
        # 現在天気（基本情報のみ）
        self.weather_icon.setText(current_data.get('weather_icon', '☀'))
        location_name = full_weather_data.get('location', {})
        if isinstance(location_name, dict):
            location_text = location_name.get('name', '東京')
        else:
            location_text = str(location_name) if location_name else '東京'
        self.weather_location.setText(location_text)
        current_temp = current_data.get('temperature', '--')
        if isinstance(current_temp, (int, float)):
            current_temp = int(round(current_temp))
        self.weather_temp.setText(f"{current_temp}°C")
        
        # 3時間後予報（JSONデータの中から次の時間を取得）
        forecast_list = full_weather_data.get('forecast_list', [])
        from datetime import datetime
        
        # forecast_listから現在時刻以降で最も近いデータを検索
        next3h = current_data  # デフォルト
        time_part = "12:00"  # デフォルトの時刻表示
        
        for forecast in forecast_list:
            try:
                forecast_datetime = datetime.strptime(forecast['date'], '%Y-%m-%d %H:%M:%S')
                if forecast_datetime > datetime.now():
                    next3h = forecast
                    # 時刻表示を抽出
                    next3h_time = forecast.get('date_display', '--:--')
                    if ' ' in next3h_time:
                        time_part = next3h_time.split(' ')[1]  # "09/05 12:00" → "12:00"
                    break
            except (ValueError, KeyError):
                continue
        
        self.next3h_time_label.setText(time_part)
        self.next3h_icon.setText(next3h.get('weather_icon', '☀'))
        next3h_temp = next3h.get('temperature', '--')
        if isinstance(next3h_temp, (int, float)):
            next3h_temp = int(round(next3h_temp))
        self.next3h_temp.setText(f"{next3h_temp}°C")
        # JSONのpopフィールドは既にパーセント値（0-100）
        rain_pop = next3h.get('pop', 0) if next3h.get('pop') else 0
        self.next3h_rain.setText(f"☔{int(rain_pop)}%")
        
        # 今日・明日予報（日別データから取得）
        days_data = self._group_forecasts_by_day(forecast_list)
        today_data = self._get_day_summary(days_data, 0)  # 今日
        tomorrow_data = self._get_day_summary(days_data, 1)  # 明日
        
        self.today_icon.setText(today_data.get('icon', '☀'))
        # 今日の気温（小数点なし）
        today_high = today_data.get('high', '--')
        today_low = today_data.get('low', '--')
        if isinstance(today_high, (int, float)):
            today_high = int(round(today_high))
        if isinstance(today_low, (int, float)):
            today_low = int(round(today_low))
        self.today_temp.setText(f"{today_high}/{today_low}")
        self.today_rain.setText(f"☔ {int(today_data.get('rain', 0))}%")
        
        self.tomorrow_icon.setText(tomorrow_data.get('icon', '☀'))
        # 明日の気温（小数点なし）
        tomorrow_high = tomorrow_data.get('high', '--')
        tomorrow_low = tomorrow_data.get('low', '--')
        if isinstance(tomorrow_high, (int, float)):
            tomorrow_high = int(round(tomorrow_high))
        if isinstance(tomorrow_low, (int, float)):
            tomorrow_low = int(round(tomorrow_low))
        self.tomorrow_temp.setText(f"{tomorrow_high}/{tomorrow_low}")
        self.tomorrow_rain.setText(f"☔ {int(tomorrow_data.get('rain', 0))}%")
        
        # 更新時刻表示（collection_timeから抽出）
        collection_time = full_weather_data.get('collection_time', '')
        if collection_time and 'T' in collection_time:
            # "2025-09-05T11:08:24.735776" → "11:08"
            time_part = collection_time.split('T')[1][:5]  # HH:MM
            self.weather_update_time.setText(time_part)
        else:
            self.weather_update_time.setText('--:--')

    def _update_weather_from_api(self, weather_data):
        """APIデータから天気バー更新（既存方式）"""
        # 現在天気（基本情報のみ）
        self.weather_icon.setText(weather_data['current_icon'])
        self.weather_location.setText(weather_data['current_location'])
        current_temp = weather_data['current_temp']
        if isinstance(current_temp, (int, float)):
            current_temp = int(round(current_temp))
        self.weather_temp.setText(f"{current_temp}°C")
        
        # 3時間後予報（時刻表示追加）
        self.next3h_time_label.setText(weather_data['next3h_time'])
        self.next3h_icon.setText(weather_data['next3h_icon'])
        next3h_temp = weather_data['next3h_temp']
        if isinstance(next3h_temp, (int, float)):
            next3h_temp = int(round(next3h_temp))
        self.next3h_temp.setText(f"{next3h_temp}°C")
        self.next3h_rain.setText(f"☔{weather_data['next3h_rain']}%")
        
        # 今日・明日予報（温度 + 降水確率）- Neutral版アイコン使用
        today_neutral_icon = self._get_neutral_weather_icon(weather_data['today_icon'])
        self.today_icon.setText(today_neutral_icon)
        # 今日の気温（小数点なし）
        today_high = weather_data['today_high']
        today_low = weather_data['today_low']
        if isinstance(today_high, (int, float)):
            today_high = int(round(today_high))
        if isinstance(today_low, (int, float)):
            today_low = int(round(today_low))
        self.today_temp.setText(f"{today_high}/{today_low}")
        self.today_rain.setText(f"☔ {weather_data['today_rain']}%")
        
        tomorrow_neutral_icon = self._get_neutral_weather_icon(weather_data['tomorrow_icon'])
        self.tomorrow_icon.setText(tomorrow_neutral_icon)
        # 明日の気温（小数点なし）
        tomorrow_high = weather_data['tomorrow_high']
        tomorrow_low = weather_data['tomorrow_low']
        if isinstance(tomorrow_high, (int, float)):
            tomorrow_high = int(round(tomorrow_high))
        if isinstance(tomorrow_low, (int, float)):
            tomorrow_low = int(round(tomorrow_low))
        self.tomorrow_temp.setText(f"{tomorrow_high}/{tomorrow_low}")
        self.tomorrow_rain.setText(f"☔ {weather_data['tomorrow_rain']}%")
        
        # 更新時刻表示（縦レイアウト・コンパクト）
        self.weather_update_time.setText(weather_data['last_update'])

    def _group_forecasts_by_day(self, forecast_list):
        """40予報データを日別にグループ化"""
        days_data = {}
        for item in forecast_list:
            date_key = item.get('date', '').split(' ')[0]
            if date_key not in days_data:
                days_data[date_key] = []
            days_data[date_key].append(item)
        return days_data

    def _get_neutral_weather_icon(self, weather_icon):
        """天気アイコンをNeutral版（昼間アイコン）に変換"""
        # 夜間アイコンから昼間アイコンへの変換マップ
        night_to_day_map = {
            '\uf02e': '\uf00d',  # night-clear → day-sunny
            '\uf083': '\uf002',  # night-partly-cloudy → day-cloudy
            '\uf086': '\uf002',  # night-alt-cloudy → day-cloudy
            '\uf02b': '\uf009',  # night-alt-sprinkle → day-sprinkle
            '\uf026': '\uf008',  # night-alt-rain-mix → day-rain
            '\uf028': '\uf008',  # night-alt-rain → day-rain
            '\uf029': '\uf00a',  # night-alt-showers → day-showers
            '\uf02a': '\uf01b',  # night-alt-snow → snow
            '\uf0b4': '\uf006',  # night-alt-sleet → day-sleet
            '\uf02d': '\uf010',  # night-alt-thunderstorm → day-thunderstorm
            '\uf025': '\uf005',  # night-alt-lightning → day-lightning
            '\uf04a': '\uf003',  # night-fog → day-fog
        }
        
        # 夜間アイコンの場合は昼間アイコンに変換、そうでなければそのまま
        return night_to_day_map.get(weather_icon, weather_icon)

    def _get_day_summary(self, days_data, day_offset):
        """日別データのサマリー取得（Neutral版アイコン使用）"""
        from datetime import timedelta
        target_date = (datetime.now() + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        
        day_forecasts = days_data.get(target_date, [])
        if not day_forecasts:
            return {'icon': '☀', 'high': '--', 'low': '--', 'rain': 0}
        
        temps = [item.get('temperature', 0) for item in day_forecasts if item.get('temperature')]
        rains = [item.get('pop', 0) for item in day_forecasts]  # popフィールドを使用
        
        # 昼間の予報を優先的に選択してアイコンを決定
        daytime_forecast = None
        for forecast in day_forecasts:
            # is_nightがFalse（昼間）の予報を優先
            if not forecast.get('is_night', True):
                daytime_forecast = forecast
                break
        
        # 昼間の予報が無い場合は最初の予報を使用
        selected_forecast = daytime_forecast if daytime_forecast else day_forecasts[0]
        original_icon = selected_forecast.get('weather_icon', '☀')
        
        # デバッグ情報追加
        if day_offset == 1:  # 明日の場合のみログ出力
            self.logger.info(f"明日のアイコン調査: 予報数={len(day_forecasts)}")
            self.logger.info(f"明日のアイコン調査: 選択した予報={selected_forecast.get('date')} is_night={selected_forecast.get('is_night')}")
            self.logger.info(f"明日のアイコン調査: 元アイコン={repr(original_icon)}")
        
        # 天気アイコンをNeutral版（昼間アイコン）に変換
        neutral_icon = self._get_neutral_weather_icon(original_icon)
        
        # デバッグ情報追加（続き）
        if day_offset == 1:  # 明日の場合のみログ出力
            self.logger.info(f"明日のアイコン調査: 変換後アイコン={repr(neutral_icon)}")
        
        return {
            'icon': neutral_icon,
            'high': max(temps) if temps else '--',
            'low': min(temps) if temps else '--',
            'rain': max(rains) if rains else 0
        }

    
    def _original_setup_styles(self):
        """Logic分離統一完了: 重複削除済み"""
        pass
    
    def _load_holiday_cache_immediate(self):
        """祝日キャッシュ読み込み - Logic分離統一で削除予定"""
        # Logic分離統一: CalendarLogicクラスに統合されました
        return self.calendar_logic.load_holiday_cache_immediate()
    
    def _is_cached_holiday(self, day):
        """キャッシュから指定日の祝日判定 - Logic分離統一"""
        # Logic分離統一: CalendarLogicクラスに処理を委譲
        from datetime import date
        target_date = date(self.current_date.year, self.current_date.month, day)
        return self.calendar_logic.is_cached_holiday(target_date)
    
    def start_updates(self):
        """定期更新開始"""
        # 時刻更新タイマー
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)  # 1秒間隔
        
        # センサーデータ更新スレッド
        self.sensor_thread = SensorDataThread()
        self.sensor_thread.data_updated.connect(self.update_sensor_data)
        self.sensor_thread.date_changed.connect(self.handle_date_change)  # 日付変更ハンドラーを追加
        self.sensor_thread.start()
        
        # 初回更新
        self.update_time()
        self.update_weather_display()  # 初回天気表示
        
        # シンプル天気監視: 5分間隔でJSON更新チェック
        self.weather_monitor_timer = QTimer()
        self.weather_monitor_timer.timeout.connect(self.update_all_weather_displays)
        self.weather_monitor_timer.start(300000)  # 5分 = 300,000ms
        self.logger.info("天気監視タイマー開始: 5分間隔でJSON更新チェック（バー＋詳細ページ）")

        # カレンダー定期更新タイマー: 1時間ごとにGoogle Calendarから最新予定を取得
        self.calendar_refresh_timer = QTimer()
        self.calendar_refresh_timer.timeout.connect(self.load_calendar_data)
        self.calendar_refresh_timer.start(60 * 60 * 1000)  # 1時間 = 3,600,000ms
        self.logger.info("カレンダー定期更新タイマー開始: 1時間間隔")

    def update_all_weather_displays(self):
        """5分間隔統一更新: 天気バー＋詳細ページ（表示中の場合）"""
        try:
            # 天気バー更新
            self.update_weather_display()
            
            # 詳細ページが表示されている場合のみ更新
            if hasattr(self, 'stacked_widget') and self.stacked_widget.currentWidget() == self.weather_detail_page:
                self.logger.info("詳細ページ表示中 - データ更新実行")
                self.refresh_weather_detail_page()
                
        except Exception as e:
            self.logger.error(f"統一天気更新エラー: {e}")

    def refresh_weather_detail_page(self):
        """詳細ページのデータを再取得・更新"""
        try:
            from logic.weather_detail_logic import WeatherDetailLogic
            weather_detail_logic = WeatherDetailLogic()
            detail_data = weather_detail_logic.prepare_detail_data()
            data_source_info = weather_detail_logic.get_data_source_info()
            
            # 詳細ページに新データを設定
            self.weather_detail_page.clear_scroll_content()
            if detail_data and detail_data.get('days'):
                self.populate_weather_detail_content(detail_data)
                self.weather_detail_page.update_footer_status(
                    data_source_info['source'], 
                    data_source_info['update_time']
                )
                self.logger.info("詳細ページのデータ更新完了")
            else:
                self.weather_detail_page.show_error_message("天気データの取得に失敗しました")
                
        except Exception as e:
            self.logger.error(f"詳細ページ更新エラー: {e}")

    def update_time(self):
        """時刻表示更新（効率化：天気更新は別スケジュール）"""
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M"))
        
    def handle_date_change(self):
        """日付変更時のカレンダー更新処理（5分毎センサー更新時にトリガー）"""
        now = datetime.now()
        current_year = self.current_date.year
        current_month = self.current_date.month

        if now.year != current_year or now.month != current_month:
            # 年または月が変わった場合：カレンダーを新しい月に更新
            self.logger.info(f"📅 月変更対応: {current_year}年{current_month}月 → {now.year}年{now.month}月")
            self.current_date = now.date()
            self.calendar_title.setText(f"{now.year}年{now.month}月")

            # APIデータをクリアして新しい月のデータを読み込み
            self.api_holidays.clear()
            self.personal_events = {}

            # カレンダー表示を更新してから API読み込み
            self.update_calendar_display()
            self.load_calendar_data()
        elif now.day != self.current_date.day and now.year == current_year and now.month == current_month:
            # 日のみ変更の場合（表示中の月が現在の月と一致する場合のみ）：カレンダー表示のみ更新（APIは再取得しない）
            self.logger.info(f"📅 日変更対応: {self.current_date.day}日 → {now.day}日")
            self.current_date = now.date()
            self.update_calendar_display()
        else:
            # 表示中の月が現在の月と異なる場合でも、日付変更があればカレンダー表示を更新
            # （次月表示中に月が変わった場合、当日マークを表示するため）
            if now.day != self.current_date.day:
                self.logger.info(f"📅 表示月({current_year}年{current_month}月)と実際の日付({now.year}年{now.month}月{now.day}日)が異なるため、カレンダー表示のみ更新")
                self.update_calendar_display()
        
    def prev_month(self):
        """前月表示"""
        if self.api_loading:
            self.logger.info("API読み込み中のためスキップ")
            return
            
        try:
            # ボタン連続押し防止：即座に処理中状態にする
            self.api_loading = True
            self.logger.info("⬅ 前月ボタンが押されました")
            
            # 安全な年月計算
            current_year = self.current_date.year
            current_month = self.current_date.month
            
            if current_month == 1:
                new_year = current_year - 1
                new_month = 12
            else:
                new_year = current_year
                new_month = current_month - 1
            
            # 年の範囲チェック（極端な値を防ぐ）
            if new_year < 1900 or new_year > 2200:
                self.logger.warning("年の範囲外エラー", new_year=new_year)
                self.api_loading = False
                return
            
            # 日付更新
            from datetime import date
            self.current_date = date(new_year, new_month, 1)
            self.calendar_title.setText(f"{self.current_date.year}年{self.current_date.month}月")
            self.logger.success("📅 月変更完了: 年月", year=self.current_date.year, month=self.current_date.month)
            
            # APIデータをクリアしてから新しい月のデータを読み込み
            self.api_holidays.clear()
            self.personal_events = {}  # 個人予定もクリア
            
            # まず表示を更新してから API読み込み
            self.update_calendar_display()
            self.load_calendar_data()  # API読み込み後にカレンダー更新
            
        except Exception as e:
            self.logger.error("前月移動エラー", error=str(e))
            self.api_loading = False
            self.status_dot.setStyleSheet("color: #e53e3e; font-size: 8px;")
            self.status_text.setText("Error")  # API読み込み後にカレンダー更新
        
    def next_month(self):
        """次月表示"""
        if self.api_loading:
            self.logger.info("API読み込み中のためスキップ")
            return
            
        try:
            # ボタン連続押し防止：即座に処理中状態にする
            self.api_loading = True
            self.logger.info("➡ 次月ボタンが押されました")
            
            # 安全な年月計算
            current_year = self.current_date.year
            current_month = self.current_date.month
            
            if current_month == 12:
                new_year = current_year + 1
                new_month = 1
            else:
                new_year = current_year
                new_month = current_month + 1
            
            # 年の範囲チェック（極端な値を防ぐ）
            if new_year < 1900 or new_year > 2200:
                self.logger.warning("年の範囲外エラー", new_year=new_year)
                self.api_loading = False
                return
            
            # 日付更新
            from datetime import date
            self.current_date = date(new_year, new_month, 1)
            self.calendar_title.setText(f"{self.current_date.year}年{self.current_date.month}月")
            self.logger.success("📅 月変更完了: 年月", year=self.current_date.year, month=self.current_date.month)
            
            # APIデータをクリアしてから新しい月のデータを読み込み
            self.api_holidays.clear()
            self.personal_events = {}  # 個人予定もクリア
            
            # まず表示を更新してから API読み込み
            self.update_calendar_display()
            self.load_calendar_data()  # API読み込み後にカレンダー更新
            
        except Exception as e:
            self.logger.error("次月移動エラー", error=str(e))
            self.api_loading = False
            self.status_dot.setStyleSheet("color: #e53e3e; font-size: 8px;")
            self.status_text.setText("Error")  # API読み込み後にカレンダー更新
        
    def load_calendar_data(self):
        """カレンダーAPIデータ読み込み"""
        # 既存のスレッドを安全に停止
        if self.calendar_thread and self.calendar_thread.isRunning():
            self.logger.info("🛑 既存のAPIスレッドを安全に停止中...")
            try:
                # シグナルを切断
                self.calendar_thread.calendar_updated.disconnect()
                # スレッドの完了を待機（強制終了はしない）
                if not self.calendar_thread.wait(2000):  # 2秒待機
                    self.logger.warning("スレッド停止タイムアウト、新しいスレッドを開始")
                else:
                    self.logger.info("スレッド正常停止完了")
            except Exception as e:
                self.logger.warning("スレッド停止時エラー", error=str(e))
            finally:
                self.calendar_thread = None
        
        # api_loadingは既にprev_month/next_monthでTrue設定済み
        # しかし基本カレンダーが即座に表示されるため、Loading状態は最小限に
        
        self.logger.info("カレンダーAPI読み込み開始: 年月", year=self.current_date.year, month=self.current_date.month)
        
        try:
            self.calendar_thread = CalendarDataThread(self.current_date.year, self.current_date.month)
            self.calendar_thread.calendar_updated.connect(self.update_holiday_data)
            self.calendar_thread.start()
            self.logger.info("新しいカレンダースレッド開始完了")
        except Exception as e:
            self.logger.error("カレンダースレッド開始エラー", error=str(e))
            # エラー時は状態をリセット
            self.api_loading = False
            self.status_dot.setStyleSheet("color: #e53e3e; font-size: 8px;")
            self.status_text.setText("Error")
        
    def update_holiday_data(self, api_data):
        """カレンダーAPIデータ更新 - Logic分離統一"""
        # Logic分離統一: CalendarLogicクラスに処理を委譲
        self.calendar_logic.update_holiday_data(api_data, self.current_date)
        
        # Logic分離統一: 個人予定データをUIに反映（元の動作を復元）
        if api_data and 'data' in api_data:
            calendar_data = api_data['data']

            # 個人予定をpersonal_eventsに反映（追加・削除の両方に対応）
            if 'calendar_data' in calendar_data and 'days' in calendar_data['calendar_data']:
                for day, day_data in calendar_data['calendar_data']['days'].items():
                    if isinstance(day_data, dict):
                        day_key = (self.current_date.year, self.current_date.month, int(day))
                        events = day_data.get('events', [])
                        if events:
                            self.personal_events[day_key] = events
                        elif day_key in self.personal_events:
                            del self.personal_events[day_key]
        
        # UIの状態更新のみdashboardで処理
        self.api_loading = False
        
        # ステータスを正常に戻す
        self.status_dot.setStyleSheet("color: #38a169; font-size: 8px;")
        self.status_text.setText("システム正常")
        
        # APIデータが取得できた場合のみカレンダー表示を更新
        if api_data and 'data' in api_data:
            self.update_calendar_display()
        else:
            self.logger.info("APIデータが取得できなかったため、カレンダー表示をスキップします")
            # キャッシュ優先システムが動作している場合は正常として扱う
            if api_data and api_data.get("status") == "success":
                self.status_dot.setStyleSheet("color: #38a169; font-size: 8px;")
                self.status_text.setText("キャッシュ表示")
                self.logger.info("キャッシュ優先システムからデータを表示")
                # 空のデータでもカレンダー表示を更新
                self.update_calendar_display()
            else:
                self.status_dot.setStyleSheet("color: #e53e3e; font-size: 8px;")
                self.status_text.setText("APIエラー")
        
    def update_calendar(self):
        """カレンダー更新"""
        self.calendar_title.setText(f"{self.current_date.year}年{self.current_date.month}月")
        self.update_calendar_display()  # カレンダー表示を実際に更新
    
    def update_sensor_data(self, json_data):
        """センサーデータ更新 - Logic分離統一"""
        try:
            # Logic分離統一: SensorLogicクラスでデータ処理
            if json_data.get('status') == 'success' and 'data' in json_data:
                raw_data = json_data['data']
                processed_data = self.sensor_logic.process_sensor_data(raw_data)
                
                # Logic分離統一: DataTransformationLogicでUIフォーマット処理
                if processed_data['temperature'] is not None:
                    self.temp_value.setText(self.data_transformation_logic.format_temperature(processed_data['temperature']))
                    self.humidity_value.setText(self.data_transformation_logic.format_humidity(processed_data['humidity']))
                    
                    # Logic分離統一: DataTransformationLogicで不快度指数フォーマット
                    discomfort_index = raw_data.get('discomfort_index')
                    comfort_level = raw_data.get('comfort_level')
                    if discomfort_index is not None:
                        self.discomfort_value.setText(self.data_transformation_logic.format_discomfort_index(discomfort_index))
                        self.discomfort_level.setText(comfort_level)
                    
                    # Logic分離統一: DataTransformationLogicでCO2フォーマット
                    if processed_data['co2'] is not None:
                        self.co2_value.setText(self.data_transformation_logic.format_co2(processed_data['co2']))
                        
                        # CO2レベル判定（raw_dataから）
                        co2_level = raw_data.get('co2_level')
                        co2_color = raw_data.get('co2_color', 'gray')
                        co2_message = raw_data.get('co2_message', '')
                        
                        # 警告メッセージがある場合はメッセージを、そうでなければレベルを表示
                        if co2_message and processed_data['co2'] >= 1000:  # 1000ppm以上で警告メッセージ表示
                            self.co2_level.setText(co2_message)
                        else:
                            self.co2_level.setText(co2_level)
                        
                        # Logic分離統一: DataTransformationLogicから色マップ取得
                        color_map = self.data_transformation_logic.get_color_style_map()
                        self.co2_level.setStyleSheet(color_map.get(co2_color, ''))
                        
                        # CO2アイコンの色も変更
                        if hasattr(self, 'co2_icon'):
                            base_color_style = color_map.get(co2_color, '')
                            self.co2_icon.setStyleSheet(f"#sensor_co2_icon {{ {base_color_style} font-size: 48px; }}")
                        
                        # 警告メッセージはカレンダーヘッダーに移動済み
                        if hasattr(self, 'header_co2_message'):
                            self.header_co2_message.setVisible(False)
                    
                    # Material Iconsを動的に更新
                    if hasattr(self, 'temp_icon_label'):
                        temp_icon = self.get_sensor_icon("temperature", processed_data['temperature'])
                        self.temp_icon_label.setText(temp_icon)
                        self.logger.info("🌡 温度アイコン更新: {processed_data['temperature']:.1f}°C →", temp_icon=temp_icon)
                    
                    if hasattr(self, 'discomfort_icon_label') and discomfort_index is not None:
                        discomfort_icon = self.get_sensor_icon("discomfort", discomfort_index)
                        self.discomfort_icon_label.setText(discomfort_icon)
                        self.logger.info("😊 不快度アイコン更新: {discomfort_index:.1f} →", discomfort_icon=discomfort_icon)
                    
                    # ステータス更新
                    self.status_dot.setObjectName("status_dot")
                    if processed_data['status'] == 'warning':
                        self.status_text.setText("センサー警告")
                    else:
                        self.status_text.setText("システム正常")
                else:
                    # データなし時のUI更新
                    self.temp_value.setText("--°C")
                    self.humidity_value.setText("--%") 
                    self.discomfort_value.setText("--")
                    self.discomfort_level.setText("--")
                    self.status_text.setText("データなし")
                
                # 最終更新ラベルは削除済み（天気予報スペース確保のため）
                # self.last_update_label.setText(f"最終更新: {datetime.now().strftime('%H:%M:%S')}")
                
        except Exception as e:
            self.logger.error("センサーデータUI更新エラー:", e=e)
    
    def keyPressEvent(self, event):
        """キーイベント処理"""
        if event.key() == Qt.Key_Escape or event.key() == Qt.Key_Q:
            self.close()
    
    def closeEvent(self, event):
        """終了処理"""
        self.logger.info("🛑 アプリケーション終了処理開始")
        
        try:
            # タイマー停止
            if hasattr(self, 'time_timer') and self.time_timer:
                self.time_timer.stop()
                self.logger.info("タイマー停止完了")
            if hasattr(self, 'calendar_refresh_timer') and self.calendar_refresh_timer:
                self.calendar_refresh_timer.stop()
            
            # センサースレッド停止
            if hasattr(self, 'sensor_thread') and self.sensor_thread:
                self.logger.info("センサースレッド停止中...")
                self.sensor_thread.stop()
                if not self.sensor_thread.wait(2000):
                    self.logger.warning("センサースレッド停止タイムアウト")
                else:
                    self.logger.info("センサースレッド正常停止")
            
            # カレンダースレッド安全停止
            if hasattr(self, 'calendar_thread') and self.calendar_thread:
                self.logger.info("🗓 カレンダースレッド安全停止中...")
                try:
                    # シグナル切断
                    if self.calendar_thread.isRunning():
                        self.calendar_thread.calendar_updated.disconnect()
                    
                    # 安全な停止（terminate使わない）
                    if not self.calendar_thread.wait(3000):
                        self.logger.warning("カレンダースレッド停止タイムアウト")
                    else:
                        self.logger.info("カレンダースレッド正常停止")
                        
                except Exception as e:
                    self.logger.warning("カレンダースレッド停止時エラー", error=str(e))
                finally:
                    self.calendar_thread = None
            
            # メモリクリア
            if hasattr(self, 'api_holidays'):
                self.api_holidays.clear()
            if hasattr(self, 'personal_events'):
                self.personal_events.clear()
            if hasattr(self, 'cached_holidays'):
                self.cached_holidays.clear()
                
            self.logger.info("✅ 終了処理完了")
            
        except Exception as e:
            self.logger.error("終了処理エラー", error=str(e))
        finally:
            event.accept()

def main():
    import logging
    logger = logging.getLogger(__name__)
    logger.info("デバッグ: アプリケーション開始")
    
    # Raspberry Pi用プラットフォーム設定
    import os
    
    if 'WAYLAND_DISPLAY' in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'wayland'
    elif 'DISPLAY' in os.environ:
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
    else:
        os.environ['QT_QPA_PLATFORM'] = 'linuxfb'
    
    try:
        app = QApplication(sys.argv)
        dashboard = WebExactDashboard()
        dashboard.showFullScreen()
        
        logger.info("🚀 Dashboard開始")
        logger.info("終了: ESCキーまたはQキー")
        
        result = app.exec_()
        sys.exit(result)
        
    except Exception as e:
        logger.error("エラー発生: %s", e)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()