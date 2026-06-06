"""
SSD API Blueprint
M.2 SSD健康状態・SMART関連のAPIエンドポイントを管理

要件: SSD健康状態、ヘルステスト、SMART履歴
"""

import logging
import json
from datetime import datetime
from flask import Blueprint, jsonify
from functools import wraps

# app.pyからの共通モジュールをインポート
from error_handler import DashboardError, ErrorCode, ErrorLevel, get_error_handler
from logging_config import get_performance_logger

# ログ設定
logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()
error_handler = get_error_handler()

# Blueprint作成
ssd_bp = Blueprint('ssd', __name__)

def monitor_performance(endpoint_name=None):
    """
    API パフォーマンス監視デコレーター
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            status_code = 200
            error_occurred = False
            
            try:
                result = func(*args, **kwargs)
                
                # Flaskレスポンスオブジェクトからステータスコードを取得
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                elif isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                
                return result
                
            except Exception as e:
                error_occurred = True
                status_code = 500
                
                # エラーハンドリング
                dashboard_error = DashboardError(
                    message=f"SSD API endpoint error: {str(e)}",
                    error_code=ErrorCode.API_INTERNAL_ERROR,
                    level=ErrorLevel.ERROR,
                    context={'endpoint': endpoint_name or func.__name__},
                    original_exception=e
                )
                
                error_handler.handle_error(dashboard_error, reraise=False)
                
                return jsonify({
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
                
            finally:
                # パフォーマンスログ記録
                duration = time.time() - start_time
                performance_logger.log_api_performance(
                    endpoint=endpoint_name or func.__name__,
                    duration=duration,
                    status_code=status_code,
                    error_occurred=error_occurred
                )
        
        return wrapper
    return decorator

@ssd_bp.route('/api/ssd/health')
@monitor_performance('ssd_health')
def get_ssd_health():
    """
    M.2 SSD健康状態取得エンドポイント
    
    Returns:
        JSON: SSD健康状態情報
    """
    try:
        from scripts.ssd_management.ssd_health_check import SSDHealthChecker
        
        checker = SSDHealthChecker()
        health_status = checker.get_latest_health_status()
        
        if health_status:
            return jsonify({
                'status': 'success',
                'data': health_status,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'no_data',
                'message': 'SSD健康状態データが見つかりません',
                'timestamp': datetime.now().isoformat()
            }), 404
    
    except Exception as e:
        logger.error(f"SSD健康状態取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@ssd_bp.route('/api/ssd/test', methods=['POST'])
@monitor_performance('ssd_test')
def run_ssd_health_test():
    """
    M.2 SSDヘルステスト実行エンドポイント
    
    Returns:
        JSON: テスト実行結果
    """
    try:
        from scripts.ssd_management.ssd_health_check import SSDHealthChecker
        
        # force = request.json.get('force', False) if request.is_json else False  # 将来の拡張用
        
        checker = SSDHealthChecker()
        test_result = checker.run_comprehensive_test()
        
        # テスト結果を保存
        if test_result['success']:
            checker.save_health_status(test_result)
        
        return jsonify({
            'status': 'success' if test_result['success'] else 'error',
            'data': test_result,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"SSDヘルステスト実行エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@ssd_bp.route('/api/ssd/smart-history')
@monitor_performance('ssd_smart_history')
def get_ssd_smart_history():
    """
    M.2 SSD SMART履歴取得エンドポイント
    
    Returns:
        JSON: SMART履歴データ
    """
    try:
        from scripts.ssd_management.ssd_health_check import SSDHealthChecker
        
        checker = SSDHealthChecker()
        history = []
        
        if checker.smart_history_file.exists():
            with open(checker.smart_history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        
        # 最新10件に制限
        recent_history = history[-10:] if len(history) > 10 else history
        
        return jsonify({
            'status': 'success',
            'data': {
                'history': recent_history,
                'total_count': len(history)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"SSD SMART履歴取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500