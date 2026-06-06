#!/usr/bin/env python3
"""
バックアップCLIツール - Raspberry Pi Dashboard
Phase 1: 基本バックアップシステム実装

機能:
- コマンドライン引数解析
- 対話式バックアップ作成
- バックアップ一覧表示・状態確認
- 手動バックアップ実行
- バックアップ検証
"""

import argparse
import sys
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# バックアップマネージャー読み込み
sys.path.append(str(Path(__file__).parent.parent))
from scripts.backup_manager import BackupManager, BackupError
from logging_system import get_logger


class BackupCLI:
    """バックアップCLIメインクラス"""
    
    def __init__(self):
        """CLI初期化"""
        self.logger = get_logger("backup_cli")
        self.manager = None
    
    def _init_manager(self, config_file: Optional[str] = None) -> BackupManager:
        """バックアップマネージャー初期化"""
        if self.manager is None:
            try:
                self.manager = BackupManager(config_file)
            except BackupError as e:
                print(f"❌ エラー: {e}")
                sys.exit(1)
        return self.manager
    
    def create_backup(self, args):
        """バックアップ作成コマンド"""
        manager = self._init_manager(args.config)
        
        backup_type = args.type or "incremental"
        name = args.name
        description = args.description
        
        print(f"=== {backup_type}バックアップ作成 ===")
        
        if not args.yes:
            print(f"バックアップタイプ: {backup_type}")
            print(f"バックアップ名: {name or '自動生成'}")
            print(f"説明: {description or 'なし'}")
            
            confirm = input("バックアップを作成しますか？ [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                print("バックアップ作成をキャンセルしました")
                return
        
        try:
            start_time = datetime.now()
            print("バックアップ作成中...")
            
            result = manager.create_local_backup(
                backup_type=backup_type,
                name=name,
                description=description
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            print("✅ バックアップ作成完了")
            print(f"   バックアップID: {result['backup_id']}")
            print(f"   サイズ: {self._format_size(result['size_bytes'])}")
            print(f"   所要時間: {duration:.1f}秒")
            print(f"   パス: {result['path']}")
            
        except BackupError as e:
            print(f"❌ バックアップエラー: {e}")
            sys.exit(1)
    
    def list_backups(self, args):
        """バックアップ一覧表示コマンド"""
        manager = self._init_manager(args.config)
        
        backup_type = args.type
        limit = args.limit
        
        print(f"=== バックアップ一覧 ===")
        if backup_type:
            print(f"タイプフィルタ: {backup_type}")
        if limit:
            print(f"表示件数制限: {limit}")
        print()
        
        try:
            backups = manager.list_backups(backup_type=backup_type, limit=limit)
            
            if not backups:
                print("バックアップが見つかりません")
                return
            
            print(f"総数: {len(backups)}個のバックアップ")
            print()
            
            # テーブル形式で表示
            print(f"{'ID':<25} {'タイプ':<12} {'ステータス':<10} {'サイズ':<10} {'作成日時':<16}")
            print("-" * 80)
            
            for backup in backups:
                backup_id = backup['backup_id'][:24] + "..." if len(backup['backup_id']) > 24 else backup['backup_id']
                backup_type_str = backup.get('type', 'unknown')
                status = backup.get('status', 'unknown')
                size = self._format_size(backup.get('size_bytes', 0))
                timestamp = backup.get('timestamp', '')[:16]
                
                print(f"{backup_id:<25} {backup_type_str:<12} {status:<10} {size:<10} {timestamp:<16}")
                
                if args.verbose:
                    print(f"   説明: {backup.get('description', 'なし')}")
                    print(f"   パス: {backup.get('path', 'なし')}")
                    if 'duration_seconds' in backup:
                        print(f"   所要時間: {backup['duration_seconds']:.1f}秒")
                    print()
            
        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)
    
    def verify_backup(self, args):
        """バックアップ検証コマンド"""
        manager = self._init_manager(args.config)
        
        backup_id = args.backup_id
        
        print(f"=== バックアップ検証: {backup_id} ===")
        
        try:
            print("検証中...")
            result = manager.verify_backup(backup_id)
            
            print(f"検証結果: {result['status']}")
            
            if result['status'] == 'passed':
                print("✅ バックアップ検証成功")
                print(f"   サイズ一致: {result['size_match']}")
                print(f"   チェックサム一致: {result['checksum_match']}")
            elif result['status'] == 'failed':
                print("❌ バックアップ検証失敗")
                if not result.get('size_match', True):
                    print(f"   サイズ不一致: 現在={self._format_size(result['current_size'])}, "
                          f"期待={self._format_size(result['expected_size'])}")
                if not result.get('checksum_match', True):
                    print("   チェックサム不一致")
            else:
                print(f"❌ 検証エラー: {result.get('error', '不明なエラー')}")
            
        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)
    
    def show_statistics(self, args):
        """統計情報表示コマンド"""
        manager = self._init_manager(args.config)
        
        print("=== バックアップ統計情報 ===")
        
        try:
            stats = manager.get_statistics()
            
            print(f"総バックアップ数: {stats.get('total_backups', 0)}")
            print(f"成功数: {stats.get('successful_backups', 0)}")
            print(f"失敗数: {stats.get('failed_backups', 0)}")
            print(f"総サイズ: {self._format_size(stats.get('total_size_bytes', 0))}")
            
            if 'last_backup' in stats:
                last_backup = stats['last_backup']
                if isinstance(last_backup, str):
                    last_backup = last_backup[:19]  # YYYY-MM-DD HH:MM:SS
                print(f"最新バックアップ: {last_backup}")
            else:
                print("最新バックアップ: なし")
            
        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)
    
    def cleanup_old_backups(self, args):
        """古いバックアップクリーンアップコマンド"""
        manager = self._init_manager(args.config)
        
        print("=== 古いバックアップクリーンアップ ===")
        
        if not args.yes:
            stats_before = manager.get_statistics()
            print(f"現在のバックアップ数: {stats_before.get('total_backups', 0)}")
            print(f"現在の総サイズ: {self._format_size(stats_before.get('total_size_bytes', 0))}")
            
            confirm = input("古いバックアップを削除しますか？ [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                print("クリーンアップをキャンセルしました")
                return
        
        try:
            print("クリーンアップ中...")
            manager.cleanup_old_backups()
            
            stats_after = manager.get_statistics()
            print("✅ クリーンアップ完了")
            print(f"残りバックアップ数: {stats_after.get('total_backups', 0)}")
            print(f"残り総サイズ: {self._format_size(stats_after.get('total_size_bytes', 0))}")
            
        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)
    
    def interactive_create(self, args):
        """対話式バックアップ作成"""
        manager = self._init_manager(args.config)
        
        print("=== 対話式バックアップ作成 ===")
        
        # バックアップタイプ選択
        print("バックアップタイプを選択してください:")
        print("1. 増分バックアップ (incremental) - 推奨")
        print("2. フルバックアップ (full)")
        
        while True:
            choice = input("選択 [1-2]: ").strip()
            if choice == "1":
                backup_type = "incremental"
                break
            elif choice == "2":
                backup_type = "full"
                break
            else:
                print("1または2を入力してください")
        
        # 名前入力
        name = input("バックアップ名 (空白で自動生成): ").strip()
        if not name:
            name = None
        
        # 説明入力
        description = input("説明 (オプション): ").strip()
        if not description:
            description = None
        
        # 確認
        print("\n--- 設定確認 ---")
        print(f"タイプ: {backup_type}")
        print(f"名前: {name or '自動生成'}")
        print(f"説明: {description or 'なし'}")
        
        confirm = input("\nバックアップを作成しますか？ [y/N]: ")
        if confirm.lower() not in ['y', 'yes']:
            print("バックアップ作成をキャンセルしました")
            return
        
        try:
            print("\nバックアップ作成中...")
            start_time = datetime.now()
            
            result = manager.create_local_backup(
                backup_type=backup_type,
                name=name,
                description=description
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            print("\n✅ バックアップ作成完了")
            print(f"   バックアップID: {result['backup_id']}")
            print(f"   サイズ: {self._format_size(result['size_bytes'])}")
            print(f"   所要時間: {duration:.1f}秒")
            
        except BackupError as e:
            print(f"\n❌ バックアップエラー: {e}")
            sys.exit(1)
    
    def delete_backup(self, args):
        """バックアップ削除コマンド"""
        manager = self._init_manager(args.config)
        
        backup_id = args.backup_id
        
        print(f"=== バックアップ削除: {backup_id} ===")
        
        if not args.yes:
            # バックアップ情報取得
            backups = manager.list_backups()
            backup_info = None
            for backup in backups:
                if backup['backup_id'] == backup_id:
                    backup_info = backup
                    break
            
            if not backup_info:
                print(f"❌ バックアップが見つかりません: {backup_id}")
                return
            
            print(f"削除対象:")
            print(f"  ID: {backup_info['backup_id']}")
            print(f"  説明: {backup_info.get('description', 'なし')}")
            print(f"  サイズ: {self._format_size(backup_info.get('size_bytes', 0))}")
            print(f"  作成日時: {backup_info.get('timestamp', '')[:19].replace('T', ' ')}")
            print(f"  パス: {backup_info.get('path', '')}")
            
            confirm = input("\nこのバックアップを削除しますか？ [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                print("削除をキャンセルしました")
                return
        
        try:
            print("削除中...")
            success = manager.delete_backup(backup_id)
            
            if success:
                print("✅ バックアップ削除完了")
                print(f"   メタデータも更新されました")
            else:
                print("❌ バックアップ削除失敗")
                sys.exit(1)
            
        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)
    
    def check_integrity(self, args):
        """メタデータ整合性チェックコマンド"""
        manager = self._init_manager(args.config)

        print("=== メタデータ整合性チェック ===")

        try:
            result = manager.check_metadata_integrity(fix_issues=args.fix)

            print(f"チェック結果:")
            print(f"  総メタデータエントリ: {result['total_metadata_entries']}")
            print(f"  有効エントリ: {result['valid_entries']}")
            print(f"  無効エントリ: {result['invalid_entries']}")
            print(f"  孤立ファイル: {result['orphaned_files']}")

            if result['issues']:
                print(f"\n発見された問題:")
                for issue in result['issues']:
                    if issue['type'] == 'missing_file':
                        print(f"  ❌ ファイル未発見: {issue['backup_id']}")
                        print(f"     パス: {issue['path']}")
                        print(f"     サイズ: {issue['size_mb']}MB")
                    elif issue['type'] == 'orphaned_file':
                        print(f"  ⚠️  孤立ファイル: {issue['name']}")
                        print(f"     パス: {issue['path']}")

            if args.fix and result['fixed_issues'] > 0:
                print(f"\n✅ 修復完了: {result['fixed_issues']}個の問題を解決")
            elif result['invalid_entries'] > 0 and not args.fix:
                print(f"\n💡 --fix オプションを使用して自動修復できます")

            if result['orphaned_files'] > 0:
                print(f"\n⚠️  孤立ファイルは手動確認後に削除してください")

        except BackupError as e:
            print(f"❌ エラー: {e}")
            sys.exit(1)

    def _format_size(self, size_bytes: int) -> str:
        """ファイルサイズフォーマット"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"


def create_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサー作成"""
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Dashboard バックアップCLIツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s --create --type incremental --name "manual-backup"
  %(prog)s --list --type incremental --limit 10
  %(prog)s --verify backup_id_here
  %(prog)s --interactive
  %(prog)s --stats
  %(prog)s --cleanup --yes
        """
    )
    
    # 共通オプション
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='設定ファイルパス (デフォルト: config/backup_config.json)'
    )
    
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='確認プロンプトをスキップ'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='詳細情報表示'
    )
    
    # メインコマンド
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument(
        '--create',
        action='store_true',
        help='バックアップ作成'
    )
    
    group.add_argument(
        '--list',
        action='store_true',
        help='バックアップ一覧表示'
    )
    
    group.add_argument(
        '--verify',
        type=str,
        metavar='BACKUP_ID',
        help='バックアップ検証'
    )
    
    group.add_argument(
        '--stats',
        action='store_true',
        help='統計情報表示'
    )
    
    group.add_argument(
        '--cleanup',
        action='store_true',
        help='古いバックアップクリーンアップ'
    )
    
    group.add_argument(
        '--interactive',
        action='store_true',
        help='対話式バックアップ作成'
    )
    
    group.add_argument(
        '--delete',
        type=str,
        metavar='BACKUP_ID',
        help='指定バックアップ削除'
    )

    group.add_argument(
        '--check-integrity',
        action='store_true',
        help='メタデータ整合性チェック'
    )
    
    # バックアップ作成オプション
    parser.add_argument(
        '--type', '-t',
        type=str,
        choices=['incremental', 'full'],
        help='バックアップタイプ (デフォルト: incremental)'
    )
    
    parser.add_argument(
        '--name', '-n',
        type=str,
        help='バックアップ名'
    )
    
    parser.add_argument(
        '--description', '-d',
        type=str,
        help='バックアップ説明'
    )
    
    # リスト表示オプション
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='表示件数制限'
    )

    # 整合性チェックオプション
    parser.add_argument(
        '--fix',
        action='store_true',
        help='整合性チェック時に発見した問題を自動修復'
    )

    return parser


def main():
    """メイン関数"""
    parser = create_parser()
    args = parser.parse_args()
    
    cli = BackupCLI()
    
    try:
        if args.create:
            cli.create_backup(args)
        elif args.list:
            cli.list_backups(args)
        elif args.verify:
            args.backup_id = args.verify
            cli.verify_backup(args)
        elif args.stats:
            cli.show_statistics(args)
        elif args.cleanup:
            cli.cleanup_old_backups(args)
        elif args.interactive:
            cli.interactive_create(args)
        elif args.delete:
            args.backup_id = args.delete
            cli.delete_backup(args)
        elif args.check_integrity:
            cli.check_integrity(args)
        
    except KeyboardInterrupt:
        print("\n\n処理をキャンセルしました")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 予期しないエラー: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()