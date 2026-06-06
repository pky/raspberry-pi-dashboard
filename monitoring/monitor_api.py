#!/usr/bin/env python3
"""
APIサーバー監視スクリプト
定期的にAPIサーバーのヘルスチェックを行い、異常時にアラートを出す
"""

import requests
import time
import logging
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
import psutil
import subprocess

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class APIMonitor:
    def __init__(self, base_url: str = "http://localhost:5000", check_interval: int = 30):
        self.base_url = base_url
        self.check_interval = check_interval
        self.endpoints = [
            "/health",
            "/api/sensor", 
            "/api/calendar?monitor=true",  # 監視モードで軽量処理
            "/api/system/metrics"
        ]
        self.alert_thresholds = {
            "response_time": 5.0,  # 秒
            "error_rate": 0.1,     # 10%
            "memory_usage": 0.8,   # 80%
            "cpu_usage": 0.9       # 90%
        }
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "last_check": None
        }
        
    def check_endpoint(self, endpoint: str) -> Dict:
        """指定エンドポイントのヘルスチェック"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            response = requests.get(url, timeout=10)
            response_time = time.time() - start_time
            
            result = {
                "endpoint": endpoint,
                "status_code": response.status_code,
                "response_time": response_time,
                "success": 200 <= response.status_code < 300,
                "timestamp": datetime.now().isoformat(),
                "error": None
            }
            
            # レスポンス内容も記録（healthエンドポイントの場合）
            if endpoint == "/health":
                try:
                    result["response_data"] = response.json()
                except:
                    result["response_data"] = response.text[:200]
            
            return result
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            return {
                "endpoint": endpoint,
                "status_code": 0,
                "response_time": response_time,
                "success": False,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict:
        """システムリソースの監視"""
        try:
            # APIプロセスを探す
            api_process = None
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['cmdline'] and 'app.py' in ' '.join(proc.info['cmdline']):
                        api_process = psutil.Process(proc.info['pid'])
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            system_stats = {
                "timestamp": datetime.now().isoformat(),
                "system": {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_percent": psutil.disk_usage('/').percent,
                    "load_avg": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None
                },
                "api_process": None
            }
            
            if api_process:
                try:
                    system_stats["api_process"] = {
                        "pid": api_process.pid,
                        "cpu_percent": api_process.cpu_percent(),
                        "memory_percent": api_process.memory_percent(),
                        "memory_mb": api_process.memory_info().rss / 1024 / 1024,
                        "status": api_process.status(),
                        "create_time": datetime.fromtimestamp(api_process.create_time()).isoformat()
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    system_stats["api_process"] = {"error": "Process access denied"}
            
            return system_stats
            
        except Exception as e:
            logger.error(f"システムリソース監視エラー: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def analyze_and_alert(self, results: List[Dict], system_stats: Dict):
        """結果を分析してアラートを出す"""
        alerts = []
        
        # エンドポイント監視結果の分析
        for result in results:
            if not result["success"]:
                alerts.append({
                    "level": "ERROR",
                    "message": f"エンドポイント {result['endpoint']} が応答していません",
                    "details": result
                })
            
            elif result["response_time"] > self.alert_thresholds["response_time"]:
                alerts.append({
                    "level": "WARNING", 
                    "message": f"エンドポイント {result['endpoint']} の応答が遅いです ({result['response_time']:.2f}秒)",
                    "details": result
                })
        
        # システムリソースの分析
        if "system" in system_stats:
            sys_stats = system_stats["system"]
            
            if sys_stats["memory_percent"] > self.alert_thresholds["memory_usage"] * 100:
                alerts.append({
                    "level": "WARNING",
                    "message": f"メモリ使用率が高いです ({sys_stats['memory_percent']:.1f}%)",
                    "details": sys_stats
                })
            
            if sys_stats["cpu_percent"] > self.alert_thresholds["cpu_usage"] * 100:
                alerts.append({
                    "level": "WARNING",
                    "message": f"CPU使用率が高いです ({sys_stats['cpu_percent']:.1f}%)",
                    "details": sys_stats
                })
        
        # APIプロセスの分析
        if system_stats.get("api_process") is None:
            alerts.append({
                "level": "ERROR",
                "message": "APIプロセスが見つかりません",
                "details": system_stats
            })
        
        # アラート出力
        for alert in alerts:
            if alert["level"] == "ERROR":
                logger.error(f"🚨 {alert['message']}")
            else:
                logger.warning(f"⚠️ {alert['message']}")
        
        return alerts
    
    def restart_api_service(self):
        """APIサーバーを再起動（systemdサービス経由）"""
        try:
            logger.info("🔄 APIサーバーを再起動しています...")
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "raspberry-pi-api-server"],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                logger.info("✅ APIサーバーの再起動が完了しました")
                return True
            else:
                logger.error(f"❌ APIサーバー再起動失敗: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ APIサーバー再起動がタイムアウトしました")
            return False
        except Exception as e:
            logger.error(f"❌ APIサーバー再起動エラー: {e}")
            return False
    
    def run_monitoring_cycle(self):
        """1回の監視サイクルを実行"""
        logger.info("🔍 APIサーバー監視開始")
        
        # エンドポイントチェック
        results = []
        for endpoint in self.endpoints:
            result = self.check_endpoint(endpoint)
            results.append(result)
            
            # 統計更新
            self.stats["total_requests"] += 1
            if not result["success"]:
                self.stats["failed_requests"] += 1
            self.stats["response_times"].append(result["response_time"])
        
        # システムリソースチェック
        system_stats = self.check_system_resources()
        
        # 分析とアラート
        alerts = self.analyze_and_alert(results, system_stats)
        
        # 統計情報をログ出力
        error_rate = self.stats["failed_requests"] / self.stats["total_requests"] if self.stats["total_requests"] > 0 else 0
        avg_response_time = sum(self.stats["response_times"]) / len(self.stats["response_times"]) if self.stats["response_times"] else 0
        
        self.stats["last_check"] = datetime.now().isoformat()
        
        logger.info(f"📊 統計 - エラー率: {error_rate:.1%}, 平均応答時間: {avg_response_time:.2f}秒")
        
        # 重大なエラーが連続している場合は再起動を試行
        if len([a for a in alerts if a["level"] == "ERROR"]) >= 2:
            logger.warning("🚨 重大なエラーが検出されました。APIサーバーの再起動を試行します。")
            self.restart_api_service()
            time.sleep(10)  # 再起動後の待機時間
        
        return {
            "results": results,
            "system_stats": system_stats,
            "alerts": alerts,
            "monitoring_stats": self.stats.copy()
        }
    
    def run_continuous_monitoring(self):
        """継続監視を実行"""
        logger.info(f"🚀 APIサーバー継続監視開始 (間隔: {self.check_interval}秒)")
        
        try:
            while True:
                self.run_monitoring_cycle()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("📋 監視を停止しました")
        except Exception as e:
            logger.error(f"❌ 監視エラー: {e}")
            return 1

def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="APIサーバー監視スクリプト")
    parser.add_argument("--url", default="http://localhost:5000", help="APIサーバーURL")
    parser.add_argument("--interval", type=int, default=30, help="チェック間隔（秒）")
    parser.add_argument("--once", action="store_true", help="1回だけ実行")
    
    args = parser.parse_args()
    
    monitor = APIMonitor(base_url=args.url, check_interval=args.interval)
    
    if args.once:
        result = monitor.run_monitoring_cycle()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    else:
        return monitor.run_continuous_monitoring()

if __name__ == "__main__":
    sys.exit(main())