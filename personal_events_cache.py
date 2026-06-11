#!/usr/bin/env python3
"""
個人予定キャッシュシステム
Google Calendar APIの頻繁なアクセスを避けて安定性を向上
"""

import json
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from logging_system import get_logger

logger = logging.getLogger(__name__)

class PersonalEventsCache:
    """個人予定のキャッシュ管理クラス"""

    # クラスレベルのロック（複数スレッドからの同時更新を防ぐ）
    _update_lock = threading.Lock()

    def __init__(self, cache_dir: str = "cache/personal_events", cache_validity_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_validity_hours = cache_validity_hours  # デフォルト24時間有効
    
    def get_cache_file_path(self, year: int, month: int) -> Path:
        """キャッシュファイルパスを取得"""
        return self.cache_dir / f"personal_events_{year}_{month:02d}.json"
    
    def is_cache_valid(self, cache_file: Path) -> bool:
        """キャッシュが有効かチェック"""
        if not cache_file.exists():
            return False
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cached_at = datetime.fromisoformat(data.get('cached_at', ''))
            now = datetime.now()
            
            # 24時間以内なら有効
            return (now - cached_at).total_seconds() < self.cache_validity_hours * 3600
            
        except Exception as e:
            logger.warning(f"キャッシュファイル読み込みエラー: {e}")
            return False
    
    def save_events(self, year: int, month: int, events: List[Dict]) -> bool:
        """個人予定をキャッシュに保存"""
        try:
            cache_file = self.get_cache_file_path(year, month)

            # datetimeオブジェクトをISO形式文字列に変換
            serializable_events = []
            for event in events:
                event_copy = event.copy()
                if isinstance(event_copy.get('start_datetime'), datetime):
                    event_copy['start_datetime'] = event_copy['start_datetime'].isoformat()
                if isinstance(event_copy.get('end_datetime'), datetime):
                    event_copy['end_datetime'] = event_copy['end_datetime'].isoformat()
                serializable_events.append(event_copy)

            cache_data = {
                'year': year,
                'month': month,
                'cached_at': datetime.now().isoformat(),
                'events_count': len(serializable_events),
                'events': serializable_events
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            if len(events) == 0:
                logger.info(f"個人予定キャッシュ保存（予定なし）: {year}年{month}月")
            else:
                logger.info(f"個人予定キャッシュ保存: {year}年{month}月 - {len(events)}件")
            return True

        except Exception as e:
            logger.error(f"個人予定キャッシュ保存エラー: {e}")
            return False
    
    def load_events(self, year: int, month: int) -> List[Dict]:
        """キャッシュから個人予定を読み込み"""
        cache_file = self.get_cache_file_path(year, month)
        
        if not self.is_cache_valid(cache_file):
            logger.info(f"個人予定キャッシュが無効または存在しません: {year}年{month}月")
            return []
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            events = data.get('events', [])
            logger.info(f"個人予定キャッシュ読み込み: {year}年{month}月 - {len(events)}件")
            return events
            
        except Exception as e:
            logger.error(f"個人予定キャッシュ読み込みエラー: {e}")
            return []
    
    def clear_cache(self, year: Optional[int] = None, month: Optional[int] = None):
        """キャッシュをクリア"""
        try:
            if year and month:
                # 特定月のキャッシュを削除
                cache_file = self.get_cache_file_path(year, month)
                if cache_file.exists():
                    cache_file.unlink()
                    logger.info(f"個人予定キャッシュを削除: {year}年{month}月")
            else:
                # 全キャッシュを削除
                for cache_file in self.cache_dir.glob("personal_events_*.json"):
                    cache_file.unlink()
                logger.info("全個人予定キャッシュを削除")
                
        except Exception as e:
            logger.error(f"キャッシュ削除エラー: {e}")
    
    def update_cache_for_current_month(self) -> bool:
        """現在月の個人予定キャッシュを更新（手動実行用）"""
        now = datetime.now()
        year = now.year
        month = now.month
        
        return self.update_cache_for_month(year, month)
    
    def update_cache_for_month(self, year: int, month: int) -> bool:
        """指定月の個人予定キャッシュを更新（スレッドセーフ）"""
        # 複数スレッドからの同時更新を防ぐ
        if not PersonalEventsCache._update_lock.acquire(blocking=False):
            logger.warning(f"他のスレッドがキャッシュ更新中のためスキップ: {year}年{month}月")
            return True  # 別スレッドが更新中なので待たずに成功扱い

        try:
            from google_calendar_service import get_google_calendar_service

            service = get_google_calendar_service()

            # refresh_token自動更新で個人予定を取得
            events = service.get_personal_events(year, month)

            if not events:
                # 0件の場合、既存キャッシュにデータがあれば上書きしない
                # （ネットワーク未確立・API一時エラー・競合等による誤った空キャッシュ保存を防ぐ）
                cache_file = self.get_cache_file_path(year, month)
                if cache_file.exists():
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            existing = json.load(f)
                        if existing.get('events_count', 0) > 0:
                            # cached_atを更新してキャッシュを有効状態に保つ
                            # （更新しないとload_events()が期限切れと判断して[]を返してしまう）
                            existing['cached_at'] = datetime.now().isoformat()
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                json.dump(existing, f, indent=2, ensure_ascii=False)
                            logger.warning(f"API取得結果が0件のため既存キャッシュを維持（cached_at更新）: {year}年{month}月 ({existing['events_count']}件保持)")
                            return True
                    except Exception:
                        pass
                events = []
                logger.info(f"個人予定なし（空配列をキャッシュ保存）: {year}年{month}月")
            else:
                logger.info(f"個人予定をAPIから取得してキャッシュ更新: {year}年{month}月 - {len(events)}件")

            return self.save_events(year, month, events)

        except Exception as e:
            logger.error(f"個人予定キャッシュ更新エラー ({year}年{month}月): {e}")
            return False

        finally:
            PersonalEventsCache._update_lock.release()
    
    def load_events_with_auto_update(self, year: int, month: int) -> List[Dict]:
        """キャッシュから個人予定を読み込み（期限切れ時は自動更新）"""
        cache_file = self.get_cache_file_path(year, month)
        
        # キャッシュが有効なら既存データを返す（予定なしでもキャッシュされていれば使用）
        if self.is_cache_valid(cache_file):
            events = self.load_events(year, month)
            if len(events) == 0:
                logger.info(f"個人予定キャッシュから読み込み（予定なし）: {year}年{month}月")
            else:
                logger.info(f"個人予定キャッシュから読み込み: {year}年{month}月 - {len(events)}件")
            return events
        
        # キャッシュが無効または存在しない場合は自動更新を試行
        logger.info(f"個人予定キャッシュが無効または存在しません。自動更新を試行: {year}年{month}月")
        
        if self.update_cache_for_month(year, month):
            # 更新成功時は新しいキャッシュを読み込み（空配列でも成功とみなす）
            events = self.load_events(year, month)
            logger.info(f"個人予定の自動更新完了: {year}年{month}月")
            return events
        else:
            # 更新失敗時は空配列を返す
            logger.warning(f"個人予定の自動更新に失敗しました: {year}年{month}月")
            return []

def get_personal_events_cache() -> PersonalEventsCache:
    """個人予定キャッシュインスタンスを取得"""
    import os
    current_dir = os.getcwd()
    if current_dir.endswith('raspberry-pi-dashboard'):
        cache_dir = "cache/personal_events"
    else:
        cache_dir = "raspberry-pi-dashboard/cache/personal_events"
    return PersonalEventsCache(cache_dir=cache_dir)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    cache = get_personal_events_cache()
    if cache.update_cache_for_current_month():
        logger.info("個人予定キャッシュを更新しました")
    else:
        logger.warning("個人予定キャッシュ更新に失敗しました")