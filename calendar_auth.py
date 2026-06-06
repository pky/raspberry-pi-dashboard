"""
Google Calendar API認証モジュール
OAuth2認証フローと認証情報の安全な保存機能を実装
"""

import os
import json
import logging
import time
import fcntl
import threading
from typing import Optional, Dict, Any
from datetime import datetime

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
    logger.info("Google API libraries loaded successfully")
except ImportError as e:
    GOOGLE_LIBS_AVAILABLE = False
    logger.warning(f"Google API libraries not available: {e}. Running in simulation mode.")

from config import get_config

class GoogleCalendarAuth:
    """
    Google Calendar API認証クラス
    OAuth2認証フローと認証情報管理を実装
    
    要件: 1.1, 3.5
    """
    
    def __init__(self):
        """認証クラスの初期化"""
        self.settings = get_config()
        self.scopes = ['https://www.googleapis.com/auth/calendar.readonly']  # 設定から読み込み予定
        self.credentials_file = 'credentials/credentials.json'
        self.token_file = 'credentials/token.json'
        self.credentials = None
        self.service = None
        self._lock = threading.Lock()
        self._auth_lock_file = self.token_file + '.lock'
        
        # 認証情報ディレクトリの作成
        self._ensure_credentials_directory()
        
        logger.info("Google Calendar認証クラスが初期化されました")
    
    def _ensure_credentials_directory(self):
        """認証情報ディレクトリの存在確認と作成"""
        credentials_dir = os.path.dirname(self.credentials_file)
        token_dir = os.path.dirname(self.token_file)
        
        for directory in [credentials_dir, token_dir]:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, mode=0o700)  # 所有者のみアクセス可能
                    logger.info(f"認証情報ディレクトリを作成しました: {directory}")
                except OSError as e:
                    logger.error(f"ディレクトリ作成エラー: {directory} - {e}")
    
    def load_credentials(self) -> bool:
        """
        保存された認証情報を読み込み
        
        Returns:
            bool: 認証情報の読み込み成功可否
        """
        if not GOOGLE_LIBS_AVAILABLE:
            logger.warning("Google APIライブラリが利用できません")
            return False
        
        try:
            # 既存のトークンファイルから認証情報を読み込み
            if os.path.exists(self.token_file):
                # ファイルサイズをチェック（空ファイル対策）
                file_size = os.path.getsize(self.token_file)
                if file_size == 0:
                    logger.warning(f"認証トークンファイルが空です。削除します: {self.token_file}")
                    os.remove(self.token_file)
                    return False
                
                self.credentials = Credentials.from_authorized_user_file(
                    self.token_file, self.scopes
                )
                logger.info("保存された認証情報を読み込みました")
                
                # 認証情報の有効性確認（柔軟なチェック）
                if self.credentials:
                    if self.credentials.valid:
                        logger.info("認証情報は有効です")
                        return True
                    elif self.credentials.refresh_token:
                        # 期限切れでもrefresh_tokenがあれば更新を試行
                        logger.info("認証情報の更新を試行します")
                        if self._refresh_credentials():
                            return True
                        else:
                            logger.warning("認証情報の更新に失敗しました")
                    
                    # 最後の手段として、APIアクセステストを実行
                    if self._test_credentials_with_api():
                        logger.info("API接続テストが成功しました。認証情報は使用可能です")
                        return True
                    
                logger.warning("認証情報が無効です。再認証が必要です")
                return False
            else:
                logger.info("保存された認証情報が見つかりません")
                return False
                
        except Exception as e:
            logger.error(f"認証情報読み込みエラー: {e}")
            
            # 破損したトークンファイルを削除
            try:
                if os.path.exists(self.token_file):
                    logger.warning(f"破損したトークンファイルを削除します: {self.token_file}")
                    os.remove(self.token_file)
            except Exception as cleanup_error:
                logger.error(f"トークンファイル削除エラー: {cleanup_error}")
            
            return False
    
    def _test_credentials_with_api(self) -> bool:
        """
        実際のAPI呼び出しで認証情報をテスト
        
        Returns:
            bool: API接続成功可否
        """
        try:
            if not self.credentials:
                return False
                
            # 一時的なサービスオブジェクトでAPI呼び出し
            temp_service = build('calendar', 'v3', credentials=self.credentials)
            
            # 最小限のAPI呼び出し（カレンダーリスト取得）
            calendar_list = temp_service.calendarList().list(maxResults=1).execute()
            
            logger.info("API接続テストが成功しました")
            return True
            
        except Exception as e:
            logger.debug(f"API接続テストエラー: {e}")
            return False

    def _refresh_credentials(self) -> bool:
        """
        認証情報の更新
        
        Returns:
            bool: 更新成功可否
        """
        try:
            self.credentials.refresh(Request())
            self._save_credentials()
            logger.info("認証情報を更新しました")
            return True
        except Exception as e:
            logger.error(f"認証情報更新エラー: {e}")
            return False
    
    def _acquire_process_lock(self) -> Optional[object]:
        """プロセス間排他制御のためのファイルロックを取得"""
        try:
            lock_fd = os.open(self._auth_lock_file, os.O_CREAT | os.O_WRONLY, 0o600)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("認証プロセスロックを取得しました")
            return lock_fd
        except (OSError, IOError) as e:
            logger.warning(f"認証プロセスロック取得失敗: {e}")
            return None
    
    def _release_process_lock(self, lock_fd):
        """プロセス間排他制御のファイルロックを解放"""
        try:
            if lock_fd is not None:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
                if os.path.exists(self._auth_lock_file):
                    os.remove(self._auth_lock_file)
                logger.info("認証プロセスロックを解放しました")
        except (OSError, IOError) as e:
            logger.warning(f"認証プロセスロック解放エラー: {e}")

    def authenticate(self) -> bool:
        """
        OAuth2認証フローを実行（プロセス間排他制御付き）
        
        Returns:
            bool: 認証成功可否
            
        要件: 1.1, 3.5 - OAuth2認証フローの実装
        """
        if not GOOGLE_LIBS_AVAILABLE:
            logger.warning("Google APIライブラリが利用できません")
            return False
        
        with self._lock:  # スレッド間排他制御
            # 既存の認証情報を確認
            if self.load_credentials():
                return True
            
            # プロセス間排他制御
            lock_fd = self._acquire_process_lock()
            if lock_fd is None:
                # 他のプロセスが認証中の場合、待機して再試行
                logger.info("他のプロセスが認証中です。待機中...")
                for i in range(30):  # 最大30秒待機
                    time.sleep(1)
                    if self.load_credentials():
                        logger.info("他のプロセスの認証完了を確認しました")
                        return True
                logger.error("認証待機タイムアウト")
                return False
            
            try:
                # 再度認証情報を確認（他のプロセスが完了している可能性）
                if self.load_credentials():
                    return True
                
                # 新規認証フロー
                if not os.path.exists(self.credentials_file):
                    logger.error(f"認証情報ファイルが見つかりません: {self.credentials_file}")
                    logger.info("Google Cloud Consoleから credentials.json をダウンロードして配置してください")
                    return False
                
                logger.info("OAuth2認証フローを開始します")
                
                # OAuth2フローの実行
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                
                # ローカルサーバーでの認証（開発時）
                self.credentials = flow.run_local_server(port=0)
                
                # 認証情報の保存
                self._save_credentials()
                
                logger.info("OAuth2認証が完了しました")
                return True
                
            except Exception as e:
                logger.error(f"OAuth2認証エラー: {e}")
                return False
            finally:
                self._release_process_lock(lock_fd)
    
    def _save_credentials(self):
        """
        認証情報の安全な保存
        
        要件: 3.5 - 認証情報の安全な保存
        """
        try:
            # トークンファイルに認証情報を保存
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
            
            # ファイル権限を所有者のみに制限
            os.chmod(self.token_file, 0o600)
            
            logger.info(f"認証情報を安全に保存しました: {self.token_file}")
            
        except Exception as e:
            logger.error(f"認証情報保存エラー: {e}")
    
    def get_service(self):
        """
        Google Calendar APIサービスオブジェクトを取得
        
        Returns:
            Google Calendar APIサービスオブジェクト
        """
        if not GOOGLE_LIBS_AVAILABLE:
            logger.warning("Google APIライブラリが利用できません")
            return None
        
        if not self.credentials or not self.credentials.valid:
            if not self.authenticate():
                logger.error("認証に失敗しました")
                return None
        
        try:
            if not self.service:
                self.service = build('calendar', 'v3', credentials=self.credentials)
                logger.info("Google Calendar APIサービスを初期化しました")
            
            return self.service
            
        except Exception as e:
            logger.error(f"APIサービス初期化エラー: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Google Calendar APIへの接続テスト
        
        Returns:
            bool: 接続テスト成功可否
        """
        try:
            service = self.get_service()
            if not service:
                return False
            
            # カレンダーリストの取得テスト
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            logger.info(f"接続テスト成功: {len(calendars)}個のカレンダーが見つかりました")
            
            # プライマリカレンダーの確認
            primary_calendar = None
            for calendar in calendars:
                if calendar.get('primary', False):
                    primary_calendar = calendar
                    break
            
            if primary_calendar:
                logger.info(f"プライマリカレンダー: {primary_calendar.get('summary', 'Unknown')}")
            
            return True
            
        except HttpError as e:
            logger.error(f"Google Calendar API接続エラー: {e}")
            return False
        except Exception as e:
            logger.error(f"接続テストエラー: {e}")
            return False
    
    def get_calendar_info(self) -> Dict[str, Any]:
        """
        カレンダー情報を取得
        
        Returns:
            Dict: カレンダー情報
        """
        if not GOOGLE_LIBS_AVAILABLE:
            return {
                'status': 'simulation',
                'calendars': [],
                'primary_calendar': None,
                'error': 'Google APIライブラリが利用できません'
            }
        
        try:
            service = self.get_service()
            if not service:
                return {
                    'status': 'error',
                    'calendars': [],
                    'primary_calendar': None,
                    'error': 'APIサービスの初期化に失敗しました'
                }
            
            # カレンダーリストの取得
            calendar_list = service.calendarList().list().execute()
            calendars = calendar_list.get('items', [])
            
            # プライマリカレンダーの特定
            primary_calendar = None
            for calendar in calendars:
                if calendar.get('primary', False):
                    primary_calendar = {
                        'id': calendar.get('id'),
                        'summary': calendar.get('summary'),
                        'timeZone': calendar.get('timeZone')
                    }
                    break
            
            return {
                'status': 'success',
                'calendars': [
                    {
                        'id': cal.get('id'),
                        'summary': cal.get('summary'),
                        'primary': cal.get('primary', False),
                        'timeZone': cal.get('timeZone')
                    }
                    for cal in calendars
                ],
                'primary_calendar': primary_calendar,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"カレンダー情報取得エラー: {e}")
            return {
                'status': 'error',
                'calendars': [],
                'primary_calendar': None,
                'error': str(e)
            }
    
    def revoke_credentials(self):
        """認証情報の取り消し"""
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info("認証情報を削除しました")
            
            self.credentials = None
            self.service = None
            
        except Exception as e:
            logger.error(f"認証情報削除エラー: {e}")

# グローバル認証インスタンス
_auth_instance = None

def get_calendar_auth() -> GoogleCalendarAuth:
    """
    シングルトンGoogle Calendar認証インスタンスを取得
    
    Returns:
        GoogleCalendarAuth: 認証インスタンス
    """
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = GoogleCalendarAuth()
    return _auth_instance