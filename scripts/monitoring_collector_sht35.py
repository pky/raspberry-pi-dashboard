#!/usr/bin/env python3
"""
SHT35専用監視データ収集スクリプト - シンプル・高品質データ専用
DHT22時代のハズレ値問題を完全解決したSHT35向け最適化システム

特徴:
- ハズレ値除外システム完全削除（SHT35は外れ値ゼロ）
- 5分間隔収集（安定データのため1分間隔不要）
- インメモリフィルタリング不要
- 直接JSONファイル出力のシンプル設計

使用方法:
    python3 monitoring_collector_sht35.py

出力:
    static/data/metrics.json - Chart.jsが直接読み込むJSONファイル
"""

import json
import os
import sys
import fcntl
import tempfile
from datetime import datetime, timedelta
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
    from logging_system import get_logger
except ImportError as e:
    print(f"ERROR: モジュール読み込みエラー - {e}")
    sys.exit(1)

# ログシステム初期化
logger = get_logger("sht35_collector")

def collect_sensor_data():
    """SHT35センサーから直接データを取得"""
    try:
        sensor = get_sensor()
        sensor_data = sensor.get_sensor_data(smart_averaging=True, verification_mode="smart")
        
        if sensor_data.get('error'):
            logger.warning(f"センサー読み取りエラー: {sensor_data['error']}")
            return None
            
        return {
            'room_temperature': sensor_data.get('temperature'),
            'humidity': sensor_data.get('humidity'),
            'co2_ppm': sensor_data.get('co2_ppm')
        }
    except Exception as e:
        logger.error(f"センサーデータ取得エラー: {e}")
        return None

def collect_system_metrics():
    """システムメトリクス取得"""
    try:
        return get_simple_system_metrics()
    except Exception as e:
        logger.error(f"システムメトリクス取得エラー: {e}")
        return {}

def create_metric_entry():
    """メトリクスエントリを作成（SHT35専用・フィルタリングなし）"""
    timestamp = datetime.now().isoformat()
    
    # センサーデータ取得
    sensor_data = collect_sensor_data()
    
    # システムメトリクス取得
    system_metrics = collect_system_metrics()
    
    # 統合メトリクス作成
    metric_entry = {
        'timestamp': timestamp,
        'cpu_percent': system_metrics.get('cpu_percent', 0.0),
        'memory_percent': system_metrics.get('memory_percent', 0.0),
        'cpu_temperature': system_metrics.get('cpu_temperature', 0.0),
        'disk_used_gb': system_metrics.get('disk_used_gb', 0.0),
        'disk_percent': system_metrics.get('disk_percent', 0.0),
        'network_sent_mb': system_metrics.get('network_sent_mb', 0.0),
        'network_recv_mb': system_metrics.get('network_recv_mb', 0.0),
        'uptime_seconds': system_metrics.get('uptime_seconds', 0.0),
        'load_average': system_metrics.get('load_average', [0.0, 0.0, 0.0])
    }
    
    # センサーデータ追加（SHT35は常に高品質）
    if sensor_data:
        metric_entry.update(sensor_data)
        logger.info(f"SHT35データ取得成功: {sensor_data['room_temperature']}°C, {sensor_data['humidity']}%, {sensor_data['co2_ppm']}ppm")
    else:
        # センサーエラー時のデフォルト値
        metric_entry.update({
            'room_temperature': 0,
            'humidity': 0,
            'co2_ppm': 0
        })
        logger.warning("センサーデータ取得失敗、デフォルト値を使用")
    
    return metric_entry

def load_existing_data(json_file):
    """既存のJSONデータを読み込み"""
    try:
        if os.path.exists(json_file):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('metrics', [])
        return []
    except Exception as e:
        logger.error(f"既存データ読み込みエラー: {e}")
        return []

def cleanup_old_data(metrics_list, hours=168):
    """古いデータのクリーンアップ（7日間保持）"""
    if not metrics_list:
        return metrics_list
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    filtered_metrics = []
    
    for metric in metrics_list:
        try:
            metric_time = datetime.fromisoformat(metric['timestamp'])
            if metric_time > cutoff_time:
                filtered_metrics.append(metric)
        except (ValueError, KeyError):
            # 無効なタイムスタンプは除外
            continue
    
    removed_count = len(metrics_list) - len(filtered_metrics)
    if removed_count > 0:
        logger.info(f"古いデータ{removed_count}件をクリーンアップ")
    
    return filtered_metrics

def save_metrics_data(json_file, metrics_list):
    """メトリクスデータをJSONファイルに保存"""
    output_data = {
        'metrics': metrics_list,
        'last_updated': datetime.now().isoformat(),
        'total_points': len(metrics_list),
        'data_range_hours': 168,  # 7日間
        'collector_type': 'sht35_optimized',
        'data_quality': 'high_precision_no_filtering'
    }
    
    # 原子的書き込みでファイル競合を回避
    temp_file = json_file + '.tmp'
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, separators=(',', ':'))
        
        # 原子的リネーム
        os.rename(temp_file, json_file)
        logger.info(f"メトリクスデータ保存完了: {len(metrics_list)}件")
        
    except Exception as e:
        logger.error(f"メトリクスデータ保存エラー: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise

def main():
    """メイン処理：SHT35専用データ収集"""
    
    # プロセス重複防止
    lock_file = tempfile.gettempdir() + '/sht35_collector.lock'
    try:
        lock_fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except OSError:
        logger.info("他のプロセスが実行中です")
        sys.exit(0)
    
    try:
        # 出力ファイルパス設定
        json_file = json_output_root / 'static' / 'data' / 'metrics.json'
        json_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("SHT35専用データ収集開始")
        
        # 既存データ読み込み
        existing_metrics = load_existing_data(json_file)
        
        # 新しいメトリクス作成
        new_metric = create_metric_entry()
        
        # データ追加
        existing_metrics.append(new_metric)
        
        # 古いデータクリーンアップ
        cleaned_metrics = cleanup_old_data(existing_metrics)
        
        # JSONファイル保存
        save_metrics_data(json_file, cleaned_metrics)
        
        logger.info(f"SHT35データ収集完了: {new_metric['room_temperature']}°C, {new_metric['humidity']}%, {new_metric['co2_ppm']}ppm")
        
    except Exception as e:
        logger.error(f"データ収集エラー: {e}")
        sys.exit(1)
        
    finally:
        # ロックファイル削除
        try:
            os.close(lock_fd)
            os.unlink(lock_file)
        except:
            pass

if __name__ == "__main__":
    main()