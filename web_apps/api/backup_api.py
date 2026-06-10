#!/usr/bin/env python3
"""
バックアップ管理REST API - Raspberry Pi Dashboard
Phase 2: Web管理インターフェース実装

機能:
- RESTful APIエンドポイント
- バックアップ操作のWeb API化
- 統一エラーハンドリング
- JSON応答形式統一
"""

import os
import sys
import json
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from flask import Blueprint, request, jsonify, current_app

# バックアップシステム統合
sys.path.append(str(Path(__file__).parent.parent))
from scripts.backup_manager import BackupManager, BackupError
from logging_system import get_logger

# APIブループリント作成
backup_api = Blueprint('backup_api', __name__, url_prefix='/api/backup')

# グローバル変数
_backup_manager = None
_current_operations = {}  # 進行中の操作管理
_operation_lock = threading.Lock()

logger = get_logger("backup_api")


def get_backup_manager() -> BackupManager:
    """バックアップマネージャーインスタンス取得"""
    global _backup_manager
    
    if _backup_manager is None:
        try:
            # 設定ファイルパス決定（プロジェクトルートの config/ を使用）
            config_path = str(Path(__file__).resolve().parent.parent.parent / "config" / "backup_config.json")
            logger.info("設定ファイルパス", config_path=config_path)
            logger.info("BackupManager初期化開始", config_path=config_path)
            _backup_manager = BackupManager(config_path)
            logger.success("バックアップマネージャー初期化完了")
            
        except Exception as e:
            logger.error("バックアップマネージャー初期化エラー", 
                        error=str(e), 
                        error_type=type(e).__name__,
                        config_path=config_path)
            import traceback
            logger.error("詳細エラー情報", traceback=traceback.format_exc())
            raise BackupError(f"バックアップマネージャー初期化エラー: {e}")
    
    return _backup_manager


def create_api_response(success: bool = True, data: Any = None, 
                       message: str = None, error: str = None) -> Dict[str, Any]:
    """統一API応答フォーマット"""
    response = {
        'success': success,
        'timestamp': datetime.now().isoformat(),
    }
    
    if data is not None:
        response['data'] = data
    
    if message:
        response['message'] = message
    
    if error:
        response['error'] = error
        response['success'] = False
    
    return response


def validate_request_data(required_fields: List[str], request_data: Dict[str, Any]) -> Optional[str]:
    """リクエストデータ検証"""
    for field in required_fields:
        if field not in request_data:
            return f"必須フィールドが不足しています: {field}"
        
        if request_data[field] is None or request_data[field] == '':
            return f"フィールドが空です: {field}"
    
    return None


@backup_api.route('/list', methods=['GET'])
def list_backups():
    """
    バックアップ一覧取得 API
    GET /api/backup/list?type=incremental&limit=10
    """
    try:
        manager = get_backup_manager()
        
        # クエリパラメーター取得
        backup_type = request.args.get('type')  # incremental, full
        limit = request.args.get('limit', type=int)
        
        logger.debug("バックアップ一覧取得開始", 
                    backup_type=backup_type, limit=limit)
        
        # バックアップ一覧取得
        backups = manager.list_backups(backup_type=backup_type, limit=limit)
        
        # フォーマット情報を追加（backup_manager.pyで既にフォーマットされている場合はスキップ）
        for backup in backups:
            # フォーマット済み情報が存在しない場合のみ追加
            if 'size_bytes' in backup and 'size_formatted' not in backup:
                backup['size_formatted'] = _format_file_size(backup['size_bytes'])
            
            # 転送サイズ情報を追加（増分バックアップの効率表示）
            if 'rsync_stats' in backup and 'transferred_size_formatted' not in backup:
                rsync_stats = backup['rsync_stats']
                transferred_size = rsync_stats.get('transferred_file_size', 0)
                files_transferred = rsync_stats.get('files_transferred', 0)
                
                # 転送サイズをフォーマット
                backup['transferred_size_bytes'] = transferred_size
                backup['transferred_size_formatted'] = _format_file_size(transferred_size)
                backup['files_transferred'] = files_transferred
                
                # 増分バックアップの効率計算
                if backup.get('type') == 'incremental' and 'size_bytes' in backup:
                    total_size = backup['size_bytes']
                    if total_size > 0:
                        efficiency = (1 - (transferred_size / total_size)) * 100
                        backup['efficiency_percent'] = round(efficiency, 1)
                    else:
                        backup['efficiency_percent'] = 0
            
            if 'timestamp' in backup and 'timestamp_formatted' not in backup:
                backup['timestamp_formatted'] = _format_timestamp(backup['timestamp'])
        
        logger.success("バックアップ一覧取得完了", count=len(backups))
        
        return jsonify(create_api_response(
            success=True,
            data={
                'backups': backups,
                'total_count': len(backups),
                'filter': {
                    'type': backup_type,
                    'limit': limit
                }
            },
            message=f"{len(backups)}個のバックアップを取得しました"
        ))
        
    except BackupError as e:
        logger.error("バックアップ一覧取得エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=str(e)
        )), 500
        
    except Exception as e:
        logger.critical("予期しないエラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"予期しないエラー: {e}"
        )), 500


