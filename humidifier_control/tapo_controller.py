"""
Tapo P110M Smart Plug Controller (python-kasa版)
Tapo P110M スマートプラグ制御クラス

python-kasaライブラリを使用してKLAPプロトコルでP110Mを制御
"""

import asyncio
import logging
from typing import Optional
from dataclasses import dataclass

from kasa import (
    Device,
    Credentials,
    DeviceConfig,
    DeviceConnectionParameters,
    DeviceEncryptionType,
    DeviceFamily,
)

logger = logging.getLogger(__name__)


@dataclass
class PlugStatus:
    """プラグ状態"""
    device_on: bool
    nickname: str
    model: str
    signal_level: Optional[int] = None


@dataclass
class EnergyUsage:
    """電力使用状況"""
    current_power_w: float      # 現在の電力 (W)
    today_energy_wh: float      # 今日の消費電力量 (Wh)


class TapoPlugController:
    """Tapo P110M スマートプラグ制御クラス (python-kasa版)"""

    def __init__(self, ip: str, email: str, password: str):
        """
        Args:
            ip: プラグのIPアドレス
            email: Tapoアカウントのメールアドレス
            password: Tapoアカウントのパスワード
        """
        self.ip = ip
        self.email = email
        self.password = password
        self._device: Optional[Device] = None

    def _create_config(self) -> DeviceConfig:
        """デバイス接続設定を作成"""
        creds = Credentials(self.email, self.password)
        conn_type = DeviceConnectionParameters(
            device_family=DeviceFamily.SmartTapoPlug,
            encryption_type=DeviceEncryptionType.Klap,
            login_version=2
        )
        return DeviceConfig(
            host=self.ip,
            credentials=creds,
            connection_type=conn_type
        )

    async def connect(self) -> bool:
        """プラグに接続

        Returns:
            bool: 接続成功かどうか
        """
        try:
            config = self._create_config()
            self._device = await Device.connect(config=config)
            await self._device.update()
            logger.info(f"Tapo P110M接続成功: {self.ip} ({self._device.alias})")
            return True
        except Exception as e:
            logger.error(f"Tapo P110M接続失敗: {self.ip} - {e}")
            self._device = None
            return False

    async def _ensure_connected(self) -> bool:
        """接続を確保"""
        if self._device is None:
            return await self.connect()
        return True

    async def turn_on(self) -> bool:
        """プラグをONにする

        Returns:
            bool: 成功かどうか
        """
        try:
            if not await self._ensure_connected():
                return False
            await self._device.turn_on()
            logger.info(f"Tapo P110M ON: {self.ip}")
            return True
        except Exception as e:
            logger.error(f"Tapo P110M ON失敗: {self.ip} - {e}")
            self._device = None  # 再接続を促す
            return False

    async def turn_off(self) -> bool:
        """プラグをOFFにする

        Returns:
            bool: 成功かどうか
        """
        try:
            if not await self._ensure_connected():
                return False
            await self._device.turn_off()
            logger.info(f"Tapo P110M OFF: {self.ip}")
            return True
        except Exception as e:
            logger.error(f"Tapo P110M OFF失敗: {self.ip} - {e}")
            self._device = None
            return False

    async def get_status(self) -> Optional[PlugStatus]:
        """プラグの状態を取得

        Returns:
            PlugStatus: プラグ状態、失敗時はNone
        """
        try:
            if not await self._ensure_connected():
                return None
            await self._device.update()
            return PlugStatus(
                device_on=self._device.is_on,
                nickname=self._device.alias,
                model=self._device.model,
                signal_level=getattr(self._device, 'rssi', None),
            )
        except Exception as e:
            logger.error(f"Tapo P110Mステータス取得失敗: {self.ip} - {e}")
            self._device = None
            return None

    async def get_energy_usage(self) -> Optional[EnergyUsage]:
        """電力使用状況を取得（P110M専用機能）

        Returns:
            EnergyUsage: 電力使用状況、失敗時はNone
        """
        try:
            if not await self._ensure_connected():
                return None
            await self._device.update()

            # Energy moduleから電力情報を取得
            if hasattr(self._device, 'modules') and 'Energy' in self._device.modules:
                energy = self._device.modules['Energy']
                return EnergyUsage(
                    current_power_w=getattr(energy, 'current_consumption', 0) or 0,
                    today_energy_wh=getattr(energy, 'consumption_today', 0) or 0,
                )
            return None
        except Exception as e:
            logger.error(f"Tapo P110M電力取得失敗: {self.ip} - {e}")
            return None

    async def is_on(self) -> Optional[bool]:
        """プラグがONかどうかを確認

        Returns:
            bool: ONならTrue、OFFならFalse、取得失敗時はNone
        """
        status = await self.get_status()
        if status is None:
            return None
        return status.device_on

    async def disconnect(self):
        """接続を切断"""
        if self._device is not None:
            try:
                await self._device.disconnect()
            except Exception:
                pass
            self._device = None
