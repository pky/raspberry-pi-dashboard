"""
CalendarLogic - カレンダー祝日処理ロジック
既存dashboard.pyの祝日API処理から抽出・独立化

Phase2 Day22-24実装 - ロジック分離
計画書：SEPARATION_APPROACH_DESIGN.md Phase4
"""

import json
from datetime import datetime, date
from pathlib import Path
from logging_system import get_logger


class CalendarLogic:
    """
    カレンダー祝日処理ロジッククラス
    既存dashboard.pyの祝日関連処理から抽出・独立化
    """
    
    def __init__(self):
        self.logger = get_logger("calendar_logic")
        self.holidays = {}  # 古い固定祝日データは削除、APIで動的取得
        self.api_holidays = {}  # APIから取得した祝日データ
        self.cached_holidays = self.load_holiday_cache_immediate()
        
    def load_holiday_cache_immediate(self):
        """起動時に祝日キャッシュを即座に読み込み"""
        try:
            cache_file = Path(f"cache/holidays/holidays_{datetime.now().year}.json")
            if cache_file.exists():
                with cache_file.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                holidays = data.get('holidays', [])
                self.logger.info("🎌 起動時祝日キャッシュ読み込み: {len(holidays)}件")
                return holidays
            else:
                self.logger.warning("祝日キャッシュファイルが見つかりません")
                return []
        except Exception as e:
            self.logger.info("祝日キャッシュ読み込みエラー:", e=e)
            return []
    
    def is_cached_holiday(self, target_date):
        """キャッシュから指定日の祝日判定"""
        if not hasattr(self, 'cached_holidays') or not self.cached_holidays:
            return False
            
        if isinstance(target_date, tuple):
            year, month, day = target_date
            target_date = date(year, month, day)
        
        for holiday in self.cached_holidays:
            holiday_datetime_str = holiday.get('start_datetime', '')
            if holiday_datetime_str:
                try:
                    holiday_date_str = holiday_datetime_str[:10]  # YYYY-MM-DD部分
                    holiday_date = date.fromisoformat(holiday_date_str)
                    
                    if holiday_date == target_date:
                        holiday_name = holiday.get('title', '祝日')
                        self.logger.info("🎌 キャッシュ祝日適用: 日 -", day=target_date.day, holiday_name=holiday_name)
                        return True
                except ValueError:
                    continue
        
        return False
    
    def is_holiday(self, year, month, day):
        """指定日が祝日かどうかを判定"""
        # 静的祝日 + API祝日 + キャッシュ祝日の全てをチェック
        static_holiday = (year, month, day) in self.holidays
        api_holiday = (year, month, day) in self.api_holidays
        cached_holiday = self.is_cached_holiday((year, month, day))
        
        return static_holiday or api_holiday or cached_holiday
    
    def get_holiday_name(self, year, month, day):
        """指定日の祝日名を取得（API優先）"""
        return (self.api_holidays.get((year, month, day), "") or 
               self.holidays.get((year, month, day), ""))
    
    def update_holiday_data(self, api_data, current_date):
        """カレンダーAPIデータから祝日データを更新"""
        holidays_count = 0
        
        # Web版API形式: data.calendar_data.days
        if api_data and 'data' in api_data and 'calendar_data' in api_data['data'] and 'days' in api_data['data']['calendar_data']:
            days_data = api_data['data']['calendar_data']['days']
            
            for day, day_info in days_data.items():
                try:
                    day = int(day)
                    
                    # 祝日データを取得（is_holiday=trueのみを信頼）
                    holiday_name = None
                    is_holiday_flag = day_info.get('is_holiday', False)
                    api_holiday_name = day_info.get('holiday_name')
                    day_type = day_info.get('day_type', '')
                    
                    self.logger.debug("日の判定: is_holiday=, holiday_name=, day_type=", day=day, is_holiday_flag=is_holiday_flag, api_holiday_name=api_holiday_name)
                    
                    # is_holiday=trueの場合のみ祝日として扱う
                    if is_holiday_flag:
                        # eventsから祝日名を取得（holiday_nameがnullの場合）
                        if api_holiday_name and api_holiday_name.strip():
                            holiday_name = api_holiday_name
                        else:
                            # eventsから日本の祝日を探す
                            events = day_info.get('events', [])
                            for event in events:
                                if isinstance(event, dict) and event.get('type') == 'japanese_holiday':
                                    holiday_name = event.get('title', '祝日')
                                    break
                            if not holiday_name:
                                holiday_name = '祝日'  # フォールバック
                        
                        # 祝日として登録
                        self.api_holidays[(current_date.year, current_date.month, day)] = holiday_name
                        holidays_count += 1
                        self.logger.info("📅 祝日追加: --", year=current_date.year, month=current_date.month, day=day)
                    else:
                        # is_holiday=falseの場合は祝日として扱わない
                        if api_holiday_name and api_holiday_name.strip():
                            self.logger.info("🚫 is_holiday=falseのため祝日として扱いません: 日  (day_type: )", day=day, api_holiday_name=api_holiday_name, day_type=day_type)
                        elif day_type == 'holiday':
                            self.logger.info("🚫 day_type=holidayですがis_holiday=falseのため祝日として扱いません: 日", day=day)
                
                except (ValueError, TypeError) as e:
                    self.logger.error("日付データ処理エラー", day=day, error=str(e))
                    continue
        else:
            self.logger.error("APIデータ形式が不正または空です")
            self.logger.info("受信データ構造確認", data_type=type(api_data).__name__, data_keys=str(list(api_data.keys()) if isinstance(api_data, dict) else "not_dict"))
        
        self.logger.success("📅 APIデータ読み込み完了: 祝日件", holidays_count=holidays_count)
        return holidays_count
    
    def clear_api_holidays(self):
        """API祝日データをクリア"""
        self.api_holidays.clear()
    
    def clear_all_holidays(self):
        """全祝日データをクリア"""
        self.api_holidays.clear()
        if hasattr(self, 'cached_holidays'):
            self.cached_holidays.clear()