#!/usr/bin/env python3
"""
バリデーションLogic クラス
Raspberry Pi Dashboard のデータ検証・範囲チェック処理を統合管理

Logic分離統一 Phase 3: バリデーションLogic分離
- センサー値検証（温度・湿度・CO2の範囲チェック）
- データ型変換・補正処理（float/int変換、丸め処理）
- 異常値検知（しきい値ベースの警告判定）
- バリデーション設定管理（範囲定義・しきい値設定）
"""

from logging_system import get_logger


class ValidationLogic:
    """データ検証・範囲チェック処理Logic"""
    
    def __init__(self):
        self.logger = get_logger("validation_logic")
        
        # センサー値の有効範囲定義
        self.sensor_ranges = {
            'temperature': {'min': -40.0, 'max': 80.0},    # 温度: -40℃〜80℃
            'humidity': {'min': 0.0, 'max': 100.0},        # 湿度: 0%〜100%
            'co2': {'min': 200, 'max': 5000}               # CO2: 200ppm〜5000ppm
        }
        
        # 異常値検知用しきい値設定
        self.alert_thresholds = {
            'temperature': {'min': 18.0, 'max': 28.0},     # 快適温度範囲
            'humidity': {'min': 40.0, 'max': 70.0},        # 快適湿度範囲  
            'co2': {'min': 400, 'max': 1000}               # 正常CO2範囲
        }
        
    def validate_temperature(self, temp_value):
        """温度データの検証・補正
        
        Args:
            temp_value: 温度値（数値または文字列）
            
        Returns:
            float or None: 検証済み温度値（1桁丸め）、無効時はNone
        """
        if temp_value is None:
            return None
            
        try:
            temp = float(temp_value)
            # 範囲チェック（-40℃〜80℃）
            if self.sensor_ranges['temperature']['min'] <= temp <= self.sensor_ranges['temperature']['max']:
                return round(temp, 1)
            else:
                self.logger.warning("温度値が範囲外", 
                                  temp=temp, 
                                  valid_range=self.sensor_ranges['temperature'])
                return None
        except (ValueError, TypeError) as e:
            self.logger.warning("無効な温度データ", value=temp_value, error=str(e))
            return None
    
    def validate_humidity(self, humidity_value):
        """湿度データの検証・補正
        
        Args:
            humidity_value: 湿度値（数値または文字列）
            
        Returns:
            float or None: 検証済み湿度値（1桁丸め）、無効時はNone
        """
        if humidity_value is None:
            return None
            
        try:
            humidity = float(humidity_value)
            # 範囲チェック（0%〜100%）
            if self.sensor_ranges['humidity']['min'] <= humidity <= self.sensor_ranges['humidity']['max']:
                return round(humidity, 1)
            else:
                self.logger.warning("湿度値が範囲外", 
                                  humidity=humidity, 
                                  valid_range=self.sensor_ranges['humidity'])
                return None
        except (ValueError, TypeError) as e:
            self.logger.warning("無効な湿度データ", value=humidity_value, error=str(e))
            return None
    
    def validate_co2(self, co2_value):
        """CO2データの検証・補正
        
        Args:
            co2_value: CO2値（数値または文字列）
            
        Returns:
            int or None: 検証済みCO2値（整数）、無効時はNone
        """
        if co2_value is None:
            return None
            
        try:
            co2 = int(float(co2_value))
            # 範囲チェック（200ppm〜5000ppm）
            if self.sensor_ranges['co2']['min'] <= co2 <= self.sensor_ranges['co2']['max']:
                return co2
            else:
                self.logger.warning("CO2値が範囲外", 
                                  co2=co2, 
                                  valid_range=self.sensor_ranges['co2'])
                return None
        except (ValueError, TypeError) as e:
            self.logger.warning("無効なCO2データ", value=co2_value, error=str(e))
            return None
            
    def detect_sensor_anomalies(self, sensor_data):
        """センサー異常値検知（しきい値ベース）
        
        Args:
            sensor_data (dict): センサーデータ {'temperature': float, 'humidity': float, 'co2': int}
            
        Returns:
            dict: {
                'status': str,           # 'normal' or 'warning'
                'warnings': list,        # 警告メッセージリスト
                'anomaly_count': int     # 異常項目数
            }
        """
        warnings = []
        
        try:
            # 温度異常チェック
            temp = sensor_data.get('temperature')
            if temp is not None:
                if temp < self.alert_thresholds['temperature']['min']:
                    warnings.append(f"低温警告: {temp}℃ (推奨: {self.alert_thresholds['temperature']['min']}℃以上)")
                elif temp > self.alert_thresholds['temperature']['max']:
                    warnings.append(f"高温警告: {temp}℃ (推奨: {self.alert_thresholds['temperature']['max']}℃以下)")
            
            # 湿度異常チェック
            humidity = sensor_data.get('humidity')
            if humidity is not None:
                if humidity < self.alert_thresholds['humidity']['min']:
                    warnings.append(f"低湿度警告: {humidity}% (推奨: {self.alert_thresholds['humidity']['min']}%以上)")
                elif humidity > self.alert_thresholds['humidity']['max']:
                    warnings.append(f"高湿度警告: {humidity}% (推奨: {self.alert_thresholds['humidity']['max']}%以下)")
            
            # CO2異常チェック
            co2 = sensor_data.get('co2')
            if co2 is not None:
                if co2 > self.alert_thresholds['co2']['max']:
                    warnings.append(f"CO2高濃度警告: {co2}ppm (推奨: {self.alert_thresholds['co2']['max']}ppm以下)")
            
            if warnings:
                self.logger.warning("センサー異常検知", 
                                  anomaly_count=len(warnings), 
                                  warnings=warnings)
                
            return {
                'status': 'warning' if warnings else 'normal',
                'warnings': warnings,
                'anomaly_count': len(warnings)
            }
            
        except Exception as e:
            self.logger.error("異常値検知処理エラー", error=str(e), sensor_data=sensor_data)
            return {
                'status': 'error',
                'warnings': ['異常値検知処理でエラーが発生しました'],
                'anomaly_count': 1
            }
    
    def validate_sensor_data_batch(self, raw_data):
        """センサーデータ一括検証
        
        Args:
            raw_data (dict): 生センサーデータ
            
        Returns:
            dict: {
                'temperature': float or None,
                'humidity': float or None,
                'co2': int or None,
                'validation_status': str,
                'failed_validations': list
            }
        """
        try:
            validated_data = {
                'temperature': self.validate_temperature(raw_data.get('temperature')),
                'humidity': self.validate_humidity(raw_data.get('humidity')),
                'co2': self.validate_co2(raw_data.get('co2_ppm'))  # 'co2_ppm'キー使用
            }
            
            # 検証失敗項目の特定
            failed_validations = []
            for key, value in validated_data.items():
                if value is None and raw_data.get(key) is not None:
                    failed_validations.append(key)
            
            validation_status = 'failed' if failed_validations else 'success'
            
            self.logger.debug("一括検証完了", 
                            validation_status=validation_status,
                            failed_count=len(failed_validations))
            
            return {
                **validated_data,
                'validation_status': validation_status,
                'failed_validations': failed_validations
            }
            
        except Exception as e:
            self.logger.error("一括検証処理エラー", error=str(e), raw_data=raw_data)
            return {
                'temperature': None,
                'humidity': None,
                'co2': None,
                'validation_status': 'error',
                'failed_validations': ['批判的エラー']
            }
    
    def get_sensor_ranges(self):
        """センサー有効範囲情報取得（設定用）
        
        Returns:
            dict: センサー有効範囲設定
        """
        return self.sensor_ranges.copy()
        
    def get_alert_thresholds(self):
        """異常値検知しきい値情報取得（設定用）
        
        Returns:
            dict: しきい値設定
        """
        return self.alert_thresholds.copy()
        
    def update_thresholds(self, sensor_type, min_value=None, max_value=None):
        """しきい値設定更新
        
        Args:
            sensor_type (str): センサータイプ ('temperature', 'humidity', 'co2')
            min_value (float, optional): 最小しきい値
            max_value (float, optional): 最大しきい値
            
        Returns:
            bool: 更新成功フラグ
        """
        try:
            if sensor_type not in self.alert_thresholds:
                self.logger.error("無効なセンサータイプ", sensor_type=sensor_type)
                return False
                
            if min_value is not None:
                self.alert_thresholds[sensor_type]['min'] = min_value
            if max_value is not None:
                self.alert_thresholds[sensor_type]['max'] = max_value
                
            self.logger.info("しきい値設定更新", 
                           sensor_type=sensor_type,
                           thresholds=self.alert_thresholds[sensor_type])
            return True
            
        except Exception as e:
            self.logger.error("しきい値設定更新エラー", error=str(e))
            return False