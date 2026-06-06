"""
システム監視とヘルスチェック機能
要件7.2: システム全体のエラーハンドリング統合の一部
"""

import psutil
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import json

from error_handler import DashboardError, ErrorCode, ErrorLevel, get_error_handler
from logging_config import get_performance_logger

class HealthStatus(Enum):
    """ヘルス状態定義"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class SystemMetrics:
    """システムメトリクスデータクラス"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_percent: float
    disk_free_gb: float
    temperature: Optional[float]
    load_average: Optional[List[float]]
    network_bytes_sent: int
    network_bytes_recv: int
    uptime_seconds: float

@dataclass
class HealthCheck:
    """ヘルスチェック結果データクラス"""
    component: str
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: str

class SystemMonitor:
    """システム監視クラス"""
    
    def __init__(
        self,
        monitoring_interval: int = 30,
        enable_continuous_monitoring: bool = True,
        temperature_threshold: float = 75.0,
        memory_threshold: float = 85.0,
        disk_threshold: float = 90.0,
        cpu_threshold: float = 90.0
    ):
        self.monitoring_interval = monitoring_interval
        self.enable_continuous_monitoring = enable_continuous_monitoring
        self.temperature_threshold = temperature_threshold
        self.memory_threshold = memory_threshold
        self.disk_threshold = disk_threshold
        self.cpu_threshold = cpu_threshold
        
        self.logger = logging.getLogger(__name__)
        self.performance_logger = get_performance_logger()
        self.error_handler = get_error_handler()
        
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        self._metrics_history: List[SystemMetrics] = []
        self._max_history_size = 1440  # 24時間分（30秒間隔）
        
        self._boot_time = psutil.boot_time()
        self._process = psutil.Process()
    
    def start_monitoring(self):
        """継続的な監視を開始"""
        if not self.enable_continuous_monitoring:
            return
        
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self.logger.warning("Monitoring is already running")
            return
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="SystemMonitor",
            daemon=True
        )
        self._monitoring_thread.start()
        self.logger.info("System monitoring started")
    
    def stop_monitoring(self):
        """継続的な監視を停止"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5)
            self.logger.info("System monitoring stopped")
    
    def _monitoring_loop(self):
        """監視ループ"""
        while not self._stop_monitoring.is_set():
            try:
                metrics = self.get_system_metrics()
                self._store_metrics(metrics)
                self._check_thresholds(metrics)
                
                # パフォーマンスログに記録
                self.performance_logger.log_system_metrics(
                    cpu_percent=metrics.cpu_percent,
                    memory_percent=metrics.memory_percent,
                    disk_percent=metrics.disk_percent,
                    temperature=metrics.temperature
                )
                
            except Exception as e:
                self.error_handler.handle_error(
                    DashboardError(
                        message=f"System monitoring error: {str(e)}",
                        error_code=ErrorCode.SYSTEM_CONFIG_ERROR,
                        level=ErrorLevel.WARNING,
                        original_exception=e
                    ),
                    reraise=False
                )
            
            # 次のチェックまで待機
            self._stop_monitoring.wait(self.monitoring_interval)
    
    def get_system_metrics(self) -> SystemMetrics:
        """現在のシステムメトリクスを取得"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)
            
            # ディスク使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # CPU温度（Raspberry Piの場合）
            temperature = self._get_cpu_temperature()
            
            # ロードアベレージ
            load_average = list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
            
            # ネットワーク統計
            network = psutil.net_io_counters()
            
            # アップタイム
            uptime_seconds = time.time() - self._boot_time
            
            return SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_mb=round(memory_available_mb, 2),
                disk_percent=round(disk_percent, 2),
                disk_free_gb=round(disk_free_gb, 2),
                temperature=temperature,
                load_average=load_average,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                uptime_seconds=uptime_seconds
            )
            
        except Exception as e:
            raise DashboardError(
                message=f"Failed to get system metrics: {str(e)}",
                error_code=ErrorCode.SYSTEM_CONFIG_ERROR,
                level=ErrorLevel.ERROR,
                original_exception=e
            )
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """CPU温度を取得（Raspberry Pi専用）"""
        try:
            # Raspberry Piの温度ファイルを読み取り
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = int(f.read().strip()) / 1000.0
                return round(temp, 1)
        except (FileNotFoundError, PermissionError, ValueError):
            # Raspberry Pi以外の環境では温度情報を取得できない
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get CPU temperature: {e}")
            return None
    
    def _store_metrics(self, metrics: SystemMetrics):
        """メトリクスを履歴に保存"""
        self._metrics_history.append(metrics)
        
        # 履歴サイズを制限
        if len(self._metrics_history) > self._max_history_size:
            self._metrics_history.pop(0)
    
    def _check_thresholds(self, metrics: SystemMetrics):
        """閾値チェックとアラート"""
        alerts = []
        
        # CPU使用率チェック
        if metrics.cpu_percent > self.cpu_threshold:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        
        # メモリ使用率チェック
        if metrics.memory_percent > self.memory_threshold:
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")
        
        # ディスク使用率チェック
        if metrics.disk_percent > self.disk_threshold:
            alerts.append(f"High disk usage: {metrics.disk_percent:.1f}%")
        
        # CPU温度チェック
        if metrics.temperature and metrics.temperature > self.temperature_threshold:
            alerts.append(f"High CPU temperature: {metrics.temperature:.1f}°C")
        
        # アラートをログに記録
        for alert in alerts:
            self.logger.warning(f"System threshold exceeded: {alert}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """システム全体のヘルス状態を取得"""
        health_checks = []
        
        try:
            # システムメトリクスを取得
            metrics = self.get_system_metrics()
            
            # CPU ヘルスチェック
            cpu_status = HealthStatus.HEALTHY
            cpu_message = f"CPU usage: {metrics.cpu_percent:.1f}%"
            
            if metrics.cpu_percent > self.cpu_threshold:
                cpu_status = HealthStatus.CRITICAL
                cpu_message += " (Critical)"
            elif metrics.cpu_percent > self.cpu_threshold * 0.8:
                cpu_status = HealthStatus.WARNING
                cpu_message += " (Warning)"
            
            health_checks.append(HealthCheck(
                component="cpu",
                status=cpu_status,
                message=cpu_message,
                details={"percent": metrics.cpu_percent},
                timestamp=metrics.timestamp
            ))
            
            # メモリ ヘルスチェック
            memory_status = HealthStatus.HEALTHY
            memory_message = f"Memory usage: {metrics.memory_percent:.1f}%"
            
            if metrics.memory_percent > self.memory_threshold:
                memory_status = HealthStatus.CRITICAL
                memory_message += " (Critical)"
            elif metrics.memory_percent > self.memory_threshold * 0.8:
                memory_status = HealthStatus.WARNING
                memory_message += " (Warning)"
            
            health_checks.append(HealthCheck(
                component="memory",
                status=memory_status,
                message=memory_message,
                details={
                    "percent": metrics.memory_percent,
                    "available_mb": metrics.memory_available_mb
                },
                timestamp=metrics.timestamp
            ))
            
            # ディスク ヘルスチェック
            disk_status = HealthStatus.HEALTHY
            disk_message = f"Disk usage: {metrics.disk_percent:.1f}%"
            
            if metrics.disk_percent > self.disk_threshold:
                disk_status = HealthStatus.CRITICAL
                disk_message += " (Critical)"
            elif metrics.disk_percent > self.disk_threshold * 0.8:
                disk_status = HealthStatus.WARNING
                disk_message += " (Warning)"
            
            health_checks.append(HealthCheck(
                component="disk",
                status=disk_status,
                message=disk_message,
                details={
                    "percent": metrics.disk_percent,
                    "free_gb": metrics.disk_free_gb
                },
                timestamp=metrics.timestamp
            ))
            
            # 温度 ヘルスチェック
            if metrics.temperature:
                temp_status = HealthStatus.HEALTHY
                temp_message = f"CPU temperature: {metrics.temperature:.1f}°C"
                
                if metrics.temperature > self.temperature_threshold:
                    temp_status = HealthStatus.CRITICAL
                    temp_message += " (Critical)"
                elif metrics.temperature > self.temperature_threshold * 0.9:
                    temp_status = HealthStatus.WARNING
                    temp_message += " (Warning)"
                
                health_checks.append(HealthCheck(
                    component="temperature",
                    status=temp_status,
                    message=temp_message,
                    details={"celsius": metrics.temperature},
                    timestamp=metrics.timestamp
                ))
            
            # センサー ヘルスチェック
            sensor_health = self._check_sensor_health()
            health_checks.append(sensor_health)
            
            # カレンダー ヘルスチェック
            calendar_health = self._check_calendar_health()
            health_checks.append(calendar_health)
            
            # 全体的なステータスを決定
            overall_status = self._determine_overall_status(health_checks)
            
            return {
                "status": overall_status.value,
                "timestamp": datetime.now().isoformat(),
                "checks": [
                    {
                        "component": check.component,
                        "status": check.status.value,
                        "message": check.message,
                        "details": check.details,
                        "timestamp": check.timestamp
                    }
                    for check in health_checks
                ],
                "metrics": metrics.__dict__
            }
            
        except Exception as e:
            self.error_handler.handle_error(
                DashboardError(
                    message=f"Health check failed: {str(e)}",
                    error_code=ErrorCode.SYSTEM_CONFIG_ERROR,
                    level=ErrorLevel.ERROR,
                    original_exception=e
                ),
                reraise=False
            )
            
            return {
                "status": HealthStatus.UNKNOWN.value,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "checks": [],
                "metrics": {}
            }
    
    def _check_sensor_health(self) -> HealthCheck:
        """センサーヘルスチェック"""
        try:
            from sensor import get_sensor
            sensor = get_sensor()
            
            if sensor.test_connection():
                return HealthCheck(
                    component="sensor",
                    status=HealthStatus.HEALTHY,
                    message="Sensor connection healthy",
                    details={"connection": "ok"},
                    timestamp=datetime.now().isoformat()
                )
            else:
                return HealthCheck(
                    component="sensor",
                    status=HealthStatus.CRITICAL,
                    message="Sensor connection failed",
                    details={"connection": "failed"},
                    timestamp=datetime.now().isoformat()
                )
                
        except Exception as e:
            return HealthCheck(
                component="sensor",
                status=HealthStatus.WARNING,
                message=f"Sensor check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now().isoformat()
            )
    
    def _check_calendar_health(self) -> HealthCheck:
        """カレンダーヘルスチェック"""
        try:
            from calendar_data import get_calendar_manager
            manager = get_calendar_manager()
            
            # 今月のデータを取得してテスト
            now = datetime.now()
            result = manager.get_month_events(now.year, now.month)
            
            if result['status'] == 'success':
                return HealthCheck(
                    component="calendar",
                    status=HealthStatus.HEALTHY,
                    message="Calendar API connection healthy",
                    details={"events_count": result.get('google_events_count', 0)},
                    timestamp=datetime.now().isoformat()
                )
            else:
                return HealthCheck(
                    component="calendar",
                    status=HealthStatus.WARNING,
                    message=f"Calendar API issue: {result.get('error', 'Unknown error')}",
                    details={"error": result.get('error')},
                    timestamp=datetime.now().isoformat()
                )
                
        except Exception as e:
            return HealthCheck(
                component="calendar",
                status=HealthStatus.WARNING,
                message=f"Calendar check error: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.now().isoformat()
            )
    
    def _determine_overall_status(self, health_checks: List[HealthCheck]) -> HealthStatus:
        """全体的なヘルス状態を決定"""
        statuses = [check.status for check in health_checks]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        elif HealthStatus.UNKNOWN in statuses:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """指定時間内のメトリクス履歴を取得"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_metrics = []
        for metrics in self._metrics_history:
            metrics_time = datetime.fromisoformat(metrics.timestamp)
            if metrics_time >= cutoff_time:
                filtered_metrics.append(metrics.__dict__)
        
        return filtered_metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンスサマリーを取得"""
        if not self._metrics_history:
            return {"error": "No metrics history available"}
        
        recent_metrics = self._metrics_history[-60:]  # 直近30分（30秒間隔）
        
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]
        
        return {
            "time_window_minutes": len(recent_metrics) * (self.monitoring_interval / 60),
            "cpu": {
                "average": round(sum(cpu_values) / len(cpu_values), 2),
                "max": max(cpu_values),
                "min": min(cpu_values)
            },
            "memory": {
                "average": round(sum(memory_values) / len(memory_values), 2),
                "max": max(memory_values),
                "min": min(memory_values)
            },
            "samples": len(recent_metrics)
        }

# グローバルインスタンス
_system_monitor = None

def get_system_monitor() -> SystemMonitor:
    """システム監視インスタンスを取得"""
    global _system_monitor
    if _system_monitor is None:
        _system_monitor = SystemMonitor()
    return _system_monitor