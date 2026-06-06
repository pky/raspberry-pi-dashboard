#!/usr/bin/env python3
"""
Restore Manager Test Cases
復元管理システムの動作テスト

Test Categories:
1. RestoreManager初期化テスト
2. 復元可能バックアップ一覧取得テスト
3. バックアップ情報取得テスト
4. 復元検証テスト
5. エラーハンドリングテスト

Phase 1, Task 6: 復元機能テスト実装
"""

import unittest
import tempfile
import shutil
import json
import os
import sys
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from scripts.restore_manager import RestoreManager, RestoreError
    from scripts.backup_manager import BackupManager, BackupError
    RESTORE_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: RestoreManager not available: {e}")
    RESTORE_MANAGER_AVAILABLE = False


@unittest.skipUnless(RESTORE_MANAGER_AVAILABLE, "RestoreManager not available")
class TestRestoreManager(unittest.TestCase):
    """RestoreManager basic functionality tests"""
    
    def setUp(self):
        """テストセットアップ"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_restore_"))
        self.config_dir = self.test_dir / "config"
        self.backup_dir = self.test_dir / "backups"
        self.config_dir.mkdir(parents=True)
        self.backup_dir.mkdir(parents=True)
        
        # テスト用設定ファイル作成
        self.config_file = self.config_dir / "backup_config.json"
        self.test_config = {
            "backup": {
                "enabled": True,
                "schedule": "daily",
                "retention_days": 30
            },
            "local_backup": {
                "base_directory": str(self.backup_dir),
                "rsync_options": ["-av", "--delete"],
                "use_hardlinks": True,
                "max_backups": 10,
                "full_retention_days": 30,
                "incremental_retention_days": 14
            },
            "source": {
                "home_directory": str(self.test_dir / "home"),
                "system_configs": [
                    "/etc/systemd/system/raspberry-pi-*.service",
                    "/etc/logrotate.d/raspberry-pi-dashboard"
                ]
            },
            "system": {
                "lock_file": str(self.test_dir / "backup.lock"),
                "timeout_minutes": 30
            }
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f, indent=2)
        
        # テスト用バックアップメタデータ作成
        self.metadata_file = self.backup_dir / "backup_metadata.json"
        self.test_metadata = {
            "version": "1.0",
            "created": "2025-08-24T10:00:00",
            "backups": [
                {
                    "backup_id": "test_backup_001",
                    "type": "incremental",
                    "name": "test_backup_001",
                    "description": "Test backup for unit tests",
                    "timestamp": "2025-08-24T10:00:00",
                    "duration_seconds": 30.5,
                    "size_bytes": 1024000,
                    "checksum": "test_checksum_001",
                    "path": str(self.backup_dir / "test_backup_001"),
                    "status": "completed",
                    "rsync_stats": {
                        "files_transferred": 100,
                        "total_file_size": 1024000
                    }
                },
                {
                    "backup_id": "test_backup_002",
                    "type": "full",
                    "name": "test_backup_002",
                    "description": "Test full backup",
                    "timestamp": "2025-08-24T11:00:00",
                    "duration_seconds": 60.0,
                    "size_bytes": 2048000,
                    "checksum": "test_checksum_002",
                    "path": str(self.backup_dir / "test_backup_002"),
                    "status": "completed",
                    "rsync_stats": {
                        "files_transferred": 200,
                        "total_file_size": 2048000
                    }
                },
                {
                    "backup_id": "test_backup_failed",
                    "type": "incremental",
                    "name": "test_backup_failed",
                    "description": "Failed backup",
                    "timestamp": "2025-08-24T12:00:00",
                    "duration_seconds": 5.0,
                    "status": "failed",
                    "error": "Test error"
                }
            ],
            "statistics": {
                "total_backups": 3,
                "successful_backups": 2,
                "failed_backups": 1,
                "total_size_bytes": 3072000
            }
        }
        
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_metadata, f, indent=2)
        
        # テスト用バックアップディレクトリ作成
        test_backup_dir1 = self.backup_dir / "test_backup_001"
        test_backup_dir2 = self.backup_dir / "test_backup_002"
        test_backup_dir1.mkdir()
        test_backup_dir2.mkdir()
        
        # テスト用ファイル作成
        (test_backup_dir1 / "test_file1.txt").write_text("test content 1")
        (test_backup_dir2 / "test_file2.txt").write_text("test content 2")
        
        # ホームディレクトリ作成
        home_dir = self.test_dir / "home"
        home_dir.mkdir()
    
    def tearDown(self):
        """テストクリーンアップ"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_restore_manager_initialization(self):
        """復元マネージャー初期化テスト"""
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            
            # 初期化確認
            self.assertIsInstance(restore_manager.backup_manager, BackupManager)
            self.assertEqual(restore_manager.config, self.test_config)
            self.assertTrue(restore_manager.temp_dir.exists())
            
            # ログ記録確認
            mock_logger.return_value.info.assert_called_with("復元マネージャー初期化完了")
    
    def test_list_available_backups(self):
        """復元可能バックアップ一覧取得テスト"""
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            backups = restore_manager.list_available_backups()
            
            # 完了済みバックアップのみが返されることを確認
            self.assertEqual(len(backups), 2)  # failed除く
            
            # バックアップ情報確認
            backup_ids = [b['backup_id'] for b in backups]
            self.assertIn('test_backup_001', backup_ids)
            self.assertIn('test_backup_002', backup_ids)
            self.assertNotIn('test_backup_failed', backup_ids)
            
            # ログ記録確認
            mock_logger.return_value.info.assert_called_with(
                "復元可能バックアップ一覧取得完了", total_count=2
            )
    
    def test_list_available_backups_empty(self):
        """復元可能バックアップなしテスト"""
        # 空のメタデータ作成
        empty_metadata = {
            "version": "1.0",
            "created": "2025-08-24T10:00:00",
            "backups": [],
            "statistics": {"total_backups": 0, "successful_backups": 0, "failed_backups": 0}
        }
        
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(empty_metadata, f, indent=2)
        
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            backups = restore_manager.list_available_backups()
            
            self.assertEqual(len(backups), 0)
    
    @patch('scripts.restore_manager.subprocess.run')
    def test_create_pre_restore_backup(self, mock_subprocess):
        """復元前バックアップ作成テスト"""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="Test rsync output"
        )
        
        with patch('scripts.restore_manager.get_logger') as mock_logger, \
             patch('scripts.backup_manager.get_logger') as mock_backup_logger:
            
            mock_logger.return_value = MagicMock()
            mock_backup_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            
            with patch.object(restore_manager.backup_manager, 'create_local_backup') as mock_create:
                mock_create.return_value = {
                    'backup_id': 'pre_restore_20250824_120000',
                    'status': 'completed'
                }
                
                result = restore_manager.create_pre_restore_backup("Test pre-restore backup")
                
                # 結果確認
                self.assertEqual(result['backup_id'], 'pre_restore_20250824_120000')
                self.assertEqual(result['status'], 'completed')
                
                # バックアップマネージャー呼び出し確認
                mock_create.assert_called_once()
                call_args = mock_create.call_args
                self.assertEqual(call_args[1]['backup_type'], 'incremental')
                self.assertEqual(call_args[1]['name'], 'pre_restore')
                self.assertEqual(call_args[1]['description'], 'Test pre-restore backup')
    
    def test_verify_restore_success(self):
        """復元検証成功テスト"""
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            
            # テスト用復元結果
            restore_result = {
                'restore_id': 'test_restore_001',
                'restored_paths': [str(self.test_dir / "home")]
            }
            
            # ホームディレクトリにテストファイル作成
            test_file = self.test_dir / "home" / "test_file.txt"
            test_file.write_text("test content")
            
            verification_result = restore_manager.verify_restore(restore_result)
            
            # 検証結果確認
            self.assertEqual(verification_result['restore_id'], 'test_restore_001')
            self.assertEqual(verification_result['verification_status'], 'passed')
            self.assertEqual(len(verification_result['verified_files']), 1)
            self.assertEqual(len(verification_result['failed_verifications']), 0)
            
            # ファイル情報確認
            verified_file = verification_result['verified_files'][0]
            self.assertEqual(verified_file['path'], str(self.test_dir / "home"))
    
    def test_verify_restore_failure(self):
        """復元検証失敗テスト"""
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            
            # 存在しないパスの復元結果
            restore_result = {
                'restore_id': 'test_restore_002',
                'restored_paths': [str(self.test_dir / "nonexistent")]
            }
            
            verification_result = restore_manager.verify_restore(restore_result)
            
            # 検証結果確認
            self.assertEqual(verification_result['restore_id'], 'test_restore_002')
            self.assertEqual(verification_result['verification_status'], 'failed')
            self.assertEqual(len(verification_result['verified_files']), 0)
            self.assertEqual(len(verification_result['failed_verifications']), 1)
    
    def test_backup_manager_error_handling(self):
        """バックアップマネージャーエラーハンドリングテスト"""
        # 無効な設定ファイルでテスト
        invalid_config = self.config_dir / "invalid_config.json"
        invalid_config.write_text("invalid json content")
        
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            with self.assertRaises((RestoreError, BackupError)):
                RestoreManager(str(invalid_config))
    
    def test_restore_error_handling(self):
        """復元エラーハンドリングテスト"""
        with patch('scripts.restore_manager.get_logger') as mock_logger:
            mock_logger.return_value = MagicMock()
            
            restore_manager = RestoreManager(str(self.config_file))
            
            # 存在しないバックアップIDでエラーテスト
            with patch.object(restore_manager.backup_manager, 'get_backup_info') as mock_get_info:
                mock_get_info.return_value = None
                
                with self.assertRaises(RestoreError) as context:
                    restore_manager.restore_full_backup("nonexistent_backup")
                
                self.assertIn("バックアップが見つかりません", str(context.exception))


