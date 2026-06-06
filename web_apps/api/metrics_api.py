"""
Metrics API Blueprint
監視データ・メトリクス関連のAPIエンドポイントを管理

要件: SQLite直読みエンドポイント、監視データ履歴、キャッシュ統計
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from functools import wraps

# app.pyからの共通モジュールをインポート
from sensor import SHT35Sensor
from simple_system_monitor import get_simple_system_metrics
from monitoring_data_cache import get_monitoring_cache
from error_handler import DashboardError, ErrorCode, ErrorLevel, get_error_handler
from logging_config import get_performance_logger

# ログ設定
logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()
error_handler = get_error_handler()

# Blueprint作成
metrics_bp = Blueprint('metrics', __name__)

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
                    message=f"Metrics API endpoint error: {str(e)}",
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

@metrics_bp.route('/api/metrics/range/<range_type>')
@monitor_performance('metrics_range')
def get_metrics_by_range(range_type):
    """
    監視データをSQLiteから直接取得（新システム）
    JSONファイルを経由せず、SQLiteから直接Chart.js用データを生成
    
    Args:
        range_type (str): 時間範囲（1h, 6h, 12h, 24h）
        
    Returns:
        JSON: Chart.js用統合メトリクスデータ
    """
    try:
        # 時間範囲マッピング
        time_ranges = {
            '1h': 1,
            '6h': 6, 
            '12h': 12,
            '24h': 24
        }
        
        if range_type not in time_ranges:
            return jsonify({
                'status': 'error',
                'error': f'Invalid range_type: {range_type}. Must be one of: {", ".join(time_ranges.keys())}',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        hours = time_ranges[range_type]
        
        # センサーインスタンス取得
        sensor = SHT35Sensor()
        
        # CO2データをSQLiteから取得
        co2_data = sensor.get_co2_history(hours=hours)
        logger.debug(f"CO2データ取得: {len(co2_data)}件")
        
        # 温度・湿度データをSQLiteから取得
        temp_humidity_data = sensor.get_temp_humidity_history(hours=hours)
        logger.debug(f"温度・湿度データ取得: {len(temp_humidity_data)}件")
        
        # システムメトリクス取得（現在値）
        current_system = get_simple_system_metrics()
        
        # データ統合処理 - 最新値保持方式
        metrics = []
        
        # 全データを時系列でマージして最新値を保持
        # 全エントリを時系列順に統合
        all_entries = []
        
        # CO2データ追加
        for entry in co2_data:
            timestamp = entry.get('timestamp')
            if timestamp:
                all_entries.append({
                    'timestamp': timestamp,
                    'type': 'co2',
                    'co2_ppm': entry.get('co2_ppm', 0)
                })
        
        # 温度・湿度データ追加
        for entry in temp_humidity_data:
            timestamp = entry.get('timestamp')
            if timestamp:
                all_entries.append({
                    'timestamp': timestamp,
                    'type': 'temp_humidity',
                    'room_temperature': entry.get('temperature', 0),
                    'humidity': entry.get('humidity', 0)
                })
        
        # 時系列でソート
        all_entries.sort(key=lambda x: x['timestamp'])
        
        # 最新値保持でChart.js形式データ生成
        latest_co2 = 0
        latest_temp = 0
        latest_humidity = 0
        
        for entry in all_entries:
            # 最新値を更新
            if entry['type'] == 'co2':
                latest_co2 = entry.get('co2_ppm', latest_co2)
            elif entry['type'] == 'temp_humidity':
                latest_temp = entry.get('room_temperature', latest_temp)
                latest_humidity = entry.get('humidity', latest_humidity)
            
            # 統合メトリクスポイント作成（最新値使用）
            metric = {
                'timestamp': entry['timestamp'],
                'co2_ppm': latest_co2,
                'room_temperature': latest_temp,
                'humidity': latest_humidity,
                # システムメトリクスは現在値を使用（簡略化）
                'cpu_percent': current_system.get('cpu_percent', 0),
                'memory_percent': current_system.get('memory_percent', 0),
                'cpu_temperature': current_system.get('temperature', 0),
                'disk_used_gb': current_system.get('disk_used_gb', 0),
                'disk_percent': current_system.get('disk_percent', 0)
            }
            metrics.append(metric)
        
        # データがない場合のフォールバック
        if not metrics:
            logger.warning(f"SQLiteからデータが取得できませんでした: {range_type}")
            
            # 現在のセンサーデータでフォールバック
            current_sensor = sensor.get_sensor_data(enable_logging=False)  # API専用：ログ記録しない
            metrics = [{
                'timestamp': datetime.now().isoformat(),
                'co2_ppm': current_sensor.get('co2_ppm', 0),
                'room_temperature': current_sensor.get('temperature', 0),
                'humidity': current_sensor.get('humidity', 0),
                'cpu_percent': current_system.get('cpu_percent', 0),
                'memory_percent': current_system.get('memory_percent', 0),
                'cpu_temperature': current_system.get('temperature', 0),
                'disk_used_gb': current_system.get('disk_used_gb', 0),
                'disk_percent': current_system.get('disk_percent', 0)
            }]
        
        # Chart.js互換形式で返却
        response_data = {
            'metrics': metrics,
            'total_points': len(metrics),
            'time_range': range_type,
            'time_range_hours': hours,
            'data_source': 'sqlite_direct',
            'last_updated': datetime.now().isoformat()
        }
        
        logger.info(f"SQLite直読みメトリクス取得完了: {len(metrics)}ポイント ({range_type})")
        
        return jsonify({
            'status': 'success',
            'data': response_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"監視メトリクス取得エラー ({range_type}): {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'range_type': range_type,
            'timestamp': datetime.now().isoformat()
        }), 500

@metrics_bp.route('/api/metrics/history')
@monitor_performance('metrics_history')
def get_metrics_history():
    """
    システム監視データ履歴取得エンドポイント
    
    Query Parameters:
        timeRange (str): 時間範囲 ('1h', '6h', '12h', '24h')
    
    Returns:
        JSON: Chart.js用監視データ
    """
    try:
        time_range = request.args.get('timeRange', '1h')
        
        # バリデーション
        valid_ranges = ['1h', '6h', '12h', '24h']
        if time_range not in valid_ranges:
            return jsonify({
                'status': 'error',
                'error': f'Invalid timeRange. Must be one of: {valid_ranges}',
                'timestamp': datetime.now().isoformat()
            }), 400
        
        # キャッシュからデータ取得
        cache = get_monitoring_cache()
        data = cache.get_time_range_data(time_range)
        
        return jsonify({
            'status': 'success',
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"監視データ履歴取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@metrics_bp.route('/api/metrics/cache-stats')
@monitor_performance('metrics_cache_stats')
def get_metrics_cache_stats():
    """
    監視データキャッシュ統計情報取得エンドポイント
    
    Returns:
        JSON: キャッシュ統計情報
    """
    try:
        cache = get_monitoring_cache()
        stats = cache.get_cache_stats()
        
        return jsonify({
            'status': 'success',
            'data': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"キャッシュ統計取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500