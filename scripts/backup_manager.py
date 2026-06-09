#!/usr/bin/env python3
"""
バックアップ管理システム - Raspberry Pi Dashboard
Phase 1: 基本バックアップシステム実装

機能:
- 設定ファイル管理
- ローカルバックアップ作成
- メタデータ管理
- バックアップ検証
"""

import json
import os
import shutil
import subprocess
import hashlib
import fcntl
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys

# ログシステム統合
sys.path.append(str(Path(__file__).parent.parent))
from logging_system import get_logger


class BackupError(Exception):
    """バックアップ関連例外"""
    pass


class BackupManager:
    """
    バックアップ管理メインクラス
    
    機能:
    - 設定ファイル読み込み・検証
    - バックアップディレクトリ管理
    - ロックファイル管理
    - rsyncベース増分バックアップ
    - メタデータ記録・管理
    - バックアップ検証
    """
    
    def __init__(self, config_file: str = None):
        """
        バックアップマネージャー初期化
        
        Args:
            config_file: 設定ファイルパス（デフォルト: config/backup_config.json）
        """
        self.logger = get_logger("backup_manager")
        
        # 設定ファイルパス決定
        if config_file is None:
            config_file = Path(__file__).parent.parent / "config" / "backup_config.json"
        
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        # パス設定
        self.backup_base_dir = Path(self.config['local_backup']['base_directory'])
        self.metadata_file = self.backup_base_dir / "backup_metadata.json"
        self.lock_file = Path(self.config['system']['lock_file'])
        
        # バックアップディレクトリ初期化
        self._initialize_backup_directory()
        
        # メタデータ初期化
        self.metadata = self._load_metadata()
        
        self.logger.info("バックアップマネージャー初期化完了", 
                        config_file=str(self.config_file),
                        backup_directory=str(self.backup_base_dir))
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """環境変数で設定値を上書き"""
        lb = config.setdefault('local_backup', {})
        if val := os.environ.get('BACKUP_BASE_DIR'):
            lb['base_directory'] = val
        if val := os.environ.get('BACKUP_MAX_BACKUPS'):
            lb['max_backups'] = int(val)
        if val := os.environ.get('BACKUP_RETENTION_DAYS'):
            lb['full_retention_days'] = int(val)
            lb['incremental_retention_days'] = int(val)
        if val := os.environ.get('BACKUP_FULL_RETENTION_DAYS'):
            lb['full_retention_days'] = int(val)
        if val := os.environ.get('BACKUP_INCREMENTAL_RETENTION_DAYS'):
            lb['incremental_retention_days'] = int(val)
        return config

    def _expand_home_in_config(self, obj):
        """設定値の ~ をホームディレクトリに再帰展開"""
        if isinstance(obj, str):
            return str(Path(obj).expanduser()) if obj.startswith('~') else obj
        if isinstance(obj, dict):
            return {k: self._expand_home_in_config(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._expand_home_in_config(v) for v in obj]
        return obj

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイル読み込み・検証"""
        if not self.config_file.exists():
            raise BackupError(f"設定ファイルが見つかりません: {self.config_file}")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # ~ をホームディレクトリに展開
            config = self._expand_home_in_config(config)

            # 環境変数で上書き
            config = self._apply_env_overrides(config)

            # 必要な設定項目の検証
            required_sections = ['backup', 'local_backup', 'source', 'system']
            for section in required_sections:
                if section not in config:
                    raise BackupError(f"設定ファイルに必要なセクションがありません: {section}")

            self.logger.success("設定ファイル読み込み完了",
                               config_sections=list(config.keys()))
            return config
            
        except json.JSONDecodeError as e:
            raise BackupError(f"設定ファイルのJSON形式エラー: {e}")
        except Exception as e:
            raise BackupError(f"設定ファイル読み込みエラー: {e}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """メタデータファイル読み込み"""
        if not self.metadata_file.exists():
            # 新規メタデータファイル作成
            initial_metadata = {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "backups": [],
                "statistics": {
                    "total_backups": 0,
                    "successful_backups": 0,
                    "failed_backups": 0,
                    "total_size_bytes": 0,
                    "last_backup": None
                }
            }
            self._save_metadata(initial_metadata)
            return initial_metadata
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            self.logger.info("メタデータ読み込み完了", 
                           backups_count=len(metadata.get('backups', [])))
            return metadata
            
        except json.JSONDecodeError as e:
            self.logger.error("メタデータファイル破損", error=str(e))
            raise BackupError(f"メタデータファイルのJSON形式エラー: {e}")
        except Exception as e:
            self.logger.error("メタデータ読み込みエラー", error=str(e))
            raise BackupError(f"メタデータ読み込みエラー: {e}")
    
    def _save_metadata(self, metadata: Dict[str, Any]):
        """メタデータファイル保存"""
        try:
            # バックアップディレクトリが存在することを確認
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 一時ファイルに書き込んで原子的更新
            temp_file = self.metadata_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
            
            # 原子的にファイル置換
            temp_file.replace(self.metadata_file)
            
            self.logger.debug("メタデータ保存完了", file=str(self.metadata_file))
            
        except Exception as e:
            self.logger.error("メタデータ保存エラー", error=str(e))
            raise BackupError(f"メタデータ保存エラー: {e}")
    
    def _reload_metadata(self):
        """メタデータ再読み込み"""
        self.metadata = self._load_metadata()
    
    def _initialize_backup_directory(self):
        """バックアップディレクトリ初期化"""
        try:
            # ディレクトリが存在しない場合のみ作成
            self.backup_base_dir.mkdir(parents=True, exist_ok=True)
            
            # 権限設定は手動で設定済みのため削除
            # バックアップベースディレクトリのみ使用（サブディレクトリ不要）
            
            self.logger.success("バックアップディレクトリ初期化完了",
                               directory=str(self.backup_base_dir))
                               
        except PermissionError:
            raise BackupError(f"バックアップディレクトリの権限がありません: {self.backup_base_dir}")
        except Exception as e:
            raise BackupError(f"バックアップディレクトリ初期化エラー: {e}")
    

    
    def acquire_lock(self) -> bool:
        """
        バックアップロック取得（同時実行防止）
        
        Returns:
            bool: ロック取得成功時True
        """
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            self._lock_fd = open(self.lock_file, 'w')
            fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # ロック情報記録
            self._lock_fd.write(json.dumps({
                'pid': os.getpid(),
                'start_time': datetime.now().isoformat(),
                'operation': 'backup'
            }))
            self._lock_fd.flush()
            
            self.logger.info("バックアップロック取得成功")
            return True
            
        except (IOError, OSError):
            self.logger.warning("バックアップロック取得失敗 - 他のプロセスが実行中")
            return False
    
    def release_lock(self):
        """バックアップロック解除"""
        try:
            if hasattr(self, '_lock_fd') and self._lock_fd:
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                self._lock_fd.close()
                self._lock_fd = None
                
                # ロックファイル削除
                if self.lock_file.exists():
                    self.lock_file.unlink()
                
                self.logger.info("バックアップロック解除完了")
                
        except Exception as e:
            self.logger.error("バックアップロック解除エラー", error=str(e))
    
    def create_local_backup(self, backup_type: str = "incremental", 
                           name: str = None, description: str = None) -> Dict[str, Any]:
        """
        ローカルバックアップ作成
        
        Args:
            backup_type: バックアップタイプ ("incremental" or "full")
            name: バックアップ名（オプション）
            description: バックアップ説明（オプション）
            
        Returns:
            Dict: バックアップ結果情報
        """
        if not self.acquire_lock():
            raise BackupError("他のバックアッププロセスが実行中です")
        
        backup_start = datetime.now()
        backup_id = f"{backup_type}_{backup_start.strftime('%Y%m%d_%H%M%S')}"
        
        if name:
            backup_id = f"{backup_id}_{name}"
        
        try:
            self.logger.info("バックアップ開始", 
                           backup_id=backup_id, 
                           backup_type=backup_type)
            
            # バックアップディレクトリ作成（直接ベースディレクトリに保存）
            backup_dir = self.backup_base_dir / backup_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # rsyncコマンド構築・実行
            result = self._execute_rsync_backup(backup_dir, backup_type)
            
            # バックアップサイズ計算
            backup_size = self._calculate_directory_size(backup_dir)
            
            # チェックサム計算
            checksum = self._calculate_backup_checksum(backup_dir)
            
            # メタデータ記録
            backup_info = {
                'backup_id': backup_id,
                'type': backup_type,
                'name': name or backup_id,
                'description': description or f"{backup_type} backup",
                'timestamp': backup_start.isoformat(),
                'duration_seconds': (datetime.now() - backup_start).total_seconds(),
                'size_bytes': backup_size,
                'checksum': checksum,
                'path': str(backup_dir),
                'status': 'completed',
                'rsync_stats': result,
                'source_paths': [
                    self.config['source']['home_directory']
                ] + self.config['source']['system_configs']
            }
            
            # フォーマット済み情報を追加
            backup_info.update(self._add_formatted_fields(backup_info, result))
            
            # メタデータ更新
            self.metadata['backups'].append(backup_info)
            self.metadata['statistics']['total_backups'] += 1
            self.metadata['statistics']['successful_backups'] += 1
            self.metadata['statistics']['total_size_bytes'] += backup_size
            self.metadata['statistics']['last_backup'] = backup_start.isoformat()
            self._save_metadata(self.metadata)
            
            self.logger.success("バックアップ完了", 
                              backup_id=backup_id,
                              size_mb=round(backup_size / 1024 / 1024, 2),
                              duration=round((datetime.now() - backup_start).total_seconds(), 2))
            
            return backup_info
            
        except Exception as e:
            self.logger.error("バックアップエラー", 
                            backup_id=backup_id, 
                            error=str(e))
            
            # エラー情報をメタデータに記録
            error_info = {
                'backup_id': backup_id,
                'type': backup_type,
                'timestamp': backup_start.isoformat(),
                'status': 'failed',
                'error': str(e),
                'duration_seconds': (datetime.now() - backup_start).total_seconds()
            }
            
            self.metadata['backups'].append(error_info)
            self.metadata['statistics']['total_backups'] += 1
            self.metadata['statistics']['failed_backups'] += 1
            self._save_metadata(self.metadata)
            
            raise BackupError(f"バックアップ作成エラー: {e}")
            
        finally:
            self.release_lock()
    
    def _execute_rsync_backup(self, backup_dir: Path, backup_type: str) -> Dict[str, Any]:
        """rsyncコマンド実行"""
        source_home = self.config['source']['home_directory']
        exclude_file = Path(self.config_file.parent) / "exclude_patterns.txt"
        
        # rsyncオプション構築
        rsync_cmd = ['rsync'] + [opt for opt in self.config['local_backup']['rsync_options'] 
                                if not opt.startswith('--exclude-from')]
        
        # 除外パターンファイル指定
        if exclude_file.exists():
            rsync_cmd.extend(['--exclude-from', str(exclude_file)])
        
        # ハードリンク使用（増分バックアップの場合）
        if (backup_type == "incremental" and 
            self.config['local_backup']['use_hardlinks']):
            print(f"🔍 DEBUG: 増分バックアップ設定確認")
            print(f"🔍 DEBUG: use_hardlinks = {self.config['local_backup']['use_hardlinks']}")
            
            # 最新のバックアップを探してリンク先に指定（現在作成中のディレクトリは除外）
            current_backup_name = backup_dir.name
            latest_backup = self._find_latest_backup("incremental", exclude_current=current_backup_name)
            print(f"🔍 DEBUG: 現在作成中のディレクトリ = {current_backup_name}")
            print(f"🔍 DEBUG: 検索された最新バックアップ = {latest_backup}")
            
            if latest_backup:
                print(f"🔍 DEBUG: --link-dest オプション追加: {latest_backup}")
                rsync_cmd.extend(['--link-dest', latest_backup])
            else:
                print(f"🔍 DEBUG: 最新バックアップが見つからない - 初回フルバックアップ実行")
        else:
            print(f"🔍 DEBUG: ハードリンク使用しない (backup_type={backup_type}, use_hardlinks={self.config['local_backup'].get('use_hardlinks', False)})")
        
        # 統計情報出力
        rsync_cmd.append('--stats')
        
        # ソース・デスティネーション指定
        rsync_cmd.extend([f"{source_home}/", str(backup_dir) + "/"])
        
        self.logger.info("rsyncコマンド実行", command=' '.join(rsync_cmd))
        print(f"🔍 DEBUG: rsyncコマンド = {' '.join(rsync_cmd)}")
        
        try:
            # rsync実行
            result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=self.config['system']['timeout_minutes'] * 60,
                check=True
            )
            
            # 統計情報解析
            stats = self._parse_rsync_stats(result.stdout)
            
            self.logger.success("rsync実行完了", 
                              files_transferred=stats.get('files_transferred', 0),
                              total_size=stats.get('total_file_size', 0))
            
            return stats
            
        except subprocess.TimeoutExpired:
            raise BackupError(f"rsyncタイムアウト ({self.config['system']['timeout_minutes']}分)")
        except subprocess.CalledProcessError as e:
            self.logger.error("rsyncエラー", 
                            returncode=e.returncode,
                            stderr=e.stderr)
            raise BackupError(f"rsyncエラー: {e.stderr}")
    
    def _find_latest_backup(self, backup_type: str, exclude_current: str = None) -> Optional[str]:
        """最新のバックアップディレクトリパスを取得"""
        # 直接ベースディレクトリから検索
        if not self.backup_base_dir.exists():
            return None
        
        # 日付順でソート（backup_metadata.jsonは除外）
        backup_dirs = [d for d in self.backup_base_dir.iterdir() 
                      if d.is_dir() and (d.name.startswith('incremental_') or d.name.startswith('full_'))]
        
        # 現在作成中のディレクトリを除外
        if exclude_current:
            backup_dirs = [d for d in backup_dirs if d.name != exclude_current]
        
        if not backup_dirs:
            return None
        
        backup_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return str(backup_dirs[0])
    
    def _parse_rsync_stats(self, output: str) -> Dict[str, Any]:
        """rsync統計情報解析"""
        stats = {}
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if 'Number of files:' in line:
                stats['number_of_files'] = int(line.split()[3].replace(',', ''))
            elif 'Number of created files:' in line:
                stats['files_transferred'] = int(line.split()[4].replace(',', ''))
            elif 'Total file size:' in line:
                stats['total_file_size'] = int(line.split()[3].replace(',', ''))
            elif 'Total transferred file size:' in line:
                stats['transferred_file_size'] = int(line.split()[4].replace(',', ''))
        
        return stats
    
    def _calculate_directory_size(self, directory: Path) -> int:
        """ディレクトリサイズ計算"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            self.logger.warning("サイズ計算エラー", directory=str(directory), error=str(e))
        
        return total_size
    
    def _calculate_backup_checksum(self, backup_dir: Path) -> str:
        """バックアップディレクトリのチェックサム計算"""
        hasher = hashlib.md5()
        
        try:
            for dirpath, dirnames, filenames in os.walk(backup_dir):
                # ディレクトリとファイルをソート（一貫性のため）
                dirnames.sort()
                filenames.sort()
                
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists() and filepath.is_file():
                        hasher.update(str(filepath.relative_to(backup_dir)).encode('utf-8'))
                        hasher.update(str(filepath.stat().st_mtime).encode('utf-8'))
                        hasher.update(str(filepath.stat().st_size).encode('utf-8'))
            
            return hasher.hexdigest()
            
        except Exception as e:
            self.logger.warning("チェックサム計算エラー", error=str(e))
            return "checksum_error"
    
    def list_backups(self, backup_type: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """バックアップ一覧取得"""
        backups = self.metadata.get('backups', [])
        
        # タイプフィルタ
        if backup_type:
            backups = [b for b in backups if b.get('type') == backup_type]
        
        # 日付順ソート（新しい順）
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # 件数制限
        if limit:
            backups = backups[:limit]
        
        self.logger.debug("バックアップ一覧取得", 
                         total_count=len(backups), 
                         backup_type=backup_type)
        
        return backups
    
    def get_backup_info(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """指定バックアップの情報取得"""
        backups = self.metadata.get('backups', [])
        
        for backup in backups:
            if backup.get('backup_id') == backup_id:
                self.logger.debug("バックアップ情報取得", backup_id=backup_id)
                return backup
        
        self.logger.warning("バックアップが見つかりません", backup_id=backup_id)
        return None
    
    def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        """バックアップ検証"""
        backup_info = self.get_backup_info(backup_id)
        
        if not backup_info:
            raise BackupError(f"バックアップが見つかりません: {backup_id}")
        
        backup_path = Path(backup_info['path'])
        if not backup_path.exists():
            return {
                'backup_id': backup_id,
                'status': 'failed',
                'error': 'バックアップディレクトリが存在しません'
            }
        
        try:
            # サイズ検証
            current_size = self._calculate_directory_size(backup_path)
            expected_size = backup_info.get('size_bytes', 0)
            size_match = abs(current_size - expected_size) < 1024  # 1KB許容範囲
            
            # チェックサム検証
            current_checksum = self._calculate_backup_checksum(backup_path)
            expected_checksum = backup_info.get('checksum', '')
            checksum_match = current_checksum == expected_checksum
            
            verification_result = {
                'backup_id': backup_id,
                'status': 'passed' if (size_match and checksum_match) else 'failed',
                'size_match': size_match,
                'checksum_match': checksum_match,
                'current_size': current_size,
                'expected_size': expected_size,
                'current_checksum': current_checksum,
                'expected_checksum': expected_checksum,
                'verified_at': datetime.now().isoformat()
            }
            
            self.logger.success("バックアップ検証完了", 
                              backup_id=backup_id,
                              status=verification_result['status'])
            
            return verification_result
            
        except Exception as e:
            self.logger.error("バックアップ検証エラー", 
                            backup_id=backup_id, 
                            error=str(e))
            return {
                'backup_id': backup_id,
                'status': 'error',
                'error': str(e),
                'verified_at': datetime.now().isoformat()
            }
    
    def cleanup_old_backups(self):
        """古いバックアップの削除"""
        max_backups = self.config['local_backup']['max_backups']
        
        # タイプ別保持期間設定
        full_retention_days = self.config['local_backup'].get('full_retention_days', 30)
        incremental_retention_days = self.config['local_backup'].get('incremental_retention_days', 14)
        
        cleanup_count = 0
        cleanup_size = 0
        metadata_modified = False

        try:
            # _reload_metadata を1回だけ呼び、以降は self.metadata を直接操作する
            # （list_backups は内部で _reload_metadata を呼ぶため、ループ内で使うと
            #   前の反復での削除がディスク未保存のまま上書きされてしまう）
            self._reload_metadata()

            for backup_type in ['incremental', 'full']:
                # タイプ別保持期間
                retention_days = full_retention_days if backup_type == 'full' else incremental_retention_days
                cutoff_date = datetime.now() - timedelta(days=retention_days)

                self.logger.info(f"{backup_type}バックアップクリーンアップ開始",
                               retention_days=retention_days)

                # list_backups を使わず現在のメタデータを直接フィルタ・ソート
                backups = sorted(
                    [b for b in self.metadata['backups'] if b.get('type') == backup_type],
                    key=lambda x: x.get('timestamp', ''),
                    reverse=True
                )

                # 件数制限による削除
                if len(backups) > max_backups:
                    old_backups = backups[max_backups:]

                    for backup in old_backups:
                        raw_path = backup.get('path')
                        if raw_path:
                            backup_path = Path(raw_path)
                            if backup_path.exists():
                                size = backup.get('size_bytes', 0)
                                shutil.rmtree(backup_path)
                                cleanup_count += 1
                                cleanup_size += size
                            else:
                                self.logger.warning(f"{backup_type}バックアップファイル未発見（メタデータのみ削除）",
                                                  backup_id=backup['backup_id'],
                                                  path=str(backup_path))

                        # path の有無・存在に関係なくメタデータから削除
                        self.metadata['backups'] = [
                            b for b in self.metadata['backups']
                            if b['backup_id'] != backup['backup_id']
                        ]
                        metadata_modified = True

                # 保持期間による削除
                for backup in backups:
                    # 件数制限で既に削除済みのエントリはスキップ
                    if not any(b['backup_id'] == backup['backup_id'] for b in self.metadata['backups']):
                        continue

                    backup_date = datetime.fromisoformat(backup['timestamp'].replace('Z', '+00:00'))
                    if backup_date < cutoff_date:
                        raw_path = backup.get('path')
                        backup_path = Path(raw_path) if raw_path else None
                        size = backup.get('size_bytes', 0)

                        if backup_path and backup_path.exists():
                            shutil.rmtree(backup_path)
                            cleanup_count += 1
                            cleanup_size += size
                            self.logger.info(f"{backup_type}バックアップ削除（保持期間超過）",
                                           backup_id=backup['backup_id'],
                                           age_days=(datetime.now() - backup_date).days)
                        elif backup_path:
                            self.logger.warning(f"{backup_type}バックアップファイル未発見（メタデータのみ削除）",
                                              backup_id=backup['backup_id'],
                                              path=str(backup_path))

                        self.metadata['backups'] = [
                            b for b in self.metadata['backups']
                            if b['backup_id'] != backup['backup_id']
                        ]
                        metadata_modified = True

            # メタデータ保存（物理削除・孤立エントリ削除いずれかがあれば保存）
            if metadata_modified:
                self._save_metadata(self.metadata)

                self.logger.success("古いバックアップクリーンアップ完了",
                                  deleted_count=cleanup_count,
                                  freed_mb=round(cleanup_size / 1024 / 1024, 2))
            else:
                self.logger.info("クリーンアップ対象のバックアップはありません")
                
        except Exception as e:
            self.logger.error("バックアップクリーンアップエラー", error=str(e))
            raise BackupError(f"バックアップクリーンアップエラー: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """バックアップ統計情報取得"""
        stats = self.metadata.get('statistics', {})

        # 最新情報で更新
        backups = self.metadata.get('backups', [])

        # 実際の占有サイズを計算（存在するファイルのみ）
        actual_size_bytes = 0
        valid_size_bytes = 0
        try:
            if self.backup_base_dir.exists():
                import subprocess
                result = subprocess.run(['du', '-sb', str(self.backup_base_dir)],
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    actual_size_bytes = int(result.stdout.split()[0])

                # 存在するバックアップのみのサイズも計算
                for backup in backups:
                    if backup.get('status') == 'completed':
                        backup_path = Path(backup['path'])
                        if backup_path.exists():
                            valid_size_bytes += backup.get('size_bytes', 0)

        except Exception as e:
            self.logger.warning("実際のサイズ取得エラー", error=str(e))

        # ハードリンク効率性計算
        hardlink_efficiency = 0.0
        if valid_size_bytes > 0 and actual_size_bytes > 0:
            hardlink_efficiency = (1 - actual_size_bytes / valid_size_bytes) * 100

        stats.update({
            'total_backups': len(backups),
            'successful_backups': len([b for b in backups if b.get('status') == 'completed']),
            'failed_backups': len([b for b in backups if b.get('status') == 'failed']),
            'valid_backups': len([b for b in backups if b.get('status') == 'completed' and Path(b['path']).exists()]),
            'total_size_bytes_logical': valid_size_bytes,  # 存在するファイルのみのサイズ
            'total_size_bytes': actual_size_bytes,  # 実際の占有サイズ
            'hardlink_efficiency_percent': round(hardlink_efficiency, 1),
            'total_transferred_bytes': sum(b.get('rsync_stats', {}).get('transferred_file_size', 0)
                                         for b in backups if b.get('status') == 'completed' and Path(b['path']).exists())
        })

        if backups:
            stats['last_backup'] = max(b['timestamp'] for b in backups)

        return stats
    
    def create_external_backup(self, backup_name: str, external_handler) -> bool:
        """
        外部バックアップハンドラーとの統合バックアップ
        
        Args:
            backup_name: バックアップ名
            external_handler: 外部バックアップハンドラー
            
        Returns:
            bool: バックアップ成功可否
        """
        try:
            self.logger.info("外部バックアップ統合実行開始", backup_name=backup_name)
            
            # 外部バックアップハンドラーを使用してバックアップ実行
            if hasattr(external_handler, 'create_external_backup_with_manager'):
                result = external_handler.create_external_backup_with_manager(backup_name, self)
            else:
                # フォールバック：ローカルバックアップ実行
                local_result = self.create_local_backup(name=backup_name, description="External backup fallback")
                result = local_result.get('status') == 'completed'
            
            self.logger.info("外部バックアップ統合実行完了", 
                           backup_name=backup_name, 
                           success=result)
            
            return result
            
        except Exception as e:
            self.logger.error("外部バックアップ統合実行エラー", 
                            backup_name=backup_name, 
                            error=str(e))
            return False
    
    def list_backups(self, backup_type: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """バックアップ一覧取得"""
        try:
            # 最新のメタデータを読み込み
            self._reload_metadata()
            backups = self.metadata.get('backups', [])
            
            # タイプフィルター
            if backup_type:
                backups = [b for b in backups if b.get('type') == backup_type]
            
            # 日時順でソート（新しい順）
            backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 件数制限
            if limit:
                backups = backups[:limit]
                
            return backups
            
        except Exception as e:
            self.logger.error("バックアップ一覧取得エラー", error=str(e))
            return []
    
    
    def delete_backup(self, backup_id: str) -> bool:
        """個別バックアップ削除（メタデータ自動更新）"""
        try:
            # バックアップ情報を検索
            backup_info = None
            for backup in self.metadata.get('backups', []):
                if backup['backup_id'] == backup_id:
                    backup_info = backup
                    break
            
            if not backup_info:
                self.logger.error("バックアップが見つかりません", backup_id=backup_id)
                return False
            
            # バックアップディレクトリを削除
            backup_path = Path(backup_info['path'])
            if backup_path.exists():
                shutil.rmtree(backup_path)
                self.logger.info("バックアップディレクトリ削除", path=str(backup_path))
            
            # メタデータから削除
            self.metadata['backups'] = [
                b for b in self.metadata['backups'] 
                if b['backup_id'] != backup_id
            ]
            
            # 統計情報更新
            stats = self.metadata.get('statistics', {})
            stats['total_backups'] = stats.get('total_backups', 0) - 1
            if backup_info.get('status') == 'completed':
                stats['successful_backups'] = stats.get('successful_backups', 0) - 1
            else:
                stats['failed_backups'] = stats.get('failed_backups', 0) - 1
            
            # 総サイズから減算
            backup_size = backup_info.get('size_bytes', 0)
            stats['total_size_bytes'] = stats.get('total_size_bytes', 0) - backup_size
            
            # 最新バックアップ更新
            remaining_backups = self.metadata.get('backups', [])
            if remaining_backups:
                remaining_backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                stats['last_backup'] = remaining_backups[0]['timestamp']
            else:
                stats['last_backup'] = None
            
            self.metadata['statistics'] = stats
            
            # メタデータ保存
            self._save_metadata(self.metadata)
            
            self.logger.success("バックアップ削除完了", 
                              backup_id=backup_id,
                              size_mb=round(backup_size / 1024 / 1024, 2))
            return True
            
        except Exception as e:
            self.logger.error("バックアップ削除エラー", 
                            backup_id=backup_id, 
                            error=str(e))
            return False
    
    def _add_formatted_fields(self, backup_info: Dict[str, Any], rsync_result: Dict[str, Any]) -> Dict[str, Any]:
        """バックアップ情報にフォーマット済みフィールドを追加"""
        formatted_fields = {}
        
        # サイズフォーマット
        size_bytes = backup_info.get('size_bytes', 0)
        formatted_fields['size_formatted'] = self._format_size(size_bytes)
        
        # 転送サイズとファイル数（rsync_statsから）
        rsync_stats = backup_info.get('rsync_stats', {})
        transferred_size = rsync_stats.get('transferred_file_size', 0)
        files_transferred = rsync_stats.get('files_transferred', 0)
        
        formatted_fields['transferred_size_bytes'] = transferred_size
        formatted_fields['transferred_size_formatted'] = self._format_size(transferred_size)
        formatted_fields['files_transferred'] = files_transferred
        
        # 効率性計算（転送済みサイズ vs 総サイズ）
        if size_bytes > 0:
            efficiency = (1 - transferred_size / size_bytes) * 100
            formatted_fields['efficiency_percent'] = round(efficiency, 1)
        else:
            formatted_fields['efficiency_percent'] = 0.0
        
        # タイムスタンプフォーマット
        timestamp = backup_info.get('timestamp', '')
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_fields['timestamp_formatted'] = dt.strftime('%Y/%m/%d %H:%M:%S')
            except Exception:
                formatted_fields['timestamp_formatted'] = timestamp[:19].replace('T', ' ')
        
        return formatted_fields
    
    def check_metadata_integrity(self, fix_issues: bool = False) -> Dict[str, Any]:
        """
        メタデータ整合性チェック

        Args:
            fix_issues: Trueの場合、発見した問題を自動修復

        Returns:
            Dict: チェック結果
        """
        self.logger.info("メタデータ整合性チェック開始", fix_issues=fix_issues)

        results = {
            'total_metadata_entries': 0,
            'valid_entries': 0,
            'invalid_entries': 0,
            'orphaned_files': 0,
            'missing_files': 0,
            'fixed_issues': 0,
            'issues': []
        }

        try:
            # メタデータ内のバックアップをチェック
            backups = self.metadata.get('backups', [])
            results['total_metadata_entries'] = len(backups)

            valid_backups = []

            for backup in backups:
                backup_path = Path(backup['path'])

                if backup_path.exists():
                    results['valid_entries'] += 1
                    valid_backups.append(backup)
                else:
                    results['invalid_entries'] += 1
                    results['missing_files'] += 1
                    issue = {
                        'type': 'missing_file',
                        'backup_id': backup['backup_id'],
                        'path': str(backup_path),
                        'timestamp': backup.get('timestamp', ''),
                        'size_mb': backup.get('size_bytes', 0) // 1024 // 1024
                    }
                    results['issues'].append(issue)

                    self.logger.warning("バックアップファイル未発見",
                                      backup_id=backup['backup_id'],
                                      path=str(backup_path))

            # ディレクトリ内の孤立ファイルをチェック
            if self.backup_base_dir.exists():
                actual_dirs = [d for d in self.backup_base_dir.iterdir()
                             if d.is_dir() and d.name.startswith('incremental_')]

                metadata_paths = {Path(b['path']).name for b in backups}

                for actual_dir in actual_dirs:
                    if actual_dir.name not in metadata_paths:
                        results['orphaned_files'] += 1
                        issue = {
                            'type': 'orphaned_file',
                            'path': str(actual_dir),
                            'name': actual_dir.name
                        }
                        results['issues'].append(issue)

                        self.logger.warning("孤立バックアップファイル発見",
                                          path=str(actual_dir))

            # 修復処理
            if fix_issues and (results['invalid_entries'] > 0 or results['orphaned_files'] > 0):
                if results['invalid_entries'] > 0:
                    # 存在しないファイルのメタデータを削除
                    self.metadata['backups'] = valid_backups

                    # 統計情報更新
                    stats = self.metadata.get('statistics', {})
                    stats['total_backups'] = len(valid_backups)
                    stats['successful_backups'] = len([b for b in valid_backups if b.get('status') == 'completed'])
                    stats['failed_backups'] = len([b for b in valid_backups if b.get('status') == 'failed'])

                    self.metadata['statistics'] = stats
                    self._save_metadata(self.metadata)

                    results['fixed_issues'] += results['invalid_entries']
                    self.logger.info("メタデータ修復完了",
                                   removed_entries=results['invalid_entries'])

                # 孤立ファイルは手動削除を推奨（データ損失防止）
                if results['orphaned_files'] > 0:
                    self.logger.warning("孤立ファイルが発見されました",
                                      count=results['orphaned_files'],
                                      recommendation="手動確認後に削除してください")

            # サマリー
            self.logger.success("メタデータ整合性チェック完了",
                              total_entries=results['total_metadata_entries'],
                              valid=results['valid_entries'],
                              invalid=results['invalid_entries'],
                              orphaned=results['orphaned_files'],
                              fixed=results['fixed_issues'])

            return results

        except Exception as e:
            self.logger.error("メタデータ整合性チェックエラー", error=str(e))
            results['error'] = str(e)
            return results

    def _format_size(self, size_bytes: int) -> str:
        """ファイルサイズフォーマット"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"


def main():
    """テスト・デモ実行"""
    try:
        # バックアップマネージャー初期化
        manager = BackupManager()
        
        print("=== Backup Manager Test ===")
        
        # 統計情報表示
        stats = manager.get_statistics()
        print(f"統計情報: {json.dumps(stats, indent=2, ensure_ascii=False, default=str)}")
        
        # バックアップ一覧表示
        backups = manager.list_backups(limit=5)
        print(f"最新バックアップ (5件): {len(backups)}個")
        
        for backup in backups:
            print(f"  - {backup['backup_id']}: {backup.get('status', 'unknown')} "
                  f"({backup.get('size_bytes', 0) // 1024 // 1024}MB)")
        
        print("テスト完了")
        
    except Exception as e:
        print(f"エラー: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())