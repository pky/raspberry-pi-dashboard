"""
アプリケーション設定
pydantic-settings で .env を読み込み、起動時に必須値の存在を検証する。
必須値が欠けている場合はここで即座にエラーになるため、
「値が取れていないまま動き続ける」状態が起きない。
"""

import sys
from pathlib import Path
from typing import List
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / '.env'


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding='utf-8',
        extra='ignore',
        populate_by_name=True,
    )

    # Flask
    SECRET_KEY: str                         # 必須（未設定なら起動を拒否）
    DEBUG: bool = Field(default=False, validation_alias='FLASK_DEBUG')
    HOST: str  = Field(default='0.0.0.0',  validation_alias='FLASK_HOST')
    PORT: int  = Field(default=5000,       validation_alias='FLASK_PORT')

    # センサー
    SENSOR_FORCE_REAL_VALUES: bool = True
    DHT22_PIN: int = 4
    SENSOR_READ_TIMEOUT: int = 5
    SENSOR_RETRY_COUNT: int = 3
    SENSOR_MAX_RETRIES: int = 3
    SENSOR_RETRY_DELAY: float = 2.0
    SENSOR_UPDATE_INTERVAL: int = 30

    # Google Calendar
    GOOGLE_CALENDAR_ENABLED: bool = True
    GOOGLE_CREDENTIALS_FILE: str = 'credentials/credentials.json'
    GOOGLE_TOKEN_FILE: str = 'credentials/token.json'
    GOOGLE_CALENDAR_ID: str = 'primary'
    GOOGLE_ADDITIONAL_CALENDAR_IDS_RAW: str = Field(default='', alias='GOOGLE_ADDITIONAL_CALENDAR_IDS')
    GOOGLE_SCOPES: List[str] = ['https://www.googleapis.com/auth/calendar.readonly']

    @computed_field  # type: ignore[misc]
    @property
    def GOOGLE_ADDITIONAL_CALENDAR_IDS(self) -> List[str]:
        return [x.strip() for x in self.GOOGLE_ADDITIONAL_CALENDAR_IDS_RAW.split(',') if x.strip()]

    # 天気
    OPENWEATHERMAP_API_KEY: str = ''        # 未設定なら天気機能が動かない（エラーにはしない）
    WEATHER_LATITUDE: float = 35.652875
    WEATHER_LONGITUDE: float = 139.701595
    WEATHER_LOCATION_NAME: str = '渋谷区'

    # 表示
    TIMEZONE: str = 'Asia/Tokyo'
    LANGUAGE: str = 'ja'
    TOUCH_PANEL_WIDTH: int = 1024
    TOUCH_PANEL_HEIGHT: int = 600

    # ログ
    LOG_LEVEL: str = 'INFO'
    LOG_FILE: str = 'logs/dashboard.log'
    LOG_MAX_BYTES: int = 10485760
    LOG_BACKUP_COUNT: int = 5

    # システム
    AUTO_START_BROWSER: bool = True
    BROWSER_KIOSK_MODE: bool = True


try:
    settings = Settings()
except Exception as e:
    print(f"[設定エラー] .env の必須値が不足しています: {e}", file=sys.stderr)
    sys.exit(1)

# 後方互換：既存コードの Config.XXX / get_config() をそのまま動かす
Config = settings


def get_config() -> Settings:
    return settings