@backup_api.route('/create', methods=['POST'])
def create_backup():
    """
    バックアップ作成 API
    POST /api/backup/create
    {
        "type": "incremental",
        "name": "manual_backup",
        "description": "手動バックアップ"
    }
    """
    try:
        manager = get_backup_manager()
        
        # リクエストデータ検証
        data = request.get_json()
        if not data:
            return jsonify(create_api_response(
                success=False,
                error="JSONデータが必要です"
            )), 400
        
        # 必須フィールド検証
        validation_error = validate_request_data(['type'], data)
        if validation_error:
            return jsonify(create_api_response(
                success=False,
                error=validation_error
            )), 400
        
        backup_type = data['type']
        name = data.get('name')
        description = data.get('description')
        
        # バックアップタイプ検証
        if backup_type not in ['incremental', 'full']:
            return jsonify(create_api_response(
                success=False,
                error="typeは'incremental'または'full'である必要があります"
            )), 400
        
        logger.info("バックアップ作成開始", 
                   backup_type=backup_type, name=name)
        
        # 操作ID生成（進行状況追跡用）
        operation_id = f"backup_{int(time.time())}"
        
        with _operation_lock:
            _current_operations[operation_id] = {
                'type': 'create_backup',
                'status': 'running',
                'start_time': datetime.now().isoformat(),
                'backup_type': backup_type
            }
        
        try:
            # バックアップ実行
            result = manager.create_local_backup(
                backup_type=backup_type,
                name=name,
                description=description
            )
            
            # 成功時の操作状態更新
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'completed',
                    'end_time': datetime.now().isoformat(),
                    'result': result
                })
            
            # レスポンス用データ整形
            result['size_formatted'] = _format_file_size(result['size_bytes'])
            result['duration_formatted'] = f"{result['duration_seconds']:.1f}秒"
            
            logger.success("バックアップ作成完了", 
                         backup_id=result['backup_id'],
                         size_mb=result['size_bytes'] / 1024 / 1024)
            
            return jsonify(create_api_response(
                success=True,
                data={
                    'backup': result,
                    'operation_id': operation_id
                },
                message="バックアップが正常に作成されました"
            ))
            
        except Exception as e:
            # エラー時の操作状態更新
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'failed',
                    'end_time': datetime.now().isoformat(),
                    'error': str(e)
                })
            raise
        
    except BackupError as e:
        logger.error("バックアップ作成エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=str(e)
        )), 500
        
    except Exception as e:
        logger.critical("予期しないエラー", error=str(e))
        import traceback
        logger.error("詳細スタックトレース", traceback=traceback.format_exc())
        return jsonify(create_api_response(
            success=False,
            error=f"予期しないエラー: {e}"
        )), 500


