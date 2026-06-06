"""
Calendar API Blueprint
カレンダー関連のAPIエンドポイントを管理

要件: 1.1, 1.4, 1.5, 1.6
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from functools import wraps

# app.pyからの共通モジュールをインポート
from calendar_data import get_calendar_manager
from japanese_holidays import is_weekend_or_holiday, get_holiday_name
from error_handler import DashboardError, ErrorCode, ErrorLevel, get_error_handler
from logging_config import get_performance_logger

# ログ設定
logger = logging.getLogger(__name__)
performance_logger = get_performance_logger()
error_handler = get_error_handler()

# Blueprint作成
calendar_bp = Blueprint('calendar', __name__)

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
                    message=f"Calendar API endpoint error: {str(e)}",
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

@calendar_bp.route('/api/calendar')
@monitor_performance('calendar_data')
def get_calendar_data():
    """
    カレンダーAPI エンドポイント
    
    Query Parameters:
        year: 年 (デフォルト: 現在の年)
        month: 月 (デフォルト: 現在の月)
        monitor: 監視モード（軽量処理、デフォルト: false）
        
    Returns:
        JSON: 指定月のカレンダーデータ
        
    要件: 1.1, 1.4, 1.5 - 月指定でカレンダーデータを返すAPI
    """
    # クエリパラメータから年月を取得（デフォルトは現在の年月）
    now = datetime.now()
    year = request.args.get('year', default=now.year, type=int)
    month = request.args.get('month', default=now.month, type=int)
    monitor_mode = request.args.get('monitor', default='false', type=str).lower() == 'true'
    
    # パラメータの妥当性チェック（Noneチェックは不要、デフォルト値設定済み）
    if year is None or month is None:
        # この条件は通常発生しないが、type変換失敗時の安全策
        logger.warning(f"カレンダーパラメータ取得失敗、現在日時を使用: year={request.args.get('year')}, month={request.args.get('month')}")
        year = now.year
        month = now.month
    
    if not (1 <= month <= 12):
        raise DashboardError(
            message=f"Invalid month: {month}. Must be between 1 and 12.",
            error_code=ErrorCode.VALIDATION_ERROR,
            level=ErrorLevel.WARNING,
            context={'month': month}
        )
    
    if not (2020 <= year <= 2030):
        raise DashboardError(
            message=f"Invalid year: {year}. Must be between 2020 and 2030.",
            error_code=ErrorCode.VALIDATION_ERROR,
            level=ErrorLevel.WARNING,
            context={'year': year}
        )
    
    # カレンダーデータを取得（キャッシュ優先表示システムを使用）
    calendar_manager = get_calendar_manager()
    calendar_data = calendar_manager.get_month_events(year, month, use_cache_priority=True, monitor_mode=monitor_mode)
    
    # 土日祝日情報を追加（真の祝日のみ、個人予定は除外）
    if calendar_data['status'] == 'success' and 'calendar_data' in calendar_data and 'days' in calendar_data['calendar_data']:
        # Google Calendar APIから祝日を取得できているかチェック（統合判定）
        has_google_holidays = False
        google_holiday_events = []
        
        if calendar_data['status'] == 'success':
            # Method 1: google_events_countをチェック（calendar_data.pyからの情報）
            google_events_count = calendar_data.get('google_events_count', 0)
            
            # Method 2: 実際のイベントデータから祝日イベントをカウント
            if 'calendar_data' in calendar_data and 'days' in calendar_data['calendar_data']:
                google_holiday_events = [
                    event for day_data in calendar_data['calendar_data']['days'].values()
                    for event in day_data.get('events', [])
                    if isinstance(event, dict) and event.get('type') == 'japanese_holiday'
                ]
            
            # 統合判定: どちらかの方法で祝日が検出されればGoogle Calendar使用
            has_google_holidays = (google_events_count > 0) or (len(google_holiday_events) > 0)
            
            logger.info(f"Google祝日判定: google_events_count={google_events_count}, actual_events={len(google_holiday_events)}, has_google_holidays={has_google_holidays}")
        
        for day_num, day_data in calendar_data['calendar_data']['days'].items():
            date = datetime(year, month, int(day_num)).date()
            day_type = is_weekend_or_holiday(date)
            
            # 真の祝日判定（Google Calendar祝日データ + 固定祝日データ）
            google_holiday_name = None
            
            # Google Calendar APIから取得した祝日イベントをチェック
            for event in day_data.get('events', []):
                if isinstance(event, dict) and event.get('type') == 'japanese_holiday':
                    google_holiday_name = event.get('title')
                    break
            
            # 固定祝日データを常に取得（デバッグ用）
            fallback_holiday_name = get_holiday_name(date)
            
            # Google Calendar APIから祝日が取得できている場合は固定データを使用しない
            if has_google_holidays:
                true_holiday_name = google_holiday_name
            else:
                # Google Calendar APIから祝日が取得できない場合のみ固定データを使用
                true_holiday_name = google_holiday_name or fallback_holiday_name
            
            # 七夕など個人予定のデバッグ
            if month == 7 and int(day_num) == 7:
                logger.info(f"🎋 七夕判定: google_holiday_name={google_holiday_name}, fallback_holiday_name={fallback_holiday_name}, true_holiday_name={true_holiday_name}")
            
            # 真の祝日の場合のみis_holidayをtrueに設定
            if true_holiday_name:
                day_data['is_holiday'] = True
                day_data['holiday_name'] = true_holiday_name
            else:
                # 祝日でない場合はis_holidayをfalseに設定（但し、個人予定のイベントは保持）
                day_data['is_holiday'] = False
                day_data['holiday_name'] = None
                # 個人予定（events）はそのまま保持される
            
            day_data['day_type'] = day_type
    
    return jsonify({
        "holidays_count": calendar_data.get("holidays_count", 0),
        "google_events_count": calendar_data.get("google_events_count", 0),
        "month": month,
        "year": year,
        'status': calendar_data['status'],
        'timestamp': datetime.now().isoformat(),
        'data': calendar_data,
        'error': calendar_data.get('error')
    })

@calendar_bp.route('/api/calendar/today')
@monitor_performance('today_events')
def get_today_events():
    """
    今日のイベントAPI エンドポイント
    
    Returns:
        JSON: 今日のイベントデータ
    """
    calendar_manager = get_calendar_manager()
    today_data = calendar_manager.get_today_events()
    
    return jsonify({
        'status': today_data['status'],
        'timestamp': datetime.now().isoformat(),
        'data': today_data,
        'error': today_data.get('error')
    })

@calendar_bp.route('/api/calendar/priority')
@monitor_performance('calendar_priority')
def get_calendar_with_priority():
    """
    キャッシュ優先カレンダーAPI エンドポイント
    
    Query Parameters:
        year: 年 (デフォルト: 現在の年)
        month: 月 (デフォルト: 現在の月)
        
    Returns:
        JSON: キャッシュ優先カレンダーデータ
        
    要件: 1.6 - キャッシュ優先表示システム
    """
    # クエリパラメータから年月を取得
    now = datetime.now()
    year = request.args.get('year', default=now.year, type=int)
    month = request.args.get('month', default=now.month, type=int)
    
    # パラメータの妥当性チェック
    if not (1 <= month <= 12):
        return jsonify({
            'status': 'error',
            'error': f'Invalid month: {month}. Must be between 1 and 12.',
            'timestamp': datetime.now().isoformat()
        }), 400
    
    if not (2020 <= year <= 2030):
        return jsonify({
            'status': 'error',
            'error': f'Invalid year: {year}. Must be between 2020 and 2030.',
            'timestamp': datetime.now().isoformat()
        }), 400
    
    try:
        from calendar_cache_priority import get_calendar_cache_priority
        cache_priority = get_calendar_cache_priority()
        priority_data = cache_priority.get_calendar_with_cache_priority(year, month)
        
        return jsonify({
            'status': priority_data['status'],
            'timestamp': datetime.now().isoformat(),
            'data': priority_data,
            'error': priority_data.get('error')
        })
        
    except Exception as e:
        logger.error(f"キャッシュ優先カレンダー取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@calendar_bp.route('/api/calendar/cache-status')
@monitor_performance('calendar_cache_status')
def get_calendar_cache_status():
    """
    カレンダーキャッシュ状態API エンドポイント
    
    Query Parameters:
        year: 年 (デフォルト: 現在の年)
        month: 月 (デフォルト: 現在の月)
        
    Returns:
        JSON: キャッシュ状態情報
    """
    now = datetime.now()
    year = request.args.get('year', default=now.year, type=int)
    month = request.args.get('month', default=now.month, type=int)
    
    try:
        from calendar_cache_priority import get_calendar_cache_priority
        cache_priority = get_calendar_cache_priority()
        status = cache_priority.get_cache_priority_status(year, month)
        
        return jsonify({
            'status': 'success',
            'data': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"キャッシュ状態取得エラー: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500