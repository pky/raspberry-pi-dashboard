"""
システム監視アプリケーション Blueprint
既存app.pyのシステム監視機能を抽出・Blueprint化

監視機能:
- /system_monitor.html
- システムメトリクス取得
- パフォーマンス監視
"""

from flask import Blueprint, render_template, jsonify, send_file
import logging
import os

# 既存app.pyからインポート
from simple_system_monitor import get_simple_system_metrics, get_simple_health_status

monitor_bp = Blueprint('monitoring', __name__)
logger = logging.getLogger(__name__)

@monitor_bp.route('/system_monitor.html')
def system_monitor():
    """
    システム監視管理画面の表示
    既存app.pyから移植
    
    Returns:
        HTML: システム監視管理画面
    """
    # templatesディレクトリから読み込み
    return render_template('system_monitor.html')

@monitor_bp.route('/api/system/monitor/health')
def get_system_health():
    """
    システムヘルス状態取得
    
    Returns:
        JSON: システムヘルス状態
    """
    try:
        health_status = get_simple_health_status()
        return jsonify({
            'status': 'success',
            'data': health_status,
            'timestamp': get_simple_system_metrics().get('timestamp', '')
        })
    except Exception as e:
        logger.error(f"システムヘルス取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@monitor_bp.route('/api/system/monitor/metrics')
def get_system_monitoring_metrics():
    """
    システム監視メトリクス取得
    
    Returns:
        JSON: システムメトリクス
    """
    try:
        metrics = get_simple_system_metrics()
        return jsonify({
            'status': 'success',
            'data': metrics,
            'timestamp': metrics.get('timestamp', '')
        })
    except Exception as e:
        logger.error(f"システム監視メトリクス取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500