@backup_api.route('/verify/<backup_id>', methods=['POST'])
def verify_backup(backup_id: str):
    """
    バックアップ検証 API
    POST /api/backup/verify/backup_id_here
    """
    try:
        manager = get_backup_manager()
        
        logger.info("バックアップ検証開始", backup_id=backup_id)
        
        # 操作ID生成
        operation_id = f"verify_{int(time.time())}"
        
        with _operation_lock:
            _current_operations[operation_id] = {
                'type': 'verify_backup',
                'status': 'running',
                'start_time': datetime.now().isoformat(),
                'backup_id': backup_id
            }
        
        try:
            # 検証実行
            result = manager.verify_backup(backup_id)
            
            # 操作状態更新
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'completed',
                    'end_time': datetime.now().isoformat(),
                    'result': result
                })
            
            logger.success("バックアップ検証完了", 
                         backup_id=backup_id, 
                         status=result['status'])
            
            return jsonify(create_api_response(
                success=True,
                data={
                    'verification': result,
                    'operation_id': operation_id
                },
                message=f"バックアップ検証が完了しました: {result['status']}"
            ))
            
        except Exception as e:
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'failed',
                    'end_time': datetime.now().isoformat(),
                    'error': str(e)
                })
            raise
        
    except BackupError as e:
        logger.error("バックアップ検証エラー", 
                    backup_id=backup_id, error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=str(e)
        )), 500
        
    except Exception as e:
        logger.critical("予期しないエラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"予期しないエラー: {e}"
        )), 500


@backup_api.route('/statistics', methods=['GET'])
def get_statistics():
    """
    バックアップ統計情報取得 API
    GET /api/backup/statistics
    """
    try:
        manager = get_backup_manager()
        
        logger.debug("統計情報取得開始")
        
        # 統計情報取得
        stats = manager.get_statistics()
        
        # フォーマット済み情報追加
        if 'total_size_bytes' in stats:
            stats['total_size_formatted'] = _format_file_size(stats['total_size_bytes'])
            
        if 'total_size_bytes_logical' in stats:
            stats['total_size_logical_formatted'] = _format_file_size(stats['total_size_bytes_logical'])
            
        if 'total_transferred_bytes' in stats:
            stats['total_transferred_formatted'] = _format_file_size(stats['total_transferred_bytes'])
        
        if 'last_backup' in stats:
            stats['last_backup_formatted'] = _format_timestamp(stats['last_backup'])
        
        # 成功率計算
        if stats.get('total_backups', 0) > 0:
            stats['success_rate'] = round(
                (stats.get('successful_backups', 0) / stats['total_backups']) * 100, 1
            )
        else:
            stats['success_rate'] = 0.0
        
        logger.success("統計情報取得完了")
        
        return jsonify(create_api_response(
            success=True,
            data=stats,
            message="統計情報を取得しました"
        ))
        
    except Exception as e:
        logger.error("統計情報取得エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"統計情報取得エラー: {e}"
        )), 500


@backup_api.route('/cleanup', methods=['POST'])
def cleanup_old_backups():
    """
    古いバックアップクリーンアップ API
    POST /api/backup/cleanup
    """
    try:
        manager = get_backup_manager()
        
        logger.info("バックアップクリーンアップ開始")
        
        # 操作ID生成
        operation_id = f"cleanup_{int(time.time())}"
        
        with _operation_lock:
            _current_operations[operation_id] = {
                'type': 'cleanup',
                'status': 'running',
                'start_time': datetime.now().isoformat()
            }
        
        try:
            # クリーンアップ前の統計
            stats_before = manager.get_statistics()
            
            # クリーンアップ実行
            manager.cleanup_old_backups()
            
            # クリーンアップ後の統計
            stats_after = manager.get_statistics()
            
            # 削除効果計算
            deleted_count = stats_before.get('total_backups', 0) - stats_after.get('total_backups', 0)
            freed_bytes = stats_before.get('total_size_bytes', 0) - stats_after.get('total_size_bytes', 0)
            
            result = {
                'deleted_count': deleted_count,
                'freed_bytes': freed_bytes,
                'freed_formatted': _format_file_size(freed_bytes),
                'remaining_count': stats_after.get('total_backups', 0),
                'remaining_size': stats_after.get('total_size_bytes', 0),
                'remaining_formatted': _format_file_size(stats_after.get('total_size_bytes', 0))
            }
            
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'completed',
                    'end_time': datetime.now().isoformat(),
                    'result': result
                })
            
            logger.success("バックアップクリーンアップ完了",
                         deleted_count=deleted_count,
                         freed_mb=freed_bytes / 1024 / 1024)
            
            return jsonify(create_api_response(
                success=True,
                data={
                    'cleanup': result,
                    'operation_id': operation_id
                },
                message=f"{deleted_count}個のバックアップを削除しました"
            ))
            
        except Exception as e:
            with _operation_lock:
                _current_operations[operation_id].update({
                    'status': 'failed',
                    'end_time': datetime.now().isoformat(),
                    'error': str(e)
                })
            raise
        
    except Exception as e:
        logger.error("バックアップクリーンアップエラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"クリーンアップエラー: {e}"
        )), 500


