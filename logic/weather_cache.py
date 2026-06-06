#!/usr/bin/env python3
"""
天気データキャッシュシステム
高頻度API呼び出しを避けるためのキャッシュ機能
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

class WeatherCache:
    """天気データキャッシュ管理"""
    
    def __init__(self, cache_dir: str = None):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # キャッシュディレクトリ設定
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # デフォルト: プロジェクトルート/cache/weather/
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / 'cache' / 'weather'
        
        # ディレクトリ作成
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # キャッシュファイル
        self.cache_file = self.cache_dir / 'weather_cache.json'
        
        # キャッシュ有効期間（分）
        self.cache_duration_minutes = 28  # 30分更新の余裕を持って28分
        
    def get_cached_data(self) -> Optional[Dict]:
        """キャッシュからデータ取得"""
        try:
            if not self.cache_file.exists():
                self.logger.debug("キャッシュファイルが存在しません")
                return None
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # キャッシュ時刻確認
            cached_at = datetime.fromisoformat(cache_data.get('cached_at', ''))
            now = datetime.now()
            
            # 有効期間内かチェック
            if now - cached_at <= timedelta(minutes=self.cache_duration_minutes):
                self.logger.debug(f"キャッシュヒット: {cached_at} (有効期間: {self.cache_duration_minutes}分)")
                return cache_data.get('data')
            else:
                self.logger.debug(f"キャッシュ期限切れ: {cached_at}")
                return None
                
        except Exception as e:
            self.logger.warning(f"キャッシュ読み込みエラー: {e}")
            return None
    
    def save_to_cache(self, data: Dict) -> bool:
        """データをキャッシュに保存"""
        try:
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'data': data,
                'cache_duration_minutes': self.cache_duration_minutes
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            self.logger.debug(f"キャッシュ保存完了: {self.cache_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"キャッシュ保存エラー: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """キャッシュクリア"""
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                self.logger.info("キャッシュクリア完了")
            return True
        except Exception as e:
            self.logger.error(f"キャッシュクリアエラー: {e}")
            return False
    
    def get_cache_status(self) -> Dict:
        """キャッシュ状況取得"""
        try:
            if not self.cache_file.exists():
                return {
                    'exists': False,
                    'cached_at': None,
                    'age_minutes': None,
                    'is_valid': False
                }
            
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cached_at = datetime.fromisoformat(cache_data.get('cached_at', ''))
            now = datetime.now()
            age_minutes = (now - cached_at).total_seconds() / 60
            is_valid = age_minutes <= self.cache_duration_minutes
            
            return {
                'exists': True,
                'cached_at': cached_at.isoformat(),
                'age_minutes': round(age_minutes, 1),
                'is_valid': is_valid,
                'cache_duration_minutes': self.cache_duration_minutes
            }
            
        except Exception as e:
            self.logger.error(f"キャッシュ状況取得エラー: {e}")
            return {
                'exists': False,
                'error': str(e)
            }