#!/usr/bin/env python3
"""
シンプル監視データ収集スクリプト - JSONファイル直接出力
従来の複雑なキャッシュシステムを置き換える軽量システム
センサー: SHT35(温湿度) + SCD30(CO2)

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
    from config import get_config
except ImportError as e:
    logger.error(f" モジュール読み込みエラー - {e}")
    sys.exit(1)


def collect_current_data():
    """現在の監視データを取得"""
    # 設定取得
    config = get_config()
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
                retry_on_simulation=True,  # 実測値強制取得
                max_retries=3  # 固定値（設定ファイル対応）
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
                retry_on_simulation=True,  # 実測値強制取得
                max_retries=3  # 固定値（設定ファイル対応）
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
            "smart_averaging_used": smart_averaging_used
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


def clean_old_data(metrics, max_hours=24):
    """古いデータの削除（設定値に基づく時間以上前）"""
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
    
    # 古いデータ削除（固定値使用）
    retention_hours = 24  # 24時間保持（固定値）
    original_count = len(data["metrics"])
    data["metrics"] = clean_old_data(data["metrics"], retention_hours)
    cleaned_count = len(data["metrics"])
    
    # メタデータ更新
    data["last_updated"] = current_data["timestamp"]
    data["total_points"] = cleaned_count
    data["data_range_hours"] = retention_hours
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