@backup_api.route('/operations/<operation_id>', methods=['GET'])
def get_operation_status(operation_id: str):
    """
    操作状況取得 API
    GET /api/backup/operations/operation_id
    """
    try:
        with _operation_lock:
            operation = _current_operations.get(operation_id)
        
        if not operation:
            return jsonify(create_api_response(
                success=False,
                error="指定された操作IDが見つかりません"
            )), 404
        
        return jsonify(create_api_response(
            success=True,
            data=operation,
            message="操作状況を取得しました"
        ))
        
    except Exception as e:
        logger.error("操作状況取得エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"操作状況取得エラー: {e}"
        )), 500


@backup_api.route('/operations', methods=['GET'])
def list_operations():
    """
    全操作一覧取得 API
    GET /api/backup/operations
    """
    try:
        with _operation_lock:
            operations = dict(_current_operations)
        
        return jsonify(create_api_response(
            success=True,
            data={
                'operations': operations,
                'count': len(operations)
            },
            message="操作一覧を取得しました"
        ))
        
    except Exception as e:
        logger.error("操作一覧取得エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"操作一覧取得エラー: {e}"
        )), 500


@backup_api.route('/status', methods=['GET'])
def get_backup_status():
    """
    バックアップシステム全体ステータス取得 API
    GET /api/backup/status
    """
    try:
        manager = get_backup_manager()
        
        # 基本統計情報
        stats = manager.get_statistics()
        
        # 最新バックアップ情報
        backups = manager.list_backups(limit=1)
        latest_backup = backups[0] if backups else None
        
        # 進行中の操作状況
        with _operation_lock:
            running_operations = {
                op_id: op_data for op_id, op_data in _current_operations.items()
                if op_data.get('status') == 'running'
            }
        
        # ステータス情報統合
        status_data = {
            'system_status': 'healthy' if stats.get('total_backups', 0) > 0 else 'no_backups',
            'total_backups': stats.get('total_backups', 0),
            'successful_backups': stats.get('successful_backups', 0),
            'failed_backups': stats.get('failed_backups', 0),
            'success_rate': stats.get('success_rate', 0),
            'total_size_bytes': stats.get('total_size_bytes', 0),
            'total_size_formatted': _format_file_size(stats.get('total_size_bytes', 0)),
            'last_backup_time': stats.get('last_backup'),
            'last_backup_formatted': _format_timestamp(stats.get('last_backup', '')),
            'latest_backup': latest_backup,
            'running_operations': len(running_operations),
            'operations': list(running_operations.keys())
        }
        
        logger.debug("バックアップステータス取得完了",
                    total_backups=status_data['total_backups'],
                    system_status=status_data['system_status'])
        
        return jsonify(create_api_response(
            success=True,
            data=status_data,
            message="バックアップステータス取得完了"
        ))
        
    except Exception as e:
        logger.error("バックアップステータス取得エラー", error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"ステータス取得エラー: {e}"
        )), 500


