"""
統一エラーハンドリングシステム
要件7.2: システム全体のエラーハンドリング統合
"""

import logging
import traceback
import sys
from datetime import datetime
from typing import Optional, Dict, Any, Union
from enum import Enum
from functools import wraps
import json

class ErrorLevel(Enum):
    """エラーレベル定義"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorCode(Enum):
    """エラーコード定義"""
    # センサー関連エラー
    SENSOR_CONNECTION_FAILED = "SENSOR_001"
    SENSOR_READ_TIMEOUT = "SENSOR_002"
    SENSOR_INVALID_DATA = "SENSOR_003"
    SENSOR_CALIBRATION_ERROR = "SENSOR_004"
    
    # カレンダー関連エラー
    CALENDAR_API_UNAUTHORIZED = "CALENDAR_001"
    CALENDAR_API_QUOTA_EXCEEDED = "CALENDAR_002"
    CALENDAR_DATA_PARSING_ERROR = "CALENDAR_003"
    CALENDAR_NETWORK_ERROR = "CALENDAR_004"
    
    # システム関連エラー
    SYSTEM_MEMORY_ERROR = "SYSTEM_001"
    SYSTEM_DISK_FULL = "SYSTEM_002"
    SYSTEM_NETWORK_ERROR = "SYSTEM_003"
    SYSTEM_CONFIG_ERROR = "SYSTEM_004"
    
    # API関連エラー
    API_INVALID_REQUEST = "API_001"
    API_AUTHENTICATION_FAILED = "API_002"
    API_RATE_LIMIT_EXCEEDED = "API_003"
    API_INTERNAL_ERROR = "API_004"
    
    # フロントエンド関連エラー
    FRONTEND_LOAD_ERROR = "FRONTEND_001"
    FRONTEND_SCRIPT_ERROR = "FRONTEND_002"
    FRONTEND_NETWORK_ERROR = "FRONTEND_003"
    
    # 汎用エラー
    UNKNOWN_ERROR = "UNKNOWN_001"
    VALIDATION_ERROR = "VALIDATION_001"

class DashboardError(Exception):
    """ダッシュボード用カスタム例外クラス"""
    
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR,
        level: ErrorLevel = ErrorLevel.ERROR,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.level = level
        self.context = context or {}
        self.original_exception = original_exception
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式でエラー情報を返す"""
        return {
            'error_code': self.error_code.value,
            'message': self.message,
            'level': self.level.value,
            'timestamp': self.timestamp,
            'context': self.context,
            'original_exception': str(self.original_exception) if self.original_exception else None
        }
    
    def to_json(self) -> str:
        """JSON形式でエラー情報を返す"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

class ErrorHandler:
    """統一エラーハンドラークラス"""
    
    def __init__(self, logger_name: str = "dashboard"):
        self.logger = logging.getLogger(logger_name)
        self.error_stats = {
            'total_errors': 0,
            'errors_by_code': {},
            'errors_by_level': {},
            'last_error_time': None
        }
    
    def handle_error(
        self, 
        error: Union[Exception, DashboardError], 
        context: Optional[Dict[str, Any]] = None,
        reraise: bool = True
    ) -> DashboardError:
        """
        エラーの統一処理
        
        Args:
            error: 処理するエラー
            context: 追加のコンテキスト情報
            reraise: エラーを再発生させるかどうか
            
        Returns:
            DashboardError: 統一されたエラーオブジェクト
        """
        # DashboardErrorに変換
        if isinstance(error, DashboardError):
            dashboard_error = error
            if context:
                dashboard_error.context.update(context)
        else:
            # 一般的な例外をDashboardErrorに変換
            error_code = self._classify_error(error)
            level = self._determine_error_level(error)
            
            dashboard_error = DashboardError(
                message=str(error),
                error_code=error_code,
                level=level,
                context=context or {},
                original_exception=error
            )
        
        # エラー統計を更新
        self._update_error_stats(dashboard_error)
        
        # ログに記録
        self._log_error(dashboard_error)
        
        # 必要に応じて通知
        self._notify_error(dashboard_error)
        
        if reraise:
            raise dashboard_error
        
        return dashboard_error
    
    def _classify_error(self, error: Exception) -> ErrorCode:
        """エラーの種類を分類"""
        error_name = type(error).__name__
        error_message = str(error).lower()
        
        # センサー関連エラー
        if 'sensor' in error_message or 'dht' in error_message:
            if 'timeout' in error_message:
                return ErrorCode.SENSOR_READ_TIMEOUT
            elif 'connection' in error_message:
                return ErrorCode.SENSOR_CONNECTION_FAILED
            else:
                return ErrorCode.SENSOR_INVALID_DATA
        
        # カレンダー関連エラー
        elif 'calendar' in error_message or 'google' in error_message:
            if 'unauthorized' in error_message or 'auth' in error_message:
                return ErrorCode.CALENDAR_API_UNAUTHORIZED
            elif 'quota' in error_message or 'limit' in error_message:
                return ErrorCode.CALENDAR_API_QUOTA_EXCEEDED
            elif 'network' in error_message or 'connection' in error_message:
                return ErrorCode.CALENDAR_NETWORK_ERROR
            else:
                return ErrorCode.CALENDAR_DATA_PARSING_ERROR
        
        # システム関連エラー
        elif error_name in ['MemoryError', 'OSError']:
            if 'memory' in error_message:
                return ErrorCode.SYSTEM_MEMORY_ERROR
            elif 'disk' in error_message or 'space' in error_message:
                return ErrorCode.SYSTEM_DISK_FULL
            else:
                return ErrorCode.SYSTEM_CONFIG_ERROR
        
        # ネットワーク関連エラー
        elif error_name in ['ConnectionError', 'TimeoutError', 'NetworkError']:
            return ErrorCode.SYSTEM_NETWORK_ERROR
        
        # バリデーション関連エラー
        elif error_name in ['ValueError', 'ValidationError']:
            return ErrorCode.VALIDATION_ERROR
        
        return ErrorCode.UNKNOWN_ERROR
    
    def _determine_error_level(self, error: Exception) -> ErrorLevel:
        """エラーレベルを決定"""
        error_name = type(error).__name__
        error_message = str(error).lower()
        
        # クリティカルレベル
        if error_name in ['MemoryError', 'SystemExit', 'KeyboardInterrupt']:
            return ErrorLevel.CRITICAL
        
        # エラーレベル
        elif error_name in ['ConnectionError', 'TimeoutError', 'IOError']:
            return ErrorLevel.ERROR
        
        # 警告レベル
        elif error_name in ['UserWarning', 'DeprecationWarning']:
            return ErrorLevel.WARNING
        
        # 一般的なエラー
        else:
            return ErrorLevel.ERROR
    
    def _update_error_stats(self, error: DashboardError):
        """エラー統計を更新"""
        self.error_stats['total_errors'] += 1
        self.error_stats['last_error_time'] = error.timestamp
        
        # コード別統計
        code = error.error_code.value
        if code not in self.error_stats['errors_by_code']:
            self.error_stats['errors_by_code'][code] = 0
        self.error_stats['errors_by_code'][code] += 1
        
        # レベル別統計
        level = error.level.value
        if level not in self.error_stats['errors_by_level']:
            self.error_stats['errors_by_level'][level] = 0
        self.error_stats['errors_by_level'][level] += 1
    
    def _log_error(self, error: DashboardError):
        """ログにエラーを記録"""
        log_level = getattr(logging, error.level.value)
        
        log_message = f"[{error.error_code.value}] {error.message}"
        if error.context:
            log_message += f" | Context: {json.dumps(error.context)}"
        
        # トレースバック情報も含める
        if error.original_exception:
            exc_info = (
                type(error.original_exception),
                error.original_exception,
                error.original_exception.__traceback__
            )
            self.logger.log(log_level, log_message, exc_info=exc_info)
        else:
            self.logger.log(log_level, log_message)
    
    def _notify_error(self, error: DashboardError):
        """重要なエラーの通知"""
        if error.level in [ErrorLevel.CRITICAL, ErrorLevel.ERROR]:
            # ここで重要なエラーの通知処理を実装
            # 例: メール送信、外部監視システムへの通知など
            pass
    
    def get_error_stats(self) -> Dict[str, Any]:
        """エラー統計情報を取得"""
        return self.error_stats.copy()
    
    def reset_error_stats(self):
        """エラー統計をリセット"""
        self.error_stats = {
            'total_errors': 0,
            'errors_by_code': {},
            'errors_by_level': {},
            'last_error_time': None
        }

# グローバルエラーハンドラーインスタンス
_global_error_handler = None

def get_error_handler() -> ErrorHandler:
    """グローバルエラーハンドラーを取得"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler

