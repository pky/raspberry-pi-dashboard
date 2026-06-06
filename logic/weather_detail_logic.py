#!/usr/bin/env python3
"""
Weather Detail Logic - 天気詳細データ処理ロジック

JSON読み込み版の天気詳細ロジック
40データポイント → 5日間構造変換

機能:
- weather_data.jsonからの40データポイント読み込み
- 5日間×8時間構造への変換
- 昼夜アイコン判定
- 表示用データフォーマット
- フォールバック機能
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from logging_system import get_logger


class WeatherDetailLogic:
    """天気詳細データ処理ロジック"""
    
    def __init__(self):
        """初期化"""
        self.logger = get_logger("weather_detail_logic")
        self.base_dir = str(Path(__file__).parent.parent)
        self.weather_file = f"{self.base_dir}/cache/weather/weather_data.json"
        
        self.logger.info("WeatherDetailLogic初期化完了")
    
    def prepare_detail_data(self) -> Dict[str, Any]:
        """詳細データ準備 - JSONから40データポイントを5日間構造に変換"""
        try:
            # JSONデータ読み込み
            weather_data = self._load_weather_json()
            
            if not weather_data or 'forecast_list' not in weather_data:
                self.logger.warning("有効な天気データがありません。フォールバック中...")
                return self._generate_fallback_data()
            
            # 40データポイントを日付別に分類
            days_data = self._group_by_date(weather_data['forecast_list'])
            
            # 5日間構造に整理
            structured_data = self._structure_for_display(days_data, weather_data)
            
            self.logger.info(f"詳細データ準備完了 - {len(structured_data['days'])}日間")
            return structured_data
            
        except Exception as e:
            self.logger.error(f"詳細データ準備エラー: {e}")
            return self._generate_fallback_data()
    
    def _load_weather_json(self) -> Optional[Dict]:
        """JSONファイル読み込み"""
        try:
            if os.path.exists(self.weather_file):
                with open(self.weather_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self.logger.debug(f"Weather JSON読み込み成功 - {data.get('forecast_count', 0)}件")
                return data
            else:
                self.logger.warning(f"Weather JSONファイルが見つかりません: {self.weather_file}")
                return None
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON形式エラー: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Weather JSON読み込みエラー: {e}")
            return None
    
    def _group_by_date(self, forecast_list: List[Dict]) -> Dict[str, List[Dict]]:
        """40データポイントを日付別にグループ化"""
        days_data = {}
        
        for item in forecast_list:
            try:
                # 日付部分を抽出（"2025-09-04 15:00:00" → "2025-09-04"）
                date_key = item['date'].split(' ')[0]
                
                if date_key not in days_data:
                    days_data[date_key] = []
                
                # 予報アイテムをフォーマット
                formatted_item = self._format_forecast_item(item)
                days_data[date_key].append(formatted_item)
                
            except Exception as e:
                self.logger.error(f"予報データ処理エラー: {e}, item: {item}")
                continue
        
        self.logger.debug(f"日付別グループ化完了 - {len(days_data)}日間")
        return days_data
    
    def _format_forecast_item(self, item: Dict) -> Dict:
        """予報アイテムをフォーマット"""
        try:
            # 基本データ
            formatted = {
                'time': item['date_display'],           # "09/04 15:00"
                'datetime_str': item['date'],           # "2025-09-04 15:00:00"
                'temperature': item['temperature'],     # 26.7
                'feels_like': item['feels_like'],      # 29.7
                'temp_min': item['temp_min'],           # 26.7
                'temp_max': item['temp_max'],           # 26.9
                'humidity': item['humidity'],           # 86
                'pressure': item['pressure'],           # 1011
                'weather_icon': item['weather_icon'],   # '\uf008'
                'weather_description': item['weather_description'], # "小雨"
                'wind_speed': item.get('wind_speed', 0),            # 2.1
                'wind_deg': item.get('wind_deg', 0),                # 180
                'clouds': item.get('clouds', 0),                    # 100
                'pop': item.get('pop', 0),                          # 降水確率
                'rain_3h': item.get('rain_3h', 0),                  # 3時間降水量
                'is_night': item.get('is_night', False)             # 夜間判定
            }
            
            return formatted
            
        except Exception as e:
            self.logger.error(f"予報アイテムフォーマットエラー: {e}")
            return self._create_fallback_item()
    
    def _structure_for_display(self, days_data: Dict[str, List[Dict]], weather_data: Dict) -> Dict[str, Any]:
        """5日間構造に整理"""
        try:
            structured = {
                'collection_time': weather_data.get('collection_time', ''),
                'location': weather_data.get('location', {}),
                'total_forecasts': sum(len(forecasts) for forecasts in days_data.values()),
                'days': {}
            }
            
            # 日付順でソート
            sorted_dates = sorted(days_data.keys())
            
            for date_key in sorted_dates:
                forecasts = days_data[date_key]
                
                # 日付表示フォーマット生成
                date_display = self._format_date_display(date_key)
                day_of_week = self._get_day_of_week(date_key)
                
                structured['days'][date_key] = {
                    'date': date_key,                    # "2025-09-04"
                    'date_display': date_display,        # "9月4日（木）"
                    'day_of_week': day_of_week,          # "木曜日"
                    'forecast_count': len(forecasts),    # 8
                    'forecasts': sorted(forecasts, key=lambda x: x['datetime_str'])  # 時刻順ソート
                }
            
            self.logger.debug(f"5日間構造化完了 - {len(structured['days'])}日間, 計{structured['total_forecasts']}予報")
            return structured
            
        except Exception as e:
            self.logger.error(f"構造化エラー: {e}")
            return self._generate_fallback_data()
    
    def _format_date_display(self, date_str: str) -> str:
        """日付表示フォーマット生成（日にちのみ）"""
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            # 「今日・明日・明後日」表示を廃止し、常に「月日」形式に統一
            return f"{dt.month}月{dt.day}日"
                
        except Exception as e:
            self.logger.error(f"日付フォーマットエラー: {e}")
            return date_str
    
    def _get_day_of_week(self, date_str: str) -> str:
        """曜日取得"""
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
            return weekdays[dt.weekday()]
        except Exception as e:
            self.logger.error(f"曜日取得エラー: {e}")
            return "不明"
    
    def _create_fallback_item(self) -> Dict:
        """フォールバック予報アイテム作成"""
        return {
            'time': '--:--',
            'datetime_str': '',
            'temperature': 0,
            'feels_like': 0,
            'temp_min': 0,
            'temp_max': 0,
            'humidity': 0,
            'pressure': 1013,
            'weather_icon': '\\uf07b',
            'weather_description': 'データなし',
            'wind_speed': 0,
            'wind_deg': 0,
            'clouds': 0,
            'pop': 0,
            'rain_3h': 0,
            'is_night': False
        }
    
    def _generate_fallback_data(self) -> Dict[str, Any]:
        """フォールバックデータ生成"""
        fallback_data = {
            'collection_time': '',
            'location': {'name': os.environ.get('WEATHER_LOCATION_NAME', '渋谷区鶯谷町')},
            'total_forecasts': 0,
            'days': {}
        }
        
        # 今日から5日間のフォールバックデータ
        today = datetime.now().date()
        for i in range(5):
            target_date = today + timedelta(days=i)
            date_key = target_date.strftime('%Y-%m-%d')
            
            fallback_data['days'][date_key] = {
                'date': date_key,
                'date_display': self._format_date_display(date_key),
                'day_of_week': self._get_day_of_week(date_key),
                'forecast_count': 0,
                'forecasts': []
            }
        
        self.logger.info("フォールバックデータ生成完了")
        return fallback_data
    
    def get_data_source_info(self) -> Dict[str, str]:
        """データソース情報取得（天気バーと同じJSON collection_time使用）"""
        try:
            if os.path.exists(self.weather_file):
                with open(self.weather_file, 'r', encoding='utf-8') as f:
                    weather_data = json.load(f)
                
                # JSONのcollection_timeから更新時刻取得（天気バーと同じロジック）
                collection_time = weather_data.get('collection_time', '')
                if collection_time and 'T' in collection_time:
                    # "2025-09-05T12:03:01.904451" → "12:03"
                    time_part = collection_time.split('T')[1][:5]  # HH:MM
                    update_time = time_part
                else:
                    # collection_timeがない場合はファイル更新時刻をフォールバック
                    mtime = os.path.getmtime(self.weather_file)
                    update_time = datetime.fromtimestamp(mtime).strftime('%H:%M')
                
                return {
                    'source': 'JSON (Cron)',
                    'update_time': update_time
                }
            else:
                return {
                    'source': 'データなし',
                    'update_time': '--:--'
                }
                
        except Exception as e:
            self.logger.error(f"データソース情報取得エラー: {e}")
            return {
                'source': 'エラー',
                'update_time': '--:--'
            }