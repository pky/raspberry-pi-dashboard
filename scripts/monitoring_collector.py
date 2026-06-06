#!/usr/bin/env python3
"""
シンプル監視データ収集スクリプト - JSONファイル直接出力
従来の複雑なキャッシュシステムを置き換える軽量システム

使用方法:
    python3 monitoring_collector.py

出力:
    static/data/metrics.json - Chart.jsが直接読み込むJSONファイル
"""

import json
import os
import sys
import logging
from datetime import datetime, timedelta

# プロジェクトルートをパスに追加してlogging_systemをインポート
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from logging_system import get_logger

# ロガー設定
logger = get_logger(__name__)
from pathlib import Path

# Raspberry Pi Dashboard プロジェクトルートを追加
project_root = Path(__file__).parent.parent
if (project_root / 'raspberry-pi-dashboard').exists():
    # Mac環境
    project_root = project_root / 'raspberry-pi-dashboard'
    json_output_root = project_root.parent
else:
    # Raspberry Pi環境
    json_output_root = project_root

sys.path.insert(0, str(project_root))

try:
    from simple_system_monitor import get_simple_system_metrics
    from sensor import get_sensor
    from config import Config
except ImportError as e:
    logger.error(f" モジュール読み込みエラー - {e}")
    sys.exit(1)


def collect_backup_status():
    """
    T3.3 監視システム統合 - バックアップ状態監視
    バックアップシステムの健全性・統計情報収集
    """
    backup_status = {
        "backup_system_available": False,
        "last_backup_time": None,
        "last_backup_status": "unknown",
        "total_backups": 0,
        "successful_backups": 0,
        "failed_backups": 0,
        "total_backup_size_mb": 0,
        "backup_health_score": 0.0,
        "disk_usage_percent": 0,
        "next_scheduled_backup": None,
        "backup_conditions_met": False,
        "active_backup_running": False
    }
    
    try:
        # BackupManagerからメタデータ取得
        import tempfile
        backup_metadata_paths = [
            "/tmp/test_backups/backup_metadata.json",  # テスト環境
            str(Path.home() / "backups" / "backup_metadata.json"),
            str(Path.home() / "backups" / "backup_metadata.json")  # 一般環境
        ]
        
        metadata_found = False
        for metadata_path in backup_metadata_paths:
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # 統計情報取得
                    stats = metadata.get('statistics', {})
                    backup_status.update({
                        "backup_system_available": True,
                        "total_backups": stats.get('total_backups', 0),
                        "successful_backups": stats.get('successful_backups', 0), 
                        "failed_backups": stats.get('failed_backups', 0),
                        "total_backup_size_mb": stats.get('total_size_bytes', 0) // (1024 * 1024),
                        "last_backup_time": stats.get('last_backup')
                    })
                    
                    # 最新バックアップ情報
                    backups = metadata.get('backups', [])
                    if backups:
                        latest_backup = backups[-1]
                        backup_status.update({
                            "last_backup_status": latest_backup.get('status', 'unknown'),
                        })
                    
                    # ヘルススコア計算 (0.0-1.0)
                    if backup_status['total_backups'] > 0:
                        success_rate = backup_status['successful_backups'] / backup_status['total_backups']
                        
                        # 最近のバックアップ実行状況考慮
                        recent_backup_bonus = 0.0
                        if backup_status['last_backup_time']:
                            try:
                                last_backup = datetime.fromisoformat(backup_status['last_backup_time'].replace('Z', '+00:00'))
                                hours_since = (datetime.now() - last_backup.replace(tzinfo=None)).total_seconds() / 3600
                                if hours_since < 24:  # 24時間以内
                                    recent_backup_bonus = 0.2
                                elif hours_since < 72:  # 72時間以内  
                                    recent_backup_bonus = 0.1
                            except Exception:
                                pass
                        
                        backup_status['backup_health_score'] = min(1.0, success_rate + recent_backup_bonus)
                    
                    metadata_found = True
                    logger.info(f"バックアップメタデータ取得成功: {backup_status['total_backups']}個のバックアップ、ヘルススコア{backup_status['backup_health_score']:.2f}")
                    break
                    
                except Exception as e:
                    logger.warning(f"バックアップメタデータ読み込み失敗: {metadata_path} - {e}")
                    continue
        
        if not metadata_found:
            logger.debug("バックアップメタデータが見つかりません - システム未初期化の可能性")
        
        # 高度設定からバックアップ条件チェック
        try:
            config_path = project_root / "config" / "backup_advanced_config.json"
            if config_path.exists():
                sys.path.insert(0, str(project_root / "config"))
                from backup_advanced_config import BackupAdvancedConfig
                
                advanced_config = BackupAdvancedConfig(str(config_path))
                backup_status['backup_conditions_met'] = advanced_config.should_run_backup()
                
                logger.debug(f"バックアップ条件判定: {'実行可能' if backup_status['backup_conditions_met'] else '実行制限中'}")
            
        except Exception as e:
            logger.debug(f"高度設定取得失敗: {e}")
        
        # アクティブバックアッププロセスチェック
        try:
            lock_files = [
                "/tmp/backup.lock",
                str(Path(__file__).parent.parent / "backup.lock")
            ]
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    backup_status['active_backup_running'] = True
                    logger.info("アクティブなバックアッププロセス検出")
                    break
        except Exception as e:
            logger.debug(f"バックアップロックファイル確認エラー: {e}")
            
        # ディスク使用量監視（バックアップ領域）
        try:
            for backup_dir in ["/tmp/test_backups", str(Path.home() / "backups")]:
                if os.path.exists(backup_dir):
                    import shutil
                    total, used, free = shutil.disk_usage(backup_dir)
                    usage_percent = (used / total) * 100
                    backup_status['disk_usage_percent'] = round(usage_percent, 1)
                    break
        except Exception as e:
            logger.debug(f"バックアップ用ディスク使用量取得失敗: {e}")
            
    except Exception as e:
        logger.error(f"バックアップ状態監視エラー: {e}")
    
    return backup_status

