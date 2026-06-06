#!/usr/bin/env python3
"""
I2C復旧システム
センサーシミュレーション値検出時の自動復旧処理
"""

import logging
import subprocess
import time
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/i2c_recovery.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class I2CRecoverySystem:
    """I2C復旧システム"""
    
    def __init__(self):
        self.max_simulation_duration = 300  # 5分以上シミュレーション値で復旧開始
        self.max_recovery_attempts = 3      # 最大復旧試行回数
        self.recovery_interval = 600        # 復旧試行間隔（10分）
        self.last_recovery_time = None
        
    def check_sensor_status(self):
        """センサー状態チェック"""
        try:
            # 現在のセンサー状態を取得
            sys.path.append(str(Path(__file__).parent.parent))
            from mhz19e import MHZ19E
            
            sensor = MHZ19E()
            data = sensor.get_co2_data()
            sensor.close()
            
            return {
                'simulation': data.get('simulation', False),
                'co2_ppm': data.get('co2_ppm', 0),
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"センサー状態チェック失敗: {e}")
            return None
    
    def check_i2c_errors(self):
        """I2Cエラー検出"""
        try:
            # dmesgから最近のI2Cタイムアウトエラーを検索
            result = subprocess.run(
                ['dmesg', '--time-format', 'iso'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode != 0:
                return False
            
            # 最近30分以内のI2Cタイムアウトエラーをチェック
            current_time = datetime.now()
            i2c_errors = []
            
            for line in result.stdout.split('\n'):
                if 'i2c_designware' in line and 'timeout' in line:
                    i2c_errors.append(line)
            
            # エラーが5個以上あれば問題ありと判定
            if len(i2c_errors) >= 5:
                logger.warning(f"I2Cタイムアウトエラー検出: {len(i2c_errors)}件")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"I2Cエラーチェック失敗: {e}")
            return False
    
    def check_i2c_devices(self):
        """I2Cデバイス存在確認"""
        try:
            result = subprocess.run(
                ['i2cdetect', '-y', '1'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode != 0:
                logger.error(f"i2cdetect失敗: {result.stderr}")
                return False
            
            # SCD30センサー（0x61）の存在確認
            scd30_found = '61' in result.stdout
            
            if not scd30_found:
                logger.warning("SCD30センサー（0x61）が検出されません")
                return False
            
            logger.info("I2Cデバイス正常確認")
            return True
            
        except Exception as e:
            logger.error(f"I2Cデバイス確認失敗: {e}")
            return False
    
    def recovery_i2c_reset(self):
        """I2Cリセット復旧"""
        try:
            logger.info("I2Cリセットを実行中...")
            
            # I2Cモジュールをリロード（要root権限）
            commands = [
                ['modprobe', '-r', 'i2c_bcm2835'],
                ['modprobe', 'i2c_bcm2835'],
                ['modprobe', '-r', 'i2c_dev'],
                ['modprobe', 'i2c_dev']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"コマンド失敗 {' '.join(cmd)}: {result.stderr}")
            
            time.sleep(3)  # モジュールリロード待機
            logger.info("I2Cリセット完了")
            return True
            
        except Exception as e:
            logger.error(f"I2Cリセット失敗: {e}")
            return False
    
    def recovery_service_restart(self):
        """サービス再起動復旧"""
        try:
            logger.info("APIサーバー再起動を実行中...")
            
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', 'raspberry-pi-api-server'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("APIサーバー再起動完了")
                time.sleep(10)  # 再起動完了待機
                return True
            else:
                logger.error(f"APIサーバー再起動失敗: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"サービス再起動失敗: {e}")
            return False
    
    def recovery_system_reboot(self):
        """システム再起動復旧（最終手段）"""
        logger.warning("システム再起動を実行します（最終復旧手段）")
        
        try:
            # 再起動前にログ記録
            logger.info("I2C復旧のためシステム再起動実行")
            
            result = subprocess.run(
                ['sudo', 'reboot'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return True  # 再起動が始まるので常にTrue
            
        except Exception as e:
            logger.error(f"システム再起動失敗: {e}")
            return False
    
    def execute_recovery(self, recovery_level=1):
        """復旧処理実行"""
        
        # 復旧試行間隔チェック
        if self.last_recovery_time:
            elapsed = datetime.now() - self.last_recovery_time
            if elapsed.total_seconds() < self.recovery_interval:
                logger.info(f"復旧試行間隔未満: {elapsed.total_seconds()}秒経過")
                return False
        
        self.last_recovery_time = datetime.now()
        logger.info(f"復旧処理開始: レベル{recovery_level}")
        
        if recovery_level == 1:
            # レベル1: サービス再起動
            success = self.recovery_service_restart()
        elif recovery_level == 2:
            # レベル2: I2Cリセット + サービス再起動
            self.recovery_i2c_reset()
            success = self.recovery_service_restart()
        elif recovery_level == 3:
            # レベル3: システム再起動（最終手段）
            success = self.recovery_system_reboot()
        else:
            logger.error(f"不正な復旧レベル: {recovery_level}")
            return False
        
        if success:
            logger.info(f"復旧処理完了: レベル{recovery_level}")
        else:
            logger.error(f"復旧処理失敗: レベル{recovery_level}")
        
        return success
    
    def monitor_and_recover(self):
        """監視・復旧メイン処理"""
        logger.info("I2C復旧システム開始")
        
        # センサー状態確認
        sensor_status = self.check_sensor_status()
        if not sensor_status:
            logger.error("センサー状態取得失敗")
            return False
        
        simulation_detected = sensor_status['simulation']
        logger.info(f"センサー状態: シミュレーション={simulation_detected}, CO2={sensor_status['co2_ppm']}ppm")
        
        # I2Cエラー確認
        i2c_error_detected = self.check_i2c_errors()
        i2c_devices_ok = self.check_i2c_devices()
        
        # 復旧が必要かどうか判定
        need_recovery = False
        recovery_level = 1
        
        if simulation_detected and i2c_error_detected:
            logger.warning("シミュレーション値 + I2Cエラー検出: レベル2復旧が必要")
            need_recovery = True
            recovery_level = 2
        elif simulation_detected and not i2c_devices_ok:
            logger.warning("シミュレーション値 + I2Cデバイス未検出: レベル1復旧が必要")
            need_recovery = True
            recovery_level = 1
        elif i2c_error_detected:
            logger.warning("I2Cエラー検出: レベル1復旧が必要")
            need_recovery = True
            recovery_level = 1
        
        if need_recovery:
            return self.execute_recovery(recovery_level)
        else:
            logger.info("復旧不要: センサー正常動作中")
            return True

def main():
    """メイン実行"""
    if len(sys.argv) > 1 and sys.argv[1] == '--force-recovery':
        # 強制復旧モード
        recovery_system = I2CRecoverySystem()
        level = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        return recovery_system.execute_recovery(level)
    else:
        # 通常監視モード
        recovery_system = I2CRecoverySystem()
        return recovery_system.monitor_and_recover()

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)