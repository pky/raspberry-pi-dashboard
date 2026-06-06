"""
DataThreads - データ取得スレッドモジュール
既存dashboard.pyのSensorDataThread, CalendarDataThreadから抽出・独立化

Phase2 Day15実装 - UI基盤・共通モジュール
計画書：FINAL_IMPLEMENTATION_PLAN_V2.md Day15-17
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class SensorDataThread(QThread):
    """
    センサーデータ取得用スレッド（Web監視グラフ統一方式）
    既存dashboard.pyから抽出・独立化
    """
    data_updated = pyqtSignal(dict)
    date_changed = pyqtSignal()  # 日付変更時のシグナルを追加
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("sensordatathread")
        self.running = True
        self.last_check_date = datetime.now().date()  # 前回チェック日を記録
        
    def run(self):
        while self.running:
            try:
                # Web監視グラフと同じ統一JSONファイルから最新センサーデータを取得
                # この方式により、Web・Dashboard・将来のモバイルアプリが同じデータソースを利用
                
                # 実行環境に応じてパスを決定
                script_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(os.path.dirname(script_dir))
                metrics_file = os.path.join(project_root, 'static', 'data', 'metrics.json')
                
                # metrics.jsonから直接データを取得
                try:
                    with open(metrics_file, 'r', encoding='utf-8') as f:
                        metrics_data = json.load(f)
                    latest_metric = metrics_data['metrics'][-1] if metrics_data.get('metrics') else {}
                except Exception as e:
                    self.logger.error(f"metrics.jsonの読み込みエラー: {e}")
                    latest_metric = {}
                
                # DashboardのAPIレスポンス形式に変換
                temp = latest_metric.get('room_temperature')
                humidity = latest_metric.get('humidity')
                co2_ppm = latest_metric.get('co2_ppm')
                
                # 不快度指数を計算
                discomfort_index = None
                comfort_level = "取得中"
                if temp is not None and humidity is not None:
                    # 不快度指数 = 0.81 * 温度 + 0.01 * 湿度 * (0.99 * 温度 - 14.3) + 46.3
                    discomfort_index = 0.81 * temp + 0.01 * humidity * (0.99 * temp - 14.3) + 46.3
                    
                    # 快適度レベル判定
                    if discomfort_index < 55:
                        comfort_level = "寒い"
                    elif discomfort_index < 60:
                        comfort_level = "肌寒い"
                    elif discomfort_index < 65:
                        comfort_level = "涼しい"
                    elif discomfort_index < 70:
                        comfort_level = "快適"
                    elif discomfort_index < 75:
                        comfort_level = "暖かい"
                    elif discomfort_index < 80:
                        comfort_level = "やや暑い"
                    elif discomfort_index < 85:
                        comfort_level = "暑くて不快"
                    else:
                        comfort_level = "非常に不快"
                
                # CO2レベル判定
                co2_level = "正常"
                co2_color = "green"
                co2_message = ""
                if co2_ppm is not None:
                    if co2_ppm < 1000:
                        co2_level = "正常"
                        co2_color = "green"
                    elif co2_ppm < 1500:
                        co2_level = "注意"
                        co2_color = "yellow"
                        co2_message = "換気をして"
                    elif co2_ppm < 3000:
                        co2_level = "警告"
                        co2_color = "orange"
                        co2_message = "換気が必要"
                    else:
                        co2_level = "危険"
                        co2_color = "red"
                        co2_message = "至急換気して！"
                
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
                                   temperature=temp, humidity=humidity, co2_ppm=co2_ppm,
                                   metrics_file=metrics_file)
                else:
                    self.logger.warning("メトリクスデータが空です", metrics_file=metrics_file)
                    
            except Exception as e:
                self.logger.error(f"センサーデータ取得エラー: {e}")
            
            self.msleep(120000)  # 2分間隔（負荷軽減・適切な応答性確保）
    
    def stop(self):
        self.running = False


class CalendarDataThread(QThread):
    """
    カレンダーデータ取得用スレッド
    既存dashboard.pyから抽出・独立化
    """
    calendar_updated = pyqtSignal(dict)  # dashboard_working.pyと一致させる
    
    def __init__(self, year, month):  # dashboard_working.pyと一致させる
        super().__init__()
        self.year = year
        self.month = month
        self.logger = logging.getLogger("calendardatathread")
        self.running = True
        
    def run(self):
        try:
            self.logger.info(f"Calendar API開始: {self.year}年{self.month}月")
            
            # APIリクエスト送信
            import requests
            import json
            params = {'year': self.year, 'month': self.month}
            response = requests.get('http://localhost:5000/api/calendar', params=params, timeout=5)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    # APIレスポンス形式の検証
                    if 'status' in data and data['status'] == 'success' and 'data' in data:
                        self.logger.info(f"Calendar API成功: {self.year}年{self.month}月")
                        self.calendar_updated.emit(data)  # シグナル名を修正
                        return
                    else:
                        self.logger.warning(f"Calendar APIレスポンス形式エラー: {data}")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Calendar API JSON解析エラー: {e}")
            else:
                self.logger.error(f"Calendar APIエラー: HTTP {response.status_code}")
        
        except requests.exceptions.Timeout:
            self.logger.warning(f"Calendar APIタイムアウト: {self.year}年{self.month}月")
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Calendar API接続エラー: {self.year}年{self.month}月")
        except Exception as e:
            self.logger.error(f"Calendar API例外エラー: {e}")
        
        # フォールバック: 基本カレンダーデータ生成
        self.logger.info(f"フォールバック: 基本カレンダー生成 {self.year}年{self.month}月")
        
        import calendar
        month_days = calendar.monthrange(self.year, self.month)[1]
        first_day = datetime(self.year, self.month, 1)
        first_weekday = first_day.weekday()
        
        now = datetime.now()
        days = {}
        for day in range(1, month_days + 1):
            day_date = datetime(self.year, self.month, day)
            is_today = (day_date.date() == now.date())
            is_weekend = day_date.weekday() in [5, 6]
            
            days[str(day)] = {
                'is_today': is_today,
                'is_weekend': is_weekend,
                'is_holiday': False,
                'events': []
            }
        
        fallback_data = {
            'status': 'success',
            'data': {
                'year': self.year,
                'month': self.month,
                'days': days,
                'first_day_weekday': first_weekday
            }
        }
        
        # フォールバックデータを送信
        self.calendar_updated.emit(fallback_data)
    
    def stop(self):
        self.running = False