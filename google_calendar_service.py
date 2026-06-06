#!/usr/bin/env python3
"""
Google Calendar サービス（簡素化版）
refresh_tokenベースの永続認証
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
import os
from logging_system import get_logger

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import requests as _requests
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

# Google APIのネットワークタイムアウト（秒）
# タイムアウトなしだとスレッドが永遠にブロックしてシステムが不安定になる
_API_TIMEOUT_SECONDS = 30


def _make_timeout_session() -> '_requests.Session':
    """タイムアウト付きrequestsセッションを生成"""
    class _TimeoutAdapter(_requests.adapters.HTTPAdapter):
        def send(self, *args, **kwargs):
            kwargs.setdefault('timeout', _API_TIMEOUT_SECONDS)
            return super().send(*args, **kwargs)
    session = _requests.Session()
    session.mount('https://', _TimeoutAdapter())
    session.mount('http://', _TimeoutAdapter())
    return session

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    """簡素化されたGoogle Calendarサービス"""
    
    def __init__(self, token_file: str = "credentials/token.json"):
        self.token_file = Path(token_file)
        self.credentials = None
        self.service = None
        
    def load_and_refresh_credentials(self) -> bool:
        """認証情報を読み込み、必要に応じて更新"""
        if not self.token_file.exists():
            logger.warning(f"トークンファイルが見つかりません: {self.token_file}")
            return False
        
        try:
            # 既存の認証情報を読み込み
            self.credentials = Credentials.from_authorized_user_file(
                str(self.token_file), 
                ['https://www.googleapis.com/auth/calendar.readonly']
            )
            
            # 期限切れの場合は更新（expiryがNoneの場合も含む）
            if not self.credentials.valid:
                if self.credentials.refresh_token:
                    logger.info("アクセストークンを更新中...")
                    # タイムアウト付きセッションでトークン更新（無期限ブロック防止）
                    self.credentials.refresh(Request(session=_make_timeout_session()))
                    
                    # 更新されたトークンを保存
                    token_data = {
                        'token': self.credentials.token,
                        'refresh_token': self.credentials.refresh_token,
                        'token_uri': self.credentials.token_uri,
                        'client_id': self.credentials.client_id,
                        'client_secret': self.credentials.client_secret,
                        'scopes': self.credentials.scopes,
                        'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
                    }
                    
                    with open(self.token_file, 'w') as f:
                        json.dump(token_data, f, indent=2)
                    
                    logger.info("アクセストークンの更新が完了しました")
                else:
                    logger.error("認証情報が無効で、refresh_tokenがありません")
                    return False
            
            # Calendarサービスを初期化
            # httplib2.Http(timeout=...)でAPIコールのタイムアウトを保証
            import httplib2
            import google_auth_httplib2
            _http = google_auth_httplib2.AuthorizedHttp(
                self.credentials,
                http=httplib2.Http(timeout=_API_TIMEOUT_SECONDS)
            )
            self.service = build('calendar', 'v3', http=_http)
            logger.info(f"Google Calendar サービスが初期化されました（タイムアウト: {_API_TIMEOUT_SECONDS}秒）")
            return True
            
        except Exception as e:
            logger.error(f"認証情報の読み込みエラー: {e}")
            return False
    
    def _fetch_events_from_calendar(self, calendar_id: str, time_min: str, time_max: str) -> List[Dict]:
        """指定カレンダーからイベントを取得して標準形式に変換"""
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            formatted_events = []
            for event in events:
                # 開始日時を取得してdatetimeオブジェクトに変換
                start_raw = event['start'].get('dateTime', event['start'].get('date'))
                if 'T' in start_raw:
                    # 時刻指定イベント: ISO形式をdatetimeに変換（timezone-naiveに統一）
                    start_datetime = datetime.fromisoformat(start_raw.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    # 終日イベント: 日付のみをdatetimeに変換
                    start_datetime = datetime.strptime(start_raw, '%Y-%m-%d')

                # 終了日時を取得してdatetimeオブジェクトに変換
                end_raw = event['end'].get('dateTime', event['end'].get('date'))
                if 'T' in end_raw:
                    end_datetime = datetime.fromisoformat(end_raw.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    end_datetime = datetime.strptime(end_raw, '%Y-%m-%d')

                formatted_events.append({
                    'id': event.get('id', ''),
                    'title': event.get('summary', '無題'),
                    'description': event.get('description', ''),
                    'start_datetime': start_datetime,  # datetimeオブジェクト
                    'end_datetime': end_datetime,      # datetimeオブジェクト
                    'all_day': 'date' in event['start'],
                    'location': event.get('location', ''),
                    'type': 'personal_event'
                })

            return formatted_events

        except Exception as e:
            logger.error(f"カレンダー '{calendar_id}' からのイベント取得エラー: {e}")
            return []

    def get_personal_events(self, year: int, month: int) -> List[Dict]:
        """指定月の個人予定を取得（複数カレンダー対応）"""
        if not self.service:
            if not self.load_and_refresh_credentials():
                logger.error("Google Calendar サービスが利用できません")
                return []

        try:
            # 月の範囲を計算
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)

            # APIリクエスト（RFC3339フォーマット）
            time_min = start_date.strftime('%Y-%m-%dT00:00:00Z')
            time_max = end_date.strftime('%Y-%m-%dT23:59:59Z')

            # primaryカレンダーからイベント取得
            formatted_events = self._fetch_events_from_calendar('primary', time_min, time_max)
            logger.info(f"primaryカレンダー: {len(formatted_events)}件")

            # 追加カレンダーからもイベント取得
            try:
                from config import Config
                additional_ids = getattr(Config, 'GOOGLE_ADDITIONAL_CALENDAR_IDS', [])
                for cal_id in additional_ids:
                    extra_events = self._fetch_events_from_calendar(cal_id, time_min, time_max)
                    logger.info(f"追加カレンダー '{cal_id[:20]}...': {len(extra_events)}件")
                    formatted_events.extend(extra_events)
            except Exception as e:
                logger.warning(f"追加カレンダー取得エラー: {e}")

            # 開始日時でソート
            formatted_events.sort(key=lambda x: x['start_datetime'])

            logger.info(f"個人予定を取得: {year}年{month}月 - {len(formatted_events)}件（全カレンダー合計）")
            return formatted_events

        except Exception as e:
            logger.error(f"個人予定取得エラー: {e}")
            return []

def get_google_calendar_service() -> GoogleCalendarService:
    """Google Calendarサービスインスタンスを取得"""
    return GoogleCalendarService()

if __name__ == "__main__":
    # テスト実行
    service = get_google_calendar_service()
    if service.load_and_refresh_credentials():
        events = service.get_personal_events(2025, 8)
        self.logger.success("8月の個人予定: {len(events)}件")
        for event in events[:3]:  # 最初の3件を表示
            self.logger.info("- {event['title']}")
    else:
        self.logger.warning("認証に失敗しました")