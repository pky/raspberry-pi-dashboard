#!/usr/bin/env python3
"""
monitoring_data_cache.py - システム監視データキャッシュシステム

5分間隔で収集される監視データを時系列で管理し、
Chart.js用のグラフデータ生成を行うシステム
"""

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

# ローカルモジュール
from simple_system_monitor import get_simple_system_metrics
from sensor import get_sensor


# ログ設定
logger = logging.getLogger(__name__)


@dataclass
class MetricsDataPoint:
    """監視データポイント"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    cpu_temperature: float
    room_temperature: float
    humidity: float
    co2_ppm: int
    disk_used_gb: float
    disk_total_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    uptime_seconds: float


class MonitoringDataCache:
    """
    監視データキャッシュシステム
    
    5分間隔で収集されるシステム監視データを最大24時間分保持し、
    時系列グラフ用のデータ提供を行う
    """
    
    def __init__(self, max_hours: int = 24):
        """
        初期化
        
        Args:
            max_hours: 最大保持時間（時間）
        """
        # 5分間隔で24時間 = 288ポイント
        self.max_points = max_hours * 12
        self.data_storage: deque[MetricsDataPoint] = deque(maxlen=self.max_points)
        self.lock = threading.Lock()
        
        # センサーインスタンス
        self.sensor = get_sensor()
        
        logger.info(f"監視データキャッシュ初期化: 最大{max_hours}時間分({self.max_points}ポイント)")
        
        # グラフ表示用にサンプルデータを初期化（開発・デモ用）
        self._initialize_sample_data()
    
    def collect_current_metrics(self) -> Optional[MetricsDataPoint]:
        """
        現在のシステムメトリクスを収集
        
        Returns:
            MetricsDataPoint: 収集されたデータポイント
        """
        try:
            # システムメトリクス取得
            system_metrics = get_simple_system_metrics()
            
            # センサーデータ取得
            sensor_data = self.sensor.get_sensor_data()
            
            # データポイント作成
            data_point = MetricsDataPoint(
                timestamp=datetime.now(),
                cpu_percent=system_metrics.get('cpu_percent', 0.0),
                memory_percent=system_metrics.get('memory_percent', 0.0),
                cpu_temperature=system_metrics.get('temperature', 0.0),
                room_temperature=sensor_data.get('temperature', 0.0),
                humidity=sensor_data.get('humidity', 0.0),
                co2_ppm=sensor_data.get('co2_ppm', 400),
                disk_used_gb=system_metrics.get('disk_used_gb', 0.0),
                disk_total_gb=system_metrics.get('disk_total_gb', 64.0),
                network_bytes_sent=system_metrics.get('network_bytes_sent', 0),
                network_bytes_recv=system_metrics.get('network_bytes_recv', 0),
                uptime_seconds=system_metrics.get('uptime_seconds', 0.0)
            )
            
            logger.debug(f"メトリクス収集完了: CPU {data_point.cpu_percent}%, "
                        f"メモリ {data_point.memory_percent}%, "
                        f"温度 {data_point.room_temperature}°C, "
                        f"CO2 {data_point.co2_ppm}ppm")
            
            return data_point
            
        except Exception as e:
            logger.error(f"メトリクス収集エラー: {e}")
            return None
    
    def add_data_point(self, data_point: Optional[MetricsDataPoint] = None) -> bool:
        """
        データポイントをキャッシュに追加
        
        Args:
            data_point: 追加するデータポイント（Noneの場合は現在のメトリクスを収集）
            
        Returns:
            bool: 追加成功フラグ
        """
        if data_point is None:
            data_point = self.collect_current_metrics()
        
        if data_point is None:
            return False
        
        with self.lock:
            self.data_storage.append(data_point)
            logger.debug(f"データポイント追加: {data_point.timestamp}, "
                        f"キャッシュサイズ: {len(self.data_storage)}")
            return True
    
    def get_time_range_data(self, time_range: str) -> Dict[str, Any]:
        """
        指定期間のデータを取得
        
        Args:
            time_range: 時間範囲 ('1h', '6h', '12h', '24h')
            
        Returns:
            Dict: Chart.js用フォーマットのデータ
        """
        # 時間範囲マッピング
        hours_map = {
            '1h': {'hours': 1, 'description': '過去1時間', 'expected_points': 12},
            '6h': {'hours': 6, 'description': '過去6時間', 'expected_points': 72},
            '12h': {'hours': 12, 'description': '過去12時間', 'expected_points': 144},
            '24h': {'hours': 24, 'description': '過去24時間', 'expected_points': 288}
        }
        
        if time_range not in hours_map:
            raise ValueError(f"無効な時間範囲: {time_range}。有効な値: {list(hours_map.keys())}")
        
        range_info = hours_map[time_range]
        target_hours = range_info['hours']
        cutoff_time = datetime.now() - timedelta(hours=target_hours)
        
        with self.lock:
            # 指定期間内のデータをフィルタ
            filtered_data = [
                point for point in self.data_storage
                if point.timestamp >= cutoff_time
            ]
            
            # データポイント数
            data_count = len(filtered_data)
            
            if data_count == 0:
                return self._create_empty_response(time_range, range_info)
            
            # データを時系列順にソート
            filtered_data.sort(key=lambda x: x.timestamp)
            
            # Chart.js用データ形式に変換
            return self._format_chart_data(filtered_data, time_range, range_info)
    
    def get_latest_data(self, count: int = 12) -> List[MetricsDataPoint]:
        """
        最新N件のデータを取得
        
        Args:
            count: 取得するデータ数
            
        Returns:
            List[MetricsDataPoint]: 最新データリスト
        """
        with self.lock:
            return list(self.data_storage)[-count:]
    
    def _format_chart_data(self, data_points: List[MetricsDataPoint], time_range: str, range_info: Dict) -> Dict[str, Any]:
        """
        Chart.js用データ形式に変換
        
        Args:
            data_points: データポイントリスト
            time_range: 時間範囲
            range_info: 時間範囲詳細情報
            
        Returns:
            Dict: Chart.js用フォーマットのデータ
        """
        if not data_points:
            return self._create_empty_response(time_range, range_info)
        
        # タイムスタンプとメトリクス配列を生成
        timestamps = []
        metrics = {
            'cpu_percent': [],
            'memory_percent': [],
            'cpu_temperature': [],
            'room_temperature': [],
            'humidity': [],
            'co2_ppm': [],
            'disk_used_gb': [],
            'network_bytes_sent_mb': [],
            'network_bytes_recv_mb': []
        }
        
        for point in data_points:
            # ISO形式のタイムスタンプ
            timestamps.append(point.timestamp.isoformat())
            
            # メトリクス値
            metrics['cpu_percent'].append(round(point.cpu_percent, 1))
            metrics['memory_percent'].append(round(point.memory_percent, 1))
            metrics['cpu_temperature'].append(round(point.cpu_temperature, 1))
            metrics['room_temperature'].append(round(point.room_temperature, 1))
            metrics['humidity'].append(round(point.humidity, 1))
            metrics['co2_ppm'].append(point.co2_ppm)
            metrics['disk_used_gb'].append(round(point.disk_used_gb, 1))
            # ネットワークはMB単位に変換
            metrics['network_bytes_sent_mb'].append(round(point.network_bytes_sent / 1024 / 1024, 2))
            metrics['network_bytes_recv_mb'].append(round(point.network_bytes_recv / 1024 / 1024, 2))
        
        # データカバレッジ計算
        actual_points = len(data_points)
        expected_points = range_info['expected_points']
        coverage_percent = round((actual_points / expected_points) * 100, 1) if expected_points > 0 else 0
        
        return {
            'timeRange': time_range,
            'timeRangeDescription': range_info['description'],
            'interval': '5m',
            'dataPoints': actual_points,
            'expectedPoints': expected_points,
            'dataCoverage': coverage_percent,
            'data': {
                'timestamps': timestamps,
                'metrics': metrics
            },
            'timeInfo': {
                'startTime': timestamps[0] if timestamps else None,
                'endTime': timestamps[-1] if timestamps else None,
                'currentTime': datetime.now().isoformat()
            },
            'thresholds': {
                'co2_warning': [1000, 1500, 3000],
                'cpu_temperature_warning': 70,
                'cpu_percent_warning': 80,
                'memory_percent_warning': 80
            }
        }
    
    def _create_empty_response(self, time_range: str, range_info: Dict = None) -> Dict[str, Any]:
        """
        空のレスポンスを作成
        
        Args:
            time_range: 時間範囲
            range_info: 時間範囲詳細情報
            
        Returns:
            Dict: 空のChart.js用データ
        """
        if range_info is None:
            range_info = {'description': time_range, 'expected_points': 0}
            
        return {
            'timeRange': time_range,
            'timeRangeDescription': range_info['description'],
            'interval': '5m',
            'dataPoints': 0,
            'expectedPoints': range_info['expected_points'],
            'dataCoverage': 0,
            'data': {
                'timestamps': [],
                'metrics': {
                    'cpu_percent': [],
                    'memory_percent': [],
                    'cpu_temperature': [],
                    'room_temperature': [],
                    'humidity': [],
                    'co2_ppm': [],
                    'disk_used_gb': [],
                    'network_bytes_sent_mb': [],
                    'network_bytes_recv_mb': []
                }
            },
            'timeInfo': {
                'startTime': None,
                'endTime': None,
                'currentTime': datetime.now().isoformat()
            },
            'thresholds': {
                'co2_warning': [1000, 1500, 3000],
                'cpu_temperature_warning': 70,
                'cpu_percent_warning': 80,
                'memory_percent_warning': 80
            }
        }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        キャッシュ統計情報を取得
        
        Returns:
            Dict: キャッシュ統計
        """
        with self.lock:
            data_count = len(self.data_storage)
            if data_count == 0:
                return {
                    'total_points': 0,
                    'max_points': self.max_points,
                    'usage_percent': 0,
                    'oldest_timestamp': None,
                    'newest_timestamp': None,
                    'time_span_hours': 0
                }
            
            oldest = self.data_storage[0].timestamp
            newest = self.data_storage[-1].timestamp
            time_span = (newest - oldest).total_seconds() / 3600
            
            return {
                'total_points': data_count,
                'max_points': self.max_points,
                'usage_percent': round((data_count / self.max_points) * 100, 1),
                'oldest_timestamp': oldest.isoformat(),
                'newest_timestamp': newest.isoformat(),
                'time_span_hours': round(time_span, 1)
            }
    
    def cleanup_old_data(self, hours: int = 24) -> int:
        """
        古いデータをクリーンアップ
        
        Args:
            hours: 保持時間（時間）
            
        Returns:
            int: 削除されたデータ数
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        removed_count = 0
        
        with self.lock:
            original_length = len(self.data_storage)
            
            # 古いデータを削除
            while self.data_storage and self.data_storage[0].timestamp < cutoff_time:
                self.data_storage.popleft()
                removed_count += 1
            
            if removed_count > 0:
                logger.info(f"古いデータクリーンアップ: {removed_count}件削除")
        
        return removed_count
    
    def _initialize_sample_data(self):
        """
        グラフ表示用サンプルデータの初期化
        
        実際の運用では5分間隔のcronジョブがデータを蓄積するが、
        開発・デモ目的で過去1時間分のサンプルデータを生成
        """
        import random
        from datetime import datetime, timedelta
        
        logger.info("グラフ表示用サンプルデータを初期化中...")
        
        # 過去1時間分のサンプルデータを生成（5分間隔 = 12ポイント）
        now = datetime.now()
        
        for i in range(12):
            # 過去から現在に向かって時系列データを生成
            timestamp = now - timedelta(minutes=55 - (i * 5))
            
            # リアルなシミュレーションデータ生成
            base_cpu = 20 + random.uniform(-10, 30)  # 10-50%
            base_memory = 40 + random.uniform(-15, 20)  # 25-60%
            base_temp = 50 + random.uniform(-5, 15)  # 45-65°C
            base_room_temp = 22 + random.uniform(-2, 4)  # 20-26°C
            base_humidity = 50 + random.uniform(-10, 20)  # 40-70%
            base_co2 = 800 + random.uniform(-200, 600)  # 600-1400ppm
            
            sample_point = MetricsDataPoint(
                timestamp=timestamp,
                cpu_percent=round(max(0, min(100, base_cpu)), 1),
                memory_percent=round(max(0, min(100, base_memory)), 1),
                cpu_temperature=round(max(40, min(80, base_temp)), 1),
                room_temperature=round(max(18, min(30, base_room_temp)), 1),
                humidity=round(max(20, min(90, base_humidity)), 1),
                co2_ppm=int(max(400, min(3000, base_co2))),
                disk_used_gb=9.1 + random.uniform(-0.1, 0.1),
                disk_total_gb=234.2,
                network_bytes_sent=int(76000000 + random.uniform(-1000000, 2000000)),
                network_bytes_recv=int(2600000000 + random.uniform(-10000000, 20000000)),
                uptime_seconds=50000 + (i * 300)  # 5分ずつ増加
            )
            
            with self.lock:
                self.data_storage.append(sample_point)
        
        logger.info(f"サンプルデータ初期化完了: {len(self.data_storage)}ポイント")


# グローバルキャッシュインスタンス
_cache_instance: Optional[MonitoringDataCache] = None


def get_monitoring_cache() -> MonitoringDataCache:
    """
    シングルトン監視データキャッシュインスタンスを取得
    
    Returns:
        MonitoringDataCache: キャッシュインスタンス
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = MonitoringDataCache()
    return _cache_instance


