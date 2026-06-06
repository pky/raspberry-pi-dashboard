#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_monitor.py - システム監視機能（簡易復元版）
"""

import psutil
import time
from datetime import datetime
from typing import Dict, Any

class SystemMonitor:
    """システム監視クラス"""
    
    def __init__(self):
        self.start_time = time.time()
        self.is_monitoring = False
        
    def start_monitoring(self):
        """監視開始"""
        self.is_monitoring = True
        
    def stop_monitoring(self):
        """監視停止"""
        self.is_monitoring = False
        
    def get_health_status(self) -> Dict[str, Any]:
        """システムヘルス状態を取得"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int(time.time() - self.start_time)
        }
        
    def get_system_metrics(self) -> Dict[str, Any]:
        """システムメトリクスを取得"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "usage_percent": memory.percent,
                    "used": memory.used
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "usage_percent": (disk.used / disk.total) * 100
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンス概要を取得"""
        try:
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            
            return {
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "boot_time": boot_time.isoformat(),
                "process_count": len(psutil.pids()),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# グローバルインスタンス
_system_monitor_instance = None

def get_system_monitor() -> SystemMonitor:
    """システムモニターインスタンスを取得"""
    global _system_monitor_instance
    if _system_monitor_instance is None:
        _system_monitor_instance = SystemMonitor()
    return _system_monitor_instance

if __name__ == "__main__":
    # テスト実行
    monitor = get_system_monitor()
    print("Health Status:", monitor.get_health_status())
    print("System Metrics:", monitor.get_system_metrics())
    print("Performance Summary:", monitor.get_performance_summary())