"""
Sensor API Blueprint
センサーデータ取得・収集関連のAPIエンドポイント

既存app.pyからの関数移植・Blueprint化
"""

import time
from datetime import datetime
from flask import Blueprint, jsonify
from functools import wraps

from sensor import get_sensor
from logging_config import get_performance_logger

import logging
logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()

# Blueprintの作成
sensor_bp = Blueprint('sensor', __name__)

def monitor_performance(endpoint_name=None):
    """
    API パフォーマンス監視デコレーター
    既存app.pyから移植（正確な形式）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
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
                raise e
                
            finally:
                # パフォーマンスログ記録
                duration = time.time() - start_time
                if performance_logger:
                    performance_logger.log_api_performance(
                        endpoint=endpoint_name or func.__name__,
                        duration=duration,
                        status_code=status_code,
                        error_occurred=error_occurred
                    )
        
        return wrapper
    return decorator

@sensor_bp.route('/api/sensor')
@monitor_performance('sensor_data')
def get_sensor_data():
    """
    センサーデータAPI エンドポイント
    既存app.pyから移植
    
    Returns:
        JSON: 温湿度、不快度指数、CO2濃度データ
        
    要件: 2.5, 5.1, 7.1 - センサーデータをJSON形式で返すAPI
    """
    sensor = get_sensor()
    sensor_data = sensor.get_sensor_data(enable_logging=False)  # API専用：ログ記録しない
    
    return jsonify({
        'status': sensor_data.get('status', 'success'),
        'timestamp': datetime.now().isoformat(),
        'data': sensor_data,
        'error': sensor_data.get('error')
    })

@sensor_bp.route('/api/sensor/collect')
@monitor_performance('sensor_data_collect')
def collect_sensor_data():
    """
    センサーデータ収集エンドポイント（記録あり）
    既存app.pyから移植
    
    APIサーバー内蔵方式でセンサーデータを収集・記録する
    5分間隔でcronから呼び出される想定
    
    Returns:
        JSON: 収集・記録されたセンサーデータ
        
    要件: センサーデータ収集復旧 - APIサーバー内蔵方式
    """
    try:
        sensor = get_sensor()
        sensor_data = sensor.get_sensor_data(enable_logging=True)  # ログ記録を有効化
        
        # monitoring_collector.pyが読み込むためのログファイル記録処理
        if sensor_data.get('status') == 'success':
            try:
                # CO2データ記録：SQLite削除、JSONログ統合システム使用
                if 'co2_ppm' in sensor_data:
                    # CO2Logger削除: monitoring_collector.pyのJSONログに統一
                    logger.info(f"CO2データ取得: {sensor_data['co2_ppm']}ppm (JSONログ統合システム使用)")
                
                # 温度・湿度ログファイルに記録
                if 'temperature' in sensor_data and 'humidity' in sensor_data:
                    from temperature_humidity_logger import TemperatureHumidityLogger
                    temp_logger = TemperatureHumidityLogger()
                    temp_logger.log_data(
                        temperature=sensor_data['temperature'],
                        humidity=sensor_data['humidity']
                    )
                    logger.info(f"温湿度データ記録: 温度{sensor_data['temperature']}°C, 湿度{sensor_data['humidity']}%")
                    
            except Exception as log_error:
                logger.warning(f"センサーデータ記録エラー（データ取得は成功）: {log_error}")
        
        return jsonify({
            'status': sensor_data.get('status', 'success'),
            'timestamp': datetime.now().isoformat(),
            'data': sensor_data,
            'error': sensor_data.get('error')
        })
        
    except Exception as e:
        logger.error(f"センサーデータ収集エラー: {e}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': f"センサーデータ収集に失敗しました: {str(e)}"
        }), 500