#!/usr/bin/env python3
"""
Humidifier Control Tests
湿度連動加湿器制御のテスト
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from humidifier_control.config import HumidifierConfig
from humidifier_control.humidifier_logic import (
    HumidifierController,
    ControlAction,
    ControlResult,
)
from humidifier_control.tapo_controller import TapoPlugController, PlugStatus


class TestHumidifierConfig:
    """HumidifierConfig のテスト"""

    def test_default_values(self):
        """デフォルト値のテスト"""
        config = HumidifierConfig(
            tapo_email="test@example.com",
            tapo_password="password"
        )
        assert config.tapo_ip == ""
        assert config.humidity_on_threshold == 40.0
        assert config.humidity_off_threshold == 55.0

    def test_validate_success(self):
        """正常な設定の検証"""
        config = HumidifierConfig(
            tapo_email="test@example.com",
            tapo_password="password"
        )
        valid, error = config.validate()
        assert valid is True
        assert error == ""

    def test_validate_missing_email(self):
        """メール未設定時のエラー"""
        config = HumidifierConfig(tapo_password="password")
        valid, error = config.validate()
        assert valid is False
        assert "TAPO_EMAIL" in error

    def test_validate_missing_password(self):
        """パスワード未設定時のエラー"""
        config = HumidifierConfig(tapo_email="test@example.com")
        valid, error = config.validate()
        assert valid is False
        assert "TAPO_PASSWORD" in error

    def test_validate_invalid_threshold(self):
        """不正な閾値設定のエラー"""
        config = HumidifierConfig(
            tapo_email="test@example.com",
            tapo_password="password",
            humidity_on_threshold=60.0,  # ON > OFF はエラー
            humidity_off_threshold=50.0
        )
        valid, error = config.validate()
        assert valid is False
        assert "閾値" in error


class TestHumidifierController:
    """HumidifierController のテスト"""

    @pytest.fixture
    def config(self):
        """テスト用設定"""
        return HumidifierConfig(
            tapo_email="test@example.com",
            tapo_password="password",
            humidity_on_threshold=40.0,
            humidity_off_threshold=55.0
        )

    @pytest.fixture
    def controller(self, config):
        """テスト用コントローラ"""
        return HumidifierController(config)

    def test_determine_action_turn_on(self, controller):
        """低湿度時のON判定"""
        action, reason = controller._determine_action(
            humidity=35.0,
            current_state=False
        )
        assert action == ControlAction.TURN_ON
        assert "ON" in reason

    def test_determine_action_turn_off(self, controller):
        """高湿度時のOFF判定"""
        action, reason = controller._determine_action(
            humidity=60.0,
            current_state=True
        )
        assert action == ControlAction.TURN_OFF
        assert "OFF" in reason

    def test_determine_action_hysteresis_on(self, controller):
        """ヒステリシス帯域でON維持"""
        action, reason = controller._determine_action(
            humidity=50.0,  # 40-55の間
            current_state=True
        )
        assert action == ControlAction.NO_CHANGE
        assert "ヒステリシス" in reason

    def test_determine_action_hysteresis_off(self, controller):
        """ヒステリシス帯域でOFF維持"""
        action, reason = controller._determine_action(
            humidity=50.0,  # 40-55の間
            current_state=False
        )
        assert action == ControlAction.NO_CHANGE
        assert "ヒステリシス" in reason

    def test_determine_action_already_on(self, controller):
        """既にONの場合"""
        action, reason = controller._determine_action(
            humidity=35.0,
            current_state=True  # 既にON
        )
        assert action == ControlAction.NO_CHANGE
        assert "既にON" in reason

    def test_determine_action_already_off(self, controller):
        """既にOFFの場合"""
        action, reason = controller._determine_action(
            humidity=60.0,
            current_state=False  # 既にOFF
        )
        assert action == ControlAction.NO_CHANGE
        assert "既にOFF" in reason

    @pytest.mark.asyncio
    async def test_evaluate_and_control_turn_on(self, controller):
        """ON制御の実行テスト"""
        # モック設定
        controller.plug.is_on = AsyncMock(return_value=False)
        controller.plug.turn_on = AsyncMock(return_value=True)

        result = await controller.evaluate_and_control(humidity=35.0)

        assert result.action == ControlAction.TURN_ON
        assert result.success is True
        assert result.plug_state_before is False
        assert result.plug_state_after is True
        controller.plug.turn_on.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_and_control_turn_off(self, controller):
        """OFF制御の実行テスト"""
        controller.plug.is_on = AsyncMock(return_value=True)
        controller.plug.turn_off = AsyncMock(return_value=True)

        result = await controller.evaluate_and_control(humidity=60.0)

        assert result.action == ControlAction.TURN_OFF
        assert result.success is True
        assert result.plug_state_before is True
        assert result.plug_state_after is False
        controller.plug.turn_off.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_and_control_no_change(self, controller):
        """状態維持テスト"""
        controller.plug.is_on = AsyncMock(return_value=True)

        result = await controller.evaluate_and_control(humidity=50.0)

        assert result.action == ControlAction.NO_CHANGE
        assert result.success is True
        assert result.plug_state_before is True
        assert result.plug_state_after is True

    @pytest.mark.asyncio
    async def test_evaluate_and_control_connection_error(self, controller):
        """接続エラー時のテスト"""
        controller.plug.is_on = AsyncMock(return_value=None)

        result = await controller.evaluate_and_control(humidity=35.0)

        assert result.action == ControlAction.ERROR
        assert result.success is False
        assert controller._consecutive_failures == 1

    def test_should_skip_control(self, controller):
        """連続失敗時のスキップ判定"""
        controller._consecutive_failures = 3
        should_skip, reason = controller.should_skip_control()

        assert should_skip is True
        assert "一時停止" in reason

    def test_reset_failure_count(self, controller):
        """失敗カウントリセット"""
        controller._consecutive_failures = 5
        controller.reset_failure_count()
        assert controller._consecutive_failures == 0


class TestControlResult:
    """ControlResult のテスト"""

    def test_to_dict(self):
        """辞書変換テスト"""
        result = ControlResult(
            action=ControlAction.TURN_ON,
            humidity=35.0,
            plug_state_before=False,
            plug_state_after=True,
            reason="テスト理由"
        )
        d = result.to_dict()

        assert d['action'] == 'turn_on'
        assert d['humidity'] == 35.0
        assert d['plug_state_before'] is False
        assert d['plug_state_after'] is True
        assert d['reason'] == "テスト理由"
        assert d['success'] is True
        assert 'timestamp' in d


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
