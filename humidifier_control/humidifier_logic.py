"""
Humidifier Control Logic
湿度連動加湿器制御ロジック
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from .config import HumidifierConfig
from .tapo_controller import TapoPlugController

logger = logging.getLogger(__name__)


class ControlAction(Enum):
    """制御アクション"""
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    NO_CHANGE = "no_change"
    ERROR = "error"


@dataclass
class ControlResult:
    """制御結果"""
    action: ControlAction
    humidity: Optional[float]
    plug_state_before: Optional[bool]
    plug_state_after: Optional[bool]
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        """辞書形式に変換"""
        return {
            'action': self.action.value,
            'humidity': self.humidity,
            'plug_state_before': self.plug_state_before,
            'plug_state_after': self.plug_state_after,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat(),
            'success': self.success,
            'error_message': self.error_message,
        }


class HumidifierController:
    """湿度連動加湿器制御クラス"""

    def __init__(self, config: HumidifierConfig):
        """
        Args:
            config: 加湿器制御設定
        """
        self.config = config
        self.plug = TapoPlugController(
            ip=config.tapo_ip,
            email=config.tapo_email,
            password=config.tapo_password,
        )
        self._consecutive_failures = 0

    def _determine_action(
        self,
        humidity: float,
        current_state: bool
    ) -> tuple[ControlAction, str]:
        """制御アクションを決定（ヒステリシス制御）

        Args:
            humidity: 現在の湿度 (%)
            current_state: 現在のプラグ状態 (True=ON)

        Returns:
            tuple: (アクション, 理由)
        """
        on_threshold = self.config.humidity_on_threshold
        off_threshold = self.config.humidity_off_threshold

        if humidity <= on_threshold:
            if not current_state:
                return (
                    ControlAction.TURN_ON,
                    f"湿度{humidity}%が閾値{on_threshold}%以下のためON"
                )
            else:
                return (
                    ControlAction.NO_CHANGE,
                    f"湿度{humidity}%: 既にON状態"
                )
        elif humidity >= off_threshold:
            if current_state:
                return (
                    ControlAction.TURN_OFF,
                    f"湿度{humidity}%が閾値{off_threshold}%以上のためOFF"
                )
            else:
                return (
                    ControlAction.NO_CHANGE,
                    f"湿度{humidity}%: 既にOFF状態"
                )
        else:
            # ヒステリシス帯域内: 状態維持
            state_str = "ON" if current_state else "OFF"
            return (
                ControlAction.NO_CHANGE,
                f"湿度{humidity}%: ヒステリシス帯域内({on_threshold}%-{off_threshold}%)、{state_str}維持"
            )

    async def evaluate_and_control(self, humidity: float) -> ControlResult:
        """湿度を評価して制御を実行

        Args:
            humidity: 現在の湿度 (%)

        Returns:
            ControlResult: 制御結果
        """
        try:
            # 現在のプラグ状態を取得
            current_state = await self.plug.is_on()
            if current_state is None:
                self._consecutive_failures += 1
                return ControlResult(
                    action=ControlAction.ERROR,
                    humidity=humidity,
                    plug_state_before=None,
                    plug_state_after=None,
                    reason="プラグ状態取得失敗",
                    success=False,
                    error_message=f"連続失敗: {self._consecutive_failures}回"
                )

            # 制御アクションを決定
            action, reason = self._determine_action(humidity, current_state)

            # アクション実行
            new_state = current_state
            if action == ControlAction.TURN_ON:
                success = await self.plug.turn_on()
                if success:
                    new_state = True
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    return ControlResult(
                        action=action,
                        humidity=humidity,
                        plug_state_before=current_state,
                        plug_state_after=current_state,
                        reason=reason,
                        success=False,
                        error_message="ON操作失敗"
                    )
            elif action == ControlAction.TURN_OFF:
                success = await self.plug.turn_off()
                if success:
                    new_state = False
                    self._consecutive_failures = 0
                else:
                    self._consecutive_failures += 1
                    return ControlResult(
                        action=action,
                        humidity=humidity,
                        plug_state_before=current_state,
                        plug_state_after=current_state,
                        reason=reason,
                        success=False,
                        error_message="OFF操作失敗"
                    )
            else:
                # NO_CHANGE
                self._consecutive_failures = 0

            return ControlResult(
                action=action,
                humidity=humidity,
                plug_state_before=current_state,
                plug_state_after=new_state,
                reason=reason,
                success=True
            )

        except Exception as e:
            self._consecutive_failures += 1
            logger.exception("制御処理で例外発生")
            return ControlResult(
                action=ControlAction.ERROR,
                humidity=humidity,
                plug_state_before=None,
                plug_state_after=None,
                reason="制御処理例外",
                success=False,
                error_message=str(e)
            )

    def should_skip_control(self) -> tuple[bool, str]:
        """制御をスキップすべきか判定

        Returns:
            tuple: (スキップするか, 理由)
        """
        max_failures = self.config.max_consecutive_failures
        if self._consecutive_failures >= max_failures:
            return (
                True,
                f"連続失敗が{max_failures}回に達したため一時停止"
            )
        return False, ""

    def reset_failure_count(self):
        """失敗カウントをリセット"""
        self._consecutive_failures = 0
        logger.info("失敗カウントをリセット")
