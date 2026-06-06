#!/usr/bin/env python3
"""
復元管理システム - Raspberry Pi Dashboard
Phase 1: 基本復元機能実装

機能:
- バックアップ選択・復元実行
- 部分復元機能（ファイル・ディレクトリ指定）
- 復元前現在状態バックアップ
- 復元検証・ロールバック
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys

# ログシステム統合
sys.path.append(str(Path(__file__).parent.parent))
from logging_system import get_logger
from scripts.backup_manager import BackupManager, BackupError


class RestoreError(Exception):
    """復元関連例外"""
    pass


class RestoreManager:
    """
    復元管理メインクラス
    
    機能:
    - バックアップ選択・復元実行
    - 部分復元機能
    - 復元前バックアップ
    - 復元検証
    """
    
    def __init__(self, config_file: str = None):
        """復元マネージャー初期化"""
        self.logger = get_logger("restore_manager")
        
        # バックアップマネージャー連携
        self.backup_manager = BackupManager(config_file)
        self.config = self.backup_manager.config
        
        # 復元用一時ディレクトリ
        self.temp_dir = Path(tempfile.gettempdir()) / "raspberry-pi-restore"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info("復元マネージャー初期化完了")
    
    def list_available_backups(self) -> List[Dict[str, Any]]:
        """復元可能なバックアップ一覧取得"""
        try:
            backups = self.backup_manager.list_backups()
            # 完了済みのバックアップのみを復元対象とする
            available_backups = [
                backup for backup in backups 
                if backup.get('status') == 'completed'
            ]
            
            self.logger.info("復元可能バックアップ一覧取得完了", 
                           total_count=len(available_backups))
            return available_backups
            
        except Exception as e:
            self.logger.error("バックアップ一覧取得エラー", error=str(e))
            raise RestoreError(f"バックアップ一覧取得エラー: {e}")
    
    def create_pre_restore_backup(self, description: str = None) -> Dict[str, Any]:
        """復元前の現在状態バックアップ作成"""
        try:
            if description is None:
                description = f"復元前自動バックアップ - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            self.logger.info("復元前バックアップ作成開始")
            
            # 自動バックアップ作成
            backup_info = self.backup_manager.create_local_backup(
                backup_type="incremental",
                name="pre_restore",
                description=description
            )
            
            self.logger.success("復元前バックアップ作成完了", 
                              backup_id=backup_info['backup_id'])
            return backup_info
            
        except Exception as e:
            self.logger.error("復元前バックアップ作成エラー", error=str(e))
            raise RestoreError(f"復元前バックアップ作成エラー: {e}")
    
    def restore_full_backup(self, backup_id: str, 
                           create_pre_backup: bool = True) -> Dict[str, Any]:
        """フルバックアップ復元"""
        try:
            self.logger.info("フル復元開始", backup_id=backup_id)
            
            # バックアップ情報取得・検証
            backup_info = self.backup_manager.get_backup_info(backup_id)
            if not backup_info:
                raise RestoreError(f"バックアップが見つかりません: {backup_id}")
            
            backup_path = Path(backup_info['path'])
            if not backup_path.exists():
                raise RestoreError(f"バックアップディレクトリが存在しません: {backup_path}")
            
            # 復元前バックアップ作成
            pre_backup_info = None
            if create_pre_backup:
                pre_backup_info = self.create_pre_restore_backup(
                    f"復元前バックアップ (復元対象: {backup_id})"
                )
            
            # 復元実行
            restore_start = datetime.now()
            
            # ホームディレクトリ復元
            home_directory = self.config['source']['home_directory']
            self.logger.info("ホームディレクトリ復元開始", 
                           source=str(backup_path),
                           destination=home_directory)
            
            # rsync使用で安全復元（deleteオプションなし・より安全）
            rsync_cmd = [
                'rsync', '-avz',
                f"{backup_path}/",
                f"{home_directory}/"
            ]
            
            self.logger.info("rsyncコマンド実行", command=' '.join(rsync_cmd))
            
            result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分タイムアウト
                check=True
            )
            
            # システム設定ファイル復元（オプション）
            system_configs = self.config['source'].get('system_configs', [])
            restored_configs = []
            
            for config_path in system_configs:
                try:
                    config_backup_path = backup_path / config_path.lstrip('/')
                    if config_backup_path.exists():
                        shutil.copy2(str(config_backup_path), config_path)
                        restored_configs.append(config_path)
                        self.logger.debug("システム設定復元", config=config_path)
                except Exception as config_error:
                    self.logger.warning("システム設定復元スキップ", 
                                      config=config_path, 
                                      error=str(config_error))
            
            restore_duration = (datetime.now() - restore_start).total_seconds()
            
            # 復元結果記録
            restore_result = {
                'restore_id': f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'backup_id': backup_id,
                'restore_type': 'full',
                'timestamp': restore_start.isoformat(),
                'duration_seconds': restore_duration,
                'status': 'completed',
                'pre_backup_id': pre_backup_info['backup_id'] if pre_backup_info else None,
                'restored_paths': [home_directory] + restored_configs,
                'rsync_output': result.stdout
            }
            
            self.logger.success("フル復元完了",
                              backup_id=backup_id,
                              duration_seconds=round(restore_duration, 2))
            
            return restore_result
            
        except subprocess.TimeoutExpired:
            self.logger.error("復元タイムアウト", backup_id=backup_id)
            raise RestoreError("復元処理がタイムアウトしました")
        except subprocess.CalledProcessError as e:
            self.logger.error("rsync復元エラー", 
                            backup_id=backup_id,
                            stderr=e.stderr)
            raise RestoreError(f"復元処理エラー: {e.stderr}")
        except Exception as e:
            self.logger.error("復元エラー", 
                            backup_id=backup_id, 
                            error=str(e))
            raise RestoreError(f"復元エラー: {e}")
    
    def restore_partial_backup(self, backup_id: str, 
                             target_paths: List[str]) -> Dict[str, Any]:
        """部分復元（指定パスのみ）"""
        try:
            self.logger.info("部分復元開始", 
                           backup_id=backup_id,
                           target_paths=target_paths)
            
            # バックアップ情報取得・検証
            backup_info = self.backup_manager.get_backup_info(backup_id)
            if not backup_info:
                raise RestoreError(f"バックアップが見つかりません: {backup_id}")
            
            backup_path = Path(backup_info['path'])
            if not backup_path.exists():
                raise RestoreError(f"バックアップディレクトリが存在しません: {backup_path}")
            
            restore_start = datetime.now()
            restored_files = []
            skipped_files = []
            
            # 各ターゲットパス個別復元
            for target_path in target_paths:
                try:
                    # 相対パス変換
                    relative_path = target_path.replace(self.config['source']['home_directory'], '').lstrip('/')
                    source_file = backup_path / relative_path
                    
                    if source_file.exists():
                        if source_file.is_file():
                            # ファイル復元
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            shutil.copy2(str(source_file), target_path)
                            restored_files.append(target_path)
                        elif source_file.is_dir():
                            # ディレクトリ復元
                            if os.path.exists(target_path):
                                shutil.rmtree(target_path)
                            shutil.copytree(str(source_file), target_path)
                            restored_files.append(target_path)
                        
                        self.logger.debug("ファイル復元成功", target=target_path)
                    else:
                        skipped_files.append(target_path)
                        self.logger.warning("復元対象ファイルが見つかりません", 
                                          target=target_path,
                                          source=str(source_file))
                        
                except Exception as file_error:
                    skipped_files.append(target_path)
                    self.logger.error("ファイル復元エラー", 
                                    target=target_path,
                                    error=str(file_error))
            
            restore_duration = (datetime.now() - restore_start).total_seconds()
            
            # 復元結果記録
            restore_result = {
                'restore_id': f"partial_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'backup_id': backup_id,
                'restore_type': 'partial',
                'timestamp': restore_start.isoformat(),
                'duration_seconds': restore_duration,
                'status': 'completed',
                'target_paths': target_paths,
                'restored_files': restored_files,
                'skipped_files': skipped_files,
                'success_count': len(restored_files),
                'failure_count': len(skipped_files)
            }
            
            self.logger.success("部分復元完了",
                              backup_id=backup_id,
                              restored_count=len(restored_files),
                              skipped_count=len(skipped_files),
                              duration_seconds=round(restore_duration, 2))
            
            return restore_result
            
        except Exception as e:
            self.logger.error("部分復元エラー", 
                            backup_id=backup_id, 
                            error=str(e))
            raise RestoreError(f"部分復元エラー: {e}")
    
    def verify_restore(self, restore_result: Dict[str, Any]) -> Dict[str, Any]:
        """復元検証"""
        try:
            self.logger.info("復元検証開始", 
                           restore_id=restore_result.get('restore_id'))
            
            verification_start = datetime.now()
            verified_files = []
            failed_verifications = []
            
            restored_paths = restore_result.get('restored_files', 
                                              restore_result.get('restored_paths', []))
            
            for path in restored_paths:
                try:
                    if os.path.exists(path):
                        # 基本的なファイル存在確認
                        stat_info = os.stat(path)
                        verified_files.append({
                            'path': path,
                            'size': stat_info.st_size,
                            'mtime': stat_info.st_mtime
                        })
                    else:
                        failed_verifications.append(path)
                        
                except Exception as verify_error:
                    failed_verifications.append(path)
                    self.logger.warning("ファイル検証エラー", 
                                      path=path,
                                      error=str(verify_error))
            
            verification_duration = (datetime.now() - verification_start).total_seconds()
            
            verification_result = {
                'restore_id': restore_result.get('restore_id'),
                'verification_status': 'passed' if not failed_verifications else 'failed',
                'verified_files': verified_files,
                'failed_verifications': failed_verifications,
                'verification_timestamp': verification_start.isoformat(),
                'verification_duration_seconds': verification_duration
            }
            
            self.logger.success("復元検証完了",
                              verified_count=len(verified_files),
                              failed_count=len(failed_verifications),
                              status=verification_result['verification_status'])
            
            return verification_result
            
        except Exception as e:
            self.logger.error("復元検証エラー", error=str(e))
            raise RestoreError(f"復元検証エラー: {e}")


def main():
    """テスト・デモ実行"""
    try:
        # 復元マネージャー初期化
        restore_manager = RestoreManager()
        
        print("=== Restore Manager Test ===")
        
        # 利用可能なバックアップ一覧表示
        backups = restore_manager.list_available_backups()
        print(f"復元可能なバックアップ: {len(backups)}個")
        
        for backup in backups[:3]:  # 最新3件表示
            print(f"  - {backup['backup_id']}: {backup.get('type', 'unknown')} "
                  f"({backup.get('size_bytes', 0) // 1024 // 1024}MB) "
                  f"[{backup.get('timestamp', 'unknown')}]")
        
        print("復元マネージャーテスト完了")
        
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())