def main():
    """
    メイン関数 - コマンドライン引数対応
    """
    import sys
    import time
    
    # コマンドライン引数確認
    if len(sys.argv) > 1 and sys.argv[1] == '--collect-once':
        # 本番用: 1つのデータポイントのみ追加
        logging.basicConfig(level=logging.WARNING)  # 本番用にWARNINGレベル
        cache = get_monitoring_cache()
        success = cache.add_data_point()
        if success:
            stats = cache.get_cache_stats()
            logger.info(f"データポイント追加成功 - 総ポイント数: {stats['total_points']}")
            # cronログ用に簡潔な出力
            print(f"OK: {datetime.now().strftime('%H:%M:%S')} - Points: {stats['total_points']}")
        else:
            logger.error("データポイント追加失敗")
            print(f"ERROR: {datetime.now().strftime('%H:%M:%S')} - データポイント追加失敗")
    else:
        # テストモード: 複数データポイント追加
        logging.basicConfig(level=logging.DEBUG)
        cache = get_monitoring_cache()
        print("監視データキャッシュテスト開始...")
        
        # テストデータを追加
        for i in range(5):
            success = cache.add_data_point()
            if success:
                print(f"データポイント{i+1}追加成功")
            else:
                print(f"データポイント{i+1}追加失敗")
            time.sleep(1)
        
        # キャッシュ統計表示
        stats = cache.get_cache_stats()
        print(f"\nキャッシュ統計: {json.dumps(stats, indent=2, ensure_ascii=False)}")
        
        # 1時間データ取得テスト
        data = cache.get_time_range_data('1h')
        print(f"\n1時間データ: データポイント数 = {data['dataPoints']}")
        
        print("テスト完了")


if __name__ == "__main__":
    main()