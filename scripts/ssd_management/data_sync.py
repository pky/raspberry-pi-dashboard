#!/usr/bin/env python3
"""
M.2 SSD データ同期システム
タスク34対応 - 重要データの両ストレージ間自動同期機能

機能:
- 重要データの自動同期 (M.2 SSD ↔ microSD)
- 増分同期・整合性チェック
- cron自動化・監視統合
- 障害時フォールバック対応
"""

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from logging_system import get_logger

# プロジェクトルートを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import get_settings

class DataSyncSystem:
    """M.2 SSD データ同期システム"""
    
    def __init__(self):
        """初期化"""
        # ログ設定
        self.logger = get_logger(__name__)
        
        # 設定取得
        self.settings = get_settings()
        
        # 基本設定
        self.project_root = Path(__file__).parent.parent.parent

        # ストレージパス設定
        self.m2_ssd_root = Path("/")  # M.2 SSDルート (現在のシステム)
        self.microsd_backup = Path.home() / "backups" / "microsd_sync"
        
        # 同期設定
        self.sync_status_file = self.project_root / "logs/data_sync_status.json"
        self.sync_log_file = self.project_root / "logs/data_sync.log"
        
        # 重要データリスト定義
        self.critical_data_paths = [
            {
                "name": "credentials",
                "source_path": "raspberry-pi-dashboard/credentials/",
                "priority": 1,
                "sync_interval": 300,  # 5分
                "description": "Google認証情報・API証明書"
            },
            {
                "name": "co2_data",
                "source_path": "raspberry-pi-dashboard/logs/co2_data.db",
                "priority": 2,
                "sync_interval": 3600,  # 1時間
                "description": "CO2センサーデータベース"
            },
            {
                "name": "calendar_cache",
                "source_path": "raspberry-pi-dashboard/cache/holidays/",
                "priority": 3,
                "sync_interval": 86400,  # 24時間
                "description": "カレンダー・祝日キャッシュ"
            },
            {
                "name": "config_files",
                "source_path": "raspberry-pi-dashboard/config.py",
                "priority": 2,
                "sync_interval": 3600,  # 1時間
                "description": "アプリケーション設定"
            },
            {
                "name": "systemd_services",
                "source_path": "/etc/systemd/system/raspberry-pi-*.service",
                "priority": 1,
                "sync_interval": 86400,  # 24時間
                "description": "systemdサービス設定"
            }
        ]
        
        # 同期状態管理
        self.sync_status = self.load_sync_status()
        
    def load_sync_status(self) -> Dict:
        """同期状態ファイルの読み込み"""
        try:
            if self.sync_status_file.exists():
                with open(self.sync_status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    "last_full_sync": None,
                    "sync_history": [],
                    "file_checksums": {},
                    "sync_count": 0,
                    "error_count": 0
                }
        except Exception as e:
            self.logger.error(f"同期状態ファイル読み込みエラー: {e}")
            return {
                "last_full_sync": None,
                "sync_history": [],
                "file_checksums": {},
                "sync_count": 0,
                "error_count": 0
            }
    
    def save_sync_status(self):
        """同期状態ファイルの保存"""
        try:
            self.sync_status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.sync_status_file, 'w', encoding='utf-8') as f:
                json.dump(self.sync_status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"同期状態ファイル保存エラー: {e}")
    
    def calculate_file_checksum(self, file_path: Path) -> str:
        """ファイルチェックサム計算"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            self.logger.error(f"チェックサム計算エラー {file_path}: {e}")
            return ""
    
    def setup_backup_directory(self) -> bool:
        """バックアップディレクトリセットアップ"""
        try:
            self.microsd_backup.mkdir(parents=True, exist_ok=True)
            
            # テスト書き込み
            test_file = self.microsd_backup / "sync_test.tmp"
            test_file.write_text("sync_test")
            test_file.unlink()
            
            self.logger.info(f"バックアップディレクトリ準備完了: {self.microsd_backup}")
            return True
            
        except Exception as e:
            self.logger.error(f"バックアップディレクトリセットアップエラー: {e}")
            return False
    
    def sync_single_file(self, source_path: Path, dest_path: Path, 
                        sync_config: Dict) -> Tuple[bool, str]:
        """単一ファイルの同期"""
        try:
            # ソースファイル存在確認
            if not source_path.exists():
                return False, f"ソースファイル不存在: {source_path}"
            
            # 宛先ディレクトリ作成
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # チェックサム比較による変更検出
            source_checksum = self.calculate_file_checksum(source_path)
            file_key = str(source_path)
            
            # 既存ファイルのチェックサム確認
            if dest_path.exists() and file_key in self.sync_status["file_checksums"]:
                if self.sync_status["file_checksums"][file_key] == source_checksum:
                    return True, "変更なし"
            
            # ファイルコピー実行
            shutil.copy2(source_path, dest_path)
            
            # 権限設定
            if sync_config["name"] == "credentials":
                dest_path.chmod(0o600)
            elif sync_config["name"] == "systemd_services":
                dest_path.chmod(0o644)
            
            # チェックサム記録
            self.sync_status["file_checksums"][file_key] = source_checksum
            
            self.logger.info(f"ファイル同期成功: {source_path.name}")
            return True, "同期完了"
            
        except Exception as e:
            error_msg = f"ファイル同期エラー {source_path.name}: {e}"
            self.logger.error(error_msg)
            return False, error_msg
    
    def sync_directory(self, source_path: Path, dest_path: Path, 
                      sync_config: Dict) -> Tuple[bool, int, int]:
        """ディレクトリの同期"""
        success_count = 0
        error_count = 0
        
        try:
            # ディレクトリ作成
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # 全ファイルを同期
            for source_file in source_path.rglob("*"):
                if source_file.is_file():
                    relative_path = source_file.relative_to(source_path)
                    dest_file = dest_path / relative_path
                    
                    success, msg = self.sync_single_file(source_file, dest_file, sync_config)
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
            
            return True, success_count, error_count
            
        except Exception as e:
            self.logger.error(f"ディレクトリ同期エラー {source_path}: {e}")
            return False, success_count, error_count + 1
    
    def sync_data_set(self, sync_config: Dict, force: bool = False) -> Dict:
        """データセットの同期実行"""
        result = {
            "name": sync_config["name"],
            "success": False,
            "files_synced": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "message": ""
        }
        
        try:
            # 同期間隔チェック（強制実行でない場合）
            if not force:
                last_sync_key = f"last_sync_{sync_config['name']}"
                if last_sync_key in self.sync_status:
                    last_sync = datetime.fromisoformat(self.sync_status[last_sync_key])
                    interval = timedelta(seconds=sync_config["sync_interval"])
                    if datetime.now() - last_sync < interval:
                        result["message"] = "同期間隔内のためスキップ"
                        result["success"] = True
                        return result
            
            # ソースパス解決
            source_path_str = sync_config["source_path"]
            
            # systemdファイルの特別処理
            if sync_config["name"] == "systemd_services":
                systemd_files = list(Path("/etc/systemd/system").glob("raspberry-pi-*.service"))
                dest_dir = self.microsd_backup / "systemd"
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                for systemd_file in systemd_files:
                    dest_file = dest_dir / systemd_file.name
                    success, msg = self.sync_single_file(systemd_file, dest_file, sync_config)
                    if success:
                        result["files_synced"] += 1
                    else:
                        result["errors"] += 1
            else:
                # 通常ファイル・ディレクトリ処理
                if source_path_str.startswith("/"):
                    source_path = Path(source_path_str)
                else:
                    source_path = Path(__file__).parent.parent.parent.parent / source_path_str
                
                dest_path = self.microsd_backup / sync_config["name"]
                
                if source_path.is_dir():
                    success, synced, errors = self.sync_directory(source_path, dest_path, sync_config)
                    result["files_synced"] = synced
                    result["errors"] = errors
                elif source_path.is_file():
                    dest_file = dest_path.parent / source_path.name
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    success, msg = self.sync_single_file(source_path, dest_file, sync_config)
                    if success:
                        result["files_synced"] = 1
                    else:
                        result["errors"] = 1
                        result["message"] = msg
                else:
                    result["message"] = f"ソースパス不存在: {source_path}"
                    result["errors"] = 1
            
            # 結果判定
            if result["errors"] == 0:
                result["success"] = True
                result["message"] = f"{result['files_synced']}ファイル同期完了"
                # 最終同期時刻記録
                self.sync_status[f"last_sync_{sync_config['name']}"] = datetime.now().isoformat()
            else:
                result["message"] = f"{result['files_synced']}成功, {result['errors']}失敗"
            
        except Exception as e:
            result["errors"] += 1
            result["message"] = f"同期処理エラー: {e}"
            self.logger.error(f"データセット同期エラー {sync_config['name']}: {e}")
        
        finally:
            result["end_time"] = datetime.now().isoformat()
        
        return result
    
    def run_full_sync(self, force: bool = False) -> Dict:
        """完全同期実行"""
        sync_report = {
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "backup_available": False,
            "total_datasets": len(self.critical_data_paths),
            "successful_datasets": 0,
            "failed_datasets": 0,
            "total_files_synced": 0,
            "total_errors": 0,
            "sync_results": []
        }
        
        try:
            self.logger.info("M.2 SSD データ同期開始")
            
            # バックアップディレクトリセットアップ
            if not self.setup_backup_directory():
                sync_report["error"] = "バックアップディレクトリセットアップ失敗"
                self.logger.error("バックアップディレクトリセットアップ失敗 - 同期中断")
                return sync_report
            
            sync_report["backup_available"] = True
            
            # データセット毎に同期実行
            for sync_config in self.critical_data_paths:
                self.logger.info(f"データセット同期開始: {sync_config['name']}")
                
                result = self.sync_data_set(sync_config, force)
                sync_report["sync_results"].append(result)
                
                if result["success"]:
                    sync_report["successful_datasets"] += 1
                else:
                    sync_report["failed_datasets"] += 1
                
                sync_report["total_files_synced"] += result["files_synced"]
                sync_report["total_errors"] += result["errors"]
            
            # 同期履歴記録
            self.sync_status["last_full_sync"] = datetime.now().isoformat()
            self.sync_status["sync_count"] += 1
            self.sync_status["error_count"] += sync_report["total_errors"]
            
            self.sync_status["sync_history"].append({
                "timestamp": datetime.now().isoformat(),
                "total_files": sync_report["total_files_synced"],
                "errors": sync_report["total_errors"],
                "success": sync_report["failed_datasets"] == 0
            })
            
            # 履歴制限（最新20件）
            if len(self.sync_status["sync_history"]) > 20:
                self.sync_status["sync_history"] = self.sync_status["sync_history"][-20:]
            
        except Exception as e:
            sync_report["error"] = f"完全同期エラー: {e}"
            self.logger.error(f"完全同期エラー: {e}")
            
        finally:
            sync_report["end_time"] = datetime.now().isoformat()
            self.save_sync_status()
        
        return sync_report
    
    def generate_sync_report(self) -> str:
        """同期レポート生成"""
        try:
            report_lines = [
                "M.2 SSD データ同期システム レポート",
                f"生成時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "=" * 50,
                ""
            ]
            
            # 基本状況
            if self.sync_status["last_full_sync"]:
                last_sync = datetime.fromisoformat(self.sync_status["last_full_sync"])
                report_lines.extend([
                    f"最終完全同期: {last_sync.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"同期からの経過: {datetime.now() - last_sync}",
                    f"累計同期回数: {self.sync_status['sync_count']}",
                    f"累計エラー数: {self.sync_status['error_count']}",
                    f"追跡ファイル数: {len(self.sync_status['file_checksums'])}",
                    ""
                ])
            else:
                report_lines.extend([
                    "最終完全同期: 未実行",
                    ""
                ])
            
            # 同期履歴（最新3件）
            report_lines.extend([
                "同期履歴（最新3件）:",
                "-" * 30
            ])
            
            recent_history = self.sync_status["sync_history"][-3:]
            for history in reversed(recent_history):
                timestamp = datetime.fromisoformat(history["timestamp"])
                status = "✅ 成功" if history["success"] else "❌ 失敗"
                report_lines.append(
                    f"{timestamp.strftime('%m-%d %H:%M')} {status} "
                    f"({history['total_files']}ファイル, {history['errors']}エラー)"
                )
            
            if not recent_history:
                report_lines.append("履歴なし")
            
            report_lines.append("")
            
            # 重要データ設定
            report_lines.extend([
                "重要データ設定:",
                "-" * 30
            ])
            
            for config in self.critical_data_paths:
                interval_str = f"{config['sync_interval']//60}分" if config['sync_interval'] < 3600 else f"{config['sync_interval']//3600}時間"
                
                report_lines.extend([
                    f"📁 {config['name']} (優先度{config['priority']})",
                    f"   同期間隔: {interval_str}",
                    f"   説明: {config['description']}",
                    ""
                ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            self.logger.error(f"レポート生成エラー: {e}")
            return f"レポート生成エラー: {e}"

def main():
    """メイン実行"""
    import argparse
    
    parser = argparse.ArgumentParser(description="M.2 SSD データ同期システム")
    parser.add_argument("--auto-sync", action="store_true", help="自動同期実行")
    parser.add_argument("--force-sync", action="store_true", help="強制完全同期")
    parser.add_argument("--report", action="store_true", help="同期レポート表示")
    
    args = parser.parse_args()
    
    sync_system = DataSyncSystem()
    
    if args.auto_sync:
        # 自動同期（間隔チェックあり）
        result = sync_system.run_full_sync(force=False)
        self.logger.success("自動同期完了: {result['successful_datasets']}/{result['total_datasets']} 成功")
        
    elif args.force_sync:
        # 強制完全同期
        result = sync_system.run_full_sync(force=True)
        self.logger.success("強制同期完了: {result['successful_datasets']}/{result['total_datasets']} 成功, {result['total_files_synced']} ファイル")
        
    elif args.report:
        # レポート表示
        self.logger.info("Manual conversion needed: sync_system.generate_sync_report()...")  # TODO: 手動変換
        
    else:
        # デフォルト: レポート表示
        self.logger.info("Manual conversion needed: sync_system.generate_sync_report()...")  # TODO: 手動変換

if __name__ == "__main__":
    main()