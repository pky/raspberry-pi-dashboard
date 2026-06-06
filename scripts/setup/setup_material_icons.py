#!/usr/bin/env python3
"""
Google Material Icons フォントのセットアップスクリプト
"""

import os
import urllib.request
import zipfile
import shutil

def download_material_icons():
    """Material Iconsフォントをダウンロード"""
    
    # アイコンディレクトリ作成
    icons_dir = "icons"
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
        print(f"✅ {icons_dir}ディレクトリを作成しました")
    
    # Material Icons フォントURL (Google Fonts CDN)
    font_urls = {
        "MaterialIcons-Regular.ttf": "https://github.com/google/material-design-icons/raw/master/font/MaterialIcons-Regular.ttf",
        "MaterialIconsOutlined-Regular.otf": "https://github.com/google/material-design-icons/raw/master/font/MaterialIconsOutlined-Regular.otf",
        "MaterialIconsRound-Regular.otf": "https://github.com/google/material-design-icons/raw/master/font/MaterialIconsRound-Regular.otf",
        "MaterialIconsSharp-Regular.otf": "https://github.com/google/material-design-icons/raw/master/font/MaterialIconsSharp-Regular.otf",
        "MaterialIconsTwoTone-Regular.otf": "https://github.com/google/material-design-icons/raw/master/font/MaterialIconsTwoTone-Regular.otf"
    }
    
    # 基本のMaterial Iconsフォントをダウンロード
    main_font = "MaterialIcons-Regular.ttf"
    font_path = os.path.join(icons_dir, main_font)
    
    if not os.path.exists(font_path):
        print(f"📥 {main_font}をダウンロード中...")
        try:
            urllib.request.urlretrieve(font_urls[main_font], font_path)
            print(f"✅ {main_font}をダウンロードしました")
        except Exception as e:
            print(f"❌ ダウンロードエラー: {e}")
            print("代替方法: Material Symbols変数フォントを使用します")
            
            # Material Symbols変数フォント（最新版）
            symbols_url = "https://github.com/google/material-design-icons/raw/master/variablefont/MaterialSymbolsOutlined%5BFILL%2CGRAD%2Copsz%2Cwght%5D.ttf"
            symbols_font = "MaterialSymbolsOutlined.ttf"
            symbols_path = os.path.join(icons_dir, symbols_font)
            
            try:
                urllib.request.urlretrieve(symbols_url, symbols_path)
                print(f"✅ {symbols_font}をダウンロードしました")
            except Exception as e2:
                print(f"❌ 代替フォントのダウンロードも失敗: {e2}")
                return False
    else:
        print(f"✅ {main_font}は既に存在します")
    
    # コードポイントマッピングファイルを作成
    create_icon_mappings(icons_dir)
    
    return True

def create_icon_mappings(icons_dir):
    """Material Iconsのコードポイントマッピングを作成"""
    
    # よく使うアイコンのコードポイント
    icon_mappings = {
        # 温度関連
        "thermostat": "\ue1ff",
        "device_thermostat": "\ue1ff",
        "thermostat_auto": "\uf076",
        
        # 湿度関連
        "water_drop": "\ue798",
        "opacity": "\ue91c",
        "water": "\uf084",
        "humidity_percentage": "\uf87e",
        
        # 感情・快適度関連
        "sentiment_very_satisfied": "\ue815",
        "sentiment_satisfied": "\ue813",
        "sentiment_neutral": "\ue812",
        "sentiment_dissatisfied": "\ue811",
        "sentiment_very_dissatisfied": "\ue814",
        "mood": "\ue7f2",
        "mood_bad": "\ue7f3",
        
        # その他センサー関連
        "sensors": "\ue51e",
        "dashboard": "\ue871",
        "speed": "\ue9e4",
        "air": "\eefd8",
        
        # 天気関連（追加用）
        "wb_sunny": "\ue80b",
        "wb_cloudy": "\ue80d",
        "cloud": "\ue2bd",
        "ac_unit": "\ueb3b",  # エアコン・冷房
        "whatshot": "\ue80e",  # 暖房・炎
    }
    
    # マッピングファイルを保存
    mapping_file = os.path.join(icons_dir, "icon_mappings.py")
    with open(mapping_file, "w", encoding="utf-8") as f:
        f.write('"""Material Icons コードポイントマッピング"""\n\n')
        f.write("MATERIAL_ICONS = {\n")
        for name, codepoint in icon_mappings.items():
            f.write(f'    "{name}": "{codepoint}",\n')
        f.write("}\n")
    
    print(f"✅ アイコンマッピングファイルを作成しました: {mapping_file}")

if __name__ == "__main__":
    print("🚀 Material Iconsフォントのセットアップを開始します")
    if download_material_icons():
        print("\n✅ セットアップが完了しました！")
        print("\n使用方法:")
        print("1. PyQt5でフォントをロード: QFontDatabase.addApplicationFont('icons/MaterialIcons-Regular.ttf')")
        print("2. フォントを設定: QFont('Material Icons', 48)")
        print("3. アイコンを表示: QLabel('\\ue1ff')  # thermostatアイコン")
    else:
        print("\n❌ セットアップに失敗しました")