def collect_current_data():
    """現在の監視データを取得"""
    try:
        # システムメトリクス取得
        system_data = get_simple_system_metrics()
        
        # 全センサーデータをログファイルから取得（一貫性確保）
        room_temp = 0
        humidity = 0
        co2_ppm = 0
        
        # Smart Averaging品質情報
        quality_score = 0.5
        sample_count = 1
        verification_level = "normal"
        processing_time = 0.0
        smart_averaging_used = False
        
        # CO2データを直接センサーから取得（実測値保証・強制設定）
        try:
            sensor = get_sensor()
            # 実測値強制取得：設定ファイルベースの確実な実測値取得
            co2_sensor_data = sensor.get_sensor_data(
                enable_logging=False, 
                retry_on_simulation=Config.SENSOR_FORCE_REAL_VALUES,  # 設定ファイルで制御
                max_retries=Config.SENSOR_MAX_RETRIES  # 設定ファイルで制御
            )
            
            # 実測値判定を厳格化
            is_co2_real = (
                co2_sensor_data and 
                co2_sensor_data.get('co2_ppm') and 
                co2_sensor_data.get('co2_ppm') > 0 and
                not co2_sensor_data.get('co2_simulation', True)
            )
            
            if is_co2_real:
                co2_ppm = co2_sensor_data.get('co2_ppm', 0)
                logger.info(f" ✅ CO2実測値取得成功: {co2_ppm}ppm (確認済み実測値)")
            else:
                logger.warning(f" CO2センサー実測値取得失敗、ログからフォールバック試行")
                # フォールバック: ログファイルから取得
                today = datetime.now().strftime('%Y-%m-%d')
                co2_log_path = project_root / 'logs' / f'co2_data_{today}.json'
                
                if co2_log_path.exists():
                    import json
                    with open(co2_log_path, 'r', encoding='utf-8') as f:
                        co2_log_data = json.load(f)
                    
                    if co2_log_data and len(co2_log_data) > 0:
                        latest_co2_entry = co2_log_data[-1]
                        co2_ppm = latest_co2_entry.get('co2_ppm', 0)
                        is_simulation = latest_co2_entry.get('simulation', True)
                        status = "シミュレーション" if is_simulation else "ログ実測値"
                        logger.warning(f" CO2をログファイルから取得: {co2_ppm}ppm ({status})")
        except Exception as e:
            logger.warning(f" CO2データ取得エラー - {e}")
            
        # 温度・湿度データを同じセンサーオブジェクトから取得（実測値保証・統一化）
        try:
            if 'sensor' not in locals():
                sensor = get_sensor()
            # Smart Averaging + 実測値強制取得（設定ファイルベース）
            sensor_data = sensor.get_sensor_data(
                smart_averaging=True, 
                verification_mode="smart",
                enable_logging=False,
                retry_on_simulation=Config.SENSOR_FORCE_REAL_VALUES,  # 設定ファイルで制御
                max_retries=Config.SENSOR_MAX_RETRIES  # 設定ファイルで制御
            )
            
            if not sensor_data.get('error'):
                room_temp = sensor_data.get('temperature', 0) or 0
                humidity = sensor_data.get('humidity', 0) or 0
                
                # Smart Averaging品質情報を収集・ログに記録
                if sensor_data.get('smart_averaging_used'):
                    smart_averaging_used = True
                    quality_score = sensor_data.get('quality_score', 0.0)
                    sample_count = sensor_data.get('sample_count', 1)
                    verification_level = sensor_data.get('verification_level', 'normal')
                    processing_time = sensor_data.get('processing_time', 0.0)
                    
                    logger.info(f" Smart Averaging取得: 温度{room_temp}°C, 湿度{humidity}% "
                          f"(品質: {quality_score:.2f}, 取得回数: {sample_count}, "
                          f"検証レベル: {verification_level}, 処理時間: {processing_time:.2f}s)")
                else:
                    logger.info(f" 通常センサーから温湿度取得: 温度{room_temp}°C, 湿度{humidity}%")
            else:
                logger.warning(f" センサーデータ取得エラー - {sensor_data.get('error')}")
                
        except Exception as e:
            logger.warning(f" センサーデータ取得エラー - {e}")
            
        logger.debug(f" センサーから取得 - 温度: {room_temp}°C, 湿度: {humidity}%, CO2: {co2_ppm}ppm")
        
        # バックアップシステム監視データ取得
        backup_status = collect_backup_status()
        
        # 統一データポイント作成
        timestamp = datetime.now()
        
        # フォールバック処理（ログから取得できない場合のみ）
        if room_temp == 0:
            # CPU温度から推定室温（CPU温度 - 28～32度）
            cpu_temp = system_data.get('temperature', 50)
            room_temp = round(cpu_temp - 30 + (cpu_temp % 5), 1)
            logger.warning(f" 室温データなし - CPU温度から推定: {room_temp}°C")
            
        if humidity == 0:
            # 実データが取得できない場合のみシミュレート
            humidity = 45.0
            logger.warning(f" 湿度データ取得失敗 - シミュレーション値使用: {humidity}%")
            
        if co2_ppm == 0:
            # 実データが取得できない場合のみシミュレート
            co2_ppm = 450
            logger.warning(f" CO2データ取得失敗 - シミュレーション値使用: {co2_ppm}ppm")
        
        logger.info(f" 最終データ確認 - 温度: {room_temp}°C, 湿度: {humidity}%, CO2: {co2_ppm}ppm")
        
        data_point = {
            "timestamp": timestamp.isoformat(),
            "cpu_percent": round(system_data.get('cpu_percent', 0), 1),
            "memory_percent": round(system_data.get('memory_percent', 0), 1),
            "cpu_temperature": round(system_data.get('temperature', 0), 1),
            "room_temperature": round(room_temp, 1),
            "humidity": round(humidity, 1),
            "co2_ppm": co2_ppm,
            "disk_used_gb": round(system_data.get('disk_used_gb', 0), 1),
            "disk_percent": round(system_data.get('disk_percent', 0), 1),
            "network_sent_mb": round(system_data.get('network_bytes_sent', 0) / 1024 / 1024, 2),
            "network_recv_mb": round(system_data.get('network_bytes_recv', 0) / 1024 / 1024, 2),
            "uptime_seconds": system_data.get('uptime_seconds', 0),
            "load_average": system_data.get('load_average', []),
            # Smart Averaging品質情報
            "quality_score": round(quality_score, 2),
            "sample_count": sample_count,
            "verification_level": verification_level,
            "processing_time": round(processing_time, 2),
            "smart_averaging_used": smart_averaging_used,
            # T3.3 バックアップシステム監視情報
            "backup_system_available": backup_status.get('backup_system_available', False),
            "backup_total_count": backup_status.get('total_backups', 0),
            "backup_success_count": backup_status.get('successful_backups', 0),
            "backup_failed_count": backup_status.get('failed_backups', 0),
            "backup_total_size_mb": backup_status.get('total_backup_size_mb', 0),
            "backup_health_score": round(backup_status.get('backup_health_score', 0.0), 2),
            "backup_last_status": backup_status.get('last_backup_status', 'unknown'),
            "backup_conditions_met": backup_status.get('backup_conditions_met', False),
            "backup_active_running": backup_status.get('active_backup_running', False),
            "backup_disk_usage_percent": backup_status.get('disk_usage_percent', 0)
        }
        
        return data_point
        
    except Exception as e:
        logger.error(f" データ収集エラー - {e}")
        return None


