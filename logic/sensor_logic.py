"""
SensorLogic - センサーデータ処理ロジック
既存dashboard.pyのセンサー関連処理から抽出・独立化

Phase4 Day22-24実装 - ロジック分離
計画書：SEPARATION_APPROACH_DESIGN.md Phase4
"""

from datetime import datetime, timedelta
from logging_system import get_logger
from .validation_logic import ValidationLogic


class SensorLogic:
    """
    センサーデータ処理ロジッククラス
    既存dashboard.pyのセンサー関連処理から抽出・独立化
    """
    
    def __init__(self):
        self.logger = get_logger("sensor_logic")
        self.sensor_history = []  # センサー履歴データ
        self.current_data = {}    # 現在のセンサーデータ
        # Logic分離統一: ValidationLogic初期化（しきい値設定を移行）
        self.validation_logic = ValidationLogic()
        # 互換性維持のためthresholds参照を保持
        self.thresholds = self.validation_logic.get_alert_thresholds()
    
    def process_sensor_data(self, raw_data):
        """Logic分離統一: 生センサーデータを処理・検証（ValidationLogic使用）"""
        try:
            # Logic分離統一: ValidationLogicで一括検証
            validation_result = self.validation_logic.validate_sensor_data_batch(raw_data)
            
            processed_data = {
                'timestamp': datetime.now().isoformat(),
                'temperature': validation_result['temperature'],
                'humidity': validation_result['humidity'],
                'co2': validation_result['co2'],
                'status': 'normal'
            }
            
            # Logic分離統一: ValidationLogicで異常値検知
            anomaly_result = self.validation_logic.detect_sensor_anomalies(processed_data)
            processed_data['status'] = anomaly_result['status']
            
            # 履歴に追加
            self.add_to_history(processed_data)
            self.current_data = processed_data
            
            self.logger.info("センサーデータ処理完了", 
                           temp=processed_data['temperature'],
                           humidity=processed_data['humidity'],
                           co2=processed_data['co2'],
                           status=processed_data['status'])
            
            return processed_data
            
        except Exception as e:
            self.logger.error("センサーデータ処理エラー", error=str(e))
            return self.get_fallback_data()
    
    def validate_temperature(self, temp_value):
        """Logic分離統一: 温度データの検証・補正をValidationLogicに委譲"""
        return self.validation_logic.validate_temperature(temp_value)
    
    def validate_humidity(self, humidity_value):
        """Logic分離統一: 湿度データの検証・補正をValidationLogicに委譲"""
        return self.validation_logic.validate_humidity(humidity_value)
    
    def validate_co2(self, co2_value):
        """Logic分離統一: CO2データの検証・補正をValidationLogicに委譲"""
        return self.validation_logic.validate_co2(co2_value)
    
    def detect_anomalies(self, data):
        """Logic分離統一: 異常値検知をValidationLogicに委譲"""
        anomaly_result = self.validation_logic.detect_sensor_anomalies(data)
        return anomaly_result['status']
    
    def add_to_history(self, data):
        """センサー履歴にデータ追加"""
        self.sensor_history.append(data.copy())
        
        # 履歴サイズ制限（最新100件）
        if len(self.sensor_history) > 100:
            self.sensor_history = self.sensor_history[-100:]
    
    def get_current_data(self):
        """現在のセンサーデータを取得"""
        return self.current_data.copy() if self.current_data else self.get_fallback_data()
    
    def get_history_data(self, hours=24):
        """指定時間の履歴データを取得"""
        if not self.sensor_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_history = []
        
        for entry in self.sensor_history:
            try:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if entry_time >= cutoff_time:
                    filtered_history.append(entry)
            except (ValueError, KeyError):
                continue
        
        return filtered_history
    
    def get_sensor_status_summary(self):
        """センサー状態サマリーを取得"""
        current = self.get_current_data()
        history = self.get_history_data(1)  # 1時間の履歴
        
        summary = {
            'current': current,
            'data_points': len(history),
            'last_update': current.get('timestamp', 'unknown'),
            'status': current.get('status', 'unknown'),
            'connectivity': 'connected' if current.get('temperature') is not None else 'disconnected'
        }
        
        # 平均値計算（1時間）
        if history:
            temps = [h['temperature'] for h in history if h.get('temperature') is not None]
            humidities = [h['humidity'] for h in history if h.get('humidity') is not None]
            co2s = [h['co2'] for h in history if h.get('co2') is not None]
            
            if temps:
                summary['avg_temperature'] = round(sum(temps) / len(temps), 1)
            if humidities:
                summary['avg_humidity'] = round(sum(humidities) / len(humidities), 1)
            if co2s:
                summary['avg_co2'] = round(sum(co2s) / len(co2s))
        
        return summary
    
    def get_fallback_data(self):
        """フォールバックデータ（センサー接続不良時）"""
        return {
            'timestamp': datetime.now().isoformat(),
            'temperature': None,
            'humidity': None,
            'co2': None,
            'status': 'disconnected'
        }
    
    def update_thresholds(self, new_thresholds):
        """しきい値設定を更新"""
        if isinstance(new_thresholds, dict):
            self.thresholds.update(new_thresholds)
            self.logger.info("しきい値更新完了", thresholds=self.thresholds)
            return True
        return False
    
    def clear_history(self):
        """履歴データをクリア"""
        self.sensor_history.clear()
        self.logger.info("センサー履歴クリア完了")