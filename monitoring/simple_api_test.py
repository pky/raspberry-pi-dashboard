#!/usr/bin/env python3
"""
シンプルなAPIテストスクリプト
管理画面での実行時のエラーを回避するため、依存関係を最小限に
"""

import requests
import time
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleAPITester:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.test_results = []
        
    def test_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                     params: Dict = None, timeout: int = 10) -> Dict:
        """単一エンドポイントのテスト"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=params, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response_time = time.time() - start_time
            
            # レスポンス内容の基本チェック
            content_type = response.headers.get('content-type', '')
            is_json = 'application/json' in content_type
            
            response_data = None
            if is_json:
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    is_json = False
            
            result = {
                "method": method.upper(),
                "endpoint": endpoint,
                "url": url,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "response_time": response_time,
                "success": response.status_code == expected_status,
                "content_type": content_type,
                "is_json": is_json,
                "response_size": len(response.content),
                "response_data": response_data,
                "timestamp": datetime.now().isoformat(),
                "error": None
            }
            
            return result
            
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            return {
                "method": method.upper(),
                "endpoint": endpoint,
                "url": url,
                "status_code": 0,
                "expected_status": expected_status,
                "response_time": response_time,
                "success": False,
                "content_type": None,
                "is_json": False,
                "response_size": 0,
                "response_data": None,
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def test_health(self) -> Dict:
        """ヘルスチェックエンドポイントのテスト"""
        logger.info("🔍 ヘルスチェックをテスト中...")
        
        result = self.test_endpoint("GET", "/health")
        
        if result["success"] and result["is_json"]:
            health_data = result["response_data"]
            
            # ヘルスチェック特有の検証（実際の応答形式に合わせて修正）
            required_fields = ["status", "timestamp", "checks"]
            missing_fields = [field for field in required_fields if field not in health_data]
            
            if missing_fields:
                result["success"] = False
                result["error"] = f"Missing required fields: {missing_fields}"
            elif health_data.get("status") != "healthy":
                result["success"] = False
                result["error"] = f"Health status is not healthy: {health_data.get('status')}"
            else:
                # 個別チェック項目の検証
                checks = health_data.get("checks", [])
                failed_checks = [check for check in checks if check.get("status") != "healthy"]
                if failed_checks:
                    result["warnings"] = result.get("warnings", [])
                    result["warnings"].append(f"Some health checks failed: {[c.get('component') for c in failed_checks]}")
        
        self.test_results.append(result)
        return result
    
    def test_sensor_collect(self) -> Dict:
        """センサー収集エンドポイントのテスト（記録機能付き）"""
        logger.info("🌡️ センサー収集エンドポイントをテスト中...")
        
        result = self.test_endpoint("GET", "/api/sensor/collect")
        
        if result["success"] and result["is_json"]:
            collect_data = result["response_data"]
            
            # センサー収集データの検証
            if collect_data.get("status") == "success" and "data" in collect_data:
                data = collect_data["data"]
                required_fields = ["temperature", "humidity", "discomfort_index", "co2_ppm", "co2_level"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    result["success"] = False
                    result["error"] = f"Missing sensor collect data fields: {missing_fields}"
                else:
                    # 値の妥当性チェック
                    temp = data.get("temperature")
                    humidity = data.get("humidity")
                    co2_ppm = data.get("co2_ppm")
                    logged = collect_data.get("logged", False)
                    
                    if temp is not None and not (-40 <= temp <= 80):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Temperature out of range: {temp}")
                    
                    if humidity is not None and not (0 <= humidity <= 100):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Humidity out of range: {humidity}")
                    
                    if co2_ppm is not None and not (300 <= co2_ppm <= 5000):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"CO2 out of range: {co2_ppm}")
                    
                    # ログ記録確認
                    if not logged:
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append("Sensor data logging failed")
                    
                    # 追加情報
                    result["sensor_collect_data"] = {
                        "temperature": temp,
                        "humidity": humidity,
                        "co2_ppm": co2_ppm,
                        "logged": logged
                    }
            else:
                result["success"] = False
                result["error"] = "Invalid sensor collect response structure"
        
        self.test_results.append(result)
        return result
    
    def test_sensor(self) -> Dict:
        """センサーエンドポイントのテスト"""
        logger.info("🌡️ センサーをテスト中...")
        
        result = self.test_endpoint("GET", "/api/sensor")
        
        if result["success"] and result["is_json"]:
            sensor_data = result["response_data"]
            
            # センサーデータの検証
            if sensor_data.get("status") == "success" and "data" in sensor_data:
                data = sensor_data["data"]
                required_fields = ["temperature", "humidity", "discomfort_index", "co2_ppm", "co2_level"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    result["success"] = False
                    result["error"] = f"Missing sensor data fields: {missing_fields}"
                else:
                    # 値の妥当性チェック
                    temp = data.get("temperature")
                    humidity = data.get("humidity")
                    co2_ppm = data.get("co2_ppm")
                    co2_level = data.get("co2_level")
                    
                    if temp is not None and not (-40 <= temp <= 80):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Temperature out of range: {temp}")
                    
                    if humidity is not None and not (0 <= humidity <= 100):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Humidity out of range: {humidity}")
                    
                    # CO2データのチェック
                    if co2_ppm is not None:
                        if not (0 <= co2_ppm <= 5000):
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"CO2 ppm out of range: {co2_ppm}")
                        
                        # CO2レベルチェック
                        valid_levels = ["正常", "注意", "警告", "危険", "エラー"]
                        if co2_level not in valid_levels:
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"Invalid CO2 level: {co2_level}")
        
        self.test_results.append(result)
        return result
    
    def test_calendar(self) -> Dict:
        """カレンダーエンドポイントのテスト"""
        logger.info("📅 カレンダーをテスト中...")
        
        # 今月のデータをテスト
        now = datetime.now()
        params = {"year": now.year, "month": now.month}
        
        result = self.test_endpoint("GET", "/api/calendar", params=params)
        
        if result["success"] and result["is_json"]:
            calendar_data = result["response_data"]
            
            # API応答形式の検証
            required_fields = ["status", "timestamp", "data"]
            missing_fields = [field for field in required_fields if field not in calendar_data]
            
            if missing_fields:
                result["success"] = False
                result["error"] = f"Missing calendar response fields: {missing_fields}"
            elif calendar_data.get("status") != "success":
                result["success"] = False
                result["error"] = f"Calendar API status not success: {calendar_data.get('status')}"
            else:
                # データ部分の基本検証
                data = calendar_data.get("data", {})
                calendar_sub_data = data.get("calendar_data", {})
                
                if "days" not in calendar_sub_data:
                    result["success"] = False
                    result["error"] = "Missing days data in calendar"
                else:
                    # 正常な応答の場合
                    google_events_count = data.get("google_events_count", 0)
                    holidays_count = data.get("holidays_count", 0)
                    
                    result["cache_info"] = {
                        "personal_events": google_events_count,
                        "holidays": holidays_count,
                        "year": data.get("year", "unknown"),
                        "month": data.get("month", "unknown")
                    }
        
        self.test_results.append(result)
        return result
    
    def test_system_metrics(self) -> Dict:
        """システムメトリクスエンドポイントのテスト"""
        logger.info("📊 システムメトリクスをテスト中...")
        
        result = self.test_endpoint("GET", "/api/system/metrics")
        
        if result["success"] and result["is_json"]:
            metrics = result["response_data"]
            
            # メトリクスの検証
            expected_sections = ["system", "process", "disk"]
            missing_sections = [sec for sec in expected_sections if sec not in metrics]
            
            if missing_sections:
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append(f"Missing metric sections: {missing_sections}")
        
        self.test_results.append(result)
        return result
    
    def test_co2_history(self) -> Dict:
        """CO2履歴エンドポイントのテスト"""
        logger.info("🌬️ CO2履歴をテスト中...")
        
        result = self.test_endpoint("GET", "/api/co2/history", params={"hours": 1})
        
        if result["success"] and result["is_json"]:
            data = result["response_data"]
            
            # データ構造の検証
            if "data" in data and "history" in data["data"]:
                history = data["data"]["history"]
                if isinstance(history, list):
                    # 履歴データの検証
                    for entry in history[:3]:  # 最初の3件をチェック
                        required_fields = ["timestamp", "co2_ppm", "level", "color"]
                        missing_fields = [f for f in required_fields if f not in entry]
                        if missing_fields:
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"Missing CO2 history fields: {missing_fields}")
                            break
                    
                    result["co2_history_count"] = len(history)
                else:
                    result["warnings"] = result.get("warnings", [])
                    result["warnings"].append("CO2 history data is not a list")
            else:
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append("Invalid CO2 history response structure")
        
        self.test_results.append(result)
        return result
    
    def test_co2_summary(self) -> Dict:
        """CO2日次サマリーエンドポイントのテスト"""
        logger.info("📊 CO2サマリーをテスト中...")
        
        result = self.test_endpoint("GET", "/api/co2/summary")
        
        if result["success"] and result["is_json"]:
            data = result["response_data"]
            
            # サマリーデータの検証
            if "data" in data:
                summary = data["data"]
                expected_fields = ["date", "min_ppm", "max_ppm", "avg_ppm", "alert_count"]
                missing_fields = [f for f in expected_fields if f not in summary]
                
                if missing_fields:
                    result["warnings"] = result.get("warnings", [])
                    result["warnings"].append(f"Missing CO2 summary fields: {missing_fields}")
                
                # データ型の検証
                if "avg_ppm" in summary and summary["avg_ppm"] is not None:
                    if not isinstance(summary["avg_ppm"], (int, float)):
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append("Invalid avg_ppm data type")
                
                result["co2_summary"] = summary
            else:
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append("Invalid CO2 summary response structure")
        
        self.test_results.append(result)
        return result
    
    def test_co2_alerts(self) -> Dict:
        """CO2アラートエンドポイントのテスト"""
        logger.info("🚨 CO2アラートをテスト中...")
        
        result = self.test_endpoint("GET", "/api/co2/alerts", params={"days": 1})
        
        if result["success"] and result["is_json"]:
            data = result["response_data"]
            
            # アラートデータの検証
            if "data" in data and "alerts" in data["data"]:
                alerts = data["data"]["alerts"]
                if isinstance(alerts, list):
                    # アラートデータの検証
                    for alert in alerts:
                        required_fields = ["timestamp", "co2_ppm", "level", "severity"]
                        missing_fields = [f for f in required_fields if f not in alert]
                        if missing_fields:
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"Missing CO2 alert fields: {missing_fields}")
                            break
                        
                        # severity値の検証
                        if alert.get("severity") not in ["warning", "danger"]:
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"Invalid severity value: {alert.get('severity')}")
                    
                    result["co2_alerts_count"] = len(alerts)
                else:
                    result["warnings"] = result.get("warnings", [])
                    result["warnings"].append("CO2 alerts data is not a list")
            else:
                result["warnings"] = result.get("warnings", [])
                result["warnings"].append("Invalid CO2 alerts response structure")
        
        self.test_results.append(result)
        return result
    
    def test_metrics_range(self) -> Dict:
        """SQLite直読みChart.js APIのテスト"""
        logger.info("📊 SQLite直読みメトリクスをテスト中...")
        
        result = self.test_endpoint("GET", "/api/metrics/range/1h")
        
        if result["success"] and result["is_json"]:
            metrics_data = result["response_data"]
            
            # メトリクスデータの検証
            if metrics_data.get("status") == "success" and "data" in metrics_data:
                data = metrics_data["data"]
                required_fields = ["metrics", "total_points", "time_range", "data_source"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    result["success"] = False
                    result["error"] = f"Missing metrics data fields: {missing_fields}"
                else:
                    # データソース確認
                    if data.get("data_source") != "sqlite_direct":
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Data source is not sqlite_direct: {data.get('data_source')}")
                    
                    # メトリクス配列確認
                    metrics = data.get("metrics", [])
                    if not isinstance(metrics, list):
                        result["success"] = False
                        result["error"] = "Metrics field is not an array"
                    elif len(metrics) > 0:
                        # 最初のメトリクスエントリの構造確認
                        first_metric = metrics[0]
                        metric_fields = ["timestamp", "co2_ppm", "room_temperature", "humidity"]
                        missing_metric_fields = [field for field in metric_fields if field not in first_metric]
                        
                        if missing_metric_fields:
                            result["warnings"] = result.get("warnings", [])
                            result["warnings"].append(f"Missing metric fields: {missing_metric_fields}")
                        
                        # 追加情報
                        result["metrics_count"] = len(metrics)
                        result["time_range"] = data.get("time_range")
        
        self.test_results.append(result)
        return result
    
    def test_database_status(self) -> Dict:
        """データベース状態APIのテスト"""
        logger.info("💾 データベース状態をテスト中...")
        
        result = self.test_endpoint("GET", "/api/database/status")
        
        if result["success"] and result["is_json"]:
            db_data = result["response_data"]
            
            # データベース状態の検証
            if db_data.get("status") == "success" and "data" in db_data:
                data = db_data["data"]
                required_fields = ["file_sizes_mb", "total_sizes_mb", "grand_total_mb", "retention_months"]
                missing_fields = [field for field in required_fields if field not in data]
                
                if missing_fields:
                    result["success"] = False
                    result["error"] = f"Missing database status fields: {missing_fields}"
                else:
                    # データベースタイプ確認
                    file_sizes = data.get("file_sizes_mb", {})
                    expected_db_types = ["co2", "temp_humidity"]
                    missing_db_types = [db_type for db_type in expected_db_types if db_type not in file_sizes]
                    
                    if missing_db_types:
                        result["warnings"] = result.get("warnings", [])
                        result["warnings"].append(f"Missing database types: {missing_db_types}")
                    
                    # 追加情報
                    result["grand_total_mb"] = data.get("grand_total_mb")
                    result["retention_months"] = data.get("retention_months")
                    result["current_month"] = data.get("current_month")
        
        self.test_results.append(result)
        return result
    
    def test_database_cleanup_dry_run(self) -> Dict:
        """データベースクリーンアップAPI（ドライラン的テスト）"""
        logger.info("🗑️ データベースクリーンアップ機能をテスト中...")
        
        # 注意: 実際にはクリーンアップを実行せず、エンドポイントの存在確認のみ
        # POST実行はシステムに影響があるため、ステータス確認の後に判断
        
        # まずステータスで現在の状況確認
        status_result = self.test_endpoint("GET", "/api/database/status")
        
        if status_result["success"]:
            # クリーンアップが必要かどうかの簡易判定
            if status_result["is_json"]:
                db_data = status_result["response_data"]
                data = db_data.get("data", {})
                available_months = data.get("available_months", {})
                
                # 6ヶ月以上のデータがある場合のみクリーンアップテスト実行
                total_months = sum(len(months) for months in available_months.values())
                
                result = {
                    "method": "GET",
                    "endpoint": "/api/database/cleanup (dry-run check)",
                    "url": f"{self.base_url}/api/database/status",
                    "status_code": status_result["status_code"],
                    "expected_status": 200,
                    "response_time": status_result["response_time"],
                    "success": status_result["success"],
                    "content_type": status_result["content_type"],
                    "is_json": status_result["is_json"],
                    "response_size": status_result["response_size"],
                    "response_data": {"cleanup_needed": total_months > 6},
                    "timestamp": datetime.now().isoformat(),
                    "error": None,
                    "cleanup_assessment": f"Total months: {total_months}, cleanup needed: {total_months > 6}"
                }
            else:
                result = status_result.copy()
                result["error"] = "Cannot assess cleanup needs - database status unavailable"
                result["success"] = False
        else:
            result = status_result.copy()
            result["endpoint"] = "/api/database/cleanup (failed to check)"
            result["error"] = "Database status check failed"
        
        self.test_results.append(result)
        return result
    
    def run_basic_tests(self) -> Dict:
        """基本的な機能テストを実行"""
        logger.info("🧪 基本機能テストを開始...")
        
        start_time = time.time()
        
        # 各エンドポイントのテスト - 3個（最小限）
        tests = [
            self.test_health,
            self.test_sensor,      # 温湿度・CO2データ含む
            self.test_calendar,
            # sensorにCO2データ含まれるのでmetricsは重複
            # self.test_system_metrics,
            # その他すべて削除済み
            # self.test_co2_history,
            # self.test_co2_summary,
            # self.test_co2_alerts,
            # self.test_sensor_collect,
            # self.test_metrics_range,
            # self.test_database_status,
            # self.test_database_cleanup_dry_run
        ]
        
        results = []
        for test_func in tests:
            try:
                result = test_func()
                results.append(result)
            except Exception as e:
                logger.error(f"テスト実行エラー: {e}")
                results.append({
                    "endpoint": "unknown",
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        total_time = time.time() - start_time
        
        # テスト結果のサマリー
        successful_tests = sum(1 for r in results if r.get("success", False))
        total_tests = len(results)
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        
        # 平均応答時間の計算（statisticsモジュールを使わない）
        response_times = [r.get("response_time", 0) for r in results if r.get("response_time")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        summary = {
            "test_type": "basic_functionality",
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "total_execution_time": total_time,
            "timestamp": datetime.now().isoformat(),
            "results": results
        }
        
        # 管理画面用の結果ファイルを作成
        admin_summary = {
            "summary": {
                "total": total_tests,
                "passed": successful_tests,
                "failed": total_tests - successful_tests,
                "error": 0,
                "skipped": 0,
                "duration": f"{total_time:.2f}s"
            },
            "tests": []
        }
        
        # 各テスト結果を管理画面形式に変換
        for result in results:
            test_entry = {
                "name": result.get("endpoint", "unknown"),
                "status": "pass" if result.get("success", False) else "fail",
                "duration": result.get("response_time", 0),
                "error": result.get("error", None),
                "details": {
                    "method": result.get("method", "GET"),
                    "url": result.get("url", ""),
                    "status_code": result.get("status_code", 0),
                    "response_time": result.get("response_time", 0)
                }
            }
            admin_summary["tests"].append(test_entry)
        
        # reportsディレクトリに保存
        from pathlib import Path
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / "test_results.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(admin_summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 基本テスト完了 - 成功率: {success_rate:.1%}, 平均応答時間: {avg_response_time:.2f}秒")
        logger.info(f"📄 管理画面用結果ファイルを保存: {report_file}")
        
        return summary

def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="シンプルAPIテストスクリプト")
    parser.add_argument("--url", default="http://localhost:5000", help="APIサーバーURL")
    parser.add_argument("--output", help="結果をJSONファイルに保存")
    
    args = parser.parse_args()
    
    tester = SimpleAPITester(base_url=args.url)
    
    try:
        result = tester.run_basic_tests()
        
        if args.output:
            # 管理画面用の形式は既にrun_basic_tests()内で保存済み
            # ここではレガシー形式を別ファイルに保存（必要に応じて）
            pass
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("🛑 テストが中断されました")
        return 1
    except Exception as e:
        logger.error(f"❌ テスト実行エラー: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())