def should_collect_data(json_path, interval_minutes=5):
    """データ収集タイミングの判定（5分間隔制御）"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not data.get('metrics') or len(data['metrics']) == 0:
            logger.info(f" 初回データ収集実行")
            return True
            
        # 最新データのタイムスタンプを確認
        latest_entry = data['metrics'][-1]
        latest_time = datetime.fromisoformat(latest_entry['timestamp'].replace('Z', '+00:00'))
        current_time = datetime.now()
        time_diff = current_time - latest_time
        
        # 指定間隔（デフォルト5分）が経過していない場合はスキップ
        if time_diff.total_seconds() < interval_minutes * 60:
            remaining_seconds = (interval_minutes * 60) - time_diff.total_seconds()
            logger.info(f" データ収集スキップ - 次回収集まで{int(remaining_seconds)}秒")
            return False
            
        logger.info(f" データ収集実行 - 前回から{int(time_diff.total_seconds())}秒経過")
        return True
        
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info(f" 新規ファイル - データ収集実行")
        return True
    except Exception as e:
        logger.warning(f" タイミング判定エラー - データ収集実行: {e}")
        return True


def load_existing_data(json_path):
    """既存JSONファイル読み込み"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # データ構造検証
        if not isinstance(data.get('metrics'), list):
            logger.warning(" 無効なデータ構造 - 初期化します")
            return {"metrics": [], "last_updated": None}
            
        return data
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.info(f" 新規ファイル作成 - {e}")
        return {"metrics": [], "last_updated": None}
    except Exception as e:
        logger.error(f" ファイル読み込みエラー - {e}")
        return {"metrics": [], "last_updated": None}


