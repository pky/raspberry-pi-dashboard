"""
Google Calendar データ取得モジュール
指定月のカレンダーイベント取得と日本の祝日データ統合機能を実装
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import calendar as cal_module
import json

try:
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    logging.warning("Google API libraries not available. Running in simulation mode.")

from calendar_auth import get_calendar_auth
from service_account_auth import get_service_account_auth
from config import get_config
from holiday_cache import get_holiday_cache

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 日本の祝日データ（2024-2025年）
JAPANESE_HOLIDAYS = {
    "2024": {
        "01-01": "元日",
        "01-08": "成人の日",
        "02-11": "建国記念の日",
        "02-12": "振替休日",
        "02-23": "天皇誕生日",
        "03-20": "春分の日",
        "04-29": "昭和の日",
        "05-03": "憲法記念日",
        "05-04": "みどりの日",
        "05-05": "こどもの日",
        "05-06": "振替休日",
        "07-15": "海の日",
        "08-11": "山の日",
        "08-12": "振替休日",
        "09-16": "敬老の日",
        "09-22": "秋分の日",
        "09-23": "振替休日",
        "10-14": "スポーツの日",
        "11-03": "文化の日",
        "11-04": "振替休日",
        "11-23": "勤労感謝の日"
    },
    "2025": {
        "01-01": "元日",
        "01-13": "成人の日",
        "02-11": "建国記念の日",
        "02-23": "天皇誕生日",
        "02-24": "振替休日",
        "03-20": "春分の日",
        "04-29": "昭和の日",
        "05-03": "憲法記念日",
        "05-04": "みどりの日",
        "05-05": "こどもの日",
        "05-06": "振替休日",
        "07-21": "海の日",
        "08-11": "山の日",
        "09-15": "敬老の日",
        "09-23": "秋分の日",
        "10-13": "スポーツの日",
        "11-03": "文化の日",
        "11-23": "勤労感謝の日",
        "11-24": "振替休日"
    }
}

class CalendarDataManager:
    """
    Google Calendar データ管理クラス
    カレンダーイベント取得と祝日データ統合を実装
    
    サービスアカウント認証とOAuth2認証の両方に対応し、
    完全自動化を実現
    
    要件: 1.1, 1.2, 7.6
    """
    
    def __init__(self, auth_method: str = "service_account"):
        """
        カレンダーデータ管理クラスの初期化
        
        Args:
            auth_method: 認証方式 ("service_account" or "oauth")
        """
        self.config = get_config()
        self.auth_method = auth_method
        self.calendar_id = self.config.GOOGLE_CALENDAR_ID
        
        # 認証方式に応じて認証オブジェクトを初期化
        if auth_method == "service_account":
            self.auth = get_service_account_auth()
            logger.info("カレンダーデータ管理クラス（サービスアカウント認証）が初期化されました")
        else:
            self.auth = get_calendar_auth()
            logger.info("カレンダーデータ管理クラス（OAuth2認証）が初期化されました")
    
    def get_month_events(self, year: int, month: int, use_cache_priority: bool = True, monitor_mode: bool = False) -> Dict[str, Any]:
        """
        指定月のカレンダーイベントを取得
        
        Args:
            year: 年
            month: 月 (1-12)
            use_cache_priority: キャッシュ優先表示を使用するか（要件1.6対応）
            monitor_mode: 監視モード（軽量処理）
            
        Returns:
            Dict: カレンダーデータ
            
        要件: 1.1 - 指定月のカレンダーイベントを取得する機能
        要件: 1.6 - キャッシュ優先表示機能
        """
        try:
            # 要件1.6: キャッシュ優先表示システムを使用
            if use_cache_priority:
                try:
                    from calendar_cache_priority import get_calendar_cache_priority
                    cache_priority = get_calendar_cache_priority()
                    priority_result = cache_priority.get_calendar_with_cache_priority(year, month, monitor_mode=monitor_mode)
                    
                    # キャッシュ優先システムが成功した場合はそれを返す
                    if priority_result.get('status') in ['success', 'fallback']:
                        logger.info(f"キャッシュ優先システム使用: {year}年{month}月 - {priority_result.get('cache_priority_status', {}).get('display_source', 'unknown')}")
                        return priority_result
                    else:
                        logger.warning(f"キャッシュ優先システム失敗、標準モードにフォールバック: {year}年{month}月")
                except Exception as e:
                    logger.warning(f"キャッシュ優先システムエラー、標準モードにフォールバック: {e}")
            
            # 標準モード: 従来の処理
            # 月の開始日と終了日を計算
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # 個人予定をキャッシュから取得（自動更新機能付き）
            try:
                from personal_events_cache import get_personal_events_cache
                personal_cache = get_personal_events_cache()
                # 新しい自動更新機能を使用（1日前なら新しく取得）
                google_events = personal_cache.load_events_with_auto_update(year, month)
                
                if google_events:
                    logger.info(f"個人予定を取得: {len(google_events)}件 ({year}年{month}月)")
                else:
                    logger.info(f"個人予定なし（キャッシュ済み）: {year}年{month}月")
                    
            except Exception as e:
                logger.warning(f"個人予定取得エラー: {e}")
                google_events = []
            
            # 祝日データは安定したキャッシュシステムから取得
            holiday_cache = get_holiday_cache()
            cached_holidays = holiday_cache.get_holidays_for_month(year, month)
            
            # キャッシュされた祝日データを統合
            holidays = []
            for holiday in cached_holidays:
                # キャッシュからのデータを標準形式に変換
                holiday_data = {
                    'id': holiday.get('id', f'cached_holiday_{holiday["start_datetime"].strftime("%Y%m%d")}'),
                    'title': holiday.get('title', ''),
                    'description': '日本の祝日（キャッシュ）',
                    'start_datetime': holiday['start_datetime'],
                    'end_datetime': holiday.get('end_datetime', holiday['start_datetime']),
                    'all_day': True,
                    'location': '',
                    'type': 'japanese_holiday'
                }
                holidays.append(holiday_data)
            
            logger.info(f"祝日キャッシュから{len(holidays)}件を取得。個人予定{len(google_events)}件。")
            
            # カレンダーデータを構築
            calendar_data = self._build_calendar_data(year, month, google_events, holidays)
            
            logger.info(f"{year}年{month}月のカレンダーデータを取得しました")
            
            return {
                'status': 'success',
                'year': year,
                'month': month,
                'calendar_data': calendar_data,
                'google_events_count': len(google_events),
                'holidays_count': len(holidays),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"カレンダーデータ取得エラー: {e}")
            return {
                'status': 'error',
                'year': year,
                'month': month,
                'calendar_data': None,
                'google_events_count': 0,
                'holidays_count': 0,
                'error': str(e)
            }
    
    def _get_google_personal_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Google Calendar から個人予定のみを取得（祝日は除く）
        
        Args:
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            List[Dict]: 個人イベントリスト
        """
        if not GOOGLE_LIBS_AVAILABLE:
            # シミュレーションモード
            return self._get_simulated_events(start_date, end_date)
        
        try:
            service = self.auth.get_service()
            if not service:
                logger.warning("Google Calendar APIサービスが利用できません（個人予定をスキップ）")
                return []
            
            # イベント取得のパラメータ
            time_min = start_date.strftime('%Y-%m-%dT00:00:00Z')
            time_max = end_date.strftime('%Y-%m-%dT23:59:59Z')
            
            personal_events = []
            
            # 個人カレンダーからイベントを取得（認証エラーを適切にハンドル）
            try:
                personal_events_result = service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = personal_events_result.get('items', [])
                for event in events:
                    formatted_event = self._format_google_event(event, 'google_event')
                    if formatted_event:
                        personal_events.append(formatted_event)
                
                logger.info(f"個人カレンダーから{len(personal_events)}件のイベントを取得しました")
                
            except HttpError as e:
                if e.resp.status == 401:
                    logger.warning("認証エラー: 個人予定の取得をスキップします")
                else:
                    logger.error(f"個人カレンダー取得エラー: {e}")
            except Exception as e:
                logger.warning(f"個人カレンダー取得で予期しないエラー: {e}")
            
            return personal_events
            
        except Exception as e:
            logger.error(f"イベント取得エラー: {e}")
            return []
    
    def _format_google_event(self, event: Dict[str, Any], event_type: str = 'google_event') -> Optional[Dict[str, Any]]:
        """
        Google Calendar イベントを整形
        
        Args:
            event: Google Calendar イベント
            event_type: イベントのタイプ ('google_event' or 'japanese_holiday')
            
        Returns:
            Dict: 整形されたイベント
        """
        try:
            # イベントの開始時刻を取得
            start = event.get('start', {})
            if 'dateTime' in start:
                # 時刻指定のイベント
                start_datetime = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                all_day = False
            elif 'date' in start:
                # 終日イベント
                start_datetime = datetime.fromisoformat(start['date'])
                all_day = True
            else:
                logger.warning(f"イベントの開始時刻が不明: {event.get('id')}")
                return None
            
            # イベントの終了時刻を取得
            end = event.get('end', {})
            if 'dateTime' in end:
                end_datetime = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
            elif 'date' in end:
                end_datetime = datetime.fromisoformat(end['date'])
            else:
                end_datetime = start_datetime
            
            return {
                'id': event.get('id'),
                'title': event.get('summary', '無題'),
                'description': event.get('description', ''),
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
                'all_day': all_day,
                'location': event.get('location', ''),
                'type': event_type
            }
            
        except Exception as e:
            logger.error(f"イベント整形エラー: {e}")
            return None
    
    def _get_simulated_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        シミュレーション用のイベントデータを生成
        
        Args:
            start_date: 開始日
            end_date: 終了日
            
        Returns:
            List[Dict]: シミュレーションイベント
        """
        events = []
        
        # サンプルイベントを生成
        sample_events = [
            {
                'title': '会議',
                'description': 'プロジェクト進捗会議',
                'day_offset': 5,
                'hour': 10,
                'duration': 2
            },
            {
                'title': '歯医者',
                'description': '定期検診',
                'day_offset': 12,
                'hour': 14,
                'duration': 1
            },
            {
                'title': '買い物',
                'description': '食材の買い出し',
                'day_offset': 20,
                'hour': 16,
                'duration': 1
            }
        ]
        
        for i, sample in enumerate(sample_events):
            event_date = start_date + timedelta(days=sample['day_offset'])
            if event_date <= end_date:
                start_datetime = event_date.replace(hour=sample['hour'], minute=0, second=0)
                end_datetime = start_datetime + timedelta(hours=sample['duration'])
                
                events.append({
                    'id': f'sim_{i}',
                    'title': sample['title'],
                    'description': sample['description'],
                    'start_datetime': start_datetime,
                    'end_datetime': end_datetime,
                    'all_day': False,
                    'location': '',
                    'type': 'simulated_event'
                })
        
        logger.info(f"シミュレーションイベント{len(events)}件を生成しました")
        return events
    
    def _get_japanese_holidays(self, year: int, month: int) -> List[Dict[str, Any]]:
        """
        日本の祝日データを取得
        
        Args:
            year: 年
            month: 月
            
        Returns:
            List[Dict]: 祝日リスト
            
        要件: 1.2 - 日本の祝日データを統合する機能
        """
        holidays = []
        year_str = str(year)
        
        if year_str not in JAPANESE_HOLIDAYS:
            logger.warning(f"{year}年の祝日データが見つかりません")
            return holidays
        
        year_holidays = JAPANESE_HOLIDAYS[year_str]
        
        for date_str, holiday_name in year_holidays.items():
            holiday_month = int(date_str.split('-')[0])
            holiday_day = int(date_str.split('-')[1])
            
            if holiday_month == month:
                holiday_date = datetime(year, month, holiday_day)
                holidays.append({
                    'id': f'holiday_{year}_{date_str}',
                    'title': holiday_name,
                    'description': '日本の祝日',
                    'start_datetime': holiday_date,
                    'end_datetime': holiday_date,
                    'all_day': True,
                    'location': '',
                    'type': 'japanese_holiday'
                })
        
        logger.info(f"{year}年{month}月の祝日{len(holidays)}件を取得しました")
        return holidays
    
    def _build_calendar_data(self, year: int, month: int, google_events: List[Dict], holidays: List[Dict]) -> Dict[str, Any]:
        """
        カレンダーデータを構築
        
        Args:
            year: 年
            month: 月
            google_events: Google Calendar イベント
            holidays: 祝日データ
            
        Returns:
            Dict: 構築されたカレンダーデータ
        """
        # 月の日数を取得
        days_in_month = cal_module.monthrange(year, month)[1]
        
        # 月の最初の日の曜日を取得してJavaScript形式に変換 (0=日曜日, 6=土曜日)
        python_first_day = cal_module.monthrange(year, month)[0]  # Python: 0=月曜日
        first_day_weekday = (python_first_day + 1) % 7  # JavaScript: 0=日曜日
        
        # 日別のイベントデータを初期化
        days_data = {}
        for day in range(1, days_in_month + 1):
            # JavaScript形式の曜日 (0=日曜日, 6=土曜日)
            js_weekday = (first_day_weekday + day - 1) % 7
            days_data[str(day)] = {
                'date': datetime(year, month, day),
                'weekday': js_weekday,
                'events': [],
                'is_holiday': False,
                'holiday_name': None
            }
        
        # Google Calendar イベントを日別に分類（複数日イベント対応）
        for event in google_events:
            # 文字列形式の日付をdatetimeオブジェクトに変換
            if isinstance(event['start_datetime'], str):
                try:
                    if 'T' in event['start_datetime']:
                        start_date = datetime.fromisoformat(event['start_datetime'].replace('Z', '+00:00')).date()
                    else:
                        start_date = datetime.strptime(event['start_datetime'], '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Invalid start_datetime format: {event['start_datetime']}")
                    continue
            else:
                start_date = event['start_datetime'].date()
                
            if isinstance(event['end_datetime'], str):
                try:
                    if 'T' in event['end_datetime']:
                        end_date = datetime.fromisoformat(event['end_datetime'].replace('Z', '+00:00')).date()
                    else:
                        end_date = datetime.strptime(event['end_datetime'], '%Y-%m-%d').date()
                except ValueError:
                    logger.warning(f"Invalid end_datetime format: {event['end_datetime']}")
                    continue
            else:
                end_date = event['end_datetime'].date()
            
            # 終日イベントの場合、Google Calendarは終了日を次の日の00:00として設定するため調整
            if event['all_day'] and end_date > start_date:
                end_date = end_date - timedelta(days=1)
            
            # 複数日にわたるイベントの場合、期間中のすべての日に追加
            current_date = start_date
            while current_date <= end_date:
                # 当月内の日付のみ処理
                if current_date.year == year and current_date.month == month:
                    event_day = current_date.day
                    event_day_key = str(event_day)
                    if event_day_key in days_data:
                        # イベントのコピーを作成（日付情報を調整）
                        event_copy = event.copy()
                        
                        # 複数日イベントの場合、タイトルに期間情報を追加
                        if start_date != end_date:
                            # 開始日の場合
                            if current_date == start_date:
                                event_copy['title'] = f"{event['title']} (開始)"
                            # 終了日の場合
                            elif current_date == end_date:
                                event_copy['title'] = f"{event['title']} (終了)"
                            # 中間日の場合
                            else:
                                event_copy['title'] = f"{event['title']} (継続)"
                        
                        days_data[event_day_key]['events'].append(event_copy)
                        
                        # Google Calendar APIから取得した祝日の場合、is_holidayをTrueに設定
                        if event['type'] == 'japanese_holiday':
                            days_data[event_day_key]['is_holiday'] = True
                            days_data[event_day_key]['holiday_name'] = event['title']
                            # デバッグ: 祝日フラグ設定の詳細ログ
                            logger.info(f"祝日フラグ設定: {year}年{month}月{event_day}日 - {event['title']}")
                            logger.info(f"  イベント開始日時: {event['start_datetime']}")
                            logger.info(f"  計算された日付: {current_date}")
                
                current_date += timedelta(days=1)
        
        # 固定祝日データは使用しない（Google Calendar APIで完全カバーのため）
        # 万が一Google Calendar APIで取得できなかった祝日のみフォールバックとして使用
        for holiday in holidays:
            holiday_day = holiday['start_datetime'].day
            holiday_day_key = str(holiday_day)
            if holiday_day_key in days_data:
                # 同じ日にGoogle Calendar APIからの祝日がない場合のみ追加
                has_google_holiday = any(
                    event['type'] == 'japanese_holiday' 
                    for event in days_data[holiday_day_key]['events']
                )
                if not has_google_holiday:
                    days_data[holiday_day_key]['events'].append(holiday)
                    days_data[holiday_day_key]['is_holiday'] = True
                    days_data[holiday_day_key]['holiday_name'] = holiday['title']
        
        # 各日のイベントを時刻順にソート（datetime型とstr型の混在に対応）
        for day_data in days_data.values():
            # ソート前にstart_datetimeを統一形式（datetime）に変換
            for event in day_data['events']:
                if isinstance(event['start_datetime'], str):
                    try:
                        if 'T' in event['start_datetime']:
                            event['start_datetime'] = datetime.fromisoformat(event['start_datetime'].replace('Z', '+00:00'))
                        else:
                            event['start_datetime'] = datetime.strptime(event['start_datetime'], '%Y-%m-%d')
                    except ValueError as e:
                        logger.warning(f"日時変換エラー: {event['start_datetime']} - {e}")
                        event['start_datetime'] = datetime.now()  # フォールバック

                if isinstance(event['end_datetime'], str):
                    try:
                        if 'T' in event['end_datetime']:
                            event['end_datetime'] = datetime.fromisoformat(event['end_datetime'].replace('Z', '+00:00'))
                        else:
                            event['end_datetime'] = datetime.strptime(event['end_datetime'], '%Y-%m-%d')
                    except ValueError as e:
                        logger.warning(f"日時変換エラー: {event['end_datetime']} - {e}")
                        event['end_datetime'] = datetime.now()  # フォールバック

            # datetime型に統一されたのでソート実行
            day_data['events'].sort(key=lambda x: x['start_datetime'])
        
        # 最終整合性チェック: 祝日イベントがある日は必ず is_holiday=True に設定
        for day_key, day_data in days_data.items():
            # 祝日イベントをチェック
            holiday_events = [event for event in day_data['events'] if event['type'] == 'japanese_holiday']
            
            if holiday_events:
                # 祝日イベントがある場合、必ず祝日フラグを設定
                if not day_data['is_holiday']:
                    day_data['is_holiday'] = True
                    day_data['holiday_name'] = holiday_events[0]['title']
                    print(f"🔧 祝日フラグ修正: {year}年{month}月{day_key}日 - {holiday_events[0]['title']}")
            else:
                # 祝日イベントがない場合、祝日フラグを削除
                if day_data['is_holiday']:
                    day_data['is_holiday'] = False
                    day_data['holiday_name'] = None
                    print(f"🗑️ 誤った祝日フラグを削除: {year}年{month}月{day_key}日")
        
        return {
            'year': year,
            'month': month,
            'days_in_month': days_in_month,
            'first_day_weekday': first_day_weekday,
            'days': days_data,
            'month_name': cal_module.month_name[month],
            'total_events': len(google_events) + len(holidays)
        }
    
    def get_today_events(self) -> Dict[str, Any]:
        """
        今日のイベントを取得
        
        Returns:
            Dict: 今日のイベントデータ
        """
        today = datetime.now()
        month_data = self.get_month_events(today.year, today.month)
        
        if month_data['status'] != 'success':
            return {
                'status': 'error',
                'date': today.date(),
                'events': [],
                'error': month_data['error']
            }
        
        today_events = []
        if today.day in month_data['calendar_data']['days']:
            today_events = month_data['calendar_data']['days'][today.day]['events']
        
        return {
            'status': 'success',
            'date': today.date(),
            'events': today_events,
            'error': None
        }

# グローバルカレンダーデータマネージャーインスタンス
_calendar_manager = None

def get_calendar_manager() -> CalendarDataManager:
    """
    シングルトンカレンダーデータマネージャーインスタンスを取得
    
    Returns:
        CalendarDataManager: カレンダーデータマネージャー
    """
    global _calendar_manager
    if _calendar_manager is None:
        _calendar_manager = CalendarDataManager()
    return _calendar_manager