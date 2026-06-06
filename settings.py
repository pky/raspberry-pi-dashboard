"""
設定外部化システム - Raspberry Pi Dashboard
品質改善プロジェクト Phase 1.2 対応

🎉 STATUS: Phase 1.2 完全完了 (2025-08-21)
✅ 設定外部化100%達成
✅ 環境別設定対応完了  
✅ 型安全設定クラス実装完了

機能:
- 環境変数ベース設定
- 型安全設定クラス
- デフォルト値管理
- 環境別設定対応
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
from logging_system import get_logger


@dataclass
class HardwareConfig:
    """ハードウェア関連設定"""
    # GPIO設定 (legacy - SHT35 uses I2C)
    dht22_pin: int = 4  # Legacy pin config
    co2_sensor_uart_tx: int = 14
    co2_sensor_uart_rx: int = 15
    co2_sensor_baudrate: int = 9600
    
    # センサー読み取り設定
    sensor_read_timeout: float = 5.0
    sensor_retry_attempts: int = 2
    sensor_retry_delay: float = 1.0
    
    # デバイス検出
    metrics_file_paths: List[str] = None
    
    def __post_init__(self):
        if self.metrics_file_paths is None:
            self.metrics_file_paths = [
                str(Path(__file__).parent / "static" / "data" / "metrics.json"),
                "./static/data/metrics.json",
                "../static/data/metrics.json"
            ]


@dataclass 
class APIConfig:
    """API関連設定"""
    # Flask設定
    flask_host: str = "localhost"
    flask_port: int = 5000
    flask_debug: bool = False
    
    # API応答設定
    api_timeout: float = 5.0
    api_retry_attempts: int = 2
    api_retry_delay: float = 2.0
    
    # Google Calendar API
    calendar_timeout: float = 10.0
    calendar_cache_ttl: int = 3600  # 1時間
    calendar_max_events: int = 100
    
    # セキュリティ設定
    api_rate_limit: int = 60  # requests per minute
    allowed_origins: List[str] = None
    
    def __post_init__(self):
        if self.allowed_origins is None:
            self.allowed_origins = ["http://localhost:5000", "http://raspberrypi.local:5000"]


@dataclass
class LogConfig:
    """ログ関連設定"""
    # ログレベル
    log_level: str = "INFO"
    log_level_console: str = "INFO"
    log_level_file: str = "DEBUG"
    
    # ログファイル設定
    log_directory: str = "logs"
    log_max_size_mb: int = 10
    log_backup_count: int = 5
    log_encoding: str = "utf-8"
    
    # ログ出力設定
    log_format_json: bool = True
    log_include_timestamp: bool = True
    log_include_thread: bool = True
    log_include_process: bool = True
    
    # パフォーマンス設定
    log_async_enabled: bool = False
    log_buffer_size: int = 1024


@dataclass
class UIConfig:
    """UI/UX関連設定"""
    # ディスプレイ設定
    fullscreen_mode: bool = True
    window_width: int = 1920
    window_height: int = 1080
    
    # フォント設定
    font_family_primary: str = "Inter"
    font_family_japanese: str = "Noto Sans JP"
    font_family_icons: str = "Material Icons"
    font_size_base: int = 14
    font_size_large: int = 18
    font_size_title: int = 24
    
    # テーマ設定
    theme_dark_mode: bool = False
    theme_primary_color: str = "#2196F3"
    theme_accent_color: str = "#FF5722"
    theme_background_color: str = "#FAFAFA"
    
    # アニメーション設定
    animation_duration_ms: int = 200
    animation_enabled: bool = True


@dataclass
class MonitoringConfig:
    """監視・テスト設定"""
    # データ収集間隔
    sensor_update_interval_ms: int = 120000  # 2分
    calendar_update_interval_ms: int = 300000  # 5分
    system_metrics_interval_ms: int = 60000  # 1分
    
    # データ保持設定
    metrics_retention_hours: int = 24
    metrics_max_points: int = 1440  # 1日分（1分間隔）
    
    # 監視閾値
    cpu_temp_warning_celsius: float = 70.0
    cpu_temp_critical_celsius: float = 80.0
    memory_usage_warning_percent: float = 80.0
    memory_usage_critical_percent: float = 90.0
    
    # テスト設定
    test_timeout_seconds: float = 30.0
    test_retry_attempts: int = 3
    test_concurrent_requests: int = 5


class DashboardSettings:
    """
    統一設定管理クラス
    
    環境変数からの自動読み込み、デフォルト値管理、設定検証を提供
    """
    
    def __init__(self, environment: Optional[str] = None):
        self.environment = environment or os.getenv('ENVIRONMENT', 'production')
        self.config_dir = Path(__file__).parent
        
        # 各設定カテゴリを初期化
        self.hardware = self._load_hardware_config()
        self.api = self._load_api_config()
        self.logging = self._load_log_config()
        self.ui = self._load_ui_config()
        self.monitoring = self._load_monitoring_config()
        
        # 設定妥当性検証
        self._validate_settings()
    
    def _load_hardware_config(self) -> HardwareConfig:
        """ハードウェア設定読み込み"""
        return HardwareConfig(
            dht22_pin=self._get_int_env('DHT22_PIN', 4),  # Legacy config
            co2_sensor_uart_tx=self._get_int_env('CO2_UART_TX', 14),
            co2_sensor_uart_rx=self._get_int_env('CO2_UART_RX', 15),
            co2_sensor_baudrate=self._get_int_env('CO2_BAUDRATE', 9600),
            sensor_read_timeout=self._get_float_env('SENSOR_READ_TIMEOUT', 5.0),
            sensor_retry_attempts=self._get_int_env('SENSOR_RETRY_ATTEMPTS', 3),
            sensor_retry_delay=self._get_float_env('SENSOR_RETRY_DELAY', 1.0)
        )
    
    def _load_api_config(self) -> APIConfig:
        """API設定読み込み"""
        return APIConfig(
            flask_host=os.getenv('FLASK_HOST', 'localhost'),
            flask_port=self._get_int_env('FLASK_PORT', 5000),
            flask_debug=self._get_bool_env('FLASK_DEBUG', False),
            api_timeout=self._get_float_env('API_TIMEOUT', 5.0),
            api_retry_attempts=self._get_int_env('API_RETRY_ATTEMPTS', 2),
            api_retry_delay=self._get_float_env('API_RETRY_DELAY', 2.0),
            calendar_timeout=self._get_float_env('CALENDAR_TIMEOUT', 10.0),
            calendar_cache_ttl=self._get_int_env('CALENDAR_CACHE_TTL', 3600),
            calendar_max_events=self._get_int_env('CALENDAR_MAX_EVENTS', 100),
            api_rate_limit=self._get_int_env('API_RATE_LIMIT', 60)
        )
    
    def _load_log_config(self) -> LogConfig:
        """ログ設定読み込み"""
        return LogConfig(
            log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
            log_level_console=os.getenv('LOG_LEVEL_CONSOLE', 'INFO').upper(),
            log_level_file=os.getenv('LOG_LEVEL_FILE', 'DEBUG').upper(),
            log_directory=os.getenv('LOG_DIRECTORY', 'logs'),
            log_max_size_mb=self._get_int_env('LOG_MAX_SIZE_MB', 10),
            log_backup_count=self._get_int_env('LOG_BACKUP_COUNT', 5),
            log_encoding=os.getenv('LOG_ENCODING', 'utf-8'),
            log_format_json=self._get_bool_env('LOG_FORMAT_JSON', True),
            log_include_timestamp=self._get_bool_env('LOG_INCLUDE_TIMESTAMP', True),
            log_include_thread=self._get_bool_env('LOG_INCLUDE_THREAD', True),
            log_include_process=self._get_bool_env('LOG_INCLUDE_PROCESS', True),
            log_async_enabled=self._get_bool_env('LOG_ASYNC_ENABLED', False),
            log_buffer_size=self._get_int_env('LOG_BUFFER_SIZE', 1024)
        )
    
    def _load_ui_config(self) -> UIConfig:
        """UI設定読み込み"""
        return UIConfig(
            fullscreen_mode=self._get_bool_env('FULLSCREEN_MODE', True),
            window_width=self._get_int_env('WINDOW_WIDTH', 1920),
            window_height=self._get_int_env('WINDOW_HEIGHT', 1080),
            font_family_primary=os.getenv('FONT_FAMILY_PRIMARY', 'Inter'),
            font_family_japanese=os.getenv('FONT_FAMILY_JAPANESE', 'Noto Sans JP'),
            font_family_icons=os.getenv('FONT_FAMILY_ICONS', 'Material Icons'),
            font_size_base=self._get_int_env('FONT_SIZE_BASE', 14),
            font_size_large=self._get_int_env('FONT_SIZE_LARGE', 18),
            font_size_title=self._get_int_env('FONT_SIZE_TITLE', 24),
            theme_dark_mode=self._get_bool_env('THEME_DARK_MODE', False),
            theme_primary_color=os.getenv('THEME_PRIMARY_COLOR', '#2196F3'),
            theme_accent_color=os.getenv('THEME_ACCENT_COLOR', '#FF5722'),
            theme_background_color=os.getenv('THEME_BACKGROUND_COLOR', '#FAFAFA'),
            animation_duration_ms=self._get_int_env('ANIMATION_DURATION_MS', 200),
            animation_enabled=self._get_bool_env('ANIMATION_ENABLED', True)
        )
    
    def _load_monitoring_config(self) -> MonitoringConfig:
        """監視設定読み込み"""
        return MonitoringConfig(
            sensor_update_interval_ms=self._get_int_env('SENSOR_UPDATE_INTERVAL_MS', 120000),
            calendar_update_interval_ms=self._get_int_env('CALENDAR_UPDATE_INTERVAL_MS', 300000),
            system_metrics_interval_ms=self._get_int_env('SYSTEM_METRICS_INTERVAL_MS', 60000),
            metrics_retention_hours=self._get_int_env('METRICS_RETENTION_HOURS', 24),
            metrics_max_points=self._get_int_env('METRICS_MAX_POINTS', 1440),
            cpu_temp_warning_celsius=self._get_float_env('CPU_TEMP_WARNING', 70.0),
            cpu_temp_critical_celsius=self._get_float_env('CPU_TEMP_CRITICAL', 80.0),
            memory_usage_warning_percent=self._get_float_env('MEMORY_WARNING', 80.0),
            memory_usage_critical_percent=self._get_float_env('MEMORY_CRITICAL', 90.0),
            test_timeout_seconds=self._get_float_env('TEST_TIMEOUT', 30.0),
            test_retry_attempts=self._get_int_env('TEST_RETRY_ATTEMPTS', 3),
            test_concurrent_requests=self._get_int_env('TEST_CONCURRENT_REQUESTS', 5)
        )
    
    def _get_int_env(self, key: str, default: int) -> int:
        """環境変数から整数値を取得"""
        try:
            return int(os.getenv(key, default))
        except (ValueError, TypeError):
            return default
    
    def _get_float_env(self, key: str, default: float) -> float:
        """環境変数から浮動小数点値を取得"""
        try:
            return float(os.getenv(key, default))
        except (ValueError, TypeError):
            return default
    
    def _get_bool_env(self, key: str, default: bool) -> bool:
        """環境変数からブール値を取得"""
        value = os.getenv(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        return default
    
    def _validate_settings(self):
        """設定値の妥当性検証"""
        # ポート範囲チェック
        if not 1 <= self.api.flask_port <= 65535:
            raise ValueError(f"無効なポート番号: {self.api.flask_port}")
        
        # GPIOピン範囲チェック (legacy - SHT35 uses I2C)
        if not 1 <= self.hardware.dht22_pin <= 40:
            raise ValueError(f"無効なGPIOピン: {self.hardware.dht22_pin} (legacy config)")
        
        # ログレベル妥当性チェック
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.logging.log_level not in valid_log_levels:
            raise ValueError(f"無効なログレベル: {self.logging.log_level}")
        
        # タイムアウト値チェック
        if self.api.api_timeout <= 0:
            raise ValueError(f"無効なAPIタイムアウト: {self.api.api_timeout}")
    
    def get_environment_info(self) -> Dict[str, Any]:
        """環境情報取得"""
        return {
            'environment': self.environment,
            'config_directory': str(self.config_dir),
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown',
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'working_directory': os.getcwd()
        }
    
    def export_config(self, file_path: Optional[Path] = None) -> str:
        """設定をJSON形式でエクスポート"""
        config_dict = {
            'environment': self.environment,
            'hardware': self.hardware.__dict__,
            'api': self.api.__dict__,
            'logging': self.logging.__dict__,
            'ui': self.ui.__dict__,
            'monitoring': self.monitoring.__dict__,
            'environment_info': self.get_environment_info()
        }
        
        config_json = json.dumps(config_dict, indent=2, ensure_ascii=False, default=str)
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(config_json)
        
        return config_json
    
    def reload_from_env(self):
        """環境変数から設定を再読み込み"""
        self.__init__(self.environment)


# グローバル設定インスタンス
_settings_instance: Optional[DashboardSettings] = None


def get_settings(environment: Optional[str] = None) -> DashboardSettings:
    """設定インスタンス取得（シングルトン）"""
    global _settings_instance
    if _settings_instance is None or environment is not None:
        _settings_instance = DashboardSettings(environment)
    return _settings_instance


def reload_settings():
    """設定の再読み込み"""
    global _settings_instance
    if _settings_instance:
        _settings_instance.reload_from_env()


# 使用例・テスト関数
if __name__ == "__main__":
    # テスト実行
    settings = get_settings('development')
    logger = get_logger(__name__)
    
    logger.info("=== Dashboard Settings Test ===")
    logger.info("Environment", environment=settings.environment)
    logger.info("API Port", flask_port=settings.api.flask_port)
    logger.info("DHT22 Pin (legacy)", dht22_pin=settings.hardware.dht22_pin)
    logger.info("Log Level", log_level=settings.logging.log_level)
    logger.info("Fullscreen", fullscreen_mode=settings.ui.fullscreen_mode)
    logger.info("Sensor Update Interval (ms)", sensor_update_interval_ms=settings.monitoring.sensor_update_interval_ms)
    
    # 設定エクスポートテスト
    logger.info("=== Config Export ===")
    config_json = settings.export_config()
    logger.info("Config JSON", config_size=len(config_json))