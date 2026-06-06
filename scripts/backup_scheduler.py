#!/usr/bin/env python3
"""
自動バックアップスケジューラ - Raspberry Pi Dashboard
Phase 1: 基本バックアップシステム実装

機能:
- cron経由での自動バックアップ実行
- スケジュール設定管理
- バックアップローテーション
- 実行ログ記録
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# バックアップマネージャー読み込み
sys.path.append(str(Path(__file__).parent.parent))
from scripts.backup_manager import BackupManager, BackupError
from logging_system import get_logger


class BackupScheduler:
    """自動バックアップスケジューラー"""
    
    def __init__(self, config_file: str = None):
        """スケジューラ初期化"""
        self.logger = get_logger("backup_scheduler")
        self.manager = BackupManager(config_file)
        self.config = self.manager.config
    
    def run_scheduled_backup(self, backup_type: str = "incremental"):
        """
        スケジュール実行されるバックアップ
        
        Args:
            backup_type: バックアップタイプ ("incremental" or "full")
        """
        schedule_name = f"scheduled_{backup_type}"
        
        try:
            self.logger.info("スケジュールバックアップ開始", 
                           backup_type=backup_type,
                           schedule_name=schedule_name)
            
            # バックアップ実行
            result = self.manager.create_local_backup(
                backup_type=backup_type,
                name=schedule_name,
                description=f"自動{backup_type}バックアップ"
            )
            
            self.logger.success("スケジュールバックアップ完了",
                              backup_id=result['backup_id'],
                              size_mb=round(result['size_bytes'] / 1024 / 1024, 2),
                              duration=result['duration_seconds'])
            
            # ローテーション実行
            self._run_rotation_if_needed()

            # 整合性チェック実行（日次バックアップ後）
            if backup_type == "incremental":
                self._run_integrity_check_if_needed()

            return result
            
        except BackupError as e:
            self.logger.error("スケジュールバックアップエラー", 
                            backup_type=backup_type,
                            error=str(e))
            raise
        except Exception as e:
            self.logger.critical("予期しないスケジュールバックアップエラー", 
                               backup_type=backup_type,
                               error=str(e))
            raise BackupError(f"スケジュールバックアップ予期しないエラー: {e}")
    
    def run_daily_backup(self):
        """日次バックアップ実行"""
        daily_config = self.config.get('scheduling', {}).get('daily', {})
        
        if not daily_config.get('enabled', True):
            self.logger.info("日次バックアップ無効化されています")
            return
        
        backup_type = daily_config.get('type', 'incremental')
        
        self.logger.info("日次バックアップ開始", backup_type=backup_type)
        
        try:
            return self.run_scheduled_backup(backup_type)
        except Exception as e:
            self.logger.error("日次バックアップ失敗", error=str(e))
            raise
    
    def run_weekly_backup(self):
        """週次バックアップ実行"""
        weekly_config = self.config.get('scheduling', {}).get('weekly', {})
        
        if not weekly_config.get('enabled', True):
            self.logger.info("週次バックアップ無効化されています")
            return
        
        backup_type = weekly_config.get('type', 'full')
        
        self.logger.info("週次バックアップ開始", backup_type=backup_type)
        
        try:
            return self.run_scheduled_backup(backup_type)
        except Exception as e:
            self.logger.error("週次バックアップ失敗", error=str(e))
            raise
    
    def _run_rotation_if_needed(self):
        """必要に応じてバックアップローテーション実行"""
        try:
            # 統計情報取得
            stats = self.manager.get_statistics()
            total_backups = stats.get('total_backups', 0)
            max_backups = self.config['local_backup']['max_backups']

            # 常にクリーンアップを実行（時間ベース削除と件数制限の両方を処理）
            self.logger.info("バックアップクリーンアップ実行",
                           current_count=total_backups,
                           max_count=max_backups)

            self.manager.cleanup_old_backups()

            # クリーンアップ後統計
            new_stats = self.manager.get_statistics()
            new_count = new_stats.get('total_backups', 0)

            if new_count < total_backups:
                self.logger.success("バックアップクリーンアップ完了",
                                  old_count=total_backups,
                                  new_count=new_count,
                                  deleted_count=total_backups - new_count)
            else:
                self.logger.debug("バックアップクリーンアップ実行 - 削除対象なし",
                                current_count=total_backups)

        except Exception as e:
            self.logger.warning("バックアップクリーンアップエラー", error=str(e))

    def _run_integrity_check_if_needed(self):
        """必要に応じて整合性チェック実行"""
        try:
            # 統計情報取得
            stats = self.manager.get_statistics()
            total_backups = stats.get('total_backups', 0)

            # バックアップが5個以上ある場合のみチェック実行（効率性のため）
            if total_backups >= 5:
                self.logger.info("整合性チェック実行",
                               total_backups=total_backups)

                result = self.manager.check_metadata_integrity(fix_issues=True)

                if result['invalid_entries'] > 0 or result['orphaned_files'] > 0:
                    self.logger.warning("整合性問題を発見・修復",
                                      invalid_entries=result['invalid_entries'],
                                      orphaned_files=result['orphaned_files'],
                                      fixed_issues=result['fixed_issues'])
                else:
                    self.logger.debug("整合性チェック完了 - 問題なし")
            else:
                self.logger.debug("整合性チェックスキップ",
                                reason=f"バックアップ数が少ない（{total_backups}個）")

        except Exception as e:
            self.logger.warning("整合性チェックエラー", error=str(e))
    
    def generate_cron_config(self) -> str:
        """cron設定ファイル生成"""
        schedule_config = self.config.get('scheduling', {})
        
        # プロジェクトルートパス
        project_root = str(Path(__file__).parent.parent)
        python_path = "python3"  # システムのpython3を使用
        scheduler_script = str(Path(__file__))
        
        cron_lines = []
        cron_lines.append("# Raspberry Pi Dashboard - 自動バックアップスケジュール")
        cron_lines.append("# 自動生成 - 手動編集しないでください")
        cron_lines.append("")
        
        # 日次バックアップ
        daily_config = schedule_config.get('daily', {})
        if daily_config.get('enabled', True):
            time_str = daily_config.get('time', '02:00')
            hour, minute = time_str.split(':')
            
            cron_lines.append(f"# 日次増分バックアップ - {time_str}")
            cron_lines.append(f"{minute} {hour} * * * cd {project_root} && {python_path} {scheduler_script} --daily >> /tmp/backup_cron.log 2>&1")
            cron_lines.append("")
        
        # 週次バックアップ
        weekly_config = schedule_config.get('weekly', {})
        if weekly_config.get('enabled', True):
            time_str = weekly_config.get('time', '03:00')
            day_str = weekly_config.get('day', 'sunday')
            hour, minute = time_str.split(':')
            
            # 曜日変換
            day_map = {
                'sunday': '0', 'monday': '1', 'tuesday': '2', 'wednesday': '3',
                'thursday': '4', 'friday': '5', 'saturday': '6'
            }
            day_num = day_map.get(day_str.lower(), '0')
            
            cron_lines.append(f"# 週次フルバックアップ - {day_str} {time_str}")
            cron_lines.append(f"{minute} {hour} * * {day_num} cd {project_root} && {python_path} {scheduler_script} --weekly >> /tmp/backup_cron.log 2>&1")
            cron_lines.append("")
        
        return '\n'.join(cron_lines)
    
    def install_cron_schedule(self, dry_run: bool = False):
        """cronスケジュール設定インストール"""
        cron_content = self.generate_cron_config()
        
        if dry_run:
            print("=== 生成されるcron設定内容 ===")
            print(cron_content)
            return
        
        # 一時ファイルに保存
        cron_file = Path('/tmp/raspberry-pi-backup-cron')
        
        try:
            with open(cron_file, 'w', encoding='utf-8') as f:
                f.write(cron_content)
            
            self.logger.info("cron設定ファイル作成", file=str(cron_file))
            
            # 注意事項表示
            print("✅ cron設定ファイルが作成されました")
            print(f"ファイル: {cron_file}")
            print()
            print("以下のコマンドでcronスケジュールをインストールしてください:")
            print(f"sudo crontab -u pi {cron_file}")
            print()
            print("現在のcron設定確認:")
            print("crontab -l")
            print()
            print("⚠️  注意: このコマンドは既存のcron設定を置き換えます")
            
        except Exception as e:
            self.logger.error("cron設定ファイル作成エラー", error=str(e))
            raise BackupError(f"cron設定ファイル作成エラー: {e}")


def create_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサー作成"""
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Dashboard バックアップスケジューラ",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='設定ファイルパス'
    )
    
    # 実行コマンド
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument(
        '--daily',
        action='store_true',
        help='日次バックアップ実行'
    )
    
    group.add_argument(
        '--weekly',
        action='store_true',
        help='週次バックアップ実行'
    )
    
    group.add_argument(
        '--install-cron',
        action='store_true',
        help='cronスケジュール設定インストール'
    )
    
    group.add_argument(
        '--generate-cron',
        action='store_true',
        help='cron設定内容表示（実際のインストールなし）'
    )
    
    return parser


def main():
    """メイン関数"""
    parser = create_parser()
    args = parser.parse_args()
    
    try:
        scheduler = BackupScheduler(args.config)
        
        if args.daily:
            scheduler.run_daily_backup()
            print("✅ 日次バックアップ完了")
            
        elif args.weekly:
            scheduler.run_weekly_backup()
            print("✅ 週次バックアップ完了")
            
        elif args.install_cron:
            scheduler.install_cron_schedule(dry_run=False)
            
        elif args.generate_cron:
            scheduler.install_cron_schedule(dry_run=True)
        
    except BackupError as e:
        print(f"❌ バックアップエラー: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n処理をキャンセルしました")
        sys.exit(130)
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()