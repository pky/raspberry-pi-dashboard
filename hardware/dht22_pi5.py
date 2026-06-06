#!/usr/bin/env python3
"""
Raspberry Pi 5用 DHT22センサーライブラリ
lgpioを使用してDHT22プロトコルを実装
"""

import time
import lgpio
from typing import Optional, Tuple

class DHT22_Pi5:
    """Raspberry Pi 5用 DHT22センサークラス"""
    
    def __init__(self, pin: int = 4):
        """
        DHT22センサーを初期化
        
        Args:
            pin: GPIO pin number (default: 4)
        """
        self.pin = pin
        self.handle = None
        
    def _open_gpio(self):
        """GPIOチップを開く"""
        if self.handle is None:
            self.handle = lgpio.gpiochip_open(0)
    
    def _close_gpio(self):
        """GPIOチップを閉じる"""
        if self.handle is not None:
            lgpio.gpiochip_close(self.handle)
            self.handle = None
    
    def _send_start_signal(self):
        """DHT22に開始信号を送信（改良版）"""
        # ピンを出力に設定してHIGHにする（安定化）
        lgpio.gpio_claim_output(self.handle, self.pin, 1)  # 初期値HIGH
        time.sleep(0.1)  # 100ms待機（安定化）
        
        # 開始信号：LOW
        lgpio.gpio_write(self.handle, self.pin, 0)  # LOW
        time.sleep(0.02)  # 20ms待機（少し長めに）
        
        # プルアップ信号：HIGH
        lgpio.gpio_write(self.handle, self.pin, 1)  # HIGH
        time.sleep(0.00004)  # 40μs待機（少し長めに）
        
        # ピンを入力に変更
        lgpio.gpio_free(self.handle, self.pin)
        lgpio.gpio_claim_input(self.handle, self.pin)
    
    def _read_response(self) -> Optional[list]:
        """DHT22からの応答を読み取り（改良版）"""
        data = []
        max_timeout = 50000  # タイムアウトを増加
        
        # DHT22の応答待ち（LOW → HIGH → LOW）
        # 応答信号の開始を待つ（LOW）
        timeout_count = 0
        while lgpio.gpio_read(self.handle, self.pin) == 1:
            timeout_count += 1
            if timeout_count > max_timeout:
                return None
        
        # 応答信号の継続を待つ（HIGH）
        timeout_count = 0
        while lgpio.gpio_read(self.handle, self.pin) == 0:
            timeout_count += 1
            if timeout_count > max_timeout:
                return None
        
        # 応答信号の終了を待つ（LOW）
        timeout_count = 0
        while lgpio.gpio_read(self.handle, self.pin) == 1:
            timeout_count += 1
            if timeout_count > max_timeout:
                return None
        
        # データビットを読み取り（40ビット）
        for i in range(40):
            # ビット開始の待機（HIGH）
            timeout_count = 0
            while lgpio.gpio_read(self.handle, self.pin) == 0:
                timeout_count += 1
                if timeout_count > max_timeout:
                    print(f"タイムアウト: ビット{i} 開始待ち")
                    return None
            
            # HIGHの継続時間をカウントで測定
            high_count = 0
            max_high_timeout = 5000 if i < 39 else 1000  # 最後のビットは短めのタイムアウト
            
            while lgpio.gpio_read(self.handle, self.pin) == 1:
                high_count += 1
                if high_count > max_high_timeout:
                    if i == 39:  # 最後のビット
                        # 最後のビットは終了しなくても良い
                        print(f"最後のビット{i}: HIGH継続（正常）")
                        break
                    else:
                        print(f"タイムアウト: ビット{i} HIGH継続")
                        return None
            
            # カウント値でビット値を判定
            # 閾値を動的に調整
            threshold = 80  # 基本閾値
            if high_count > threshold:
                data.append(1)
            else:
                data.append(0)
            
            # デバッグ情報（最初の数ビットのみ）
            if i < 5:
                print(f"ビット{i}: カウント={high_count}, 値={data[i]}")
        
        return data
    
    def _parse_data(self, data: list) -> Optional[Tuple[float, float]]:
        """データビットを温湿度に変換"""
        if len(data) != 40:
            return None
        
        # ビットを8ビットずつのバイトに変換
        bytes_data = []
        for i in range(0, 40, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) + data[i + j]
            bytes_data.append(byte)
        
        # チェックサム検証
        checksum = (bytes_data[0] + bytes_data[1] + bytes_data[2] + bytes_data[3]) & 0xFF
        if checksum != bytes_data[4]:
            return None
        
        # 湿度計算（上位8ビット + 下位8ビット）
        humidity = ((bytes_data[0] << 8) + bytes_data[1]) / 10.0
        
        # 温度計算（上位8ビット + 下位8ビット、符号考慮）
        temperature = ((bytes_data[2] & 0x7F) << 8) + bytes_data[3]
        temperature = temperature / 10.0
        if bytes_data[2] & 0x80:  # 負の温度
            temperature = -temperature
        
        return temperature, humidity
    
    def read(self) -> Optional[Tuple[float, float]]:
        """
        温湿度を読み取り
        
        Returns:
            Tuple[float, float]: (temperature, humidity) or None if failed
        """
        try:
            self._open_gpio()
            
            # 開始信号を送信
            self._send_start_signal()
            
            # 応答を読み取り
            data = self._read_response()
            if data is None:
                return None
            
            # データを解析
            result = self._parse_data(data)
            return result
            
        except Exception as e:
            print(f"DHT22読み取りエラー: {e}")
            return None
        finally:
            self._close_gpio()
    
    def read_retry(self, retries: int = 3, delay: float = 2.0) -> Optional[Tuple[float, float]]:
        """
        リトライ付きで温湿度を読み取り
        
        Args:
            retries: リトライ回数
            delay: リトライ間隔（秒）
            
        Returns:
            Tuple[float, float]: (temperature, humidity) or None if failed
        """
        for attempt in range(retries):
            result = self.read()
            if result is not None:
                return result
            
            if attempt < retries - 1:
                time.sleep(delay)
        
        return None

def test_dht22_pi5():
    """DHT22 Pi5ライブラリのテスト"""
    print("🍓 DHT22 Pi5ライブラリテスト")
    print("=" * 50)
    
    sensor = DHT22_Pi5(pin=4)
    
    print("温湿度読み取りテスト（10回試行）...")
    
    success_count = 0
    for i in range(10):
        print(f"\n試行 {i+1}/10:")
        result = sensor.read()
        
        if result is not None:
            temperature, humidity = result
            print(f"✅ 成功: 温度 {temperature:.1f}°C, 湿度 {humidity:.1f}%")
            success_count += 1
        else:
            print("❌ 失敗: データ読み取りエラー")
        
        time.sleep(2)  # DHT22は2秒間隔が必要
    
    print(f"\n結果: {success_count}/10 回成功")
    
    if success_count > 0:
        print("🎉 DHT22からのデータ読み取りに成功しました！")
    else:
        print("⚠️  DHT22からのデータ読み取りに失敗しました。")
        print("配線を確認してください：")
        print("- DHT22 VCC → Pi Pin 1 (3.3V)")
        print("- DHT22 Data → Pi Pin 7 (GPIO 4)")
        print("- DHT22 GND → Pi Pin 9 (GND)")

if __name__ == "__main__":
    test_dht22_pi5()