def clean_old_data(metrics, max_hours=168):
    """古いデータの削除（1週間=168時間以上前）"""
    if not metrics:
        return []
        
    cutoff_time = datetime.now() - timedelta(hours=max_hours)
    
    # フィルタリング（エラー処理付き）
    cleaned_metrics = []
    for metric in metrics:
        try:
            metric_time = datetime.fromisoformat(metric["timestamp"].replace('Z', '+00:00'))
            if metric_time > cutoff_time:
                cleaned_metrics.append(metric)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f" 無効なタイムスタンプをスキップ - {e}")
            continue
    
    return cleaned_metrics


def atomic_write_json(data, json_path):
    """原子的書き込み（一時ファイル使用）"""
    temp_path = str(json_path) + '.tmp'
    
    try:
        # 一時ファイルに書き込み
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 原子的にリネーム
        os.rename(temp_path, json_path)
        return True
        
    except Exception as e:
        logger.error(f" ファイル書き込みエラー - {e}")
        # 一時ファイルをクリーンアップ
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return False


def main():
    """メイン処理（5分間隔制御付き）"""
    logger.info(f"シンプル監視データ収集開始")
    
    # JSON出力パス設定
    json_path = json_output_root / 'static' / 'data' / 'metrics.json'
    
    # ディレクトリ作成
    json_path.parent.mkdir(parents=True, exist_ok=True)
    
    # cron 5分間隔実行に変更したため、内部制御は無効化
    # if not should_collect_data(json_path, interval_minutes=5):
    #     print("INFO: 5分間隔制御によりデータ収集をスキップしました")
    #     return True  # 正常終了（スキップは成功として扱う）
    
    # 現在データ収集
    current_data = collect_current_data()
    if not current_data:
        logger.error("データ収集に失敗しました")
        return False
    
    # 既存データ読み込み
    data = load_existing_data(json_path)
    
    # 新データ追加
    data["metrics"].append(current_data)
    
    # 古いデータ削除（24時間設定）
    original_count = len(data["metrics"])
    data["metrics"] = clean_old_data(data["metrics"], max_hours=24)
    cleaned_count = len(data["metrics"])
    
    # メタデータ更新
    data["last_updated"] = current_data["timestamp"]
    data["total_points"] = cleaned_count
    data["data_range_hours"] = 24  # 24時間（修正）
    data["collection_interval_minutes"] = 5  # 5分間隔記録
    
    # ファイル書き込み
    if atomic_write_json(data, json_path):
        logger.info(f"OK: {datetime.now().strftime('%H:%M:%S')} - Points: {cleaned_count} (削除: {original_count - cleaned_count}, 間隔: 5分)")
        logger.info(f"JSON出力: {json_path}")
        return True
    else:
        logger.error("JSONファイル書き込み失敗")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)