@backup_api.route('/download/<backup_id>', methods=['GET'])
def download_backup(backup_id):
    """
    バックアップダウンロード
    
    パス:
        backup_id: ダウンロード対象のバックアップID
        
    レスポンス:
        tar.gz形式の圧縮ファイル
    """
    logger = get_logger("backup_api")
    
    try:
        logger.info("バックアップダウンロード開始", backup_id=backup_id)
        
        # バックアップマネージャー初期化
        manager = BackupManager()
        
        # バックアップ情報取得
        backup_info = manager.get_backup_info(backup_id)
        if not backup_info:
            logger.warning("バックアップが見つかりません", backup_id=backup_id)
            return jsonify(create_api_response(
                success=False,
                error=f"バックアップが見つかりません: {backup_id}"
            )), 404
        
        # バックアップディレクトリ確認
        backup_path = Path(backup_info['path'])
        if not backup_path.exists():
            logger.error("バックアップディレクトリが存在しません",
                        backup_id=backup_id,
                        path=str(backup_path))
            return jsonify(create_api_response(
                success=False,
                error=f"バックアップディレクトリが存在しません: {backup_id}"
            )), 404
        
        # 一時ファイル作成用ディレクトリ
        import tempfile
        temp_dir = Path("/tmp/raspberry-pi-backup-downloads")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 圧縮ファイル名・パス作成
        archive_name = f"{backup_id}.tar"
        archive_path = temp_dir / archive_name
        
        # 既存の一時ファイルを削除
        if archive_path.exists():
            archive_path.unlink()
        
        logger.info("バックアップ圧縮開始",
                   source=str(backup_path),
                   archive=str(archive_path))
        
        # tar.gz形式で圧縮
        
        # tarコマンドで圧縮（プログレス表示なし、高速圧縮）
        tar_cmd = [
            'tar', '-cf', str(archive_path),
            '-C', str(backup_path.parent),
            backup_path.name
        ]
        
        result = subprocess.run(
            tar_cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10分タイムアウト
            check=True
        )
        
        # 圧縮ファイルサイズ確認
        archive_size = archive_path.stat().st_size
        
        logger.success("バックアップ圧縮完了",
                      backup_id=backup_id,
                      archive_size_mb=round(archive_size / 1024 / 1024, 2))
        
        # Flask send_file を使用してダウンロード
        from flask import send_file
        
        # ダウンロード用のResponse作成
        response = send_file(
            str(archive_path),
            as_attachment=True,
            download_name=archive_name,
            mimetype='application/x-tar'
        )
        
        # 一時ファイル削除（バックグラウンド）
        def cleanup_temp_file():
            import time
            time.sleep(10)  # ダウンロード完了を待つ
            try:
                if archive_path.exists():
                    archive_path.unlink()
                    logger.debug("一時ファイル削除完了", archive=str(archive_path))
            except Exception as cleanup_error:
                logger.warning("一時ファイル削除エラー",
                             archive=str(archive_path),
                             error=str(cleanup_error))
        
        # バックグラウンドでクリーンアップ
        import threading
        cleanup_thread = threading.Thread(target=cleanup_temp_file, daemon=True)
        cleanup_thread.start()
        
        logger.success("バックアップダウンロード準備完了",
                      backup_id=backup_id,
                      filename=archive_name)
        
        return response
        
    except subprocess.TimeoutExpired:
        logger.error("バックアップ圧縮タイムアウト", backup_id=backup_id)
        return jsonify(create_api_response(
            success=False,
            error="バックアップの圧縮処理がタイムアウトしました"
        )), 500
        
    except subprocess.CalledProcessError as e:
        logger.error("バックアップ圧縮エラー",
                    backup_id=backup_id,
                    stderr=e.stderr)
        return jsonify(create_api_response(
            success=False,
            error=f"バックアップの圧縮に失敗しました: {e.stderr}"
        )), 500
        
    except Exception as e:
        logger.error("バックアップダウンロードエラー",
                    backup_id=backup_id,
                    error=str(e))
        return jsonify(create_api_response(
            success=False,
            error=f"ダウンロードエラー: {e}"
        )), 500


