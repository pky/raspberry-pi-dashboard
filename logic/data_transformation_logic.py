#!/usr/bin/env python3
"""
データ変換Logic クラス
Raspberry Pi Dashboard のデータフォーマット・変換処理を統合管理

Logic分離統一 Phase 2: データ変換Logic分離
- 数値フォーマット処理（温度、湿度、CO2、不快度指数）
- 不快度指数計算と快適度レベル判定
- CO2レベル分類と警告メッセージ生成
"""

from logging_system import get_logger


class DataTransformationLogic:
    """データ変換・フォーマット処理Logic"""
    
    def __init__(self):
        self.logger = get_logger("data_transformation_logic")
        
    def format_temperature(self, temperature_value):
        """温度データのフォーマット処理
        
        Args:
            temperature_value (float): 温度値
            
        Returns:
            str: フォーマット済み温度文字列 (例: "23.5°C")
        """
        try:
            if temperature_value is None:
                return "取得中"
            return f"{temperature_value:.1f}°C"
        except Exception as e:
            self.logger.error("温度フォーマット処理エラー", temperature=temperature_value, error=str(e))
            return "エラー"
            
    def format_humidity(self, humidity_value):
        """湿度データのフォーマット処理
        
        Args:
            humidity_value (float): 湿度値
            
        Returns:
            str: フォーマット済み湿度文字列 (例: "65.2%")
        """
        try:
            if humidity_value is None:
                return "取得中"
            return f"{humidity_value:.1f}%"
        except Exception as e:
            self.logger.error("湿度フォーマット処理エラー", humidity=humidity_value, error=str(e))
            return "エラー"
            
    def format_co2(self, co2_value):
        """CO2データのフォーマット処理
        
        Args:
            co2_value (int): CO2値
            
        Returns:
            str: フォーマット済みCO2文字列 (例: "450")
        """
        try:
            if co2_value is None:
                return "取得中"
            return str(co2_value)
        except Exception as e:
            self.logger.error("CO2フォーマット処理エラー", co2=co2_value, error=str(e))
            return "エラー"
            
    def format_discomfort_index(self, discomfort_index_value):
        """不快度指数のフォーマット処理
        
        Args:
            discomfort_index_value (float): 不快度指数値
            
        Returns:
            str: フォーマット済み不快度指数文字列 (例: "68.5")
        """
        try:
            if discomfort_index_value is None:
                return "取得中"
            return f"{discomfort_index_value:.1f}"
        except Exception as e:
            self.logger.error("不快度指数フォーマット処理エラー", discomfort_index=discomfort_index_value, error=str(e))
            return "エラー"
            
    def calculate_discomfort_index(self, temperature, humidity):
        """不快度指数計算と快適度レベル判定
        
        Args:
            temperature (float): 温度（℃）
            humidity (float): 湿度（%）
            
        Returns:
            dict: {
                'discomfort_index': float,
                'comfort_level': str
            }
        """
        try:
            if temperature is None or humidity is None:
                return {
                    'discomfort_index': None,
                    'comfort_level': "取得中"
                }
                
            # 不快度指数計算式: 0.81 * 温度 + 0.01 * 湿度 * (0.99 * 温度 - 14.3) + 46.3
            discomfort_index = 0.81 * temperature + 0.01 * humidity * (0.99 * temperature - 14.3) + 46.3
            
            # 快適度レベル判定
            if discomfort_index < 55:
                comfort_level = "寒い"
            elif discomfort_index < 60:
                comfort_level = "肌寒い"
            elif discomfort_index < 65:
                comfort_level = "涼しい"
            elif discomfort_index < 70:
                comfort_level = "快適"
            elif discomfort_index < 75:
                comfort_level = "暖かい"
            elif discomfort_index < 80:
                comfort_level = "やや暑い"
            elif discomfort_index < 85:
                comfort_level = "暑くて不快"
            else:
                comfort_level = "非常に不快"
                
            self.logger.debug("不快度指数計算完了", 
                            temperature=temperature, 
                            humidity=humidity,
                            discomfort_index=discomfort_index, 
                            comfort_level=comfort_level)
            
            return {
                'discomfort_index': discomfort_index,
                'comfort_level': comfort_level
            }
            
        except Exception as e:
            self.logger.error("不快度指数計算エラー", 
                            temperature=temperature, 
                            humidity=humidity, 
                            error=str(e))
            return {
                'discomfort_index': None,
                'comfort_level': "エラー"
            }
            
    def classify_co2_level(self, co2_ppm):
        """CO2レベル分類と警告メッセージ生成
        
        Args:
            co2_ppm (int): CO2濃度（ppm）
            
        Returns:
            dict: {
                'co2_level': str,
                'co2_color': str,
                'co2_message': str
            }
        """
        try:
            if co2_ppm is None:
                return {
                    'co2_level': "取得中",
                    'co2_color': "gray",
                    'co2_message': ""
                }
                
            # CO2レベル分類
            if co2_ppm < 1000:
                co2_level = "正常"
                co2_color = "green"
                co2_message = ""
            elif co2_ppm < 1500:
                co2_level = "注意"
                co2_color = "yellow"
                co2_message = "換気をして"
            elif co2_ppm < 3000:
                co2_level = "警告"
                co2_color = "orange"
                co2_message = "換気が必要"
            else:
                co2_level = "危険"
                co2_color = "red"
                co2_message = "至急換気して！"
                
            self.logger.debug("CO2レベル分類完了", 
                            co2_ppm=co2_ppm, 
                            co2_level=co2_level, 
                            co2_color=co2_color)
            
            return {
                'co2_level': co2_level,
                'co2_color': co2_color,
                'co2_message': co2_message
            }
            
        except Exception as e:
            self.logger.error("CO2レベル分類エラー", co2_ppm=co2_ppm, error=str(e))
            return {
                'co2_level': "エラー",
                'co2_color': "gray",
                'co2_message': ""
            }
            
    def get_color_style_map(self):
        """CO2レベル色マッピング取得（UI用）
        
        Returns:
            dict: 色名とCSSスタイルのマッピング
        """
        return {
            'green': 'color: #4ade80;',
            'yellow': 'color: #facc15;',
            'orange': 'color: #fb923c;',
            'red': 'color: #f87171;',
            'gray': 'color: rgba(255, 255, 255, 0.5);'
        }