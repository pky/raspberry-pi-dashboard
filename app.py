"""
Raspberry Pi Dashboard - Phase1完了版
Day14リダイレクト実装：既存app.pyから新実装web_apps/main_app.pyへ

計画書：FINAL_IMPLEMENTATION_PLAN_V2.md Day14
元実装：app_original.py にバックアップ済み
"""

import os
from web_apps.main_app import create_app

app = create_app()

if __name__ == '__main__':
    print("✅ Phase1完了：app.pyリダイレクト化実装")
    print("📂 元実装：app_original.py にバックアップ済み")
    print("🔄 新実装：web_apps/ モジュラー構成で稼働")
    print("🚀 起動中...")
    
    port = int(os.environ.get('FLASK_PORT', 5000))
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    app.run(host=host, port=port)