def handle_exceptions(
    error_code: Optional[ErrorCode] = None,
    level: Optional[ErrorLevel] = None,
    context: Optional[Dict[str, Any]] = None,
    reraise: bool = True
):
    """
    デコレーター：関数の例外を自動的にハンドリング
    
    Args:
        error_code: 固定のエラーコード
        level: 固定のエラーレベル
        context: 追加のコンテキスト情報
        reraise: エラーを再発生させるかどうか
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = get_error_handler()
                
                # DashboardErrorに変換
                if isinstance(e, DashboardError):
                    dashboard_error = e
                else:
                    dashboard_error = DashboardError(
                        message=str(e),
                        error_code=error_code or handler._classify_error(e),
                        level=level or handler._determine_error_level(e),
                        context=context or {},
                        original_exception=e
                    )
                
                # 関数情報をコンテキストに追加
                function_context = {
                    'function_name': func.__name__,
                    'module': func.__module__,
                    'args_count': len(args),
                    'kwargs_keys': list(kwargs.keys())
                }
                dashboard_error.context.update(function_context)
                
                return handler.handle_error(dashboard_error, reraise=reraise)
        
        return wrapper
    return decorator

def log_and_suppress(
    error_code: Optional[ErrorCode] = None,
    level: ErrorLevel = ErrorLevel.WARNING,
    default_return: Any = None
):
    """
    デコレーター：エラーをログに記録して抑制し、デフォルト値を返す
    
    Args:
        error_code: エラーコード
        level: ログレベル
        default_return: エラー時の戻り値
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                handler = get_error_handler()
                
                dashboard_error = DashboardError(
                    message=str(e),
                    error_code=error_code or handler._classify_error(e),
                    level=level,
                    context={'function_name': func.__name__},
                    original_exception=e
                )
                
                handler.handle_error(dashboard_error, reraise=False)
                return default_return
        
        return wrapper
    return decorator