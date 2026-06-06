"""
Sensor module for Raspberry Pi Dashboard
Handles SHT35 (temperature/humidity) and SCD30 (CO2) sensor data acquisition
Note: MH-Z19E support is also available but currently using SCD30
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import statistics

try:
    import lgpio
    import board
    import adafruit_sht31d  # SHT35 library (same as SHT31D)
    GPIO_AVAILABLE = True
    SHT35_AVAILABLE = True
except ImportError as e:
    try:
        # Try alternative GPIO library for Raspberry Pi 5
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        SHT35_AVAILABLE = False  # Use RPi.GPIO with manual implementation
        logging.warning(f"Using RPi.GPIO fallback for Pi 5: {e}")
    except ImportError:
        # For development/testing on non-Raspberry Pi systems
        GPIO_AVAILABLE = False
        SHT35_AVAILABLE = False
        logging.warning(f"SHT35 libraries not available: {e}. Running in simulation mode.")

from config import get_config
from mhz19e import MHZ19E  # MH-Z19E対応維持（現在はSCD30使用中）
# from co2_logger import CO2Logger  # SQLite不使用のため削除
# temperature_humidity_logger削除: 中間JSONファイル不要
from gpio_cleanup_manager import get_gpio_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SmartAveragingSensor:
    """
    Smart Averaging Sensor System - スマート平均方式センサーシステム
    
    SHT35センサーの異常値を統計的に除去し、高品質なセンサーデータを提供する。
    通常時は1回取得、異常検出時は3回取得して統計処理を行う。
    
    Features:
    - 動的取得方式: 正常時1回、異常検出時3回
    - 異常値検出: 温度3°C/5分、湿度15%/5分の急変検出
    - 統計処理: 外れ値除去平均、中央値、通常平均の自動選択
    - 品質スコア: データの信頼度を0.0-1.0で評価
    - キャッシュフォールバック: 全異常値時の安全機能
    
    Implements: Smart Averaging System v1.0
    """
    
    def __init__(self, i2c_address: int = 0x44):
        """
        Initialize Smart Averaging Sensor System
        
        Args:
            i2c_address: I2C address of SHT35 sensor (default: 0x44)
        """
        # Smart Averaging configuration
        self.smart_averaging_enabled = True
        self.outlier_detection_enabled = True
        self.temperature_threshold = 3.0  # 温度急変閾値 (°C)
        self.humidity_threshold = 15.0    # 湿度急変閾値 (%)
        self.cache_lifetime_minutes = 30   # キャッシュ有効期間 (分)
        
        # Initialize base sensor functionality
        self._init_base_sensor(i2c_address)
    
    def _init_base_sensor(self, i2c_address: int):
        """
        Initialize base SHT35 sensor functionality (from original SHT35Sensor)
        """
        self.config = get_config()
        self.i2c_address = i2c_address
        self.max_retries = self.config.SENSOR_MAX_RETRIES
        self.retry_delay = self.config.SENSOR_RETRY_DELAY
        
        # CO2センサーの初期化
        self.co2_sensor = MHZ19E()
        # self.co2_logger = CO2Logger()  # SQLite不使用のため削除
        
        # GPIO プロセス管理の初期化
        self.gpio_manager = get_gpio_manager()
        self.gpio_manager.start_monitoring()
        
        # 実測値キャッシュ（取得失敗時のフォールバック用）
        self._last_real_sht35_data = None
        self._last_real_co2_data = None
        self._sht35_cache_timestamp = None
        self._co2_cache_timestamp = None
        
        # SHT35センサーの初期化
        if SHT35_AVAILABLE:
            try:
                i2c = board.I2C()
                self.sensor = adafruit_sht31d.SHT31D(i2c)
                logger.info(f"SHT35 sensor initialized on I2C address 0x{self.i2c_address:02X}")
            except ValueError as e:
                logger.warning(f"SHT35 sensor initialization failed: {e}")
                self.sensor = None
        else:
            self.sensor = None
            logger.warning("SHT35 sensor running in simulation mode")
    
    def get_stabilized_sensor_data(self, mode="smart") -> Dict[str, Any]:
        """
        スマート平均方式センサーデータ取得
        
        Args:
            mode: "normal" | "smart" | "force_triple"
        
        Returns:
            Dict: センサーデータ + 品質情報
            {
                "temperature": float,
                "humidity": float,
                "sample_count": int,        # 取得回数
                "verification_level": str,  # "normal" | "verified" | "statistical"
                "processing_time": float,   # 処理時間（秒）
                "quality_score": float,     # 0.0-1.0品質スコア
                "outliers_detected": int,   # 検出した異常値数
                "method": str              # "single" | "average" | "median"
            }
        """
        start_time = time.time()
        
        try:
            if mode == "normal":
                # 通常モード: 1回取得のみ
                result = self._single_reading_mode()
            elif mode == "force_triple":
                # 強制トリプルモード: 必ず3回取得
                result = self._triple_reading_mode()
            else:
                # スマートモード: 自動判定
                result = self._smart_reading_mode()
            
            processing_time = time.time() - start_time
            result["processing_time"] = round(processing_time, 2)
            
            # 品質スコア計算
            result["quality_score"] = self._calculate_quality_score(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Smart averaging failed: {e}")
            # エラー時はキャッシュフォールバック
            return self._get_cache_fallback(start_time)
    
    def _single_reading_mode(self) -> Dict[str, Any]:
        """
        通常モード: 1回取得のみ
        """
        sensor_data = self.read_sensor()
        
        if sensor_data is None:
            return self._get_cache_fallback_data()
        
        # 異常値チェック
        if self._is_sht35_value_reasonable(sensor_data):
            # 正常値: キャッシュ更新
            self._update_cache(sensor_data)
            return {
                "temperature": sensor_data["temperature"],
                "humidity": sensor_data["humidity"],
                "sample_count": 1,
                "verification_level": "normal",
                "outliers_detected": 0,
                "method": "single"
            }
        else:
            # 異常値: キャッシュフォールバック
            logger.warning(f"Outlier detected in single mode: {sensor_data}")
            return self._get_cache_fallback_data()
    
    def _smart_reading_mode(self) -> Dict[str, Any]:
        """
        スマートモード: 1回取得後、異常検出時は3回取得
        """
        # まず1回取得
        first_reading = self.read_sensor()
        
        if first_reading is None:
            return self._get_cache_fallback_data()
        
        # 異常値チェック
        if self._is_sht35_value_reasonable(first_reading):
            # 正常値: 1回取得で完了
            self._update_cache(first_reading)
            return {
                "temperature": first_reading["temperature"],
                "humidity": first_reading["humidity"],
                "sample_count": 1,
                "verification_level": "normal",
                "outliers_detected": 0,
                "method": "single"
            }
        else:
            # 異常値検出: 3回取得モードに移行
            logger.info("Outlier detected, switching to triple reading mode")
            return self._triple_reading_mode()
    
    def _triple_reading_mode(self) -> Dict[str, Any]:
        """
        トリプルモード: 3回取得して統計処理
        """
        readings = []
        
        # 3回取得 (10秒間隔)
        for i in range(3):
            if i > 0:
                time.sleep(10)  # 10秒待機
            
            reading = self.read_sensor()
            if reading is not None:
                readings.append(reading)
                logger.debug(f"Triple reading {i+1}/3: T={reading['temperature']}°C, H={reading['humidity']}%")
        
        if not readings:
            # 全て失敗: キャッシュフォールバック
            logger.error("All triple readings failed")
            return self._get_cache_fallback_data()
        
        # 異常値検出
        outlier_result = self.detect_outliers(readings)
        
        # 統計処理
        statistical_result = self.statistical_processing(readings, outlier_result)
        
        return {
            "temperature": statistical_result["result"]["temperature"],
            "humidity": statistical_result["result"]["humidity"],
            "sample_count": len(readings),
            "verification_level": "statistical" if len(readings) >= 3 else "verified",
            "outliers_detected": len(outlier_result["outliers"]),
            "method": statistical_result["method"]
        }
    
    
    def detect_outliers(self, values: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        多次元異常値検出
        
        Args:
            values: センサー値のリスト
        
        Returns:
            Dict: 異常値情報
            {
                "outliers": [index_list],
                "reasons": ["temp_spike", "humidity_spike", "out_of_range"],
                "severity": "low" | "medium" | "high"
            }
        """
        if len(values) < 2:
            return {"outliers": [], "reasons": [], "severity": "low"}
        
        outliers = []
        reasons = []
        
        # 統計的外れ値検出 (IQR方式)
        if len(values) >= 3:
            temp_values = [v['temperature'] for v in values]
            humidity_values = [v['humidity'] for v in values]
            
            temp_outliers = self._detect_iqr_outliers(temp_values)
            humidity_outliers = self._detect_iqr_outliers(humidity_values)
            
            for idx in temp_outliers:
                if idx not in outliers:
                    outliers.append(idx)
                    reasons.append("temp_statistical")
            
            for idx in humidity_outliers:
                if idx not in outliers:
                    outliers.append(idx)
                    reasons.append("humidity_statistical")
        
        # 急変検出
        for i, value in enumerate(values):
            # 絶対範囲チェック
            if not self._is_in_absolute_range(value):
                if i not in outliers:
                    outliers.append(i)
                    reasons.append("out_of_range")
            
            # キャッシュとの急変チェック
            if not self._is_sht35_value_reasonable(value):
                if i not in outliers:
                    outliers.append(i)
                    if abs(value['temperature'] - (self._last_real_sht35_data or {}).get('temperature', value['temperature'])) > self.temperature_threshold:
                        reasons.append("temp_spike")
                    if abs(value['humidity'] - (self._last_real_sht35_data or {}).get('humidity', value['humidity'])) > self.humidity_threshold:
                        reasons.append("humidity_spike")
        
        # 深刻度評価
        severity = "low"
        if len(outliers) >= len(values) * 0.5:
            severity = "high"
        elif len(outliers) > 0:
            severity = "medium"
        
        return {
            "outliers": sorted(outliers),
            "reasons": reasons,
            "severity": severity
        }
    
    def statistical_processing(self, values: List[Dict[str, float]], outliers: Dict[str, Any]) -> Dict[str, Any]:
        """
        統計的データ処理
        
        Args:
            values: センサー値のリスト
            outliers: 異常値情報
        
        Returns:
            Dict: 統計処理結果
            {
                "result": {"temperature": float, "humidity": float},
                "method": "average" | "trimmed_average" | "median" | "cached",
                "confidence": float,  # 0.0-1.0信頼度
                "used_samples": int
            }
        """
        if not values:
            return self._get_statistical_cache_fallback()
        
        outlier_indices = set(outliers["outliers"])
        outlier_count = len(outlier_indices)
        
        # 有効な値を抽出
        valid_values = [v for i, v in enumerate(values) if i not in outlier_indices]
        
        if outlier_count == 0:
            # 外れ値なし: 通常平均
            method = "average"
            confidence = 1.0
        elif outlier_count == 1 and len(valid_values) >= 2:
            # 外れ値1個: 外れ値除去平均
            method = "trimmed_average"
            confidence = 0.9
        elif len(valid_values) >= 1:
            # 外れ値多数: 中央値
            method = "median"
            confidence = 0.7
        else:
            # 全て外れ値: キャッシュフォールバック
            logger.warning("All values are outliers, using cache fallback")
            return self._get_statistical_cache_fallback()
        
        # 統計値計算
        if method == "median" and len(values) >= 3:
            # 中央値: 全データ使用
            temp_median = statistics.median([v['temperature'] for v in values])
            humidity_median = statistics.median([v['humidity'] for v in values])
            result_temp, result_humidity = temp_median, humidity_median
        else:
            # 平均値: 有効データ使用
            if valid_values:
                result_temp = statistics.mean([v['temperature'] for v in valid_values])
                result_humidity = statistics.mean([v['humidity'] for v in valid_values])
            else:
                # フォールバック
                return self._get_statistical_cache_fallback()
        
        result_data = {
            'temperature': round(result_temp, 1),
            'humidity': round(result_humidity, 1)
        }
        
        # 結果をキャッシュに保存
        self._update_cache(result_data)
        
        return {
            "result": result_data,
            "method": method,
            "confidence": confidence,
            "used_samples": len(valid_values) if method != "median" else len(values)
        }
    
    def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """
        データ品質スコア算出(0.0-1.0)
        
        算出要素:
        - sample_count: 取得回数（多いほど高品質）
        - outliers_detected: 異常値数（少ないほど高品質）
        - method: 処理方式
        - verification_level: 検証レベル
        """
        base_score = 0.5
        
        # sample_countによる加点
        sample_count = data.get("sample_count", 1)
        if sample_count >= 3:
            base_score += 0.3  # 統計的検証
        elif sample_count >= 2:
            base_score += 0.2  # 複数回検証
        else:
            base_score += 0.1  # 単一取得
        
        # 異常値による減点
        outliers_detected = data.get("outliers_detected", 0)
        if outliers_detected == 0:
            base_score += 0.2  # 異常値なし
        else:
            base_score -= min(outliers_detected * 0.1, 0.3)  # 異常値数による減点
        
        # 処理方式による調整
        method = data.get("method", "single")
        if method == "single":
            pass  # 基本スコア
        elif method == "average":
            base_score += 0.1
        elif method == "trimmed_average":
            base_score += 0.05
        elif method == "median":
            base_score -= 0.05  # 中央値は外れ値多数時の対処
        elif method == "cached":
            base_score -= 0.2  # キャッシュは品質低下
        
        return max(0.0, min(1.0, base_score))
    
    def _detect_iqr_outliers(self, values: List[float]) -> List[int]:
        """
        IQR方式による異常値検出
        """
        if len(values) < 3:
            return []
        
        q1 = statistics.quantiles(values, n=4)[0]  # 25%位
        q3 = statistics.quantiles(values, n=4)[2]  # 75%位
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = []
        for i, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                outliers.append(i)
        
        return outliers
    
    def _is_in_absolute_range(self, sensor_reading: Dict[str, float]) -> bool:
        """
        絶対範囲チェック
        """
        temp = sensor_reading.get('temperature')
        humidity = sensor_reading.get('humidity')
        
        if temp is None or humidity is None:
            return False
        
        # 物理的に不可能な範囲
        return -10 <= temp <= 60 and 0 <= humidity <= 100
    
    def _update_cache(self, sensor_data: Dict[str, float]):
        """
        キャッシュ更新
        """
        self._last_real_sht35_data = sensor_data.copy()
        self._sht35_cache_timestamp = datetime.now()
        logger.debug(f"Cache updated: T={sensor_data['temperature']}°C, H={sensor_data['humidity']}%")
    
    def _get_cache_fallback(self, start_time: float) -> Dict[str, Any]:
        """
        エラー時のキャッシュフォールバック
        """
        processing_time = time.time() - start_time
        
        if self._last_real_sht35_data is not None:
            cache_age = (datetime.now() - self._sht35_cache_timestamp).total_seconds() / 60
            if cache_age <= self.cache_lifetime_minutes:
                logger.info(f"Using cache fallback: age {cache_age:.1f} minutes")
                return {
                    "temperature": self._last_real_sht35_data["temperature"],
                    "humidity": self._last_real_sht35_data["humidity"],
                    "sample_count": 0,
                    "verification_level": "cached",
                    "processing_time": round(processing_time, 2),
                    "quality_score": 0.3,
                    "outliers_detected": 0,
                    "method": "cached"
                }
        
        # 最終フォールバック: シミュレーション値
        sim_data = self._get_simulated_data()
        return {
            "temperature": sim_data["temperature"],
            "humidity": sim_data["humidity"],
            "sample_count": 0,
            "verification_level": "simulation",
            "processing_time": round(processing_time, 2),
            "quality_score": 0.1,
            "outliers_detected": 0,
            "method": "simulated"
        }
    
    def _get_cache_fallback_data(self) -> Dict[str, Any]:
        """
        キャッシュフォールバックデータ取得
        """
        if self._last_real_sht35_data is not None:
            cache_age = (datetime.now() - self._sht35_cache_timestamp).total_seconds() / 60
            if cache_age <= self.cache_lifetime_minutes:
                return {
                    "temperature": self._last_real_sht35_data["temperature"],
                    "humidity": self._last_real_sht35_data["humidity"],
                    "sample_count": 0,
                    "verification_level": "cached",
                    "outliers_detected": 0,
                    "method": "cached"
                }
        
        # シミュレーションフォールバック
        sim_data = self._get_simulated_data()
        return {
            "temperature": sim_data["temperature"],
            "humidity": sim_data["humidity"],
            "sample_count": 0,
            "verification_level": "simulation",
            "outliers_detected": 0,
            "method": "simulated"
        }
    
    def _get_statistical_cache_fallback(self) -> Dict[str, Any]:
        """
        統計処理用キャッシュフォールバック
        """
        if self._last_real_sht35_data is not None:
            cache_age = (datetime.now() - self._sht35_cache_timestamp).total_seconds() / 60
            if cache_age <= self.cache_lifetime_minutes:
                return {
                    "result": {
                        "temperature": self._last_real_sht35_data["temperature"],
                        "humidity": self._last_real_sht35_data["humidity"]
                    },
                    "method": "cached",
                    "confidence": 0.3,
                    "used_samples": 0
                }
        
        # シミュレーションフォールバック
        sim_data = self._get_simulated_data()
        return {
            "result": {
                "temperature": sim_data["temperature"],
                "humidity": sim_data["humidity"]
            },
            "method": "simulated",
            "confidence": 0.1,
            "used_samples": 0
        }
    
    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Read temperature and humidity from SHT35 sensor with retry logic
        
        Returns:
            Dict with temperature and humidity, or None if failed
            
        Requirements: 2.1, 2.2 - Temperature and humidity data acquisition
        """
        if not SHT35_AVAILABLE or self.sensor is None:
            logger.info("Using simulation mode for SHT35 sensor")
            return self._get_simulated_data()
        
        # 実際のセンサーからデータを読み取り
        for attempt in range(self.max_retries):
            try:
                # GPIO プロセス統計を事前チェック
                stats = self.gpio_manager.get_process_statistics()
                if stats['gpio_zombies'] > 10:
                    logger.warning(f"High zombie process count detected: {stats['gpio_zombies']}")
                    self.gpio_manager.cleanup_zombie_processes()
                
                temperature = self.sensor.temperature
                humidity = self.sensor.relative_humidity
                
                if temperature is not None and humidity is not None:
                    # データの妥当性チェック
                    if self._validate_readings(temperature, humidity):
                        logger.debug(f"SHT35 read success (attempt {attempt + 1}): T={temperature:.1f}°C, H={humidity:.1f}%")
                        
                        # 読み取り後即座にプロセスクリーンアップ実行
                        try:
                            cleaned = self.gpio_manager.cleanup_zombie_processes()
                            if cleaned > 0:
                                logger.debug(f"Cleaned {cleaned} GPIO zombie processes after SHT35 read")
                        except Exception as e:
                            logger.debug(f"GPIO cleanup warning: {e}")
                        
                        return {
                            'temperature': round(temperature, 1),
                            'humidity': round(humidity, 1)
                        }
                    else:
                        logger.warning(f"Invalid readings: T={temperature}°C, H={humidity}%")
                else:
                    logger.warning(f"Failed to get readings (attempt {attempt + 1})")
                    
            except RuntimeError as e:
                logger.warning(f"SHT35 read error (attempt {attempt + 1}): {e}")
                # SHT35センサーリセット試行
                try:
                    self.sensor.reset()
                    logger.info("SHT35 sensor reset completed")
                except Exception as reset_error:
                    logger.warning(f"SHT35 sensor reset failed: {reset_error}")
            except Exception as e:
                logger.error(f"Unexpected SHT35 error (attempt {attempt + 1}): {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        logger.error(f"Failed to read SHT35 sensor after {self.max_retries} attempts")
        return None
    
    def _validate_readings(self, temperature: float, humidity: float) -> bool:
        """
        Validate sensor readings
        
        Args:
            temperature: Temperature reading in Celsius
            humidity: Humidity reading in percentage
            
        Returns:
            bool: True if readings are valid
        """
        # SHT35 specifications (より高精度)
        temp_valid = -40 <= temperature <= 125
        humidity_valid = 0 <= humidity <= 100
        
        return temp_valid and humidity_valid
    
    
    def _get_simulated_data(self) -> Dict[str, float]:
        """
        Generate simulated sensor data for testing
        
        Returns:
            Dict: Simulated temperature and humidity data
        """
        import random
        import math
        
        # 時間ベースの変動を追加（より現実的）
        current_time = time.time()
        hour_of_day = (current_time / 3600) % 24
        
        # 日中は温度が高く、夜間は低く
        base_temp = 22.0 + 3.0 * math.sin((hour_of_day - 6) * math.pi / 12)
        temp_variation = random.uniform(-2, 2)
        temperature = base_temp + temp_variation
        
        # 湿度は温度と逆相関
        base_humidity = 60.0 - (temperature - 22.0) * 1.5
        humidity_variation = random.uniform(-10, 10)
        humidity = base_humidity + humidity_variation
        
        # 範囲制限
        temperature = max(15.0, min(35.0, temperature))
        humidity = max(30.0, min(80.0, humidity))
        
        return {
            'temperature': round(temperature, 1),
            'humidity': round(humidity, 1)
        }
    
    def _get_real_sensor_data_with_retry(self, retry_on_simulation: bool, max_retries: int) -> Optional[Dict[str, float]]:
        """
        シミュレーション値検出時のリトライ付きSHT35センサーデータ取得
        
        Args:
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか
            max_retries (int): 最大リトライ回数
            
        Returns:
            Dict: センサーデータ、または None（取得失敗時）
        """
        for attempt in range(max_retries + 1):
            sensor_reading = self.read_sensor()
            
            # シミュレーションモード検出（SHT35_AVAILABLEがFalseまたはsensorがNone）
            is_simulation = not SHT35_AVAILABLE or self.sensor is None
            
            if not retry_on_simulation or not is_simulation:
                # リトライ無効 または 実測値取得成功
                return sensor_reading
            
            if attempt < max_retries:
                wait_time = 2.0 * (2 ** attempt)  # 指数的バックオフ: 2s, 4s, 8s...
                logger.warning(f"SHT35シミュレーション検出 - リトライ {attempt + 1}/{max_retries} (待機: {wait_time}s)")
                time.sleep(wait_time)
            else:
                logger.info(f"SHT35: シミュレーション値で継続 - ハードウェア問題の可能性")
        
        return sensor_reading
    
    def _get_real_co2_data_with_retry(self, retry_on_simulation: bool, max_retries: int) -> Dict[str, Any]:
        """
        シミュレーション値検出時のリトライ付きCO2センサーデータ取得
        
        Args:
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか
            max_retries (int): 最大リトライ回数
            
        Returns:
            Dict: CO2センサーデータ
        """
        for attempt in range(max_retries + 1):
            co2_data = self.co2_sensor.get_co2_data()
            
            # シミュレーション検出
            is_simulation = co2_data.get('simulation', False)
            
            if not retry_on_simulation or not is_simulation:
                # リトライ無効 または 実測値取得成功
                return co2_data
            
            if attempt < max_retries:
                wait_time = 2.0 * (2 ** attempt)  # 指数的バックオフ: 2s, 4s, 8s...
                logger.warning(f"CO2シミュレーション検出 - リトライ {attempt + 1}/{max_retries}: {co2_data['co2_ppm']}ppm (待機: {wait_time}s)")
                time.sleep(wait_time)
            else:
                logger.info(f"CO2: シミュレーション値で継続 - ハードウェア問題の可能性")
        
        return co2_data
    
    def _get_sensor_data_with_cache(self, retry_on_simulation: bool, max_retries: int) -> Optional[Dict[str, float]]:
        """
        キャッシュフォールバック付きSHT35センサーデータ取得
        
        Args:
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか
            max_retries (int): 最大リトライ回数
            
        Returns:
            Dict: センサーデータ（実測値優先、失敗時はキャッシュ、最終的にNone）
        """
        # まず実測値取得を試行
        if retry_on_simulation:
            sensor_reading = self._get_real_sensor_data_with_retry(retry_on_simulation, max_retries)
        else:
            sensor_reading = self.read_sensor()
        
        # 実測値が取得できた場合（シミュレーションでない場合）
        is_simulation = not SHT35_AVAILABLE or self.sensor is None
        if sensor_reading is not None and not is_simulation:
            # 異常値検出（急激な変化チェック）
            if self._is_sht35_value_reasonable(sensor_reading):
                # 正常値をキャッシュに保存
                self._last_real_sht35_data = sensor_reading.copy()
                self._sht35_cache_timestamp = datetime.now()
                logger.debug(f"SHT35実測値キャッシュ更新: {sensor_reading['temperature']}°C, {sensor_reading['humidity']}%")
                return sensor_reading
            else:
                # 異常値検出時はキャッシュ使用を試行
                logger.warning(f"SHT35異常値検出: {sensor_reading['temperature']}°C, {sensor_reading['humidity']}% - キャッシュ確認中")
                # わざと下のキャッシュチェックに進む
        
        # 実測値が取得できない場合、キャッシュをチェック
        if self._last_real_sht35_data is not None:
            cache_age = (datetime.now() - self._sht35_cache_timestamp).total_seconds() / 60  # 分
            if cache_age <= 30:  # 30分以内のキャッシュなら使用
                logger.info(f"SHT35キャッシュ使用: {self._last_real_sht35_data['temperature']}°C, {self._last_real_sht35_data['humidity']}% (キャッシュ経過: {cache_age:.1f}分)")
                return self._last_real_sht35_data.copy()
            else:
                logger.warning(f"SHT35キャッシュ期限切れ: {cache_age:.1f}分経過")
        
        # キャッシュも使用できない場合は現在の結果を返す
        return sensor_reading
    
    def _get_co2_data_with_cache(self, retry_on_simulation: bool, max_retries: int) -> Dict[str, Any]:
        """
        キャッシュフォールバック付きCO2センサーデータ取得
        
        Args:
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか
            max_retries (int): 最大リトライ回数
            
        Returns:
            Dict: CO2センサーデータ（実測値優先、失敗時はキャッシュ、最終的にシミュレーション値）
        """
        # まず実測値取得を試行
        if retry_on_simulation:
            co2_data = self._get_real_co2_data_with_retry(retry_on_simulation, max_retries)
        else:
            co2_data = self.co2_sensor.get_co2_data()
        
        # 実測値が取得できた場合（シミュレーションでない場合）
        is_simulation = co2_data.get('simulation', False)
        if not is_simulation:
            # 実測値をキャッシュに保存
            self._last_real_co2_data = co2_data.copy()
            self._co2_cache_timestamp = datetime.now()
            logger.debug(f"CO2実測値キャッシュ更新: {co2_data['co2_ppm']}ppm")
            return co2_data
        
        # 実測値が取得できない場合、キャッシュをチェック
        if self._last_real_co2_data is not None:
            cache_age = (datetime.now() - self._co2_cache_timestamp).total_seconds() / 60  # 分
            if cache_age <= 30:  # 30分以内のキャッシュなら使用
                cached_data = self._last_real_co2_data.copy()
                logger.info(f"CO2キャッシュ使用: {cached_data['co2_ppm']}ppm (キャッシュ経過: {cache_age:.1f}分)")
                # キャッシュであることを示すフラグを追加
                cached_data['from_cache'] = True
                return cached_data
            else:
                logger.warning(f"CO2キャッシュ期限切れ: {cache_age:.1f}分経過")
        
        # キャッシュも使用できない場合は現在の結果（シミュレーション値）を返す
        return co2_data
    
    def _is_sht35_value_reasonable(self, sensor_reading: Dict[str, float]) -> bool:
        """
        SHT35センサー値の妥当性チェック（異常値検出）
        
        Args:
            sensor_reading: センサー読み取り値
            
        Returns:
            bool: 値が妥当かどうか
        """
        temp = sensor_reading.get('temperature')
        humidity = sensor_reading.get('humidity')
        
        # 基本的な範囲チェック
        if temp is None or humidity is None:
            return False
        
        if temp < -10 or temp > 60:  # 室内温度の現実的範囲
            return False
            
        if humidity < 0 or humidity > 100:  # 湿度の物理的範囲
            return False
        
        # キャッシュとの急激な変化チェック（前回の実測値と比較）
        if self._last_real_sht35_data is not None:
            cache_age = (datetime.now() - self._sht35_cache_timestamp).total_seconds() / 60
            
            # 30分以内のキャッシュがある場合、急激変化をチェック
            if cache_age <= 30:
                prev_temp = self._last_real_sht35_data['temperature']
                prev_humidity = self._last_real_sht35_data['humidity']
                
                temp_diff = abs(temp - prev_temp)
                humidity_diff = abs(humidity - prev_humidity)
                
                # 5分間で温度3度以上、湿度15%以上の変化は異常とみなす
                if temp_diff > 3.0:
                    logger.warning(f"SHT35温度急変検出: {prev_temp}°C → {temp}°C (差: {temp_diff}°C)")
                    return False
                    
                if humidity_diff > 15.0:
                    logger.warning(f"SHT35湿度急変検出: {prev_humidity}% → {humidity}% (差: {humidity_diff}%)")
                    return False
        
        return True
    
    def calculate_discomfort_index(self, temperature: float, humidity: float) -> float:
        """
        Calculate discomfort index from temperature and humidity
        
        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity in percentage
            
        Returns:
            float: Discomfort index
            
        Requirements: 2.3 - Discomfort index calculation
        """
        # 正しい不快度指数の計算式
        # DI = 0.81 * T + 0.01 * H * (0.99 * T - 14.3) + 46.3
        # Where T is temperature in Celsius and H is relative humidity in percentage
        
        di = 0.81 * temperature + 0.01 * humidity * (0.99 * temperature - 14.3) + 46.3
        return round(di, 1)
    
    def get_comfort_level(self, discomfort_index: float) -> str:
        """
        Get comfort level description from discomfort index
        
        Args:
            discomfort_index: Calculated discomfort index
            
        Returns:
            str: Comfort level description
        """
        if discomfort_index < 60:
            return "寒い"
        elif discomfort_index < 65:
            return "肌寒い"
        elif discomfort_index < 70:
            return "快適"
        elif discomfort_index < 75:
            return "やや不快"
        elif discomfort_index < 80:
            return "不快"
        else:
            return "極めて不快"
    
        """
        Get complete sensor data including temperature, humidity, discomfort index, and CO2
        
        Args:
            enable_logging (bool): SQLite/JSONログに記録するか（デフォルト: True）
                                  Falseの場合はAPIアクセス用で記録しない
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか（デフォルト: True）
            max_retries (int): シミュレーション検出時の最大リトライ回数（デフォルト: 2）
        
        Returns:
            Dict: Complete sensor data
            
        Requirements: 2.1, 2.2, 2.3, 7.1 - Complete sensor data acquisition
        """
        # SHT35センサーデータ取得（キャッシュフォールバック付き）
        sensor_reading = self._get_sensor_data_with_cache(retry_on_simulation, max_retries)
        
        if sensor_reading is None:
            # SHT35エラー時のデフォルト値
            temperature = None
            humidity = None
            discomfort_index = None
            comfort_level = None
            sht35_error = 'Failed to read SHT35 sensor data'
        else:
            temperature = sensor_reading['temperature']
            humidity = sensor_reading['humidity']
            discomfort_index = self.calculate_discomfort_index(temperature, humidity)
            comfort_level = self.get_comfort_level(discomfort_index)
            sht35_error = None
        
        # CO2センサーデータ取得（キャッシュフォールバック付き・SHT35とは独立）
        co2_data = self._get_co2_data_with_cache(retry_on_simulation, max_retries)
        
        # ログ記録（enable_logging=Trueの場合のみ）
        if enable_logging:
            # CO2データのSQLiteログ記録を削除（JSONログ使用に統一）
            # 削除: self.co2_logger.log_co2_data() - SQLite不使用
            logger.debug("CO2データ記録: metrics.json統合システムにより不要")
            
            # 温度・湿度データをログに記録
            # 温度・湿度ログ記録削除: monitoring_collector.pyが直接取得
            logger.debug(f"温度・湿度データ生成完了: T={temperature}°C, H={humidity}%")
        else:
            logger.debug(f"API専用モード: ログ記録スキップ (T={temperature}°C, H={humidity}%, CO2={co2_data['co2_ppm']}ppm)")
        
        # SHT35シミュレーション状態を判定
        sht35_simulation = not SHT35_AVAILABLE or self.sensor is None or temperature is None or humidity is None

        # 統合データ返却
        return {
            'status': 'success' if sht35_error is None else 'partial',
            'timestamp': datetime.now().isoformat(),
            'temperature': temperature,
            'humidity': humidity,
            'discomfort_index': discomfort_index,
            'comfort_level': comfort_level,
            'co2_ppm': co2_data['co2_ppm'],
            'co2_level': co2_data['co2_level'],
            'co2_color': co2_data['co2_color'],
            'co2_message': co2_data['co2_message'],
            'co2_icon': co2_data['co2_icon'],
            'co2_simulation': co2_data['simulation'],
            'co2_from_cache': co2_data.get('from_cache', False),  # キャッシュ使用フラグ
            'sht35_simulation': sht35_simulation,
            'sensor_types': ['SHT35', 'MH-Z19E'],
            'location': '室内',
            'error': sht35_error
        }
    
    def get_co2_history(self, hours: int = 24) -> list:
        """履歴データは metrics.json から取得してください"""
        logger.info("履歴データは static/data/metrics.json から取得してください")
        return []
    
    def get_temp_humidity_history(self, hours: int = 24) -> list:
        """直近の温度・湿度履歴データを取得（削除: 中間ファイル不要）"""
        logger.warning("get_temp_humidity_history削除: metrics.jsonから取得してください")
        return []
    
    def get_co2_alerts(self, days: int = 7) -> list:
        """アラート機能は metrics.json ベースシステムで実装してください"""
        logger.info("アラート機能は metrics.json ベースシステムで実装してください")
        return []
    
    def get_co2_daily_summary(self, date: str = None) -> dict:
        """サマリー機能は metrics.json ベースシステムで実装してください"""
        logger.info("サマリー機能は metrics.json ベースシステムで実装してください")
        return {}
    
    def export_co2_data(self, start_date: str, end_date: str) -> str:
        """エクスポート機能は metrics.json ベースシステムで実装してください"""
        logger.info("エクスポート機能は metrics.json ベースシステムで実装してください")
        return None
    
    def test_connection(self) -> bool:
        """
        Test sensor connection
        
        Returns:
            bool: True if sensor is accessible
        """
        if not SHT35_AVAILABLE:
            logger.info("Sensor test: Running in simulation mode")
            return True
        
        try:
            sensor_data = self.read_sensor()
            if sensor_data is not None:
                logger.info(f"Sensor connection test: SUCCESS (T={sensor_data['temperature']}°C, H={sensor_data['humidity']}%)")
                return True
            else:
                logger.warning("Sensor connection test: FAILED")
                return False
        except Exception as e:
            logger.error(f"Sensor connection test error: {e}")
            return False
    
    def cleanup(self):
        """Clean up GPIO and UART resources"""
        # GPIO プロセス管理の停止と緊急クリーンアップ
        if hasattr(self, 'gpio_manager') and self.gpio_manager:
            try:
                self.gpio_manager.stop_monitoring()
                emergency_result = self.gpio_manager.emergency_cleanup()
                logger.info(f"GPIO emergency cleanup completed: {emergency_result}")
            except Exception as e:
                logger.warning(f"GPIO manager cleanup error: {e}")
        
        # SHT35センサーのクリーンアップ
        if SHT35_AVAILABLE and self.sensor:
            try:
                # SHT35は明示的なexitメソッドがないためシンプルにNoneに設定
                self.sensor = None
                logger.info("SHT35 sensor cleanup completed")
            except Exception as e:
                logger.warning(f"SHT35 sensor cleanup error: {e}")
        else:
            logger.info("SHT35 sensor cleanup completed (simulation mode)")
        
        # CO2センサーのクリーンアップ
        if self.co2_sensor:
            try:
                self.co2_sensor.close()
                logger.info("MH-Z19E sensor cleanup completed")
            except Exception as e:
                logger.warning(f"CO2 sensor cleanup error: {e}")

# Global sensor instance
_sensor_instance = None

# Legacy SHT35Sensor class for backward compatibility
class SHT35Sensor(SmartAveragingSensor):
    """
    Legacy SHT35Sensor class - now inherits from SmartAveragingSensor
    Maintains backward compatibility while providing Smart Averaging features
    """
    
    def __init__(self, i2c_address: int = 0x44):
        """
        Initialize legacy SHT35 sensor with Smart Averaging capabilities
        
        Args:
            i2c_address: I2C address of SHT35 sensor (default: 0x44)
        """
        super().__init__(i2c_address)
        # Legacy mode: disable smart averaging by default
        self.smart_averaging_enabled = False
        logger.info("SHT35Sensor initialized with Smart Averaging capability (disabled by default)")
    
    def get_sensor_data(self, enable_logging: bool = True, retry_on_simulation: bool = True, max_retries: int = 2, smart_averaging: bool = False, verification_mode: str = "auto") -> Dict[str, Any]:
        """
        Get complete sensor data with optional Smart Averaging
        
        Args:
            enable_logging (bool): SQLite/JSONログに記録するか（デフォルト: True）
            retry_on_simulation (bool): シミュレーション値検出時にリトライするか
            max_retries (int): シミュレーション検出時の最大リトライ回数
            smart_averaging (bool): スマート平均有効
            verification_mode (str): "auto" | "force" | "off"
        
        Returns:
            Dict: Complete sensor data
        """
        # Smart Averagingが有効な場合
        if smart_averaging or self.smart_averaging_enabled:
            # スマート平均方式でデータ取得
            if verification_mode == "force":
                smart_data = self.get_stabilized_sensor_data(mode="force_triple")
            elif verification_mode == "off":
                smart_data = self.get_stabilized_sensor_data(mode="normal")
            else:
                smart_data = self.get_stabilized_sensor_data(mode="smart")
            
            # 温度・湿度データを取得
            temperature = smart_data["temperature"]
            humidity = smart_data["humidity"]
            
            if temperature is not None and humidity is not None:
                discomfort_index = self.calculate_discomfort_index(temperature, humidity)
                comfort_level = self.get_comfort_level(discomfort_index)
                sht35_error = None
            else:
                discomfort_index = None
                comfort_level = None
                sht35_error = 'Smart averaging failed'
        else:
            # 既存のキャッシュフォールバック方式
            sensor_reading = self._get_sensor_data_with_cache(retry_on_simulation, max_retries)
            
            if sensor_reading is None:
                temperature = None
                humidity = None
                discomfort_index = None
                comfort_level = None
                sht35_error = 'Failed to read SHT35 sensor data'
            else:
                temperature = sensor_reading['temperature']
                humidity = sensor_reading['humidity']
                discomfort_index = self.calculate_discomfort_index(temperature, humidity)
                comfort_level = self.get_comfort_level(discomfort_index)
                sht35_error = None
        
        # CO2センサーデータ取得（既存のまま）
        co2_data = self._get_co2_data_with_cache(retry_on_simulation, max_retries)
        
        # SQLiteログ記録を削除（JSONログ統合システム使用）
        if enable_logging:
            # CO2データ記録：monitoring_collector.pyのJSONログに統一
            logger.debug("CO2データ記録: monitoring_collector.pyのJSONログシステム使用")
            
            logger.debug(f"温度・湿度データ生成完了: T={temperature}°C, H={humidity}%")
        else:
            logger.debug(f"API専用モード: ログ記録スキップ (T={temperature}°C, H={humidity}%, CO2={co2_data['co2_ppm']}ppm)")
        
        # SHT35シミュレーション状態を判定
        sht35_simulation = not SHT35_AVAILABLE or self.sensor is None or temperature is None or humidity is None

        # 結果返却（既存のフォーマット + スマート平均情報）
        result = {
            'status': 'success' if sht35_error is None else 'partial',
            'timestamp': datetime.now().isoformat(),
            'temperature': temperature,
            'humidity': humidity,
            'discomfort_index': discomfort_index,
            'comfort_level': comfort_level,
            'co2_ppm': co2_data['co2_ppm'],
            'co2_level': co2_data['co2_level'],
            'co2_color': co2_data['co2_color'],
            'co2_message': co2_data['co2_message'],
            'co2_icon': co2_data['co2_icon'],
            'co2_simulation': co2_data['simulation'],
            'co2_from_cache': co2_data.get('from_cache', False),
            'sht35_simulation': sht35_simulation,
            'sensor_types': ['SHT35', 'MH-Z19E'],
            'location': '室内',
            'error': sht35_error
        }
        
        # Smart Averaging情報を追加（有効時のみ）
        if smart_averaging or self.smart_averaging_enabled:
            result.update({
                'sample_count': smart_data.get('sample_count', 1),
                'verification_level': smart_data.get('verification_level', 'normal'),
                'quality_score': smart_data.get('quality_score', 0.5),
                'processing_time': smart_data.get('processing_time', 0.0),
                'outliers_detected': smart_data.get('outliers_detected', 0),
                'method': smart_data.get('method', 'single'),
                'smart_averaging_used': True
            })
        else:
            result.update({
                'smart_averaging_used': False
            })
        
        return result

def get_sensor() -> SHT35Sensor:
    """
    Get singleton SHT35 sensor instance (now with Smart Averaging capability)
    
    Returns:
        SHT35Sensor: Enhanced sensor instance with Smart Averaging
    """
    global _sensor_instance
    if _sensor_instance is None:
        _sensor_instance = SHT35Sensor()
    return _sensor_instance