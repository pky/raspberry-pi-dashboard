#!/usr/bin/env python3
"""
祝日データキャッシュシステム
Google Calendar APIから祝日を取得してローカルに保存し、安定したアクセスを提供
"""

import os
import json
import logging
import requests
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
from io import StringIO
from logging_system import get_logger

try:
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

from calendar_auth import get_calendar_auth
from config import get_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HolidayCache:
    """日本祝日データのキャッシュ管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.settings = get_config()
        self.cache_dir = Path("cache/holidays")
        self.cache_file = self.cache_dir / "japanese_holidays_cache.json"
        
        # キャッシュディレクトリ作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("祝日キャッシュシステムが初期化されました")
    
    def get_cache_path(self, year: int) -> Path:
        """年別のキャッシュファイルパスを取得"""
        return self.cache_dir / f"holidays_{year}.json"
    
    def is_cache_valid(self, year: int) -> bool:
        """キャッシュが有効かどうかチェック"""
        cache_path = self.get_cache_path(year)
        
        if not cache_path.exists():
            return False
        
        try:
            # ファイルの更新日時をチェック
            file_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            now = datetime.now()
            
            # 年に一度の更新戦略
            current_year = now.year
            
            if current_year - 1 <= year <= current_year + 1:
                # 前年・今年・翌年のデータ: 3月1日以降に更新されていれば有効
                mar_1st = datetime(current_year, 3, 1)
                is_valid = file_mtime >= mar_1st
                
                if not is_valid:
                    logger.info(f"{year}年祝日キャッシュ: 3月1日以前のデータのため更新が必要")
                else:
                    logger.info(f"{year}年祝日キャッシュ: 3月1日以降のデータのため有効")
            
            else:
                # 過去または2年以上先のデータ: 365日以内なら有効
                cache_age = now - file_mtime
                is_valid = cache_age.days < 365
                
                logger.info(f"{year}年祝日キャッシュ: {cache_age.days}日経過, 有効={is_valid}")
            
            return is_valid
            
        except Exception as e:
            logger.warning(f"キャッシュ有効性チェックエラー: {e}")
            return False
    
    def load_cached_holidays(self, year: int) -> Optional[List[Dict[str, Any]]]:
        """キャッシュから祝日データを読み込み"""
        cache_path = self.get_cache_path(year)
        
        if not self.is_cache_valid(year):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            holidays = data.get('holidays', [])
            logger.info(f"{year}年祝日キャッシュから{len(holidays)}件を読み込み")
            return holidays
            
        except Exception as e:
            logger.error(f"キャッシュ読み込みエラー: {e}")
            return None
    
    def save_holidays_to_cache(self, year: int, holidays: List[Dict[str, Any]]):
        """祝日データをキャッシュに保存"""
        cache_path = self.get_cache_path(year)
        
        try:
            # 保存用データを準備（datetime → ISO文字列変換）
            serializable_holidays = []
            for holiday in holidays:
                holiday_copy = holiday.copy()
                
                # datetime オブジェクトを ISO 文字列に変換
                for key in ['start_datetime', 'end_datetime']:
                    if isinstance(holiday_copy.get(key), datetime):
                        holiday_copy[key] = holiday_copy[key].isoformat()
                
                serializable_holidays.append(holiday_copy)
            
            cache_data = {
                'year': year,
                'cached_at': datetime.now().isoformat(),
                'holidays': serializable_holidays
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"{year}年祝日データ{len(holidays)}件をキャッシュに保存しました")
            
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
    
    def fetch_holidays_from_cabinet_office(self, year: int) -> List[Dict[str, Any]]:
        """内閣府から正式な祝日データを取得"""
        try:
            # 内閣府の祝日データURL
            url = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv"
            
            logger.info(f"内閣府から{year}年の祝日データを取得中...")
            response = requests.get(url, timeout=10)
            response.encoding = 'shift_jis'  # 内閣府のCSVはShift_JIS
            
            if response.status_code != 200:
                logger.error(f"内閣府祝日データ取得エラー: HTTP {response.status_code}")
                return []
            
            # CSVデータを解析
            holidays = []
            csv_data = StringIO(response.text)
            csv_reader = csv.reader(csv_data)
            
            # ヘッダーをスキップ
            next(csv_reader, None)
            
            for row in csv_reader:
                if len(row) >= 2:
                    date_str = row[0].strip()  # 日付（YYYY/M/D形式）
                    name = row[1].strip()      # 祝日名
                    
                    try:
                        # 日付をパース（YYYY/M/D → YYYY-MM-DD）
                        holiday_date = datetime.strptime(date_str, '%Y/%m/%d')
                        
                        # 指定年の祝日のみを抽出
                        if holiday_date.year == year:
                            holiday_data = {
                                'id': f"jp_official_{holiday_date.strftime('%Y%m%d')}_{hash(name) % 10000:04d}",
                                'title': name,
                                'description': '日本の祝日（内閣府公式）',
                                'start_datetime': holiday_date,
                                'end_datetime': holiday_date,
                                'all_day': True,
                                'location': '',
                                'type': 'japanese_holiday'
                            }
                            holidays.append(holiday_data)
                    
                    except ValueError as e:
                        logger.warning(f"日付パースエラー: {date_str} - {e}")
                        continue
            
            logger.info(f"内閣府から{year}年の正式な祝日{len(holidays)}件を取得")
            return holidays
            
        except requests.RequestException as e:
            logger.error(f"内閣府祝日データ取得エラー: {e}")
            return []
        except Exception as e:
            logger.error(f"祝日データ解析エラー: {e}")
            return []
    
    def fetch_holidays_from_google(self, year: int) -> List[Dict[str, Any]]:
        """Google Calendar APIから祝日データを取得"""
        if not GOOGLE_LIBS_AVAILABLE:
            logger.warning("Google APIライブラリが利用できません")
            return []
        
        try:
            auth = get_calendar_auth()
            service = auth.get_service()
            
            if not service:
                logger.warning("Google Calendar APIサービスが利用できません")
                return []
            
            # 1年分のデータを取得
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
            
            time_min = start_date.strftime('%Y-%m-%dT00:00:00Z')
            time_max = end_date.strftime('%Y-%m-%dT23:59:59Z')
            
            # 日本の祝日カレンダーから取得
            result = service.events().list(
                calendarId='ja.japanese#holiday@group.v.calendar.google.com',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = result.get('items', [])
            holidays = []
            
            # 正式な祝日のみを抽出するフィルター
            official_holidays = {
                '元日', '成人の日', '建国記念の日', '天皇誕生日', '春分の日',
                '昭和の日', '憲法記念日', 'みどりの日', 'こどもの日', '海の日',
                '山の日', '敬老の日', '秋分の日', 'スポーツの日', '文化の日',
                '勤労感謝の日', '振替休日', '国民の休日'
            }
            
            for event in events:
                # イベントデータを整形
                start = event.get('start', {})
                if 'date' in start:
                    start_datetime = datetime.fromisoformat(start['date'])
                    end_datetime = start_datetime
                    all_day = True
                else:
                    continue  # 終日イベント以外はスキップ
                
                title = event.get('summary', '')
                
                # 正式な祝日のみを含める（文化的行事を除外）
                is_official_holiday = any(
                    official_name in title for official_name in official_holidays
                )
                
                if not is_official_holiday:
                    logger.info(f"文化的行事を除外: {title} ({start_datetime.strftime('%Y-%m-%d')})")
                    continue
                
                holiday_data = {
                    'id': event.get('id'),
                    'title': title,
                    'description': '日本の祝日',
                    'start_datetime': start_datetime,
                    'end_datetime': end_datetime,
                    'all_day': all_day,
                    'location': '',
                    'type': 'japanese_holiday'
                }
                
                holidays.append(holiday_data)
            
            logger.info(f"Google Calendarから{year}年の祝日{len(holidays)}件を取得")
            return holidays
            
        except HttpError as e:
            logger.error(f"Google Calendar API エラー: {e}")
            return []
        except Exception as e:
            logger.error(f"祝日データ取得エラー: {e}")
            return []
    
    def get_holidays_for_year(self, year: int) -> List[Dict[str, Any]]:
        """指定年の祝日データを取得（自動更新対応）"""
        
        # 0. 自動更新チェック
        self.check_and_update_if_needed(year)
        
        # 1. キャッシュから読み込み試行
        cached_holidays = self.load_cached_holidays(year)
        if cached_holidays:
            # datetime文字列をdatetimeオブジェクトに復元
            for holiday in cached_holidays:
                for key in ['start_datetime', 'end_datetime']:
                    if isinstance(holiday.get(key), str):
                        try:
                            holiday[key] = datetime.fromisoformat(holiday[key])
                        except ValueError:
                            pass
            return cached_holidays
        
        # 2. 内閣府から正式な祝日データを取得（優先）
        logger.info(f"{year}年の祝日データを内閣府から取得中...")
        fresh_holidays = self.fetch_holidays_from_cabinet_office(year)
        
        # 3. 内閣府で取得できない場合の対応
        if not fresh_holidays:
            logger.warning(f"内閣府データが取得できませんでした。Google Calendar APIは不正確なため使用しません。")
            # Google Calendar APIは文化的行事も含むため使用せず、空のリストを返す
        
        # 4. 取得成功時はキャッシュに保存
        if fresh_holidays:
            self.save_holidays_to_cache(year, fresh_holidays)
        
        return fresh_holidays
    
    def get_holidays_for_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """指定月の祝日データを取得"""
        year_holidays = self.get_holidays_for_year(year)
        
        month_holidays = []
        for holiday in year_holidays:
            start_date = holiday['start_datetime']
            if isinstance(start_date, datetime) and start_date.month == month:
                month_holidays.append(holiday)
        
        logger.info(f"{year}年{month}月の祝日{len(month_holidays)}件を取得")
        return month_holidays
    
    def refresh_cache(self, year: int) -> bool:
        """キャッシュを強制更新"""
        logger.info(f"{year}年祝日キャッシュを強制更新中...")
        
        # 内閣府から取得を試行
        fresh_holidays = self.fetch_holidays_from_cabinet_office(year)
        
        # フォールバック: Google Calendar APIは使用しない（不正確なため）
        if not fresh_holidays:
            logger.warning(f"内閣府データが取得できませんでした。Google Calendar APIは使用しません。")
        
        if fresh_holidays:
            self.save_holidays_to_cache(year, fresh_holidays)
            logger.info(f"{year}年祝日キャッシュを更新しました")
            return True
        else:
            logger.warning(f"{year}年祝日データの更新に失敗しました")
            return False
    
    def clear_cache(self, year: Optional[int] = None):
        """キャッシュをクリア"""
        if year:
            cache_path = self.get_cache_path(year)
            if cache_path.exists():
                cache_path.unlink()
                logger.info(f"{year}年祝日キャッシュを削除しました")
        else:
            # 全キャッシュクリア
            for cache_file in self.cache_dir.glob("holidays_*.json"):
                cache_file.unlink()
            logger.info("全祝日キャッシュを削除しました")
    
    def should_update_today(self, year: int) -> bool:
        """今日更新すべきかどうかを判定"""
        now = datetime.now()
        current_year = now.year
        
        # 3月1日の年次更新（前後1年分）
        if now.month == 3 and now.day == 1:
            if current_year - 1 <= year <= current_year + 1:
                logger.info(f"年次祝日データ更新のため{year}年を更新します")
                return True
        
        return False
    
    def check_and_update_if_needed(self, year: int) -> bool:
        """必要に応じて祝日データを自動更新"""
        # 特定の日付での自動更新
        if self.should_update_today(year):
            return self.refresh_cache(year)
        
        # 通常のキャッシュ有効性チェック
        if not self.is_cache_valid(year):
            logger.info(f"{year}年祝日データの更新が必要です")
            return self.refresh_cache(year)
        
        return True
    
    def bulk_update_holidays(self, years: List[int] = None) -> Dict[int, bool]:
        """複数年の祝日データを一括更新"""
        if years is None:
            # デフォルト: 前年、今年、翌年
            current_year = datetime.now().year
            years = [current_year - 1, current_year, current_year + 1]
        
        results = {}
        logger.info(f"複数年祝日データ一括更新開始: {years}")
        
        for year in years:
            try:
                success = self.refresh_cache(year)
                results[year] = success
                if success:
                    logger.info(f"✅ {year}年祝日データ更新成功")
                else:
                    logger.warning(f"❌ {year}年祝日データ更新失敗")
            except Exception as e:
                logger.error(f"❌ {year}年祝日データ更新エラー: {e}")
                results[year] = False
        
        success_count = sum(results.values())
        logger.info(f"一括更新完了: {success_count}/{len(years)}年成功")
        return results

# グローバルキャッシュインスタンス
_holiday_cache = None

def get_holiday_cache() -> HolidayCache:
    """シングルトン祝日キャッシュインスタンスを取得"""
    global _holiday_cache
    if _holiday_cache is None:
        _holiday_cache = HolidayCache()
    return _holiday_cache

if __name__ == "__main__":
    # テスト実行
    cache = get_holiday_cache()
    
    # 2025年の祝日を取得
    holidays = cache.get_holidays_for_year(2025)
    self.logger.info("2025年祝日: {len(holidays)}件")
    
    for holiday in holidays[:5]:
        self.logger.info("- {holiday['start_datetime'].strftime('%m-%d')}: {holiday['title']}")