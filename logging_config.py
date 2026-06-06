"""
ログ設定とローテーション機能
要件7.2: ログ記録とローテーション機能の実装
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import json
import gzip
import shutil

class JsonFormatter(logging.Formatter):
    """JSON形式のログフォーマッター"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process
        }
        
        # 例外情報がある場合は追加
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 追加のカスタム属性を含める
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False)

class CompressedTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """圧縮機能付きタイムローテーションハンドラー"""
    
    def doRollover(self):
        """ローテーション実行時に圧縮"""
        super().doRollover()
        
        # 古いログファイルを圧縮
        for log_file in Path(self.baseFilename).parent.glob("*.log.*"):
            if not str(log_file).endswith('.gz'):
                compressed_file = str(log_file) + '.gz'
                with open(log_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(log_file)

class LoggingConfig:
    """ログ設定管理クラス"""
    
    def __init__(
        self,
        log_dir: str = "logs",
        log_level: str = "INFO",
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_console: bool = True,
        enable_json_format: bool = True,
        enable_compression: bool = True
    ):
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        self.enable_json_format = enable_json_format
        self.enable_compression = enable_compression
        
        # ログディレクトリを作成
        self.log_dir.mkdir(exist_ok=True)
        
        self._setup_logging()
    
    def _setup_logging(self):
        """ログ設定のセットアップ"""
        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # 既存のハンドラーをクリア
        root_logger.handlers.clear()
        
        # ファイルハンドラーの設定
        self._setup_file_handlers()
        
        # コンソールハンドラーの設定
        if self.enable_console:
            self._setup_console_handler()
        
        # 特定のロガーの設定
        self._setup_specific_loggers()
    
    def _setup_file_handlers(self):
        """ファイルハンドラーのセットアップ"""
        # メインログファイル（全レベル）
        main_log_file = self.log_dir / "dashboard.log"
        
        if self.enable_compression:
            main_handler = CompressedTimedRotatingFileHandler(
                filename=str(main_log_file),
                when='midnight',
                interval=1,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
        else:
            main_handler = logging.handlers.RotatingFileHandler(
                filename=str(main_log_file),
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
        
        main_handler.setLevel(self.log_level)
        
        if self.enable_json_format:
            main_handler.setFormatter(JsonFormatter())
        else:
            main_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        logging.getLogger().addHandler(main_handler)
        
        # エラーログファイル（ERROR以上のみ）
        error_log_file = self.log_dir / "dashboard_error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            filename=str(error_log_file),
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        
        if self.enable_json_format:
            error_handler.setFormatter(JsonFormatter())
        else:
            error_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'
            ))
        
        logging.getLogger().addHandler(error_handler)
        
        # パフォーマンスログファイル
        perf_log_file = self.log_dir / "dashboard_performance.log"
        perf_handler = logging.handlers.RotatingFileHandler(
            filename=str(perf_log_file),
            maxBytes=self.max_file_size,
            backupCount=3,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        
        if self.enable_json_format:
            perf_handler.setFormatter(JsonFormatter())
        else:
            perf_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(message)s'
            ))
        
        # パフォーマンス専用ロガー
        perf_logger = logging.getLogger('performance')
        perf_logger.addHandler(perf_handler)
        perf_logger.propagate = False
    
    def _setup_console_handler(self):
        """コンソールハンドラーのセットアップ"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # コンソールは読みやすい形式で
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        logging.getLogger().addHandler(console_handler)
    
    def _setup_specific_loggers(self):
        """特定のロガーの設定"""
        # センサーロガー
        sensor_logger = logging.getLogger('sensor')
        sensor_log_file = self.log_dir / "sensor.log"
        sensor_handler = logging.handlers.RotatingFileHandler(
            filename=str(sensor_log_file),
            maxBytes=self.max_file_size // 2,
            backupCount=3,
            encoding='utf-8'
        )
        
        if self.enable_json_format:
            sensor_handler.setFormatter(JsonFormatter())
        else:
            sensor_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
        
        sensor_logger.addHandler(sensor_handler)
        
        # カレンダーロガー
        calendar_logger = logging.getLogger('calendar')
        calendar_log_file = self.log_dir / "calendar.log"
        calendar_handler = logging.handlers.RotatingFileHandler(
            filename=str(calendar_log_file),
            maxBytes=self.max_file_size // 2,
            backupCount=3,
            encoding='utf-8'
        )
        
        if self.enable_json_format:
            calendar_handler.setFormatter(JsonFormatter())
        else:
            calendar_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
        
        calendar_logger.addHandler(calendar_handler)
        
        # 外部ライブラリのログレベルを調整
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    
    def get_log_stats(self) -> Dict[str, Any]:
        """ログファイルの統計情報を取得"""
        stats = {}
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                file_stats = log_file.stat()
                stats[log_file.name] = {
                    'size_bytes': file_stats.st_size,
                    'size_mb': round(file_stats.st_size / (1024 * 1024), 2),
                    'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    'lines': self._count_log_lines(log_file)
                }
            except Exception as e:
                stats[log_file.name] = {'error': str(e)}
        
        return stats
    
    def _count_log_lines(self, log_file: Path) -> int:
        """ログファイルの行数をカウント"""
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """古いログファイルのクリーンアップ"""
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
        
        cleaned_files = []
        for log_file in self.log_dir.glob("*.log.*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_files.append(str(log_file))
            except Exception as e:
                logging.warning(f"Failed to clean up log file {log_file}: {e}")
        
        return cleaned_files
    
    def export_logs(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, list]:
        """ログのエクスポート（JSON形式）"""
        logs = {}
        
        for log_file in self.log_dir.glob("*.log"):
            try:
                logs[log_file.name] = self._extract_log_entries(
                    log_file, start_date, end_date
                )
            except Exception as e:
                logs[log_file.name] = [{'error': f"Failed to read log: {e}"}]
        
        return logs
    
    def _extract_log_entries(self, log_file: Path, start_date: Optional[str], end_date: Optional[str]) -> list:
        """ログエントリの抽出"""
        entries = []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # JSON形式のログをパース
                    if self.enable_json_format and line.startswith('{'):
                        try:
                            entry = json.loads(line)
                            
                            # 日付フィルタリング
                            if start_date or end_date:
                                entry_date = entry.get('timestamp', '')
                                if start_date and entry_date < start_date:
                                    continue
                                if end_date and entry_date > end_date:
                                    continue
                            
                            entries.append(entry)
                        except json.JSONDecodeError:
                            entries.append({'raw': line})
                    else:
                        # プレーンテキストログ
                        entries.append({'raw': line})
        except Exception as e:
            entries.append({'error': f"Failed to parse log entries: {e}"})
        
        return entries

class PerformanceLogger:
    """パフォーマンス測定用ロガー"""
    
    def __init__(self):
        self.logger = logging.getLogger('performance')
    
    def log_api_performance(self, endpoint: str, duration: float, status_code: int, **kwargs):
        """API パフォーマンスログ"""
        self.logger.info(
            f"API Performance: {endpoint}",
            extra={
                'event_type': 'api_performance',
                'endpoint': endpoint,
                'duration_ms': round(duration * 1000, 2),
                'status_code': status_code,
                **kwargs
            }
        )
    
    def log_sensor_performance(self, sensor_type: str, duration: float, success: bool, **kwargs):
        """センサー読み取りパフォーマンスログ"""
        self.logger.info(
            f"Sensor Performance: {sensor_type}",
            extra={
                'event_type': 'sensor_performance',
                'sensor_type': sensor_type,
                'duration_ms': round(duration * 1000, 2),
                'success': success,
                **kwargs
            }
        )
    
    def log_system_metrics(self, cpu_percent: float, memory_percent: float, **kwargs):
        """システムメトリクスログ"""
        self.logger.info(
            "System Metrics",
            extra={
                'event_type': 'system_metrics',
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                **kwargs
            }
        )

# グローバルインスタンス
_logging_config = None
_performance_logger = None

def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    enable_console: bool = True,
    enable_json_format: bool = True
) -> LoggingConfig:
    """ログ設定の初期化"""
    global _logging_config
    _logging_config = LoggingConfig(
        log_dir=log_dir,
        log_level=log_level,
        enable_console=enable_console,
        enable_json_format=enable_json_format
    )
    return _logging_config

def get_logging_config() -> Optional[LoggingConfig]:
    """ログ設定インスタンスを取得"""
    return _logging_config

def get_performance_logger() -> PerformanceLogger:
    """パフォーマンスロガーを取得"""
    global _performance_logger
    if _performance_logger is None:
        _performance_logger = PerformanceLogger()
    return _performance_logger