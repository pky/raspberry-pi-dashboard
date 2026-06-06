#!/usr/bin/env python3
"""
バックアップ整合性チェッカー - Raspberry Pi Dashboard
定期実行用メタデータ整合性チェックスクリプト

機能:
- メタデータと実ファイルの整合性チェック
- 自動修復機能
- 詳細ログ記録
- エラー通知
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# バックアップマネージャー読み込み
sys.path.append(str(Path(__file__).parent.parent))
from scripts.backup_manager import BackupManager, BackupError
from logging_system import get_logger


class BackupIntegrityChecker:
    """バックアップ整合性チェッカー"""

    def __init__(self, config_file: str = None):
        """初期化"""
        self.logger = get_logger("backup_integrity_checker")
        self.manager = BackupManager(config_file)

    def run_integrity_check(self, auto_fix: bool = True,
                          detailed_report: bool = False) -> bool:
        """
        整合性チェック実行

        Args:
            auto_fix: 自動修復を行うかどうか
            detailed_report: 詳細レポートを出力するかどうか

        Returns:
            bool: チェック成功時True、エラー時False
        """
        check_start = datetime.now()

        try:
            self.logger.info("定期整合性チェック開始",
                           auto_fix=auto_fix,
                           timestamp=check_start.isoformat())

            # 整合性チェック実行
            result = self.manager.check_metadata_integrity(fix_issues=auto_fix)

            # 結果の評価
            has_issues = (result['invalid_entries'] > 0 or
                         result['orphaned_files'] > 0)

            # ログ記録
            if has_issues:
                if auto_fix and result['fixed_issues'] > 0:
                    self.logger.success("整合性問題を修復",
                                      fixed_issues=result['fixed_issues'],
                                      invalid_entries=result['invalid_entries'],
                                      orphaned_files=result['orphaned_files'])
                else:
                    self.logger.warning("整合性問題を発見",
                                      invalid_entries=result['invalid_entries'],
                                      orphaned_files=result['orphaned_files'],
                                      auto_fix_enabled=auto_fix)
            else:
                self.logger.success("整合性チェック完了 - 問題なし",
                                  valid_entries=result['valid_entries'])

            # 詳細レポート出力
            if detailed_report or has_issues:
                self._generate_detailed_report(result, check_start)

            # 統計情報更新
            duration = (datetime.now() - check_start).total_seconds()
            self.logger.info("整合性チェック完了",
                           duration_seconds=duration,
                           total_entries=result['total_metadata_entries'],
                           valid_entries=result['valid_entries'])

            return True

        except BackupError as e:
            self.logger.error("整合性チェックエラー", error=str(e))
            return False
        except Exception as e:
            self.logger.critical("予期しない整合性チェックエラー", error=str(e))
            return False

    def _generate_detailed_report(self, result: dict, check_start: datetime):
        """詳細レポート生成"""
        report_lines = [
            "=" * 60,
            f"バックアップ整合性チェック詳細レポート",
            f"実行時刻: {check_start.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 60,
            "",
            "📊 サマリー:",
            f"  総メタデータエントリ: {result['total_metadata_entries']}",
            f"  有効エントリ: {result['valid_entries']}",
            f"  無効エントリ: {result['invalid_entries']}",
            f"  孤立ファイル: {result['orphaned_files']}",
            f"  修復済み問題: {result['fixed_issues']}",
            ""
        ]

        if result['issues']:
            report_lines.extend([
                "🔍 発見された問題:",
                ""
            ])

            for issue in result['issues']:
                if issue['type'] == 'missing_file':
                    report_lines.extend([
                        f"❌ ファイル未発見:",
                        f"   ID: {issue['backup_id']}",
                        f"   パス: {issue['path']}",
                        f"   サイズ: {issue['size_mb']}MB",
                        f"   作成日時: {issue['timestamp'][:19]}",
                        ""
                    ])
                elif issue['type'] == 'orphaned_file':
                    report_lines.extend([
                        f"⚠️  孤立ファイル:",
                        f"   名前: {issue['name']}",
                        f"   パス: {issue['path']}",
                        ""
                    ])
        else:
            report_lines.append("✅ 問題は発見されませんでした")

        report_lines.extend([
            "",
            "=" * 60
        ])

        # ログに詳細レポート記録
        report_text = "\n".join(report_lines)
        self.logger.info("整合性チェック詳細レポート", report=report_text)


def create_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサー作成"""
    parser = argparse.ArgumentParser(
        description="バックアップメタデータ整合性チェッカー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s --auto-fix              # 自動修復付きチェック
  %(prog)s --no-fix --detailed     # チェックのみ（詳細レポート付き）
  %(prog)s --config custom.json    # カスタム設定ファイル使用
        """
    )

    parser.add_argument(
        '--config', '-c',
        type=str,
        help='設定ファイルパス（デフォルト: config/backup_config.json）'
    )

    parser.add_argument(
        '--auto-fix',
        action='store_true',
        default=True,
        help='発見した問題を自動修復（デフォルト）'
    )

    parser.add_argument(
        '--no-fix',
        action='store_true',
        help='自動修復を無効化（チェックのみ）'
    )

    parser.add_argument(
        '--detailed',
        action='store_true',
        help='詳細レポートを出力'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='コンソール出力を最小限に'
    )

    return parser


def main():
    """メイン関数"""
    parser = create_parser()
    args = parser.parse_args()

    # 設定の調整
    auto_fix = args.auto_fix and not args.no_fix

    try:
        checker = BackupIntegrityChecker(args.config)

        if not args.quiet:
            print("🔍 バックアップ整合性チェック開始...")

        success = checker.run_integrity_check(
            auto_fix=auto_fix,
            detailed_report=args.detailed
        )

        if success:
            if not args.quiet:
                print("✅ 整合性チェック完了")
            sys.exit(0)
        else:
            if not args.quiet:
                print("❌ 整合性チェック失敗")
            sys.exit(1)

    except KeyboardInterrupt:
        if not args.quiet:
            print("\n処理をキャンセルしました")
        sys.exit(130)
    except Exception as e:
        if not args.quiet:
            print(f"❌ 予期しないエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()