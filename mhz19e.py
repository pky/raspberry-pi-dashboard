#!/usr/bin/env python3
"""
MH-Z19E CO2センサー制御モジュール
UART通信によるCO2濃度データ取得と管理
"""

import serial
import time
import logging
import struct
from typing import Optional, Dict, Any
from datetime import datetime
import random

# ロガー設定
logger = logging.getLogger(__name__)

class MHZ19E:
    """MH-Z19E CO2センサー制御クラス"""
    
    # UARTコマンド定義
    COMMAND_READ_CO2 = bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])
    
    # CO2レベル閾値（ppm）
    LEVEL_NORMAL_MAX = 1000
    LEVEL_CAUTION_MAX = 1500
    LEVEL_WARNING_MAX = 3000
    
    # 測定範囲
    MIN_PPM = 400
    MAX_PPM = 5000
    
    def __init__(self, port: str = "/dev/ttyAMA0", baudrate: int = 9600, timeout: float = 1.0):
        """
        初期化
        
        Args:
            port: シリアルポート（RaspberryPi標準UART）
            baudrate: ボーレート（MH-Z19E標準: 9600）
            timeout: 通信タイムアウト（秒）
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.is_connected = False
        self.simulation_mode = False
        self.last_co2_value = 600  # シミュレーション用ベース値
        
        # センサー初期化試行
        self._initialize_sensor()
    
    def _initialize_sensor(self) -> None:
        """センサー初期化"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            self.is_connected = True
            logger.info(f"MH-Z19E センサー接続成功: {self.port}")
            
            # ウォームアップ時間（1分）待機はスキップ（既に起動済みの場合を考慮）
            # 初回データ取得でセンサー動作確認
            test_data = self._read_co2_raw()
            if test_data is None:
                raise Exception("センサー応答なし")
                
        except Exception as e:
            logger.warning(f"MH-Z19E センサー接続失敗: {e}")
            logger.info("シミュレーションモードで動作します")
            self.simulation_mode = True
            self.is_connected = False
            if self.serial:
                self.serial.close()
                self.serial = None
    
    def _calculate_checksum(self, data: bytes) -> int:
        """チェックサム計算"""
        if len(data) != 9:
            return -1
        
        # バイト1〜7の合計を計算
        checksum = sum(data[1:8])
        # 反転して下位8ビットを取得
        checksum = (~checksum) & 0xFF
        # 1を加算
        checksum = (checksum + 1) & 0xFF
        
        return checksum
    
    def _read_co2_raw(self) -> Optional[int]:
        """
        CO2濃度を読み取る（生データ）
        
        Returns:
            CO2濃度（ppm）、エラー時はNone
        """
        if not self.serial or not self.is_connected:
            return None
        
        try:
            # バッファクリア
            self.serial.reset_input_buffer()
            
            # コマンド送信
            self.serial.write(self.COMMAND_READ_CO2)
            
            # レスポンス受信（9バイト）
            response = self.serial.read(9)
            
            if len(response) != 9:
                logger.warning(f"不正なレスポンス長: {len(response)} bytes")
                return None
            
            # レスポンス検証
            if response[0] != 0xFF or response[1] != 0x86:
                logger.warning(f"不正なレスポンスヘッダ: {response.hex()}")
                return None
            
            # チェックサム検証
            calculated_checksum = self._calculate_checksum(response)
            if calculated_checksum != response[8]:
                logger.warning(f"チェックサムエラー: 計算値={calculated_checksum}, 受信値={response[8]}")
                return None
            
            # CO2濃度計算（HIGH_BYTE * 256 + LOW_BYTE）
            co2_ppm = (response[2] << 8) | response[3]
            
            # 異常値チェック
            if co2_ppm < self.MIN_PPM or co2_ppm > self.MAX_PPM:
                logger.warning(f"範囲外のCO2値: {co2_ppm} ppm")
                return None
            
            return co2_ppm
            
        except Exception as e:
            logger.error(f"CO2読み取りエラー: {e}")
            return None
    
    def read_co2(self, retry: int = 3) -> Optional[int]:
        """
        CO2濃度を読み取る（リトライ機能付き）
        
        Args:
            retry: リトライ回数
            
        Returns:
            CO2濃度（ppm）
        """
        if self.simulation_mode:
            return self._simulate_co2()
        
        for attempt in range(retry):
            co2_value = self._read_co2_raw()
            if co2_value is not None:
                return co2_value
            
            if attempt < retry - 1:
                logger.debug(f"CO2読み取りリトライ {attempt + 1}/{retry}")
                time.sleep(0.5)
        
        # リトライ失敗時はシミュレーションモードに切り替え
        logger.warning("CO2センサー読み取り失敗、シミュレーションモードに切り替え")
        self.simulation_mode = True
        return self._simulate_co2()
    
    def _simulate_co2(self) -> int:
        """
        CO2濃度をシミュレート
        
        Returns:
            シミュレートされたCO2濃度（ppm）
        """
        # 時間帯による変動パターン
        hour = datetime.now().hour
        
        # 基本値設定（時間帯による）
        if 6 <= hour < 9:  # 朝
            base = 500
        elif 9 <= hour < 12:  # 午前
            base = 700
        elif 12 <= hour < 14:  # 昼
            base = 900
        elif 14 <= hour < 18:  # 午後
            base = 1100
        elif 18 <= hour < 22:  # 夜
            base = 800
        else:  # 深夜
            base = 600
        
        # ランダム変動（前回値との連続性を考慮）
        variation = random.randint(-100, 200)
        new_value = int(self.last_co2_value * 0.7 + (base + variation) * 0.3)
        
        # 範囲制限
        new_value = max(self.MIN_PPM, min(2000, new_value))
        self.last_co2_value = new_value
        
        return new_value
    
    def get_co2_level(self, ppm: int) -> Dict[str, Any]:
        """
        CO2レベル判定
        
        Args:
            ppm: CO2濃度（ppm）
            
        Returns:
            レベル情報（level, color, message）
        """
        if ppm < self.LEVEL_NORMAL_MAX:
            return {
                "level": "正常",
                "color": "green",
                "message": "",
                "icon": "✓"
            }
        elif ppm < self.LEVEL_CAUTION_MAX:
            return {
                "level": "注意",
                "color": "yellow",
                "message": "換気を検討してください",
                "icon": "!"
            }
        elif ppm < self.LEVEL_WARNING_MAX:
            return {
                "level": "警告",
                "color": "orange",
                "message": "換気が必要です",
                "icon": "⚠"
            }
        else:
            return {
                "level": "危険",
                "color": "red",
                "message": "至急換気してください！",
                "icon": "⚠"
            }
    
    def get_co2_data(self) -> Dict[str, Any]:
        """
        CO2データを取得（統合形式）
        
        Returns:
            CO2データ辞書
        """
        co2_ppm = self.read_co2()
        
        if co2_ppm is None:
            # エラー時のデフォルト値
            return {
                "co2_ppm": 0,
                "co2_level": "エラー",
                "co2_color": "gray",
                "co2_message": "センサーエラー",
                "co2_icon": "?",
                "simulation": True,
                "timestamp": datetime.now().isoformat()
            }
        
        level_info = self.get_co2_level(co2_ppm)
        
        return {
            "co2_ppm": co2_ppm,
            "co2_level": level_info["level"],
            "co2_color": level_info["color"],
            "co2_message": level_info["message"],
            "co2_icon": level_info["icon"],
            "simulation": self.simulation_mode,
            "timestamp": datetime.now().isoformat()
        }
    
    def close(self):
        """リソースクリーンアップ"""
        if self.serial:
            self.serial.close()
            self.serial = None
            self.is_connected = False
            logger.info("MH-Z19E センサー接続を閉じました")


# テスト用コード
if __name__ == "__main__":
    # ロギング設定
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # センサーインスタンス作成
    sensor = MHZ19E()
    
    try:
        # 5回測定
        for i in range(5):
            data = sensor.get_co2_data()
            print(f"\n--- 測定 {i+1} ---")
            print(f"CO2濃度: {data['co2_ppm']} ppm")
            print(f"レベル: {data['co2_level']} ({data['co2_color']})")
            if data['co2_message']:
                print(f"メッセージ: {data['co2_message']}")
            print(f"シミュレーション: {data['simulation']}")
            time.sleep(2)
            
    finally:
        sensor.close()