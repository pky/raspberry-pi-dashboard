"""
ダッシュボードルート Blueprint
既存app.pyのメインダッシュボード機能を抽出・Blueprint化

機能:
- / (index)
- /backup
- /health
- /static/<path:filename>
"""

from flask import Blueprint, render_template, jsonify, send_from_directory, current_app
import logging

# 既存app.pyからインポート
from simple_system_monitor import get_simple_health_status

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

@dashboard_bp.route('/')
def index():
    """
    メインページ
    既存app.pyから移植
    
    Returns:
        HTML: ダッシュボードのメインページ
        
    要件: 3.1 - メインページの表示
    """
    return render_template('index.html')

@dashboard_bp.route('/backup')
def backup_manager():
    """
    バックアップ管理画面
    既存app.pyから移植
    
    Returns:
        HTML: バックアップ管理画面
    """
    return render_template('backup_manager.html')

@dashboard_bp.route('/health-detail')
def health_detail():
    """
    詳細ヘルスチェックエンドポイント
    既存app.pyから移植（パス変更でmain_app.pyの/healthと競合回避）
    
    Returns:
        JSON: システムの詳細状態情報
    """
    return jsonify(get_simple_health_status())

@dashboard_bp.route('/static/<path:filename>')
def static_files(filename):
    """
    静的ファイル配信
    既存app.pyから移植
    
    Args:
        filename: ファイル名
        
    Returns:
        File: 静的ファイル
        
    要件: 3.2 - 静的ファイル配信
    """
    try:
        return send_from_directory(current_app.static_folder, filename)
    except Exception as e:
        logger.error(f"Static file error: {e}")
        return jsonify({'error': 'File not found'}), 404

@dashboard_bp.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found'
    }), 404

@dashboard_bp.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An internal error occurred'
    }), 500