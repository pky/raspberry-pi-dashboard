#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weather Collector Script for Raspberry Pi Dashboard

5-Day Forecast APIからデータを収集し、JSONファイルに保存する
Cronで3時間毎（+5分オフセット）に実行される

実行方法:
    python3 weather_collector.py

出力:
    cache/weather/weather_data.json
"""

import json
import os
import sys
from pathlib import Path
import requests
import tempfile
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('weather_collector')

class WeatherCollector:
    def __init__(self):
        self.base_dir = str(Path(__file__).parent.parent)
        self.output_file = f"{self.base_dir}/cache/weather/weather_data.json"
        
        # Location (configurable via .env)
        self.latitude = float(os.environ.get('WEATHER_LATITUDE', '35.652875'))
        self.longitude = float(os.environ.get('WEATHER_LONGITUDE', '139.701595'))
        self.location_name = os.environ.get('WEATHER_LOCATION_NAME', '渋谷区鶯谷町')
        
        # API key読み込み
        self.api_key = self._load_api_key()
        
        # 5-Day Forecast API URL
        self.forecast_api_url = (
            f"http://api.openweathermap.org/data/2.5/forecast"
            f"?lat={self.latitude}&lon={self.longitude}"
            f"&appid={self.api_key}&units=metric&lang=ja"
        )
        
        # 出力ディレクトリ作成
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        
        logger.info(f"Weather Collector初期化完了 - 出力先: {self.output_file}")
    
    def _load_api_key(self) -> str:
        """API keyを既存weather_logic.pyと同じ方法で読み込む"""
        # 1. credentials/weather.confから読み込み
        config_path = f"{self.base_dir}/credentials/weather.conf"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('OPENWEATHERMAP_API_KEY='):
                            api_key = line.strip().split('=', 1)[1].strip('"\'')
                            logger.info("API keyを設定ファイルから読み込み完了")
                            return api_key
            except Exception as e:
                logger.error(f"設定ファイル読み込みエラー: {e}")
        
        # 2. 環境変数から読み込み
        api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        if api_key:
            logger.info("API keyを環境変数から読み込み完了")
            return api_key
        
        # 3. APIキー未設定
        logger.warning("OPENWEATHERMAP_API_KEY が設定されていません。credentials/weather.conf または .env に設定してください。")
        return ""
    
    def _is_nighttime(self, target_time: datetime) -> bool:
        """指定時刻が夜間（18:00-6:00）かどうか判定"""
        hour = target_time.hour
        return hour >= 18 or hour < 6
    
    def _openweather_to_icon(self, weather_id: int, target_time: datetime = None) -> str:
        """OpenWeatherMap天気IDをWeather Icons文字に変換（昼夜対応）"""
        if target_time is None:
            target_time = datetime.now()
            
        is_night = self._is_nighttime(target_time)
        
        # 完全なマッピング（weather_logic.pyと同一）
        day_night_map = {
            # Clear Sky
            800: ('\uf00d', '\uf02e'),  # day-sunny / night-clear
            
            # Clouds
            801: ('\uf002', '\uf083'),  # day-cloudy / night-partly-cloudy
            802: ('\uf002', '\uf086'),  # day-cloudy / night-alt-cloudy
            803: ('\uf013', '\uf086'),  # cloudy / night-alt-cloudy
            804: ('\uf013', '\uf086'),  # cloudy / night-alt-cloudy
            
            # Rain - Drizzle
            300: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle
            301: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle
            302: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix
            310: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle
            311: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix
            312: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix
            313: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            314: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix
            321: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            
            # Rain
            500: ('\uf008', '\uf028'),  # day-rain / night-alt-rain
            501: ('\uf008', '\uf028'),  # day-rain / night-alt-rain
            502: ('\uf008', '\uf028'),  # day-rain / night-alt-rain
            503: ('\uf008', '\uf028'),  # day-rain / night-alt-rain
            504: ('\uf008', '\uf028'),  # day-rain / night-alt-rain
            511: ('\uf006', '\uf0b4'),  # day-sleet / night-alt-sleet
            520: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            521: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            522: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            531: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers
            
            # Snow
            600: ('\uf01b', '\uf02a'),  # snow / night-alt-snow
            601: ('\uf01b', '\uf02a'),  # snow / night-alt-snow
            602: ('\uf01b', '\uf02a'),  # snow / night-alt-snow
            611: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet
            612: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet
            613: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet
            615: ('\uf017', '\uf026'),  # rain-mix / night-alt-rain-mix
            616: ('\uf017', '\uf026'),  # rain-mix / night-alt-rain-mix
            620: ('\uf01c', '\uf02b'),  # sprinkle / night-alt-sprinkle
            621: ('\uf01b', '\uf02a'),  # snow / night-alt-snow
            622: ('\uf01b', '\uf02a'),  # snow / night-alt-snow
            
            # Thunderstorm
            200: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            201: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            202: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            210: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning
            211: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning
            212: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning
            221: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning
            230: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            231: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            232: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm
            
            # Atmosphere
            701: ('\uf003', '\uf04a'),  # day-fog / night-fog
            711: ('\uf062', '\uf062'),  # smoke / smoke
            721: ('\uf0b6', '\uf0b6'),  # day-haze / night-haze
            731: ('\uf063', '\uf063'),  # dust / dust
            741: ('\uf003', '\uf04a'),  # day-fog / night-fog
            751: ('\uf063', '\uf063'),  # dust / dust
            761: ('\uf063', '\uf063'),  # dust / dust
            762: ('\uf0c7', '\uf0c7'),  # volcanic / volcanic
            771: ('\uf050', '\uf050'),  # strong-wind / strong-wind
            781: ('\uf056', '\uf056'),  # tornado / tornado
        }
        
        if weather_id in day_night_map:
            day_icon, night_icon = day_night_map[weather_id]
            return night_icon if is_night else day_icon
        
        # Fallback icons
        return '\uf02e' if is_night else '\uf00d'  # night-clear / day-sunny
    
    def _fetch_forecast_data(self) -> Optional[Dict[str, Any]]:
        """5-Day Forecast APIからデータ取得"""
        try:
            logger.info(f"5-Day Forecast API呼び出し開始: {self.forecast_api_url}")
            response = requests.get(self.forecast_api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"API呼び出し成功 - データ数: {len(data.get('list', []))}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API呼び出しエラー: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析エラー: {e}")
            return None
    
    def _process_forecast_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """APIレスポンスを詳細ページ用に処理"""
        if not raw_data or 'list' not in raw_data:
            logger.error("無効なAPIレスポンス")
            return {}
        
        forecast_list = []
        
        for item in raw_data['list']:
            try:
                # 日時解析
                dt_txt = item['dt_txt']  # "2025-01-20 12:00:00" format
                forecast_time = datetime.strptime(dt_txt, '%Y-%m-%d %H:%M:%S')
                
                # 基本天気データ
                main_data = item['main']
                weather_info = item['weather'][0]
                
                # 風・雲・降水データ
                wind_data = item.get('wind', {})
                clouds_data = item.get('clouds', {})
                rain_data = item.get('rain', {})
                snow_data = item.get('snow', {})
                
                # Weather Icon決定
                weather_icon = self._openweather_to_icon(
                    weather_info['id'], 
                    forecast_time
                )
                
                # 詳細予報データ構築
                forecast_item = {
                    'date': dt_txt,
                    'date_display': forecast_time.strftime('%m/%d %H:%M'),
                    'day_of_week': forecast_time.strftime('%a'),
                    'temperature': round(main_data['temp'], 1),
                    'feels_like': round(main_data['feels_like'], 1),
                    'temp_min': round(main_data.get('temp_min', main_data['temp']), 1),
                    'temp_max': round(main_data.get('temp_max', main_data['temp']), 1),
                    'humidity': main_data['humidity'],
                    'pressure': main_data['pressure'],
                    'sea_level': main_data.get('sea_level', main_data['pressure']),
                    'grnd_level': main_data.get('grnd_level', main_data['pressure']),
                    'weather_id': weather_info['id'],
                    'weather_main': weather_info['main'],
                    'weather_description': weather_info['description'],
                    'weather_icon': weather_icon,
                    'wind_speed': wind_data.get('speed', 0),
                    'wind_deg': wind_data.get('deg', 0),
                    'wind_gust': wind_data.get('gust', 0),
                    'clouds': clouds_data.get('all', 0),
                    'visibility': item.get('visibility', 10000) / 1000,  # m -> km
                    'pop': item.get('pop', 0) * 100,  # 0-1 -> 0-100%
                    'rain_3h': rain_data.get('3h', 0),
                    'snow_3h': snow_data.get('3h', 0),
                    'is_night': self._is_nighttime(forecast_time)
                }
                
                forecast_list.append(forecast_item)
                
            except Exception as e:
                logger.error(f"予報データ処理エラー: {e}, item: {item}")
                continue
        
        # メタデータ付きで返却
        processed_data = {
            'collection_time': datetime.now().isoformat(),
            'location': {
                'name': self.location_name,
                'latitude': self.latitude,
                'longitude': self.longitude
            },
            'forecast_count': len(forecast_list),
            'forecast_list': forecast_list,
            'api_info': {
                'source': '5-Day Weather Forecast API',
                'city_info': raw_data.get('city', {}),
                'cnt': raw_data.get('cnt', 0)
            }
        }
        
        logger.info(f"予報データ処理完了 - {len(forecast_list)}件")
        return processed_data
    
    def _save_to_json(self, data: Dict[str, Any]) -> bool:
        """JSONファイルに原子的に保存"""
        try:
            # 一時ファイルに書き込み（Atomic Write）
            temp_file = None
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=os.path.dirname(self.output_file),
                delete=False,
                encoding='utf-8'
            ) as f:
                json.dump(data, f, ensure_ascii=False, indent=2, separators=(',', ': '))
                temp_file = f.name
            
            # 原子的にファイルを置換
            os.rename(temp_file, self.output_file)
            
            logger.info(f"JSONファイル保存完了: {self.output_file}")
            return True
            
        except Exception as e:
            logger.error(f"JSONファイル保存エラー: {e}")
            # 一時ファイルのクリーンアップ
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            return False
    
    def collect_and_save(self) -> bool:
        """メイン実行メソッド"""
        logger.info("天気データ収集開始")
        
        # API呼び出し
        raw_data = self._fetch_forecast_data()
        if not raw_data:
            logger.error("APIからデータを取得できませんでした")
            return False
        
        # データ処理
        processed_data = self._process_forecast_data(raw_data)
        if not processed_data:
            logger.error("データ処理に失敗しました")
            return False
        
        # JSON保存
        if not self._save_to_json(processed_data):
            logger.error("JSON保存に失敗しました")
            return False
        
        logger.info(f"天気データ収集完了 - {processed_data['forecast_count']}件の予報を保存")
        return True


def main():
    """スクリプトのメインエントリーポイント"""
    try:
        collector = WeatherCollector()
        success = collector.collect_and_save()
        
        if success:
            logger.info("Weather Collector正常終了")
            sys.exit(0)
        else:
            logger.error("Weather Collector異常終了")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()