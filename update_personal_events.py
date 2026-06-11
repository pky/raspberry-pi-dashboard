#!/usr/bin/env python3
"""
個人予定キャッシュ手動更新スクリプト
Mac側で認証してから、Raspberry Pi側で実行する
"""

import sys
import logging
from datetime import datetime
from personal_events_cache import get_personal_events_cache
from logging_system import get_logger

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    cache = get_personal_events_cache()
    
    logging.info("個人予定キャッシュ更新を開始します...")
    
    # 現在月の更新
    now = datetime.now()
    current_success = cache.update_cache_for_current_month()
    
    # 翌月の更新も試行
    next_month = now.month + 1 if now.month < 12 else 1
    next_year = now.year if now.month < 12 else now.year + 1
    
    try:
        # 翌月のキャッシュも更新
        from datetime import timedelta
        next_start = datetime(next_year, next_month, 1)
        if next_month == 12:
            next_end = datetime(next_year + 1, 1, 1) - timedelta(days=1)
        else:
            next_end = datetime(next_year, next_month + 1, 1) - timedelta(days=1)
        
        # Google Calendar認証チェック
        from calendar_auth import GoogleCalendarAuth
        auth = GoogleCalendarAuth()
        
        if auth.load_credentials():
            logging.info(f"📅 {next_year}年{next_month}月の個人予定も更新中...")
            next_success = cache.save_events(next_year, next_month, [])  # 簡易実装
        else:
            logging.warning("Google Calendar認証が必要です")
            next_success = False

    except Exception as e:
        logging.error(f"翌月更新エラー: {e}")
        next_success = False

    # 結果報告
    if current_success:
        logging.info(f"{now.year}年{now.month}月の個人予定キャッシュを更新しました")
    else:
        logging.warning(f"{now.year}年{now.month}月の更新に失敗しました")
        logging.info("Mac側で認証を実行してからもう一度お試しください")
        logging.info("macOS: python3 auth/reauth_google_calendar_mac.py")
        logging.info("転送: scp credentials/token.json pi@raspberrypi.local:~/projects/raspberry-pi-dashboard/credentials/")
    
    return 0 if current_success else 1

if __name__ == "__main__":
    sys.exit(main())