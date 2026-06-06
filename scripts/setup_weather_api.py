#!/usr/bin/env python3
"""
OpenWeatherMap API セットアップスクリプト
安全なAPIキー管理のためのセットアップ
"""

import os
import sys
import configparser
from pathlib import Path

def setup_api_key():
    """OpenWeatherMap APIキーのセットアップ"""
    print("🌤️ OpenWeatherMap API セットアップ")
    print("=" * 50)
    
    # APIキーの入力
    print("OpenWeatherMap APIキーを入力してください:")
    print("(https://openweathermap.org/api で取得可能)")
    api_key = input("API Key: ").strip()
    
    if not api_key:
        print("❌ APIキーが入力されていません")
        return False
    
    # 設定ディレクトリの作成
    config_dir = Path(__file__).parent.parent / "config"
    config_dir.mkdir(exist_ok=True)
    
    # 設定ファイルの作成
    config_path = config_dir / "weather.conf"
    config = configparser.ConfigParser()
    
    config['openweather'] = {
        'api_key': api_key
    }
    
    config['location'] = {
        'name': os.environ.get('WEATHER_LOCATION_NAME', '渋谷区鶯谷町'),
        'latitude': os.environ.get('WEATHER_LATITUDE', '35.652875'),
        'longitude': os.environ.get('WEATHER_LONGITUDE', '139.701595')
    }
    
    config['cache'] = {
        'cache_duration': '1680'  # 28 minutes
    }
    
    config['security'] = {
        'log_api_key': 'false'
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        config.write(f)
    
    # ファイル権限を制限
    os.chmod(config_path, 0o600)  # 所有者のみ読み書き可能
    
    print(f"✅ 設定ファイルを作成しました: {config_path}")
    print(f"✅ ファイル権限を制限しました (600)")
    
    return True

def setup_environment_variable():
    """環境変数セットアップの案内"""
    print("\n🔒 より安全な環境変数設定 (推奨)")
    print("=" * 50)
    print("以下のコマンドで環境変数を設定できます:")
    print()
    print("# 一時的な設定:")
    print("export OPENWEATHER_API_KEY='your_api_key_here'")
    print()
    print("# 永続的な設定 (~/.bashrc に追加):")
    print("echo 'export OPENWEATHER_API_KEY=\"your_api_key_here\"' >> ~/.bashrc")
    print("source ~/.bashrc")
    print()

def test_api_connection():
    """API接続テスト"""
    print("\n🧪 API接続テスト")
    print("=" * 30)
    
    try:
        # WeatherLogicをインポートしてテスト
        sys.path.append(str(Path(__file__).parent.parent))
        from logic.weather_logic import WeatherLogic
        
        weather = WeatherLogic()
        test_result = weather.test_api_connection()
        
        if test_result['success']:
            print("✅ API接続テスト成功!")
            print(f"   応答時間: {test_result['response_time_ms']}ms")
            print(f"   データサイズ: {test_result.get('data_size_kb', 'N/A')}KB")
        else:
            print("❌ API接続テスト失敗")
            print(f"   エラー: {test_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")

def main():
    """メイン実行"""
    print("🚀 OpenWeatherMap API Setup Script")
    print("=" * 50)
    
    # セットアップ方法の選択
    print("セットアップ方法を選択してください:")
    print("1) 設定ファイル (credentials/weather.conf)")
    print("2) 環境変数の案内のみ")
    print("3) API接続テストのみ")
    
    choice = input("選択 [1-3]: ").strip()
    
    if choice == "1":
        success = setup_api_key()
        if success:
            setup_environment_variable()
            test_api_connection()
    elif choice == "2":
        setup_environment_variable()
    elif choice == "3":
        test_api_connection()
    else:
        print("❌ 無効な選択です")
        return False
    
    print("\n🎉 セットアップ完了!")
    print("weather_logic.py でOpenWeatherMap APIが使用できるようになりました")
    
    return True

if __name__ == "__main__":
    main()