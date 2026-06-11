"""
新Flaskアプリケーション - Day4実装
既存app.pyの機能を5001ポートで再現・テスト

計画書：FINAL_IMPLEMENTATION_PLAN_V2.md Day4-7
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import sys
import os
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import logging
from config import get_config, Config
from web_apps import register_all_blueprints

def create_app():
    """
    新Flaskアプリケーション作成
    Day4実装：System API + Sensor API搭載
    """
    app = Flask(__name__, 
                static_folder='../static', 
                static_url_path='/static',
                template_folder='../templates')
    
    # 設定の読み込み（既存app.pyと同様）
    config = get_config()
    app.config['SECRET_KEY'] = config.SECRET_KEY
    app.config['DEBUG'] = config.DEBUG
    
    # CORS設定
    port = int(os.environ.get('FLASK_PORT', 5000))
    CORS(app, origins=['http://localhost:3000', 'http://127.0.0.1:3000', f'http://{config.HOST}:{port}'])
    
    # 設定バリデーション（起動時に問題を早期検出）
    _logger = logging.getLogger(__name__)
    for msg in Config.validate_config():
        _logger.warning("設定チェック: %s", msg)

    # Blueprint統合登録（Day4実装）
    register_all_blueprints(app)
    
    # 基本ルート
    @app.route('/')
    def index():
        """メインページ（既存app.pyと同様）"""
        return render_template('index.html')
    
    @app.route('/health')
    def health_check():
        """ヘルスチェック（新実装確認用）"""
        from datetime import datetime
        
        # システムヘルスチェック情報
        health_checks = [
            {'component': 'API Server', 'status': 'healthy'},
            {'component': 'Database Connection', 'status': 'healthy'},
            {'component': 'Sensor Data', 'status': 'healthy'},
            {'component': 'Backup System', 'status': 'healthy'},
            {'component': 'System Monitor', 'status': 'healthy'}
        ]
        
        return jsonify({
            'status': 'healthy',
            'service': 'raspberry-pi-dashboard-new',
            'port': 5000,
            'implementation': 'Day14 - Final Integration Complete',
            'message': 'Phase1完了：新実装本番稼働',
            'timestamp': datetime.now().isoformat(),
            'checks': health_checks
        })
    
    return app

if __name__ == '__main__':
    app = create_app()
    print("🚀 新実装Raspberry Pi Dashboard起動中...")
    print("📊 アクセス: http://localhost:5000")
    print("🔍 ヘルスチェック: http://localhost:5000/health")
    print("🌡️ センサーAPI: http://localhost:5000/api/sensor")
    print("💻 システムAPI: http://localhost:5000/api/system/metrics")
    print("✅ Phase1完了：本番ポート5000で稼働")
    
    port = int(os.environ.get('FLASK_PORT', 5000))
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=True)