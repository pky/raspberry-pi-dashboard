#!/usr/bin/env python3
"""
祝日キャッシュ更新スクリプト
内閣府データで既存キャッシュを強制更新
"""

import sys
import logging
from holiday_cache import get_holiday_cache
from logging_system import get_logger

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """メイン処理"""
    try:
        cache = get_holiday_cache()
        
        # 引数で単年更新か複数年更新かを判定
        if len(sys.argv) > 1 and sys.argv[1] == "--bulk":
            # 複数年一括更新
            self.logger.info("前後2年分の祝日データを一括更新中...")
            results = cache.bulk_update_holidays()
            
            self.logger.info("\n 更新結果:")
            for year, success in results.items():
                status = "✅ 成功" if success else "❌ 失敗"
                self.logger.info("年:", year=year, status=status)
            
            # 各年のデータを確認
            current_year = 2025
            for test_year in [2024, 2025, 2026]:
                if results.get(test_year, False):
                    holidays = cache.get_holidays_for_year(test_year)
                    self.logger.info("\n📅 年: {len(holidays)}件の祝日", test_year=test_year)
                    
                    # 7月の祝日のみ表示
                    july_holidays = [h for h in holidays if h['start_datetime'].month == 7]
                    if july_holidays:
                        for holiday in july_holidays:
                            date_str = holiday['start_datetime'].strftime('%m-%d')
                            self.logger.info("7月:  {holiday['title']}", date_str=date_str)
            
            success_count = sum(results.values())
            total_count = len(results)
            self.logger.success("\n🎯 複数年一括更新完了: /年成功", success_count=success_count, total_count=total_count)
            return 0 if success_count == total_count else 1
        
        else:
            # 単年更新（従来の処理）
            year = 2025
            
            self.logger.info("🧹 年祝日キャッシュをクリア中...", year=year)
            cache.clear_cache(year)
            
            self.logger.info("📥 内閣府から年祝日データを取得中...", year=year)
            holidays = cache.get_holidays_for_year(year)
            
            if holidays:
                self.logger.success("{len(holidays)}件の正式な祝日データを取得しました")
                
                # 7月の祝日を確認
                july_holidays = [h for h in holidays if h['start_datetime'].month == 7]
                self.logger.info("\n📅 年7月の祝日:", year=year)
                for holiday in july_holidays:
                    date_str = holiday['start_datetime'].strftime('%Y-%m-%d')
                    self.logger.info("- : {holiday['title']}", date_str=date_str)
                
                # 七夕がないことを確認
                tanabata_found = any('七夕' in h['title'] for h in holidays)
                if tanabata_found:
                    self.logger.warning("警告: 七夕が含まれています")
                    return 1
                else:
                    self.logger.success("七夕は含まれていません（正常）")
                    
            else:
                self.logger.info("祝日データの取得に失敗しました")
                return 1
                
            self.logger.success("\n🎯 年祝日キャッシュの更新が完了しました", year=year)
            return 0
        
    except Exception as e:
        logger.error(f"エラー: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())