@backup_api.route('/restore', methods=['POST'])
def restore_backup():
    """
    バックアップ復元
    
    リクエストボディ:
        {
            "backup_id": "復元対象のバックアップID",
            "restore_type": "complete" | "partial",
            "target_paths": ["部分復元時の対象パス配列"]
        }
        
    レスポンス:
        復元結果情報
    """
    logger = get_logger("backup_api")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_api_response(
                success=False,
                error="リクエストボディが必要です"
            )), 400
        
        backup_id = data.get('backup_id')
        restore_type = data.get('restore_type', 'complete')
        target_paths = data.get('target_paths', [])
        
        if not backup_id:
            return jsonify(create_api_response(
                success=False,
                error="backup_idが必要です"
            )), 400
        
        if restore_type not in ['complete', 'partial']:
            return jsonify(create_api_response(
                success=False,
                error="restore_typeは'complete'または'partial'である必要があります"
            )), 400
        
        if restore_type == 'partial' and not target_paths:
            return jsonify(create_api_response(
                success=False,
                error="部分復元時はtarget_pathsが必要です"
            )), 400
        
        logger.info("復元開始",
                   backup_id=backup_id,
                   restore_type=restore_type,
                   target_paths=target_paths if restore_type == 'partial' else None)
        
        # 復元マネージャー初期化
        from scripts.restore_manager import RestoreManager
        restore_manager = RestoreManager()
        
        # 復元実行
        if restore_type == 'complete':
            restore_result = restore_manager.restore_full_backup(
                backup_id=backup_id,
                create_pre_backup=True
            )
        else:  # partial
            restore_result = restore_manager.restore_partial_backup(
                backup_id=backup_id,
                target_paths=target_paths
            )
        
        # 復元検証実行
        verification_result = restore_manager.verify_restore(restore_result)
        
        # レスポンス用データ整形
        response_data = {
            'restore_info': {
                'restore_id': restore_result.get('restore_id'),
                'backup_id': restore_result.get('backup_id'),
                'restore_type': restore_result.get('restore_type'),
                'status': restore_result.get('status'),
                'timestamp': restore_result.get('timestamp'),
                'duration_seconds': restore_result.get('duration_seconds'),
                'duration_formatted': f"{restore_result.get('duration_seconds', 0):.1f}秒",
                'pre_backup_id': restore_result.get('pre_backup_id')
            },
            'verification': {
                'status': verification_result.get('verification_status'),
                'verified_files_count': len(verification_result.get('verified_files', [])),
                'failed_verifications_count': len(verification_result.get('failed_verifications', [])),
                'verification_duration_seconds': verification_result.get('verification_duration_seconds')
            }
        }
        
        # 部分復元の場合は追加情報
        if restore_type == 'partial':
            response_data['restore_info'].update({
                'target_paths': restore_result.get('target_paths', []),
                'success_count': restore_result.get('success_count', 0),
                'failure_count': restore_result.get('failure_count', 0),
                'restored_files': restore_result.get('restored_files', []),
                'skipped_files': restore_result.get('skipped_files', [])
            })
        
        logger.success("復元完了",
                      restore_id=response_data['restore_info']['restore_id'],
                      restore_type=restore_type,
                      verification_status=verification_result.get('verification_status'))
        
        return jsonify(create_api_response(
            success=True,
            data=response_data,
            message=f"復元が完了しました (復元ID: {response_data['restore_info']['restore_id']})"
        ))
        
    except Exception as e:
        logger.error("復元エラー",
                    backup_id=data.get('backup_id', 'unknown') if 'data' in locals() else 'unknown',
                    error=str(e))
        
        # 復元エラーの詳細分類
        if "バックアップが見つかりません" in str(e):
            return jsonify(create_api_response(
                success=False,
                error=str(e)
            )), 404
        elif "復元処理がタイムアウトしました" in str(e):
            return jsonify(create_api_response(
                success=False,
                error=str(e)
            )), 408
        else:
            return jsonify(create_api_response(
                success=False,
                error=f"復元エラー: {e}"
            )), 500


def _format_file_size(size_bytes: int) -> str:
    """ファイルサイズフォーマット"""
    if size_bytes == 0:
        return "0B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}PB"


def _format_timestamp(timestamp_str: str) -> str:
    """タイムスタンプフォーマット"""
    try:
        if isinstance(timestamp_str, str):
            # ISO形式のタイムスタンプをパース
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return dt.strftime('%Y/%m/%d %H:%M:%S')
        return str(timestamp_str)
    except Exception:
        return str(timestamp_str)


# エラーハンドラー
@backup_api.errorhandler(404)
def not_found(error):
    """404エラーハンドラー"""
    return jsonify(create_api_response(
        success=False,
        error="指定されたエンドポイントが見つかりません"
    )), 404


@backup_api.errorhandler(500)
def internal_error(error):
    """500エラーハンドラー"""
    logger.critical("内部サーバーエラー", error=str(error))
    return jsonify(create_api_response(
        success=False,
        error="内部サーバーエラーが発生しました"
    )), 500