#!/usr/bin/env python3
"""
M.2 SSD ヘルスチェック・SMART監視システム
週1回の自動テスト + admin画面表示用

機能:
- SMART属性取得・健康状態評価
- 温度・寿命・エラー率監視
- 週1回自動テスト実行
- admin画面API連携
"""

import os
import sys
import json
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# プロジェクトルートを追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from logging_system import get_logger
from config import get_config

class SSDHealthChecker:
    """M.2 SSD ヘルスチェック・SMART監視システム"""
    
    def __init__(self):
        """初期化"""
        # ログ設定
        self.logger = get_logger(__name__)
        
        # 設定取得
        self.settings = get_config()
        
        # 基本設定
        self.project_root = Path(__file__).parent.parent.parent
        self.device_path = "/dev/nvme0n1"  # M.2 SSDデバイス
        
        # ファイルパス設定
        self.health_status_file = self.project_root / "logs/ssd_health_status.json"
        self.smart_history_file = self.project_root / "logs/ssd_smart_history.json"
        self.test_log_file = self.project_root / "logs/ssd_health_test.log"
        
        # SMART属性しきい値設定
        self.thresholds = {
            "temperature": {
                "warning": 70,    # °C
                "critical": 80    # °C
            },
            "wear_percentage": {
                "warning": 80,    # %
                "critical": 90    # %
            },
            "power_on_hours": {
                "warning": 35040,  # 4年 (24*365*4)
                "critical": 43800  # 5年 (24*365*5)
            },
            "data_units_written": {
                "warning": None,   # TB (デバイス依存)
                "critical": None   # TB (デバイス依存)
            }
        }
        
    def check_nvme_device(self) -> bool:
        """NVMeデバイス存在確認"""
        try:
            result = subprocess.run([
                "sudo", "nvme", "list"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and self.device_path in result.stdout:
                self.logger.info(f"NVMeデバイス確認完了: {self.device_path}")
                return True
            else:
                self.logger.warning(f"NVMeデバイス未検出: {self.device_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"NVMeデバイス確認エラー: {e}")
            return False
    
    def get_smart_attributes(self) -> Dict:
        """SMART属性取得"""
        smart_data = {
            "timestamp": datetime.now().isoformat(),
            "device": self.device_path,
            "available": False,
            "attributes": {},
            "error": None
        }
        
        try:
            # NVMe SMART情報取得
            result = subprocess.run([
                "sudo", "nvme", "smart-log", self.device_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                smart_data["error"] = f"SMART取得エラー: {result.stderr}"
                return smart_data
            
            # SMART情報パース
            lines = result.stdout.strip().split('\n')
            attributes = {}
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('Smart Log') or line.startswith('='):
                    continue
                
                # 主要SMART属性を抽出
                if 'temperature' in line.lower() and ('°C' in line or 'celsius' in line):
                    # temperature : 49°C (322 Kelvin)
                    parts = line.split(':')
                    if len(parts) > 1:
                        temp_part = parts[1].strip()
                        # °C または Celsius を探す
                        if '°C' in temp_part:
                            temp_str = temp_part.split('°C')[0].strip()
                        elif 'Celsius' in temp_part:
                            temp_str = temp_part.split('Celsius')[0].strip()
                        else:
                            temp_str = temp_part.split()[0]
                        try:
                            attributes["temperature"] = int(temp_str)
                        except ValueError:
                            pass
                
                elif 'percentage_used' in line.lower():
                    # percentage_used : 0%
                    parts = line.split(':')
                    if len(parts) > 1:
                        percent_part = parts[1].strip()
                        # % マークを除去
                        percent_str = percent_part.replace('%', '').strip()
                        try:
                            attributes["wear_percentage"] = int(percent_str)
                        except ValueError:
                            pass
                
                elif 'data_units_written' in line.lower():
                    # Data Units Written: 1,234,567 [632 GB]
                    parts = line.split(':')
                    if len(parts) > 1:
                        # [632 GB] の形式から抽出
                        gb_match = parts[1].strip()
                        if '[' in gb_match and 'GB' in gb_match:
                            try:
                                gb_str = gb_match.split('[')[1].split('GB')[0].strip()
                                attributes["data_units_written_gb"] = int(gb_str.replace(',', ''))
                            except (ValueError, IndexError):
                                pass
                
                elif 'power_on_hours' in line.lower():
                    # Power On Hours: 1,234
                    parts = line.split(':')
                    if len(parts) > 1:
                        hours_str = parts[1].strip().replace(',', '')
                        try:
                            attributes["power_on_hours"] = int(hours_str)
                        except ValueError:
                            pass
                
                elif 'critical_warning' in line.lower():
                    # Critical Warning: 0x00
                    parts = line.split(':')
                    if len(parts) > 1:
                        warning_str = parts[1].strip()
                        attributes["critical_warning"] = warning_str
                
                elif 'media_errors' in line.lower():
                    # Media and Data Integrity Errors: 0
                    parts = line.split(':')
                    if len(parts) > 1:
                        errors_str = parts[1].strip()
                        try:
                            attributes["media_errors"] = int(errors_str)
                        except ValueError:
                            pass
            
            smart_data["attributes"] = attributes
            smart_data["available"] = len(attributes) > 0
            
            if smart_data["available"]:
                self.logger.info(f"SMART属性取得成功: {len(attributes)}項目")
            else:
                self.logger.warning("SMART属性の解析に失敗")
            
        except subprocess.TimeoutExpired:
            smart_data["error"] = "SMART取得タイムアウト"
            self.logger.error("SMART取得タイムアウト")
        except Exception as e:
            smart_data["error"] = f"SMART取得例外エラー: {e}"
            self.logger.error(f"SMART取得例外エラー: {e}")
        
        return smart_data
    
    def evaluate_health_status(self, smart_data: Dict) -> Dict:
        """健康状態評価"""
        health_status = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "unknown",
            "health_score": 0,
            "warnings": [],
            "critical_issues": [],
            "recommendations": [],
            "next_check_due": None
        }
        
        if not smart_data.get("available"):
            health_status["overall_status"] = "unavailable"
            health_status["warnings"].append("SMART情報取得不可")
            return health_status
        
        attributes = smart_data.get("attributes", {})
        score = 100  # 初期スコア
        warnings = []
        critical_issues = []
        recommendations = []
        
        # 温度チェック
        if "temperature" in attributes:
            temp = attributes["temperature"]
            if temp >= self.thresholds["temperature"]["critical"]:
                critical_issues.append(f"危険温度: {temp}°C (≥{self.thresholds['temperature']['critical']}°C)")
                score -= 30
                recommendations.append("冷却環境の改善が必要")
            elif temp >= self.thresholds["temperature"]["warning"]:
                warnings.append(f"高温注意: {temp}°C (≥{self.thresholds['temperature']['warning']}°C)")
                score -= 10
                recommendations.append("冷却状況の確認を推奨")
        
        # 摩耗度チェック
        if "wear_percentage" in attributes:
            wear = attributes["wear_percentage"]
            if wear >= self.thresholds["wear_percentage"]["critical"]:
                critical_issues.append(f"高摩耗率: {wear}% (≥{self.thresholds['wear_percentage']['critical']}%)")
                score -= 40
                recommendations.append("SSD交換を計画")
            elif wear >= self.thresholds["wear_percentage"]["warning"]:
                warnings.append(f"摩耗進行: {wear}% (≥{self.thresholds['wear_percentage']['warning']}%)")
                score -= 15
                recommendations.append("定期バックアップの実施")
        
        # 稼働時間チェック
        if "power_on_hours" in attributes:
            hours = attributes["power_on_hours"]
            years = hours / (24 * 365)
            if hours >= self.thresholds["power_on_hours"]["critical"]:
                critical_issues.append(f"長時間稼働: {hours:,}時間 ({years:.1f}年)")
                score -= 20
                recommendations.append("予防的SSD交換を検討")
            elif hours >= self.thresholds["power_on_hours"]["warning"]:
                warnings.append(f"長期稼働: {hours:,}時間 ({years:.1f}年)")
                score -= 5
                recommendations.append("健康状態の定期監視")
        
        # メディアエラーチェック
        if "media_errors" in attributes:
            errors = attributes["media_errors"]
            if errors > 0:
                critical_issues.append(f"メディアエラー検出: {errors}件")
                score -= 25
                recommendations.append("データ整合性チェック実行")
        
        # クリティカル警告チェック
        if "critical_warning" in attributes:
            warning = attributes["critical_warning"]
            if warning != "0x00" and warning != "0":
                critical_issues.append(f"クリティカル警告: {warning}")
                score -= 35
                recommendations.append("即座にバックアップ作成")
        
        # スコア正規化
        health_status["health_score"] = max(0, score)
        health_status["warnings"] = warnings
        health_status["critical_issues"] = critical_issues
        health_status["recommendations"] = recommendations
        
        # 総合ステータス判定
        if critical_issues:
            health_status["overall_status"] = "critical"
        elif warnings:
            health_status["overall_status"] = "warning"
        else:
            health_status["overall_status"] = "healthy"
        
        # 次回チェック予定（1週間後）
        next_check = datetime.now() + timedelta(days=7)
        health_status["next_check_due"] = next_check.isoformat()
        
        return health_status
    
    def run_comprehensive_test(self) -> Dict:
        """包括的SSD健康テスト"""
        test_result = {
            "test_type": "comprehensive_health_check",
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "duration_seconds": 0,
            "success": False,
            "device_detected": False,
            "smart_available": False,
            "health_status": {},
            "smart_data": {},
            "performance_info": {},
            "error": None
        }
        
        start_time = time.time()
        
        try:
            self.logger.info("M.2 SSD包括的健康テスト開始")
            
            # 1. デバイス検出テスト
            test_result["device_detected"] = self.check_nvme_device()
            if not test_result["device_detected"]:
                test_result["error"] = "NVMeデバイス未検出"
                return test_result
            
            # 2. SMART情報取得
            smart_data = self.get_smart_attributes()
            test_result["smart_data"] = smart_data
            test_result["smart_available"] = smart_data.get("available", False)
            
            if not test_result["smart_available"]:
                test_result["error"] = smart_data.get("error", "SMART情報取得失敗")
                return test_result
            
            # 3. 健康状態評価
            health_status = self.evaluate_health_status(smart_data)
            test_result["health_status"] = health_status
            
            # 4. パフォーマンス情報取得（オプション）
            try:
                disk_usage = subprocess.run([
                    "df", "-h", "/"
                ], capture_output=True, text=True, timeout=10)
                
                if disk_usage.returncode == 0:
                    lines = disk_usage.stdout.strip().split('\n')
                    if len(lines) > 1:
                        parts = lines[1].split()
                        if len(parts) >= 5:
                            test_result["performance_info"] = {
                                "filesystem": parts[0],
                                "total_size": parts[1],
                                "used_size": parts[2],
                                "available_size": parts[3],
                                "use_percentage": parts[4]
                            }
            except Exception as e:
                self.logger.warning(f"パフォーマンス情報取得エラー: {e}")
            
            test_result["success"] = True
            self.logger.info("M.2 SSD包括的健康テスト完了")
            
        except Exception as e:
            test_result["error"] = f"テスト実行エラー: {e}"
            self.logger.error(f"M.2 SSD健康テストエラー: {e}")
        
        finally:
            end_time = time.time()
            test_result["end_time"] = datetime.now().isoformat()
            test_result["duration_seconds"] = round(end_time - start_time, 2)
        
        return test_result
    
    def save_health_status(self, health_data: Dict):
        """健康状態データ保存"""
        try:
            # ディレクトリ作成
            self.health_status_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 現在の健康状態を保存
            with open(self.health_status_file, 'w', encoding='utf-8') as f:
                json.dump(health_data, f, indent=2, ensure_ascii=False)
            
            # 履歴に追加
            history = []
            if self.smart_history_file.exists():
                try:
                    with open(self.smart_history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                except Exception:
                    history = []
            
            # 新しいデータを履歴に追加
            history.append(health_data)
            
            # 履歴制限（最新50件）
            if len(history) > 50:
                history = history[-50:]
            
            # 履歴保存
            with open(self.smart_history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            
            self.logger.info("SSD健康状態データ保存完了")
            
        except Exception as e:
            self.logger.error(f"健康状態データ保存エラー: {e}")
    
    def get_latest_health_status(self) -> Optional[Dict]:
        """最新健康状態取得"""
        try:
            if self.health_status_file.exists():
                with open(self.health_status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return None
        except Exception as e:
            self.logger.error(f"健康状態読み込みエラー: {e}")
            return None
    
    def should_run_weekly_test(self) -> bool:
        """週次テスト実行判定"""
        try:
            latest_health = self.get_latest_health_status()
            if not latest_health:
                return True
            
            last_test_time = datetime.fromisoformat(latest_health.get("timestamp", "1970-01-01T00:00:00"))
            week_ago = datetime.now() - timedelta(days=7)
            
            return last_test_time < week_ago
            
        except Exception as e:
            self.logger.error(f"週次テスト判定エラー: {e}")
            return True  # エラー時は実行

def main():
    """メイン実行"""
    import argparse
    
    logger = get_logger(__name__)
    
    parser = argparse.ArgumentParser(description="M.2 SSD ヘルスチェック・SMART監視システム")
    parser.add_argument("--test", action="store_true", help="包括的健康テスト実行")
    parser.add_argument("--status", action="store_true", help="現在の健康状態表示")
    parser.add_argument("--weekly-check", action="store_true", help="週次自動チェック")
    parser.add_argument("--force", action="store_true", help="強制実行")
    
    args = parser.parse_args()
    
    checker = SSDHealthChecker()
    
    if args.test or args.force:
        # 包括的テスト実行
        result = checker.run_comprehensive_test()
        logger.info(f"SSDヘルステスト結果: {'成功' if result['success'] else '失敗'}")
        
        if result["success"]:
            health_status = result["health_status"]
            logger.info(f"健康状態: {health_status['overall_status']}")
            logger.info(f"健康スコア: {health_status['health_score']}/100")
            
            if health_status["warnings"]:
                logger.warning("警告:")
                for warning in health_status["warnings"]:
                    logger.info(f"- {warning}")
            
            if health_status["critical_issues"]:
                logger.warning("重大問題:")
                for issue in health_status["critical_issues"]:
                    logger.info(f"- {issue}")
            
            if health_status["recommendations"]:
                logger.info("推奨事項:")
                for rec in health_status["recommendations"]:
                    logger.info(f"- {rec}")
            
            # 結果保存
            checker.save_health_status(result)
        else:
            logger.error(f"エラー: {result.get('error', '不明なエラー')}")
    
    elif args.weekly_check:
        # 週次自動チェック
        if checker.should_run_weekly_test() or args.force:
            logger.info("週次SSDヘルスチェック実行...")
            result = checker.run_comprehensive_test()
            checker.save_health_status(result)
            logger.info(f"週次チェック完了: {'成功' if result['success'] else '失敗'}")
        else:
            logger.info("週次チェック: 実行不要（1週間未経過）")
    
    elif args.status:
        # 現在状態表示
        status = checker.get_latest_health_status()
        if status:
            logger.info(f"最新健康状態 ({status.get('timestamp', 'N/A')}):")
            health = status.get("health_status", {})
            logger.info(f"ステータス: {health.get('overall_status', 'unknown')}")
            logger.info(f"健康スコア: {health.get('health_score', 0)}/100")
            logger.info(f"次回チェック予定: {health.get('next_check_due', 'N/A')}")
        else:
            logger.info("健康状態データなし - テスト実行が必要")
    
    else:
        # デフォルト: 現在状態表示
        status = checker.get_latest_health_status()
        if status:
            health = status.get("health_status", {})
            logger.info(f"M.2 SSD健康状態: {health.get('overall_status', 'unknown')} (スコア: {health.get('health_score', 0)}/100)")
        else:
            logger.info("M.2 SSD健康状態: データなし")

if __name__ == "__main__":
    main()