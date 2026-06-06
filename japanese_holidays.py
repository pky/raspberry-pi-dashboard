#!/usr/bin/env python3
"""
日本の祝日判定モジュール
"""

import datetime
from typing import Dict, List

class JapaneseHolidays:
    """日本の祝日判定クラス"""
    
    def __init__(self):
        """祝日データを初期化"""
        self.fixed_holidays = {
            (1, 1): "元日",
            (2, 11): "建国記念の日",
            (4, 29): "昭和の日",
            (5, 3): "憲法記念日",
            (5, 4): "みどりの日",
            (5, 5): "こどもの日",
            (8, 11): "山の日",
            (11, 3): "文化の日",
            (11, 23): "勤労感謝の日",
            (12, 23): "天皇誕生日"  # 2019年以降
        }
    
    def is_holiday(self, date: datetime.date) -> bool:
        """指定された日付が祝日かどうかを判定"""
        return self.get_holiday_name(date) is not None
    
    def get_holiday_name(self, date: datetime.date) -> str:
        """祝日名を取得（祝日でない場合はNone）"""
        month = date.month
        day = date.day
        year = date.year
        
        # 固定祝日
        if (month, day) in self.fixed_holidays:
            # 天皇誕生日の年代チェック
            if (month, day) == (12, 23) and year < 2019:
                return None
            if (month, day) == (12, 23) and year >= 2019:
                return self.fixed_holidays[(month, day)]
            return self.fixed_holidays[(month, day)]
        
        # 移動祝日
        holiday_name = self._get_moving_holiday(date)
        if holiday_name:
            return holiday_name
        
        # 振替休日
        if self._is_substitute_holiday(date):
            return "振替休日"
        
        return None
    
    def _get_moving_holiday(self, date: datetime.date) -> str:
        """移動祝日の判定"""
        month = date.month
        year = date.year
        
        # 成人の日（1月第2月曜日）
        if month == 1:
            second_monday = self._get_nth_weekday(year, 1, 0, 2)  # 0=月曜日
            if second_monday and date == second_monday:
                return "成人の日"
        
        # 海の日（7月第3月曜日）
        elif month == 7:
            # 2020年は東京オリンピックで7月23日、2021年は7月22日
            if year == 2020 and date.day == 23:
                return "海の日"
            elif year == 2021 and date.day == 22:
                return "海の日"
            else:
                third_monday = self._get_nth_weekday(year, 7, 0, 3)
                if third_monday and date == third_monday:
                    return "海の日"
        
        # 敬老の日（9月第3月曜日）
        elif month == 9:
            third_monday = self._get_nth_weekday(year, 9, 0, 3)
            if third_monday and date == third_monday:
                return "敬老の日"
        
        # スポーツの日（10月第2月曜日）
        elif month == 10:
            second_monday = self._get_nth_weekday(year, 10, 0, 2)
            if second_monday and date == second_monday:
                return "スポーツの日"
        
        # 2020年・2021年の東京オリンピック特別措置（7月）
        elif month == 7:
            if year == 2020 and date.day == 24:
                return "スポーツの日"
            elif year == 2021 and date.day == 23:
                return "スポーツの日"
        
        # 春分の日・秋分の日
        if month == 3:
            spring_equinox = self._calculate_equinox(year, True)
            if date.day == spring_equinox:
                return "春分の日"
        elif month == 9:
            autumn_equinox = self._calculate_equinox(year, False)
            if date.day == autumn_equinox:
                return "秋分の日"
        
        return None
    
    def _get_nth_weekday(self, year: int, month: int, weekday: int, n: int) -> datetime.date:
        """指定された月のn番目の指定曜日を取得"""
        first_day = datetime.date(year, month, 1)
        first_weekday = first_day.weekday()
        
        # 最初の指定曜日を見つける
        days_until_weekday = (weekday - first_weekday) % 7
        first_occurrence = first_day + datetime.timedelta(days=days_until_weekday)
        
        # n番目の発生日を計算
        nth_occurrence = first_occurrence + datetime.timedelta(weeks=n-1)
        
        # 月を超えていないかチェック
        if nth_occurrence.month != month:
            return None
        
        return nth_occurrence
    
    def _calculate_equinox(self, year: int, is_spring: bool) -> int:
        """春分・秋分の日を計算"""
        if is_spring:
            # 春分の日の計算式
            if 1851 <= year <= 1899:
                day = 19.8277
            elif 1900 <= year <= 1979:
                day = 21.124
            elif 1980 <= year <= 2099:
                day = 20.8431
            elif 2100 <= year <= 2150:
                day = 21.851
            else:
                day = 20.8431  # デフォルト
        else:
            # 秋分の日の計算式
            if 1851 <= year <= 1899:
                day = 22.7020
            elif 1900 <= year <= 1979:
                day = 23.73
            elif 1980 <= year <= 2099:
                day = 23.2488
            elif 2100 <= year <= 2150:
                day = 24.2488
            else:
                day = 23.2488  # デフォルト
        
        return int(day + 0.242194 * (year - 1851) - int((year - 1851) / 4))
    
    def _is_substitute_holiday(self, date: datetime.date) -> bool:
        """振替休日の判定"""
        # 月曜日でない場合は振替休日ではない
        if date.weekday() != 0:  # 0 = 月曜日
            return False
        
        # 前日（日曜日）が祝日の場合は振替休日
        prev_day = date - datetime.timedelta(days=1)
        return prev_day.weekday() == 6 and self._is_actual_holiday(prev_day)
    
    def _is_actual_holiday(self, date: datetime.date) -> bool:
        """振替休日を除く実際の祝日かどうかを判定（無限再帰回避）"""
        month = date.month
        day = date.day
        year = date.year
        
        # 固定祝日
        if (month, day) in self.fixed_holidays:
            # 天皇誕生日の年代チェック
            if (month, day) == (12, 23) and year < 2019:
                return False
            return True
        
        # 移動祝日
        holiday_name = self._get_moving_holiday(date)
        return holiday_name is not None

# グローバルインスタンス
japanese_holidays = JapaneseHolidays()

def is_holiday(date: datetime.date) -> bool:
    """指定された日付が祝日かどうかを判定"""
    return japanese_holidays.is_holiday(date)

def get_holiday_name(date: datetime.date) -> str:
    """祝日名を取得"""
    return japanese_holidays.get_holiday_name(date)

def is_weekend_or_holiday(date: datetime.date) -> str:
    """土日祝日の判定（表示用）"""
    # JavaScript形式の曜日に合わせる (0=日曜日, 6=土曜日)
    python_weekday = date.weekday()  # Python: 0=月曜日, 6=日曜日
    js_weekday = (python_weekday + 1) % 7  # JavaScript: 0=日曜日, 6=土曜日
    
    if is_holiday(date):
        return "holiday"  # 祝日（赤）
    elif js_weekday == 0:  # 日曜日
        return "sunday"   # 日曜日（赤）
    elif js_weekday == 6:  # 土曜日
        return "saturday" # 土曜日（青）
    else:
        return "weekday"  # 平日（通常）