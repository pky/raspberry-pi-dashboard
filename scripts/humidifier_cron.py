#!/usr/bin/env python3
"""
Humidifier Control Cron Script
湿度連動加湿器制御 - cron実行スクリプト

5分間隔でcronから実行され、湿度に応じてTapo P110Mを制御する。

Usage:
    */5 * * * * /path/to/raspberry-pi-dashboard/.venv/bin/python /path/to/raspberry-pi-dashboard/scripts/humidifier_cron.py

環境変数:
    TAPO_EMAIL: Tapoアカウントのメールアドレス
    TAPO_PASSWORD: Tapoアカウントのパスワード
"""

import sys
import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# .envファイルを読み込む（既存と同じ方式）
from dotenv import load_dotenv
load_dotenv(project_root / '.env')

from humidifier_control import HumidifierConfig, HumidifierController
from sensor import get_sensor

# ログディレクトリ作成
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'humidifier.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('humidifier_cron')


async def main():
    """メイン処理"""
    logger.info("=" * 50)
    logger.info("加湿器制御開始")

    controller = None
    try:
        # 設定読み込み
        config = HumidifierConfig.from_env()
        valid, error_msg = config.validate()
        if not valid:
            logger.error(f"設定エラー: {error_msg}")
            sys.exit(1)

        # 夜間停止判定
        if config.is_quiet_hours_start():
            # 夜間停止開始時刻 → 強制OFF
            logger.info(f"夜間停止開始 ({config.quiet_hours_start})")
            from humidifier_control import TapoPlugController
            plug = TapoPlugController(config.tapo_ip, config.tapo_email, config.tapo_password)
            try:
                current_state = await plug.is_on()
                if current_state:
                    success = await plug.turn_off()
                    if success:
                        logger.info("夜間停止: 加湿器をOFFにしました")
                    else:
                        logger.error("夜間停止: OFFに失敗しました")
                else:
                    logger.info("夜間停止: 既にOFFです")
            finally:
                await plug.disconnect()
            logger.info("加湿器制御完了")
            logger.info("=" * 50)
            return

        if config.is_quiet_hours():
            # 夜間停止時間帯 → 制御スキップ
            logger.info(f"夜間停止中 ({config.quiet_hours_start}〜{config.quiet_hours_end}) - 制御スキップ")
            logger.info("加湿器制御完了")
            logger.info("=" * 50)
            return

        # センサーから湿度取得
        try:
            sensor = get_sensor()
            sensor_data = sensor.get_sensor_data(enable_logging=False)
            humidity = sensor_data.get('humidity')

            if humidity is None:
                logger.error("湿度データを取得できませんでした")
                sys.exit(1)

            logger.info(f"現在の湿度: {humidity}%")

        except Exception as e:
            logger.exception(f"センサー読み取りエラー: {e}")
            sys.exit(1)

        # 加湿器制御
        controller = HumidifierController(config)

        # スキップ判定
        should_skip, skip_reason = controller.should_skip_control()
        if should_skip:
            logger.warning(f"制御スキップ: {skip_reason}")
            return

        # 制御実行
        result = await controller.evaluate_and_control(humidity)

        # 結果ログ
        if result.success:
            logger.info(f"制御結果: {result.action.value}")
            logger.info(f"理由: {result.reason}")
            if result.plug_state_before != result.plug_state_after:
                before = "ON" if result.plug_state_before else "OFF"
                after = "ON" if result.plug_state_after else "OFF"
                logger.info(f"状態変化: {before} -> {after}")
        else:
            logger.error(f"制御失敗: {result.error_message}")
            logger.error(f"アクション: {result.action.value}")

    finally:
        # 接続を切断
        if controller is not None:
            await controller.plug.disconnect()
        logger.info("加湿器制御完了")
        logger.info("=" * 50)


if __name__ == '__main__':
    asyncio.run(main())
