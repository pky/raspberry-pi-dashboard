#!/usr/bin/env python3
"""
CO2センサー監視・自動復旧システム
MH-Z19E CO2センサーの動作状況を監視し、問題を検出して自動復旧を行う

機能:
- CO2ログファイルの更新状況監視
- センサー通信テスト
- 固定値検出（センサー停止判定）
- 自動復旧処理（ロガー再起動）
- アラート生成・ログ記録
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from mhz19e import MHZ19E
except ImportError:
    print("WARNING: mhz19e module not available")
    MHZ19E = None

class CO2SensorMonitor:
    def __init__(self, log_dir="logs", alert_threshold_minutes=30):
        self.project_root = project_root
        self.log_dir = project_root / log_dir
        self.alert_threshold_minutes = alert_threshold_minutes
        self.monitor_log_path = self.log_dir / "co2_sensor_monitor.log"
        
        # ディレクトリ作成
        self.log_dir.mkdir(exist_ok=True)
    
    def log_message(self, level, message):
        """監視ログメッセージ記録"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        
        try:
            with open(self.monitor_log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry + '\n')
        except Exception as e:
            print(f"ERROR: ログ書き込み失敗 - {e}")
    
    def get_latest_co2_log_file(self):
        """最新のCO2ログファイルを取得"""
        today = datetime.now().strftime('%Y-%m-%d')
        co2_log_path = self.log_dir / f"co2_data_{today}.json"
        return co2_log_path
    
    def check_log_freshness(self):
        """CO2ログファイルの更新状況確認"""
        co2_log_path = self.get_latest_co2_log_file()
        
        if not co2_log_path.exists():
            self.log_message("WARNING", f"CO2ログファイルが存在しません: {co2_log_path}")
            return False, f"ログファイル不存在: {co2_log_path.name}"
        
        try:
            # ファイル最終更新時刻確認
            file_mtime = datetime.fromtimestamp(co2_log_path.stat().st_mtime)
            current_time = datetime.now()
            time_diff = current_time - file_mtime
            
            # JSON内容確認
            with open(co2_log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data or len(data) == 0:
                self.log_message("WARNING", "CO2ログファイルが空です")
                return False, "ログファイル空"
            
            # 最新エントリのタイムスタンプ確認
            latest_entry = data[-1]
            latest_time = datetime.fromisoformat(latest_entry['timestamp'].replace('Z', '+00:00'))
            data_age = current_time - latest_time
            
            if data_age.total_seconds() > self.alert_threshold_minutes * 60:
                self.log_message("WARNING", f"CO2データが古すぎます: {data_age.total_seconds() / 60:.1f}分前")
                return False, f"データ古い: {data_age.total_seconds() / 60:.1f}分"
            
            self.log_message("INFO", f"CO2ログ正常: 最新データ{data_age.total_seconds() / 60:.1f}分前")
            return True, latest_entry
            
        except Exception as e:
            self.log_message("ERROR", f"CO2ログファイル読み込みエラー: {e}")
            return False, f"読み込みエラー: {e}"
    
    def check_sensor_hardware(self):
        """センサーハードウェア直接テスト"""
        if not MHZ19E:
            self.log_message("WARNING", "MH-Z19E モジュールが利用できません")
            return False, "モジュール不可"
        
        try:
            sensor = MHZ19E(port='/dev/serial0', timeout=5)
            co2_ppm = sensor.read_co2()
            sensor.close()
            
            if co2_ppm is None or co2_ppm <= 0:
                self.log_message("ERROR", f"センサーから無効な値: {co2_ppm}")
                return False, f"無効値: {co2_ppm}"
            
            if co2_ppm < 300 or co2_ppm > 5000:
                self.log_message("WARNING", f"センサー値が範囲外: {co2_ppm}ppm")
                return False, f"範囲外: {co2_ppm}ppm"
            
            self.log_message("INFO", f"センサーハードウェア正常: {co2_ppm}ppm")
            return True, co2_ppm
            
        except Exception as e:
            self.log_message("ERROR", f"センサーハードウェアテスト失敗: {e}")
            return False, f"ハードウェアエラー: {e}"
    
    def check_stuck_values(self, history_hours=2):
        """固定値検出（センサー停止判定）"""
        co2_log_path = self.get_latest_co2_log_file()
        
        if not co2_log_path.exists():
            return False, "ログファイル不存在"
        
        try:
            with open(co2_log_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if len(data) < 5:  # 最低5件のデータが必要
                return True, "データ不足のためスキップ"
            
            # 過去2時間分のデータを確認
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(hours=history_hours)
            
            recent_data = []
            for entry in data:
                try:
                    entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                    if entry_time >= cutoff_time and not entry.get('simulation', False):
                        recent_data.append(entry)
                except:
                    continue
            
            if len(recent_data) < 3:
                return True, f"過去{history_hours}時間のデータ不足"
            
            # 同じ値が連続している回数を確認
            co2_values = [entry['co2_ppm'] for entry in recent_data]
            if len(set(co2_values)) == 1 and len(co2_values) >= 3:
                stuck_value = co2_values[0]
                self.log_message("WARNING", f"CO2値が固定: {stuck_value}ppm ({len(co2_values)}回連続)")
                return False, f"固定値: {stuck_value}ppm"
            
            return True, f"正常変動: {min(co2_values)}-{max(co2_values)}ppm"
            
        except Exception as e:
            self.log_message("ERROR", f"固定値チェックエラー: {e}")
            return False, f"チェックエラー: {e}"
    
    def restart_co2_logger(self):
        """CO2ロガーサービス再起動"""
        try:
            self.log_message("INFO", "CO2ロガー手動実行を開始...")
            
            # co2_logger.py を --collect オプションで実行
            result = subprocess.run([
                'python3', str(self.project_root / 'co2_logger.py'), '--collect'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.log_message("INFO", "CO2ロガー手動実行成功")
                return True, "手動実行成功"
            else:
                self.log_message("ERROR", f"CO2ロガー手動実行失敗: {result.stderr}")
                return False, f"実行失敗: {result.stderr}"
                
        except Exception as e:
            self.log_message("ERROR", f"CO2ロガー再起動エラー: {e}")
            return False, f"再起動エラー: {e}"
    
    def run_monitoring_cycle(self):
        """監視サイクル実行"""
        self.log_message("INFO", "=== CO2センサー監視サイクル開始 ===")
        
        issues_found = []
        recovery_actions = []
        
        # 1. ログファイル更新状況確認
        log_ok, log_info = self.check_log_freshness()
        if not log_ok:
            issues_found.append(f"ログ更新問題: {log_info}")
        
        # 2. センサーハードウェア確認
        hw_ok, hw_info = self.check_sensor_hardware()
        if not hw_ok:
            issues_found.append(f"ハードウェア問題: {hw_info}")
        
        # 3. 固定値検出
        stuck_ok, stuck_info = self.check_stuck_values()
        if not stuck_ok:
            issues_found.append(f"固定値問題: {stuck_info}")
        
        # 問題が検出された場合の自動復旧
        if issues_found:
            self.log_message("WARNING", f"問題検出: {len(issues_found)}件")
            for issue in issues_found:
                self.log_message("WARNING", f"  - {issue}")
            
            # CO2ロガー再起動を試行
            restart_ok, restart_info = self.restart_co2_logger()
            if restart_ok:
                recovery_actions.append(f"ロガー再起動: {restart_info}")
                self.log_message("INFO", "自動復旧処理完了")
            else:
                self.log_message("ERROR", f"自動復旧失敗: {restart_info}")
        else:
            self.log_message("INFO", "CO2センサーシステム正常動作中")
        
        # 結果サマリー
        result = {
            "timestamp": datetime.now().isoformat(),
            "status": "healthy" if not issues_found else "issues_detected",
            "issues_found": issues_found,
            "recovery_actions": recovery_actions,
            "log_status": log_info if log_ok else f"ERROR: {log_info}",
            "hardware_status": hw_info if hw_ok else f"ERROR: {hw_info}",
            "stuck_check": stuck_info if stuck_ok else f"WARNING: {stuck_info}"
        }
        
        self.log_message("INFO", "=== CO2センサー監視サイクル完了 ===")
        return result

def main():
    """メイン処理"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("CO2センサー監視・自動復旧システム")
        print("使用方法: python3 co2_sensor_monitor.py")
        print("オプション: --help")
        return
    
    monitor = CO2SensorMonitor()
    result = monitor.run_monitoring_cycle()
    
    # JSON形式で結果出力（system_monitor.htmlからの参照用）
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 問題があった場合は終了コード1で終了
    sys.exit(0 if result["status"] == "healthy" else 1)

if __name__ == "__main__":
    main()