"""
CO2 API Blueprint
CO2センサー関連のAPIエンドポイントを管理

要件: CO2履歴、アラート、サマリー、エクスポート機能
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
from functools import wraps

# app.pyからの共通モジュールをインポート
from sensor import SHT35Sensor
from error_handler import DashboardError, ErrorCode, ErrorLevel, get_error_handler
from logging_config import get_performance_logger

# ログ設定
logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()
error_handler = get_error_handler()

# Blueprint作成
co2_bp = Blueprint('co2', __name__)

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
                    message=f"CO2 API endpoint error: {str(e)}",
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

@co2_bp.route('/api/co2/history')
@monitor_performance('co2_history')
def get_co2_history():
    """
    CO2履歴データ取得エンドポイント
    
    Query Parameters:
        hours (int): 取得する時間範囲（デフォルト: 24時間）
    
    Returns:
        JSON: CO2履歴データ
    """
    try:
        hours = int(request.args.get('hours', 24))
        if hours <= 0 or hours > 168:  # 最大1週間
            hours = 24
        
        sensor = SHT35Sensor()
        history_data = sensor.get_co2_history(hours=hours)
        
        return jsonify({
            'status': 'success',
            'data': {
                'history': history_data,
                'hours': hours,
                'count': len(history_data)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"CO2履歴取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@co2_bp.route('/api/co2/alerts')
@monitor_performance('co2_alerts')
def get_co2_alerts():
    """
    CO2アラート履歴取得エンドポイント
    
    Query Parameters:
        days (int): 取得する日数範囲（デフォルト: 7日）
        resolved (bool): 解決済みアラートも含むか（デフォルト: false）
    
    Returns:
        JSON: CO2アラート履歴
    """
    try:
        days = int(request.args.get('days', 7))
        # resolved = request.args.get('resolved', 'false').lower() == 'true'  # 将来の拡張用
        
        if days <= 0 or days > 30:  # 最大1ヶ月
            days = 7
        
        sensor = SHT35Sensor()
        alerts_data = sensor.get_co2_alerts(days=days)
        
        return jsonify({
            'status': 'success',
            'data': {
                'alerts': alerts_data,
                'days': days,
                'count': len(alerts_data)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"CO2アラート取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@co2_bp.route('/api/co2/summary')
@monitor_performance('co2_summary')
def get_co2_summary():
    """
    CO2日次サマリー取得エンドポイント
    
    Query Parameters:
        date (str): 対象日（YYYY-MM-DD形式、デフォルト: 今日）
    
    Returns:
        JSON: CO2日次サマリー
    """
    try:
        date = request.args.get('date')
        
        sensor = SHT35Sensor()
        summary_data = sensor.get_co2_daily_summary(date=date)
        
        return jsonify({
            'status': 'success',
            'data': summary_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"CO2サマリー取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@co2_bp.route('/api/co2/export')
@monitor_performance('co2_export')
def export_co2_data():
    """
    CO2データCSVエクスポートエンドポイント
    
    Query Parameters:
        start_date (str): 開始日（YYYY-MM-DD形式、必須）
        end_date (str): 終了日（YYYY-MM-DD形式、必須）
    
    Returns:
        CSV: CO2データファイル
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({
                'status': 'error',
                'error': 'start_date and end_date are required',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        sensor = SHT35Sensor()
        csv_file = sensor.export_co2_data(start_date, end_date)
        
        if csv_file:
            return send_file(csv_file, as_attachment=True, 
                           download_name=f'co2_data_{start_date}_to_{end_date}.csv')
        else:
            return jsonify({
                'status': 'error',
                'error': 'Failed to export data',
                'timestamp': datetime.now().isoformat()
            }), 500
            
    except Exception as e:
        logger.error(f"CO2エクスポートエラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500