#!/usr/bin/env python3
"""
カレンダーキャッシュ優先表示システム
要件1.6: 期限切れキャッシュでも祝日データと組み合わせて優先表示し、
         API失敗時も過去のキャッシュと祝日データで表示する
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import copy
from logging_system import get_logger

logger = logging.getLogger(__name__)

class CalendarCachePriority:
    """
    カレンダーキャッシュ優先表示システム
    
    機能:
    1. 期限切れキャッシュでも祝日データと組み合わせて先行表示
    2. API取得成功時に表示を更新
    3. API失敗時も過去のキャッシュ + 祝日データで表示継続
    """
    
    def __init__(self, cache_dir: str = "cache/calendar_priority"):
        """初期化"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 標準キャッシュとの連携（シングルトンパターンで重複初期化を防止）
        self._personal_cache = None
        self._holiday_cache = None
        
        logger.info("カレンダーキャッシュ優先システムが初期化されました")
    
    @property
    def personal_cache(self):
        """個人イベントキャッシュの遅延初期化"""
        if self._personal_cache is None:
            from personal_events_cache import get_personal_events_cache
            self._personal_cache = get_personal_events_cache()
        return self._personal_cache
    
    @property
    def holiday_cache(self):
        """祝日キャッシュの遅延初期化"""
        if self._holiday_cache is None:
            from holiday_cache import get_holiday_cache
            self._holiday_cache = get_holiday_cache()
        return self._holiday_cache
    
    def get_priority_cache_file(self, year: int, month: int) -> Path:
        """優先キャッシュファイルのパスを取得"""
        return self.cache_dir / f"priority_calendar_{year}_{month:02d}.json"
    
    def get_calendar_with_cache_priority(self, year: int, month: int, monitor_mode: bool = False) -> Dict[str, Any]:
        """
        キャッシュ優先でカレンダーデータを取得
        
        処理順序:
        1. 期限切れでもキャッシュ + 祝日データで先行表示
        2. API取得を並行実行（非ブロッキング）
        3. API成功時に表示更新、失敗時は既存表示を維持
        
        Args:
            year: 年
            month: 月
            
        Returns:
            Dict: カレンダーデータ（cache_priority_status付き）
        """
        try:
            # Step 1: 期限切れでもキャッシュから先行表示データを構築
            cache_display_data = self._build_cache_first_display(year, month)
            
            # Step 2: API取得を試行（タイムアウトあり）
            api_success = False
            api_data = None
            
            try:
                api_data = self._fetch_api_data_with_timeout(year, month, timeout_seconds=5, monitor_mode=monitor_mode)
                if api_data and api_data.get('status') == 'success':
                    api_success = True
                    logger.info(f"API取得成功: {year}年{month}月")
                else:
                    logger.warning(f"API取得失敗またはエラー: {year}年{month}月")
            except Exception as e:
                logger.warning(f"API取得で例外発生: {e}")
            
            # Step 3: 結果の統合
            if api_success:
                # API成功時: 新しいデータで表示更新
                final_data = api_data
                final_data['cache_priority_status'] = {
                    'display_source': 'api_fresh',
                    'cache_available': len(cache_display_data.get('events', [])) > 0,
                    'api_success': True,
                    'fallback_used': False
                }
                
                # 新しいデータを優先キャッシュに保存
                self._save_priority_cache(year, month, final_data)
                
            else:
                # API失敗時: キャッシュ + 祝日データで表示継続
                final_data = cache_display_data
                final_data['cache_priority_status'] = {
                    'display_source': 'cache_priority',
                    'cache_available': len(cache_display_data.get('events', [])) > 0,
                    'api_success': False,
                    'fallback_used': True,
                    'api_error': getattr(api_data, 'error', None) if api_data else 'API call failed'
                }
            
            logger.info(f"キャッシュ優先表示完了: {year}年{month}月 - {final_data['cache_priority_status']['display_source']}")
            return final_data
            
        except Exception as e:
            logger.error(f"キャッシュ優先表示でエラー: {e}")
            # 完全フォールバック: 最低限の祝日データのみ
            return self._build_minimal_fallback(year, month, error=str(e))
    
    def _build_cache_first_display(self, year: int, month: int) -> Dict[str, Any]:
        """
        期限切れでもキャッシュ + 祝日データで先行表示データを構築
        """
        try:
            # 1. 個人予定キャッシュを読み込み（期限チェックなし）
            cached_events = self._load_expired_cache_events(year, month)
            
            # 2. 祝日データを取得（常に利用可能）
            holidays = self.holiday_cache.get_holidays_for_month(year, month)
            
            # 3. カレンダーデータを構築（シングルトンパターン使用）
            from calendar_data import get_calendar_manager
            manager = get_calendar_manager()
            calendar_data = manager._build_calendar_data(year, month, cached_events, holidays)
            
            return {
                'status': 'success',
                'year': year,
                'month': month,
                'calendar_data': calendar_data,
                'google_events_count': len(cached_events),
                'holidays_count': len(holidays),
                'data_source': 'cache_first',
                'cache_expired': not self.personal_cache.is_cache_valid(
                    self.personal_cache.get_cache_file_path(year, month)
                ),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"キャッシュファーストディスプレイ構築エラー: {e}")
            return self._build_minimal_fallback(year, month, error=str(e))
    
    def _load_expired_cache_events(self, year: int, month: int) -> List[Dict]:
        """
        期限切れでもキャッシュから個人予定を読み込み
        """
        cache_file = self.personal_cache.get_cache_file_path(year, month)
        
        if not cache_file.exists():
            logger.info(f"個人予定キャッシュファイル未存在: {year}年{month}月")
            return []
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            events = data.get('events', [])
            cached_at = data.get('cached_at', '')
            
            # 期限切れチェック
            if cached_at:
                cache_time = datetime.fromisoformat(cached_at)
                age_hours = (datetime.now() - cache_time).total_seconds() / 3600
                logger.info(f"期限切れキャッシュから個人予定を読み込み: {year}年{month}月 - {len(events)}件 (経過時間: {age_hours:.1f}時間)")
            else:
                logger.info(f"期限切れキャッシュから個人予定を読み込み: {year}年{month}月 - {len(events)}件")
            
            return events
            
        except Exception as e:
            logger.error(f"期限切れキャッシュ読み込みエラー: {e}")
            return []
    
    def _fetch_api_data_with_timeout(self, year: int, month: int, timeout_seconds: int = 5, monitor_mode: bool = False) -> Optional[Dict]:
        """
        タイムアウト付きでAPI データを取得
        """
        import threading
        import time

        result = {'data': None, 'completed': False}

        def api_call():
            try:
                from calendar_data import get_calendar_manager
                manager = get_calendar_manager()
                # キャッシュ優先システム内でのAPI呼び出しは標準モードを使用（無限ループ防止）
                result['data'] = manager.get_month_events(year, month, use_cache_priority=False, monitor_mode=monitor_mode)
                result['completed'] = True
            except Exception as e:
                logger.error(f"API呼び出しエラー: {e}")
                result['data'] = {'status': 'error', 'error': str(e)}
                result['completed'] = True
        
        # 別スレッドでAPI呼び出し実行
        thread = threading.Thread(target=api_call)
        thread.daemon = True
        thread.start()
        
        # タイムアウト待機
        thread.join(timeout=timeout_seconds)
        
        if result['completed']:
            return result['data']
        else:
            logger.warning(f"API呼び出しタイムアウト ({timeout_seconds}秒)")
            return None
    
    def _build_minimal_fallback(self, year: int, month: int, error: str = None) -> Dict[str, Any]:
        """
        最小フォールバック: 祝日データのみでカレンダーを表示
        """
        try:
            # 祝日データのみ取得
            holidays = self.holiday_cache.get_holidays_for_month(year, month)
            
            # 最小カレンダーデータ構築（シングルトンパターン使用）
            from calendar_data import get_calendar_manager
            manager = get_calendar_manager()
            calendar_data = manager._build_calendar_data(year, month, [], holidays)
            
            return {
                'status': 'fallback',
                'year': year,
                'month': month,
                'calendar_data': calendar_data,
                'google_events_count': 0,
                'holidays_count': len(holidays),
                'data_source': 'minimal_fallback',
                'error': error,
                'cache_priority_status': {
                    'display_source': 'minimal_fallback',
                    'cache_available': False,
                    'api_success': False,
                    'fallback_used': True,
                    'fallback_reason': error
                }
            }
            
        except Exception as e:
            logger.error(f"最小フォールバック構築エラー: {e}")
            return {
                'status': 'error',
                'year': year,
                'month': month,
                'error': f"Complete fallback failed: {e}",
                'cache_priority_status': {
                    'display_source': 'error',
                    'cache_available': False,
                    'api_success': False,
                    'fallback_used': False
                }
            }
    
    def _save_priority_cache(self, year: int, month: int, data: Dict[str, Any]):
        """
        優先キャッシュにデータを保存
        """
        try:
            cache_file = self.get_priority_cache_file(year, month)
            
            cache_data = {
                'year': year,
                'month': month,
                'cached_at': datetime.now().isoformat(),
                'data': data,
                'cache_type': 'priority_cache'
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"優先キャッシュ保存: {year}年{month}月")
            
        except Exception as e:
            logger.error(f"優先キャッシュ保存エラー: {e}")
    
    def clear_priority_cache(self, year: Optional[int] = None, month: Optional[int] = None):
        """
        優先キャッシュをクリア
        """
        try:
            if year and month:
                # 特定月のクリア
                cache_file = self.get_priority_cache_file(year, month)
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"優先キャッシュクリア: {year}年{month}月")
            else:
                # 全クリア
                for cache_file in self.cache_dir.glob("priority_calendar_*.json"):
                    cache_file.unlink()
                logger.info("全優先キャッシュクリア")
                
        except Exception as e:
            logger.error(f"優先キャッシュクリアエラー: {e}")
    
    def get_cache_priority_status(self, year: int, month: int) -> Dict[str, Any]:
        """
        キャッシュ優先システムの状態を取得
        """
        personal_cache_file = self.personal_cache.get_cache_file_path(year, month)
        priority_cache_file = self.get_priority_cache_file(year, month)
        
        return {
            'personal_cache_exists': personal_cache_file.exists(),
            'personal_cache_valid': self.personal_cache.is_cache_valid(personal_cache_file),
            'priority_cache_exists': priority_cache_file.exists(),
            'holidays_available': len(self.holiday_cache.get_holidays_for_year(year)) > 0,
            'system_ready': True
        }

# グローバルインスタンス
_cache_priority = None

def get_calendar_cache_priority() -> CalendarCachePriority:
    """シングルトンキャッシュ優先システムインスタンスを取得"""
    global _cache_priority
    if _cache_priority is None:
        _cache_priority = CalendarCachePriority()
    return _cache_priority

if __name__ == "__main__":
    # テスト実行
    priority = get_calendar_cache_priority()
    
    # 現在月での優先表示テスト
    now = datetime.now()
    result = priority.get_calendar_with_cache_priority(now.year, now.month)
    
    self.logger.success("キャッシュ優先表示テスト完了: {result['cache_priority_status']['display_source']}")
    self.logger.info("個人予定: {result['google_events_count']}件")
    self.logger.info("祝日: {result['holidays_count']}件")