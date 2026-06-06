"""
統一ログシステム - Raspberry Pi Dashboard
品質改善プロジェクト Phase 1.1.1 対応
"""
import logging
import json
import sys
import traceback
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict
import os


class LogLevel(Enum):
    """ログレベル定義"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"  # カスタムレベル


class StructuredLogger:
    """
    統一構造化ログシステム
    
    機能:
    - 環境別設定（dev/prod）
    - 構造化JSON出力
    - セキュア情報除外
    - ログローテーション
    - パフォーマンス最適化
    """
    
    _instances: Dict[str, 'StructuredLogger'] = {}
    _initialized: bool = False
    
    def __new__(cls, name: str = "dashboard", environment: str = None):
        """シングルトンパターンでインスタンス管理"""
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]
    
    def __init__(self, name: str = "dashboard", environment: str = None):
        """
        ログシステム初期化
        
        Args:
            name: ロガー名
            environment: 環境 (development/production/test)
        """
        if hasattr(self, '_logger') and self._logger is not None:
            return
            
        self.name = name
        self.environment = environment or os.getenv('ENVIRONMENT', 'production')
        self.logs_dir = Path('logs')
        self.logs_dir.mkdir(exist_ok=True)
        
        # カスタムログレベル登録
        logging.addLevelName(25, 'SUCCESS')
        logging.addLevelName(22, 'NOTICE')
        
        self._logger = self._setup_logger()
        self._performance_metrics = {
            'total_calls': 0,
            'start_time': datetime.now(),
            'last_cleanup': datetime.now()
        }
        
        if not StructuredLogger._initialized:
            self._log_system_info()
            StructuredLogger._initialized = True
    
    def _setup_logger(self) -> logging.Logger:
        """ログ設定セットアップ"""
        logger = logging.getLogger(self.name)
        logger.setLevel(logging.DEBUG if self.environment == 'development' else logging.INFO)
        
        # 既存ハンドラーをクリア
        logger.handlers = []
        
        # フォーマッター設定
        formatter = self._get_formatter()
        
        # ファイルハンドラー（logrotateでローテーション管理）
        file_handler = logging.FileHandler(
            self.logs_dir / f'{self.name}.log',
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # エラー専用ファイル（logrotateでローテーション管理）
        error_handler = logging.FileHandler(
            self.logs_dir / f'{self.name}_error.log',
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
        # 開発環境ではコンソール出力も追加
        if self.environment == 'development':
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(self._get_console_formatter())
            logger.addHandler(console_handler)
        
        return logger
    
    def _get_formatter(self) -> logging.Formatter:
        """構造化JSON フォーマッター"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_obj = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread': record.thread
                }
                
                # 追加情報があれば含める
                if hasattr(record, 'extra_data'):
                    log_obj.update(record.extra_data)
                
                # 例外情報があれば追加
                if record.exc_info:
                    log_obj['exception'] = self.formatException(record.exc_info)
                
                return json.dumps(log_obj, ensure_ascii=False, separators=(',', ':'))
        
        return JSONFormatter()
    
    def _get_console_formatter(self) -> logging.Formatter:
        """コンソール用シンプルフォーマッター"""
        return logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
    
    def _log_system_info(self):
        """システム情報をログ出力"""
        self.info("ログシステム初期化完了", extra_data={
            'environment': self.environment,
            'logs_directory': str(self.logs_dir),
            'python_version': sys.version.split()[0],
            'logger_name': self.name
        })
    
    def _sanitize_data(self, data: Any) -> Any:
        """セキュア情報除外"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in 
                      ['password', 'token', 'key', 'secret', 'auth', 'credential']):
                    sanitized[key] = '***REDACTED***'
                else:
                    sanitized[key] = self._sanitize_data(value)
            return sanitized
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_data(item) for item in data]
        elif isinstance(data, str) and len(data) > 100:
            return data[:100] + '...(truncated)'
        return data
    
    def _update_performance_metrics(self):
        """パフォーマンス メトリクス更新"""
        self._performance_metrics['total_calls'] += 1
        
        # 定期的なメトリクス出力（1000回毎）
        if self._performance_metrics['total_calls'] % 1000 == 0:
            elapsed = datetime.now() - self._performance_metrics['start_time']
            calls_per_second = self._performance_metrics['total_calls'] / elapsed.total_seconds()
            
            self.debug("ログパフォーマンス統計", extra_data={
                'total_calls': self._performance_metrics['total_calls'],
                'calls_per_second': round(calls_per_second, 2),
                'elapsed_hours': round(elapsed.total_seconds() / 3600, 1)
            })
    
    def log(self, level: str, message: str, **kwargs):
        """汎用ログ出力メソッド"""
        self._update_performance_metrics()
        
        # 追加データをサニタイズ
        extra_data = {}
        for key, value in kwargs.items():
            extra_data[key] = self._sanitize_data(value)
        
        # ログレコード作成
        record_kwargs = {'extra': {'extra_data': extra_data}} if extra_data else {}
        
        # レベル別出力
        level_map = {
            'DEBUG': self._logger.debug,
            'INFO': self._logger.info,
            'NOTICE': lambda msg, **kw: self._logger.log(22, msg, **kw),
            'WARNING': self._logger.warning,
            'ERROR': self._logger.error,
            'CRITICAL': self._logger.critical,
            'SUCCESS': lambda msg, **kw: self._logger.log(25, msg, **kw)
        }
        
        log_func = level_map.get(level.upper(), self._logger.info)
        log_func(message, **record_kwargs)
    
    # 便利メソッド
    def debug(self, message: str, **kwargs):
        """デバッグログ"""
        self.log('DEBUG', message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """情報ログ"""  
        self.log('INFO', message, **kwargs)
    
    def notice(self, message: str, **kwargs):
        """通知ログ"""
        self.log('NOTICE', message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告ログ"""
        self.log('WARNING', message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """エラーログ"""
        self.log('ERROR', message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """致命的エラーログ"""
        self.log('CRITICAL', message, **kwargs)
    
    def success(self, message: str, **kwargs):
        """成功ログ（カスタムレベル）"""
        self.log('SUCCESS', message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """例外ログ（スタックトレース含む）"""
        kwargs['exception_traceback'] = traceback.format_exc()
        self.error(message, **kwargs)


# グローバルロガーインスタンス
def get_logger(name: str = "dashboard", environment: str = None) -> StructuredLogger:
    """ロガーインスタンス取得"""
    return StructuredLogger(name, environment)


# レガシー print() 代替関数（段階的移行用）
def legacy_print(message: str, level: str = "INFO", logger_name: str = "dashboard", **kwargs):
    """
    既存 print() 文からの段階的移行用ヘルパー関数
    後で除去予定
    """
    logger = get_logger(logger_name)
    logger.log(level, str(message), **kwargs)


# 使用例・テスト関数
if __name__ == "__main__":
    # テスト実行
    logger = get_logger("test", "development")
    
    logger.info("システム開始", service="test", version="1.0")
    logger.success("処理完了", items_processed=100, duration_ms=250)
    logger.warning("設定ファイル見つからず", config_path="/etc/config.json", using_default=True)
    logger.error("API接続エラー", url="https://api.example.com", status_code=500)
    
    # セキュア情報テスト
    logger.info("認証情報テスト", username="test_user", password="secret123", api_key="abc123")
    
    logger.success("ログシステムテスト完了")