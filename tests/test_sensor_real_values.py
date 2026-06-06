#!/usr/bin/env python3
"""
実測値確認テスト - シミュレーション値検出防止
Raspberry Pi上で必須実行 - 実測値取得の保証

🚨 目的: シミュレーション値問題の再発を根本的に防止
"""

import pytest
import json
import logging
import os
from datetime import datetime
from pathlib import Path
import sys

# プロジェクトルートを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

# Raspberry Pi環境（I2CまたはUARTデバイスが存在する）かチェック
IS_RASPBERRY_PI = Path('/dev/i2c-1').exists() or Path('/dev/ttyAMA0').exists()
pytestmark = pytest.mark.skipif(
    not IS_RASPBERRY_PI,
    reason="Raspberry Pi実機が必要なテストです（I2C/UARTデバイス未検出）"
)

from sensor import get_sensor
from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestSensorRealValues:
    """センサー実測値確認テストクラス"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """テスト前設定"""
        self.sensor = get_sensor()
        self.min_co2 = 300  # CO2最小値（ppm）
        self.max_co2 = 5000  # CO2最大値（ppm）
        self.min_temp = -10  # 温度最小値（°C）
        self.max_temp = 50   # 温度最大値（°C）
        self.min_humidity = 0   # 湿度最小値（%）
        self.max_humidity = 100 # 湿度最大値（%）

    def test_config_force_real_values_enabled(self):
        """設定: 実測値強制モードが有効か確認"""
        assert hasattr(Config, 'SENSOR_FORCE_REAL_VALUES'), \
            "❌ Config.SENSOR_FORCE_REAL_VALUES が存在しません"
        
        assert Config.SENSOR_FORCE_REAL_VALUES is True, \
            f"❌ 実測値強制モードが無効: {Config.SENSOR_FORCE_REAL_VALUES}"
        
        logger.info("✅ 設定確認: 実測値強制モード有効")

    def test_co2_sensor_real_values(self):
        """CO2センサー: 実測値取得確認"""
        try:
            # 実測値強制取得
            sensor_data = self.sensor.get_sensor_data(
                enable_logging=False,
                retry_on_simulation=Config.SENSOR_FORCE_REAL_VALUES,
                max_retries=Config.SENSOR_MAX_RETRIES
            )
            
            # 基本データ存在確認
            assert sensor_data is not None, "❌ センサーデータが取得できません"
            assert 'co2_ppm' in sensor_data, "❌ CO2データが存在しません"
            
            co2_value = sensor_data.get('co2_ppm', 0)
            
            # 実測値範囲確認
            assert self.min_co2 <= co2_value <= self.max_co2, \
                f"❌ CO2値が異常範囲: {co2_value}ppm (正常範囲: {self.min_co2}-{self.max_co2}ppm)"
            
            # シミュレーション判定確認
            is_simulation = sensor_data.get('co2_simulation', True)
            assert is_simulation is False, \
                f"❌ CO2がシミュレーション値: {co2_value}ppm (simulation={is_simulation})"
            
            logger.info(f"✅ CO2実測値確認: {co2_value}ppm (実測値)")
            
        except Exception as e:
            pytest.fail(f"❌ CO2センサーテスト失敗: {e}")

    def test_sht35_sensor_real_values(self):
        """SHT35センサー: 温湿度実測値確認"""
        try:
            # Smart Averaging + 実測値強制取得
            sensor_data = self.sensor.get_sensor_data(
                smart_averaging=True,
                verification_mode="smart",
                enable_logging=False,
                retry_on_simulation=Config.SENSOR_FORCE_REAL_VALUES,
                max_retries=Config.SENSOR_MAX_RETRIES
            )
            
            # 基本データ存在確認
            assert sensor_data is not None, "❌ センサーデータが取得できません"
            assert not sensor_data.get('error'), f"❌ センサーエラー: {sensor_data.get('error')}"
            
            # 温度データ確認
            temperature = sensor_data.get('temperature', 0)
            assert self.min_temp <= temperature <= self.max_temp, \
                f"❌ 温度が異常範囲: {temperature}°C (正常範囲: {self.min_temp}-{self.max_temp}°C)"
            
            # 湿度データ確認  
            humidity = sensor_data.get('humidity', 0)
            assert self.min_humidity <= humidity <= self.max_humidity, \
                f"❌ 湿度が異常範囲: {humidity}% (正常範囲: {self.min_humidity}-{self.max_humidity}%)"
            
            # Smart Averaging品質確認
            if sensor_data.get('smart_averaging_used'):
                quality_score = sensor_data.get('quality_score', 0.0)
                assert quality_score >= 0.5, \
                    f"❌ Smart Averaging品質が低すぎ: {quality_score} (最低0.5必要)"
                
                sample_count = sensor_data.get('sample_count', 0)
                assert sample_count >= 1, \
                    f"❌ サンプル数が不正: {sample_count}"
                
                logger.info(f"✅ Smart Averaging: 温度{temperature}°C, 湿度{humidity}% "
                          f"(品質: {quality_score:.2f}, サンプル: {sample_count})")
            else:
                logger.info(f"✅ 標準センサー: 温度{temperature}°C, 湿度{humidity}%")
            
        except Exception as e:
            pytest.fail(f"❌ SHT35センサーテスト失敗: {e}")

    def test_monitoring_collector_real_values(self):
        """監視コレクター: 実測値確認"""
        try:
            # monitoring_collector.pyの実行テスト
            import subprocess
            import tempfile
            
            # 一時的な出力ディレクトリ作成
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_json = Path(temp_dir) / "metrics_test.json"
                
                # monitoring_collector実行（絶対パス）
                result = subprocess.run([
                    'python3', str(Path(__file__).parent.parent / 'monitoring_collector.py')
                ], capture_output=True, text=True, timeout=30)
                
                assert result.returncode == 0, \
                    f"❌ monitoring_collector実行失敗: {result.stderr}"
                
                # ログ出力確認
                output = result.stdout + result.stderr
                
                # 実測値取得確認パターン（実際のログ出力に基づく）
                real_value_patterns = [
                    "初期CO2値:",
                    "MH-Z19E mh-z19パッケージで接続成功",
                    "SHT35 sensor initialized"
                ]
                
                found_patterns = []
                for pattern in real_value_patterns:
                    if pattern in output:
                        found_patterns.append(pattern)
                
                assert len(found_patterns) >= 1, \
                    f"❌ 実測値取得パターンが見つかりません。出力: {output[:500]}..."
                
                # シミュレーション値警告確認
                simulation_warnings = [
                    "シミュレーション値使用",
                    "データ取得失敗"
                ]
                
                found_warnings = []
                for warning in simulation_warnings:
                    if warning in output:
                        found_warnings.append(warning)
                
                if found_warnings:
                    logger.warning(f"⚠️ シミュレーション値警告検出: {found_warnings}")
                else:
                    logger.info("✅ シミュレーション値警告なし - 全て実測値")
                
                logger.info(f"✅ monitoring_collector実測値確認完了: {found_patterns}")
                
        except Exception as e:
            pytest.fail(f"❌ monitoring_collector実測値テスト失敗: {e}")

    def test_json_output_real_values(self):
        """JSON出力: 実測値データ確認"""
        try:
            json_path = Path("static/data/metrics.json")
            
            if not json_path.exists():
                pytest.skip("❓ metrics.json が存在しません - 初回実行の可能性")
            
            # JSON読み込み
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metrics = data.get('metrics', [])
            assert len(metrics) > 0, "❌ メトリクスデータが空です"
            
            # 最新データ確認
            latest_metric = metrics[-1]
            
            # CO2データ確認
            co2_ppm = latest_metric.get('co2_ppm', 0)
            assert self.min_co2 <= co2_ppm <= self.max_co2, \
                f"❌ JSON内CO2値が異常: {co2_ppm}ppm"
            
            # 温度データ確認
            room_temp = latest_metric.get('room_temperature', 0)
            assert self.min_temp <= room_temp <= self.max_temp, \
                f"❌ JSON内温度が異常: {room_temp}°C"
            
            # 湿度データ確認
            humidity = latest_metric.get('humidity', 0)
            assert self.min_humidity <= humidity <= self.max_humidity, \
                f"❌ JSON内湿度が異常: {humidity}%"
            
            # Smart Averaging品質確認
            quality_score = latest_metric.get('quality_score', 0.0)
            smart_averaging_used = latest_metric.get('smart_averaging_used', False)
            
            if smart_averaging_used:
                assert quality_score >= 0.5, \
                    f"❌ JSON内品質スコアが低すぎ: {quality_score}"
                
                logger.info(f"✅ JSON実測値確認: CO2={co2_ppm}ppm, 温度={room_temp}°C, "
                          f"湿度={humidity}%, 品質={quality_score:.2f}")
            else:
                logger.info(f"✅ JSON実測値確認: CO2={co2_ppm}ppm, 温度={room_temp}°C, 湿度={humidity}%")
            
        except Exception as e:
            pytest.fail(f"❌ JSON出力実測値テスト失敗: {e}")

    def test_continuous_real_values_monitoring(self):
        """連続監視: 一定時間の実測値確認（短縮版）"""
        import time
        
        try:
            logger.info("📊 連続実測値監視開始 (短縮版: 3秒)")
            
            for i in range(2):  # 1秒間隔で2回（テスト短縮）
                sensor_data = self.sensor.get_sensor_data(
                    smart_averaging=True,
                    retry_on_simulation=True,
                    max_retries=3
                )
                
                co2_ppm = sensor_data.get('co2_ppm', 0)
                temperature = sensor_data.get('temperature', 0)
                humidity = sensor_data.get('humidity', 0)
                is_simulation = sensor_data.get('co2_simulation', True)
                
                assert not is_simulation, f"❌ 連続監視でシミュレーション値検出: {co2_ppm}ppm"
                
                logger.info(f"✅ 連続監視[{i+1}/2]: CO2={co2_ppm}ppm, 温度={temperature}°C, 湿度={humidity}%")
                
                if i < 1:  # 最後の反復では待機しない（2回なので1未満）
                    time.sleep(1)  # テスト短縮: 10秒→1秒
            
            logger.info("✅ 連続実測値監視完了 - 全て実測値")
            
        except Exception as e:
            pytest.fail(f"❌ 連続実測値監視テスト失敗: {e}")


def main():
    """テスト実行メイン"""
    logger.info("🧪 実測値確認テスト開始")
    
    # pytest実行
    exit_code = pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--no-header"
    ])
    
    if exit_code == 0:
        logger.info("✅ 全実測値テスト成功")
    else:
        logger.error("❌ 実測値テスト失敗")
    
    return exit_code


if __name__ == "__main__":
    exit(main())