class TestRestoreManagerStandalone(unittest.TestCase):
    """RestoreManager standalone tests (without dependencies)"""
    
    def test_restore_error_creation(self):
        """RestoreError例外クラステスト"""
        error = RestoreError("Test error message")
        self.assertEqual(str(error), "Test error message")
        self.assertIsInstance(error, Exception)
    
    @unittest.skipUnless(RESTORE_MANAGER_AVAILABLE, "RestoreManager not available")
    def test_import_availability(self):
        """インポート可能性テスト"""
        from scripts.restore_manager import RestoreManager, RestoreError
        
        # クラスが正しくインポートできることを確認
        self.assertTrue(callable(RestoreManager))
        self.assertTrue(issubclass(RestoreError, Exception))


def run_tests():
    """テスト実行メイン関数"""
    print("=== Restore Manager Test Suite ===")
    print("復元管理システム動作テスト実行中...")
    
    # テストスイート作成
    test_suite = unittest.TestSuite()
    
    # テストケース追加
    if RESTORE_MANAGER_AVAILABLE:
        test_suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRestoreManager))
    
    test_suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRestoreManagerStandalone))
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 結果サマリー
    print(f"\n=== Test Results Summary ===")
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    
    if result.failures:
        print(f"\n=== Failures ===")
        for test, traceback in result.failures:
            print(f"FAIL: {test}")
            print(f"Traceback: {traceback}")
    
    if result.errors:
        print(f"\n=== Errors ===")
        for test, traceback in result.errors:
            print(f"ERROR: {test}")
            print(f"Traceback: {traceback}")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)