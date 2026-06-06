#!/usr/bin/env python3
"""
計算Logic クラス
Raspberry Pi Dashboard の計算処理・判定処理を統合管理

Logic分離統一 Phase 2.5: 計算Logic分離
- センサーアイコン計算（温度・湿度・不快度指数に基づくアイコン選択）
- 閾値判定処理（温度・不快度指数の段階判定）
- Material Icons マッピング処理
"""

from logging_system import get_logger


class CalculationLogic:
    """計算・判定処理Logic"""
    
    def __init__(self):
        self.logger = get_logger("calculation_logic")
        
    def calculate_temperature_icon_type(self, temperature_value):
        """温度値に基づくアイコンタイプ計算
        
        Args:
            temperature_value (float): 温度値（℃）
            
        Returns:
            str: アイコンタイプ ("hot", "cold", "normal")
        """
        try:
            if temperature_value is None:
                return "normal"
                
            if temperature_value >= 30:
                return "hot"  # 暑い
            elif temperature_value <= 10:
                return "cold"  # 寒い
            else:
                return "normal"  # 通常
                
        except Exception as e:
            self.logger.error("温度アイコンタイプ計算エラー", temperature=temperature_value, error=str(e))
            return "normal"
            
    def calculate_discomfort_icon_type(self, discomfort_index_value):
        """不快度指数値に基づくアイコンタイプ計算
        
        Args:
            discomfort_index_value (float): 不快度指数値
            
        Returns:
            str: アイコンタイプ ("very_satisfied", "satisfied", "neutral", "dissatisfied", "very_dissatisfied")
        """
        try:
            if discomfort_index_value is None:
                return "neutral"
                
            if discomfort_index_value >= 85:
                return "very_dissatisfied"  # 非常に不快
            elif discomfort_index_value >= 80:
                return "dissatisfied"  # 不快
            elif discomfort_index_value >= 75:
                return "neutral"  # 普通
            elif discomfort_index_value >= 70:
                return "satisfied"  # 満足
            else:
                return "very_satisfied"  # 非常に満足
                
        except Exception as e:
            self.logger.error("不快度指数アイコンタイプ計算エラー", discomfort_index=discomfort_index_value, error=str(e))
            return "neutral"
            
    def get_sensor_icon_with_fallback(self, sensor_type, value=None, material_icons=None):
        """センサー種類と値に応じてMaterial Iconを計算・取得（フォールバック付き）
        
        Args:
            sensor_type (str): センサータイプ ("temperature", "humidity", "discomfort")
            value (float, optional): センサー値
            material_icons (dict, optional): Material Iconsマッピング辞書
            
        Returns:
            str: Material Iconまたはフォールバック文字
        """
        try:
            # Material Iconsマッピング辞書のデフォルト値
            if material_icons is None:
                material_icons = {}
                
            if sensor_type == "temperature":
                # Logic分離統一: 温度アイコンタイプ計算をCalculationLogicに委譲
                icon_type = self.calculate_temperature_icon_type(value)
                
                if icon_type == "hot":
                    return material_icons.get("whatshot", "T")  # 暑い
                elif icon_type == "cold":
                    return material_icons.get("ac_unit", "T")   # 寒い
                else:
                    return material_icons.get("thermostat", "T")  # 通常
            
            elif sensor_type == "humidity":
                return material_icons.get("water_drop", "H")
            
            elif sensor_type == "discomfort":
                # Logic分離統一: 不快度指数アイコンタイプ計算をCalculationLogicに委譲
                icon_type = self.calculate_discomfort_icon_type(value)
                
                if icon_type == "very_dissatisfied":
                    return material_icons.get("sentiment_very_dissatisfied", "😫")
                elif icon_type == "dissatisfied":
                    return material_icons.get("sentiment_dissatisfied", "😒")
                elif icon_type == "neutral":
                    return material_icons.get("sentiment_neutral", "😐")
                elif icon_type == "satisfied":
                    return material_icons.get("sentiment_satisfied", "😊")
                elif icon_type == "very_satisfied":
                    return material_icons.get("sentiment_very_satisfied", "😄")
                else:
                    return material_icons.get("sentiment_neutral", "D")
            
            # 未知のセンサータイプ
            return "?"  # フォールバック
            
        except Exception as e:
            self.logger.error("センサーアイコン計算エラー", 
                            sensor_type=sensor_type, 
                            value=value, 
                            error=str(e))
            return "?"  # エラー時フォールバック
            
    def get_temperature_threshold_info(self):
        """温度閾値情報取得（設定用）
        
        Returns:
            dict: 温度閾値とアイコンタイプのマッピング
        """
        return {
            "hot_threshold": 30.0,      # 暑いアイコンの閾値
            "cold_threshold": 10.0,     # 寒いアイコンの閾値
            "icon_mapping": {
                "hot": "whatshot",
                "cold": "ac_unit", 
                "normal": "thermostat"
            }
        }
        
    def get_discomfort_threshold_info(self):
        """不快度指数閾値情報取得（設定用）
        
        Returns:
            dict: 不快度指数閾値とアイコンタイプのマッピング
        """
        return {
            "very_dissatisfied_threshold": 85.0,  # 非常に不快の閾値
            "dissatisfied_threshold": 80.0,       # 不快の閾値
            "neutral_threshold": 75.0,            # 普通の閾値
            "satisfied_threshold": 70.0,          # 満足の閾値
            "icon_mapping": {
                "very_dissatisfied": "sentiment_very_dissatisfied",
                "dissatisfied": "sentiment_dissatisfied",
                "neutral": "sentiment_neutral",
                "satisfied": "sentiment_satisfied",
                "very_satisfied": "sentiment_very_satisfied"
            }
        }