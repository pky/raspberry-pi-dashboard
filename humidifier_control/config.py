"""
Humidifier Control Configuration
加湿器制御の設定管理
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class HumidifierConfig:
    """加湿器制御設定"""

    # Tapo P110M 設定
    tapo_ip: str = ""
    tapo_email: Optional[str] = None
    tapo_password: Optional[str] = None

    # 制御閾値
    humidity_on_threshold: float = 40.0   # この値以下でON
    humidity_off_threshold: float = 55.0  # この値以上でOFF

    # 夜間停止設定 (HH:MM形式)
    quiet_hours_start: str = "00:00"      # 停止開始時刻（この時刻にOFFにする）
    quiet_hours_end: str = "09:00"        # 停止終了時刻（この時刻から制御再開）
    quiet_hours_enabled: bool = True      # 夜間停止を有効にするか

    # 安全設定
    max_consecutive_failures: int = 3     # 連続失敗許容回数
    sensor_timeout_seconds: int = 30      # センサータイムアウト

    # ログ設定
    log_file: str = field(default_factory=lambda: str(_PROJECT_ROOT / "logs" / "humidifier.log"))

    def __post_init__(self):
        """環境変数から認証情報を取得"""
        if self.tapo_email is None:
            self.tapo_email = os.environ.get('TAPO_EMAIL')
        if self.tapo_password is None:
            self.tapo_password = os.environ.get('TAPO_PASSWORD')

    def validate(self) -> tuple[bool, str]:
        """設定値の検証

        Returns:
            tuple: (有効かどうか, エラーメッセージ)
        """
        if not self.tapo_email:
            return False, "TAPO_EMAIL環境変数が設定されていません"
        if not self.tapo_password:
            return False, "TAPO_PASSWORD環境変数が設定されていません"
        if self.humidity_on_threshold >= self.humidity_off_threshold:
            return False, "ON閾値はOFF閾値より小さくする必要があります"
        if not (0 <= self.humidity_on_threshold <= 100):
            return False, "ON閾値は0-100の範囲で指定してください"
        if not (0 <= self.humidity_off_threshold <= 100):
            return False, "OFF閾値は0-100の範囲で指定してください"
        return True, ""

    def is_quiet_hours(self) -> bool:
        """現在が夜間停止時間帯かどうかを判定

        Returns:
            bool: 夜間停止時間帯ならTrue
        """
        if not self.quiet_hours_enabled:
            return False

        from datetime import datetime

        now = datetime.now()
        current_time = now.hour * 60 + now.minute

        start_parts = self.quiet_hours_start.split(':')
        end_parts = self.quiet_hours_end.split(':')
        start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
        end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])

        # 日をまたぐ場合（例: 23:00 - 07:00）
        if start_minutes > end_minutes:
            return current_time >= start_minutes or current_time < end_minutes
        else:
            # 同じ日（例: 00:00 - 09:00）
            return start_minutes <= current_time < end_minutes

    def is_quiet_hours_start(self) -> bool:
        """現在が夜間停止開始時刻かどうかを判定（5分の幅で判定）

        Returns:
            bool: 開始時刻付近ならTrue
        """
        if not self.quiet_hours_enabled:
            return False

        from datetime import datetime

        now = datetime.now()
        current_time = now.hour * 60 + now.minute

        start_parts = self.quiet_hours_start.split(':')
        start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])

        # 5分の幅で判定（cronが5分間隔のため）
        return start_minutes <= current_time < start_minutes + 5

    @classmethod
    def from_env(cls) -> 'HumidifierConfig':
        """環境変数から設定を読み込む"""
        quiet_enabled = os.environ.get('HUMIDIFIER_QUIET_HOURS_ENABLED', 'true').lower()
        return cls(
            tapo_ip=os.environ.get('TAPO_IP', ''),
            tapo_email=os.environ.get('TAPO_EMAIL'),
            tapo_password=os.environ.get('TAPO_PASSWORD'),
            humidity_on_threshold=float(os.environ.get('HUMIDITY_ON_THRESHOLD', '40.0')),
            humidity_off_threshold=float(os.environ.get('HUMIDITY_OFF_THRESHOLD', '55.0')),
            quiet_hours_start=os.environ.get('HUMIDIFIER_QUIET_START', '00:00'),
            quiet_hours_end=os.environ.get('HUMIDIFIER_QUIET_END', '09:00'),
            quiet_hours_enabled=quiet_enabled in ('true', '1', 'yes'),
        )
