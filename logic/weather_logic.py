#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WeatherLogic:
    def __init__(self):
        self.base_dir = str(Path(__file__).parent.parent)
        self.cache_file = f"{self.base_dir}/cache/weather/weather_cache.json"
        self.api_key = self._load_api_key()
        
        # Location coordinates (configurable via .env)
        self.latitude = float(os.environ.get('WEATHER_LATITUDE', '35.652875'))
        self.longitude = float(os.environ.get('WEATHER_LONGITUDE', '139.701595'))
        self.location_name = os.environ.get('WEATHER_LOCATION_NAME', '渋谷区鶯谷町')
        
        # Cache settings
        self.cache_duration = 300  # 5 minutes
        
        # OpenWeatherMap API endpoints
        self.current_api_url = f"http://api.openweathermap.org/data/2.5/weather?lat={self.latitude}&lon={self.longitude}&appid={self.api_key}&units=metric&lang=ja"
        self.forecast_api_url = f"http://api.openweathermap.org/data/2.5/forecast?lat={self.latitude}&lon={self.longitude}&appid={self.api_key}&units=metric&lang=ja"
        
        # Create cache directory if it doesn't exist
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
    
    def _load_api_key(self) -> str:
        """API keyを安全に読み込む"""
        # 1. credentials/weather.confから読み込み
        config_path = f"{self.base_dir}/credentials/weather.conf"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('OPENWEATHERMAP_API_KEY='):
                            return line.strip().split('=', 1)[1].strip('"\'')
            except Exception as e:
                logger.error(f"設定ファイル読み込みエラー: {e}")
        
        # 2. 環境変数から読み込み
        api_key = os.getenv('OPENWEATHERMAP_API_KEY')
        if api_key:
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
        
        # Day/Night専用マッピング (day, night) のタプル形式
        day_night_map = {
            # Clear Sky
            800: ('\uf00d', '\uf02e'),  # day-sunny / night-clear
            
            # Clouds - 月が欠けた形優先
            801: ('\uf002', '\uf083'),  # day-cloudy / night-partly-cloudy (月が欠けた形)
            802: ('\uf002', '\uf086'),  # day-cloudy / night-alt-cloudy (月が欠けた形)
            803: ('\uf013', '\uf086'),  # cloudy / night-alt-cloudy (月が欠けた形)
            804: ('\uf013', '\uf086'),  # cloudy / night-alt-cloudy (月が欠けた形)
            
            # Rain - 月が欠けた形優先
            300: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle (月が欠けた形)
            301: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle (月が欠けた形)
            302: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix (月が欠けた形)
            310: ('\uf009', '\uf02b'),  # day-sprinkle / night-alt-sprinkle (月が欠けた形)
            311: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix (月が欠けた形)
            312: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix (月が欠けた形)
            313: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            314: ('\uf008', '\uf026'),  # day-rain / night-alt-rain-mix (月が欠けた形)
            321: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            500: ('\uf008', '\uf028'),  # day-rain / night-alt-rain (月が欠けた形)
            501: ('\uf008', '\uf028'),  # day-rain / night-alt-rain (月が欠けた形)
            502: ('\uf008', '\uf028'),  # day-rain / night-alt-rain (月が欠けた形)
            503: ('\uf008', '\uf028'),  # day-rain / night-alt-rain (月が欠けた形)
            504: ('\uf008', '\uf028'),  # day-rain / night-alt-rain (月が欠けた形)
            511: ('\uf006', '\uf0b4'),  # day-sleet / night-alt-sleet (月が欠けた形)
            520: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            521: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            522: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            531: ('\uf00a', '\uf029'),  # day-showers / night-alt-showers (月が欠けた形)
            
            # Snow - 月が欠けた形優先
            600: ('\uf01b', '\uf02a'),  # snow / night-alt-snow (月が欠けた形)
            601: ('\uf01b', '\uf02a'),  # snow / night-alt-snow (月が欠けた形)
            602: ('\uf01b', '\uf02a'),  # snow / night-alt-snow (月が欠けた形)
            611: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet (月が欠けた形)
            612: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet (月が欠けた形)
            613: ('\uf006', '\uf0b4'),  # sleet / night-alt-sleet (月が欠けた形)
            615: ('\uf017', '\uf026'),  # rain-mix / night-alt-rain-mix (月が欠けた形)
            616: ('\uf017', '\uf026'),  # rain-mix / night-alt-rain-mix (月が欠けた形)
            620: ('\uf01c', '\uf02b'),  # sprinkle / night-alt-sprinkle (月が欠けた形)
            621: ('\uf01b', '\uf02a'),  # snow / night-alt-snow (月が欠けた形)
            622: ('\uf01b', '\uf02a'),  # snow / night-alt-snow (月が欠けた形)
            
            # Thunderstorm - 月が欠けた形優先
            200: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            201: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            202: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            210: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning (月が欠けた形)
            211: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning (月が欠けた形)
            212: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning (月が欠けた形)
            221: ('\uf005', '\uf025'),  # day-lightning / night-alt-lightning (月が欠けた形)
            230: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            231: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            232: ('\uf010', '\uf02d'),  # day-thunderstorm / night-alt-thunderstorm (月が欠けた形)
            
            # Atmosphere
            701: ('\uf003', '\uf04a'),  # day-fog / night-fog
            711: ('\uf062', '\uf062'),  # smoke / smoke (same for both)
            721: ('\uf0b6', '\uf0b6'),  # day-haze / night-haze (same)
            731: ('\uf063', '\uf063'),  # dust / dust (same)
            741: ('\uf003', '\uf04a'),  # day-fog / night-fog
            751: ('\uf063', '\uf063'),  # dust / dust (same)
            761: ('\uf063', '\uf063'),  # dust / dust (same)
            762: ('\uf0c7', '\uf0c7'),  # volcanic / volcanic (same)
            771: ('\uf050', '\uf050'),  # strong-wind / strong-wind (same)
            781: ('\uf056', '\uf056'),  # tornado / tornado (same)
        }
        
        if weather_id in day_night_map:
            day_icon, night_icon = day_night_map[weather_id]
            return night_icon if is_night else day_icon
        
        # Fallback icons
        return '\uf02e' if is_night else '\uf00d'  # night-clear / day-sunny
    
    def _get_neutral_icon(self, weather_id: int) -> str:
        """Neutral（昼夜に関係ない）Weather Iconsを取得"""
        neutral_map = {
            # Clear Sky
            800: '\uf00d',  # day-sunny (基本の太陽)
            
            # Clouds
            801: '\uf002',  # day-cloudy
            802: '\uf002',  # day-cloudy
            803: '\uf013',  # cloudy
            804: '\uf013',  # cloudy
            
            # Rain
            300: '\uf01c',  # sprinkle
            301: '\uf01c',  # sprinkle
            302: '\uf019',  # rain
            310: '\uf01c',  # sprinkle
            311: '\uf019',  # rain
            312: '\uf019',  # rain
            313: '\uf01a',  # showers
            314: '\uf019',  # rain
            321: '\uf01a',  # showers
            500: '\uf019',  # rain
            501: '\uf019',  # rain
            502: '\uf019',  # rain
            503: '\uf019',  # rain
            504: '\uf019',  # rain
            511: '\uf0b5',  # sleet
            520: '\uf01a',  # showers
            521: '\uf01a',  # showers
            522: '\uf01a',  # showers
            531: '\uf01a',  # showers
            
            # Snow
            600: '\uf01b',  # snow
            601: '\uf01b',  # snow
            602: '\uf01b',  # snow
            611: '\uf0b5',  # sleet
            612: '\uf0b5',  # sleet
            613: '\uf0b5',  # sleet
            615: '\uf017',  # rain-mix
            616: '\uf017',  # rain-mix
            620: '\uf01c',  # sprinkle
            621: '\uf01b',  # snow
            622: '\uf01b',  # snow
            
            # Thunderstorm
            200: '\uf01e',  # thunderstorm
            201: '\uf01e',  # thunderstorm
            202: '\uf01e',  # thunderstorm
            210: '\uf016',  # lightning
            211: '\uf016',  # lightning
            212: '\uf016',  # lightning
            221: '\uf016',  # lightning
            230: '\uf01e',  # thunderstorm
            231: '\uf01e',  # thunderstorm
            232: '\uf01e',  # thunderstorm
            
            # Atmosphere
            701: '\uf014',  # fog
            711: '\uf062',  # smoke
            721: '\uf0b6',  # haze
            731: '\uf063',  # dust
            741: '\uf014',  # fog
            751: '\uf063',  # dust
            761: '\uf063',  # dust
            762: '\uf0c7',  # volcanic
            771: '\uf050',  # strong-wind
            781: '\uf056',  # tornado
        }
        
        return neutral_map.get(weather_id, '\uf00d')  # fallback to day-sunny
    
    def _get_cached_data(self) -> Optional[Dict]:
        """キャッシュされたデータを取得"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # Cache expiry check
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01T00:00:00'))
                if datetime.now() - cache_time < timedelta(seconds=self.cache_duration):
                    logger.info(f"キャッシュからデータを取得: {cache_time}")
                    return cache_data
                else:
                    logger.info(f"キャッシュが期限切れです: {cache_time}")
        except Exception as e:
            logger.error(f"キャッシュ読み込みエラー: {e}")
        return None
    
    def _save_to_cache(self, data: Dict):
        """データをキャッシュに保存"""
        try:
            data['timestamp'] = datetime.now().isoformat()
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("データをキャッシュに保存しました")
        except Exception as e:
            logger.error(f"キャッシュ保存エラー: {e}")
    
    def _get_dominant_weather(self, forecast_list: list) -> Dict:
        """予報データから主要な天気を決定（優先度: 雨 > 雪 > 雷 > 曇り > 晴れ）"""
        priority_map = {
            'rain': 5, 'drizzle': 5,
            'snow': 4,
            'thunderstorm': 3,
            'clouds': 2,
            'clear': 1,
            'mist': 1, 'fog': 1, 'haze': 1, 'dust': 1, 'sand': 1, 'ash': 1, 'squall': 1, 'tornado': 1
        }
        
        max_priority = 0
        dominant_weather = None
        
        for forecast in forecast_list:
            weather_main = forecast['weather'][0]['main'].lower()
            priority = priority_map.get(weather_main, 0)
            
            if priority > max_priority:
                max_priority = priority
                dominant_weather = forecast
        
        return dominant_weather if dominant_weather else forecast_list[0]
    
    def _get_forecast_for_day(self, forecast_data: list, target_date: str) -> Dict:
        """指定日の予報データを取得"""
        day_forecasts = []
        
        for item in forecast_data:
            forecast_date = item['dt_txt'].split(' ')[0]
            if forecast_date == target_date:
                day_forecasts.append(item)
        
        if not day_forecasts:
            return {}
        
        # 主要天気を決定
        dominant = self._get_dominant_weather(day_forecasts)
        
        # 最高・最低気温を計算
        temps = [f['main']['temp'] for f in day_forecasts]
        
        # 降水確率の最大値
        rain_prob = max([f.get('pop', 0) * 100 for f in day_forecasts])
        
        return {
            'temp_max': round(max(temps)),
            'temp_min': round(min(temps)),
            'weather_id': dominant['weather'][0]['id'],
            'weather_description': dominant['weather'][0]['description'],
            'rain_probability': round(rain_prob)
        }
    
    def get_weather_data(self) -> Dict[str, Any]:
        """天気データを取得（キャッシュまたはAPI）"""
        
        # Try cache first
        cached_data = self._get_cached_data()
        if cached_data:
            return cached_data
        
        try:
            logger.info("OpenWeatherMap APIからデータを取得中...")
            
            # Current weather
            current_response = requests.get(self.current_api_url, timeout=10)
            current_response.raise_for_status()
            current_data = current_response.json()
            
            # 5-day forecast
            forecast_response = requests.get(self.forecast_api_url, timeout=10)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            now = datetime.now()
            
            # Current weather data
            current_temp = round(current_data['main']['temp'])
            current_weather_id = current_data['weather'][0]['id']
            current_icon = self._openweather_to_icon(current_weather_id, now)
            
            # 3-hour forecast data - 現在時刻より後の最初の予報を取得
            next_forecast = None
            forecast_3h_time = now + timedelta(hours=3)  # フォールバック
            
            for forecast in forecast_data['list']:
                forecast_time = datetime.fromisoformat(forecast['dt_txt'].replace(' ', 'T'))
                if forecast_time > now:
                    next_forecast = forecast
                    forecast_3h_time = forecast_time
                    break
            
            if not next_forecast:
                next_forecast = forecast_data['list'][0] if forecast_data['list'] else {}
                
            forecast_3h_temp = round(next_forecast['main']['temp']) if next_forecast else current_temp
            forecast_3h_weather_id = next_forecast['weather'][0]['id'] if next_forecast else current_weather_id
            forecast_3h_icon = self._openweather_to_icon(forecast_3h_weather_id, forecast_3h_time)
            forecast_3h_rain = round(next_forecast.get('pop', 0) * 100) if next_forecast else 0
            
            # Today's weather (remaining forecasts for today)
            today_str = now.strftime('%Y-%m-%d')
            today_forecast = self._get_forecast_for_day(forecast_data['list'], today_str)
            
            # If today's forecast is empty (late evening), use 3-hour forecast as fallback
            if not today_forecast:
                today_forecast = {
                    'temp_max': forecast_3h_temp,
                    'temp_min': forecast_3h_temp,
                    'weather_id': forecast_3h_weather_id,
                    'weather_description': next_forecast['weather'][0]['description'] if next_forecast else 'clear',
                    'rain_probability': round(next_forecast.get('pop', 0) * 100) if next_forecast else 0
                }
            
            # 今日・明日の予報はNeutralアイコンを使用
            today_icon = self._get_neutral_icon(today_forecast['weather_id'])
            
            # Tomorrow's weather - Neutralアイコンを使用
            tomorrow = now + timedelta(days=1)
            tomorrow_str = tomorrow.strftime('%Y-%m-%d')
            tomorrow_forecast = self._get_forecast_for_day(forecast_data['list'], tomorrow_str)
            tomorrow_icon = self._get_neutral_icon(tomorrow_forecast['weather_id']) if tomorrow_forecast else self._get_neutral_icon(800)
            
            weather_data = {
                'location': self.location_name,
                'current': {
                    'temperature': current_temp,
                    'weather_icon': current_icon,
                    'description': current_data['weather'][0]['description']
                },
                'forecast_3h': {
                    'temperature': forecast_3h_temp,
                    'weather_icon': forecast_3h_icon,
                    'time': forecast_3h_time.strftime('%H:%M'),
                    'rain_probability': forecast_3h_rain
                },
                'today': {
                    'temp_max': today_forecast.get('temp_max', current_temp),
                    'temp_min': today_forecast.get('temp_min', current_temp),
                    'weather_icon': today_icon,
                    'rain_probability': today_forecast.get('rain_probability', 0)
                },
                'tomorrow': {
                    'temp_max': tomorrow_forecast.get('temp_max', current_temp),
                    'temp_min': tomorrow_forecast.get('temp_min', current_temp),
                    'weather_icon': tomorrow_icon,
                    'rain_probability': tomorrow_forecast.get('rain_probability', 0)
                } if tomorrow_forecast else {
                    'temp_max': current_temp,
                    'temp_min': current_temp,
                    'weather_icon': tomorrow_icon,
                    'rain_probability': 0
                }
            }
            
            # Cache the data
            self._save_to_cache(weather_data)
            
            logger.info("天気データの取得が完了しました")
            return weather_data
            
        except requests.RequestException as e:
            logger.error(f"API呼び出しエラー: {e}")
            return self._get_fallback_data()
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return self._get_fallback_data()
    
    def get_display_data(self) -> Dict[str, Any]:
        """ダッシュボード用の天気データを取得（互換性メソッド）"""
        weather_data = self.get_weather_data()
        
        # ダッシュボードが期待する形式に変換
        return {
            # 現在天気
            'current_icon': weather_data['current']['weather_icon'],
            'current_location': weather_data['location'],
            'current_temp': weather_data['current']['temperature'],
            
            # 3時間後予報
            'next3h_time': weather_data['forecast_3h']['time'],
            'next3h_icon': weather_data['forecast_3h']['weather_icon'],
            'next3h_temp': weather_data['forecast_3h']['temperature'],
            'next3h_rain': weather_data['forecast_3h']['rain_probability'],
            
            # 今日・明日予報
            'today_high': weather_data['today']['temp_max'],
            'today_low': weather_data['today']['temp_min'],
            'today_icon': weather_data['today']['weather_icon'],
            'today_rain': weather_data['today']['rain_probability'],
            
            'tomorrow_high': weather_data['tomorrow']['temp_max'],
            'tomorrow_low': weather_data['tomorrow']['temp_min'],
            'tomorrow_icon': weather_data['tomorrow']['weather_icon'],
            'tomorrow_rain': weather_data['tomorrow']['rain_probability'],
            
            # 更新時刻
            'last_update': weather_data.get('last_update', datetime.now().strftime("%H:%M"))
        }
    
    def _get_fallback_data(self) -> Dict[str, Any]:
        """フォールバックデータ"""
        now = datetime.now()
        fallback_icon = self._openweather_to_icon(800, now)  # Clear sky
        
        return {
            'location': self.location_name,
            'current': {
                'temperature': 20,
                'weather_icon': fallback_icon,
                'description': 'データ取得エラー'
            },
            'forecast_3h': {
                'temperature': 19,
                'weather_icon': fallback_icon,
                'time': (now + timedelta(hours=3)).strftime('%H:%M')
            },
            'today': {
                'temp_max': 22,
                'temp_min': 18,
                'weather_icon': fallback_icon,
                'rain_probability': 0
            },
            'tomorrow': {
                'temp_max': 21,
                'temp_min': 17,
                'weather_icon': fallback_icon,
                'rain_probability': 0
            }
        }

def main():
    """テスト用メイン関数"""
    weather_api = WeatherLogic()
    
    # 現在時刻と夜間判定のテスト
    now = datetime.now()
    print(f"現在時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"夜間判定: {weather_api._is_nighttime(now)}")
    
    # 天気アイコンのテスト
    test_weather_id = 800  # Clear sky
    day_icon = weather_api._openweather_to_icon(test_weather_id, now)
    print(f"天気ID {test_weather_id} のアイコン: '{day_icon}'")
    
    # 夜間時刻でのテスト
    night_time = now.replace(hour=23)
    night_icon = weather_api._openweather_to_icon(test_weather_id, night_time)
    print(f"夜間時刻 {night_time.strftime('%H:%M')} のアイコン: '{night_icon}'")
    
    # 実際の天気データ取得
    weather_data = weather_api.get_weather_data()
    print("\n=== 天気データ ===")
    print(json.dumps(weather_data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()