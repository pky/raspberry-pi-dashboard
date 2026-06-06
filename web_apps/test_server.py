#!/usr/bin/env python3
"""
テスト起動用スクリプト - test_server.py
FINAL_IMPLEMENTATION_PLAN_V2.md Day2-3最終実装

新実装Flaskアプリ（5001ポート）を起動し、既存app.py（5000ポート）との
並行テスト・検証を可能にするスクリプト
"""

import sys
import time
import signal
import requests
from pathlib import Path
from typing import Dict, Any

# プロジェクトルートをPythonパスに追加
sys.path.append(str(Path(__file__).parent))

# 新実装のインポート
from web_apps.main_app import create_app
from logging_system import get_logger

class TestServerManager:
    """テストサーバー管理クラス"""
    
    def __init__(self):
        self.logger = get_logger("test_server_manager")
        self.app = None
        self.server_info = {
            "existing_app": {"port": 5000, "status": "unknown"},
            "new_app": {"port": 5001, "status": "unknown"}
        }
    
    def check_existing_server(self) -> bool:
        """
        既存app.py（5000ポート）の稼働確認
        """
        try:
            response = requests.get("http://localhost:5000/api/sensor", timeout=5)
            if response.status_code == 200:
                self.server_info["existing_app"]["status"] = "running"
                self.logger.success("既存app.py（5000ポート）稼働確認")
                return True
            else:
                self.server_info["existing_app"]["status"] = "error"
                return False
                
        except requests.exceptions.RequestException as e:
            self.server_info["existing_app"]["status"] = "stopped"
            self.logger.warning("既存app.py（5000ポート）接続失敗", error=str(e))
            return False
    
    def create_test_app(self) -> Any:
        """
        新実装テストアプリ作成
        """
        try:
            self.app = create_app()
            self.server_info["new_app"]["status"] = "created"
            self.logger.success("新実装テストアプリ作成完了")
            return self.app
            
        except Exception as e:
            self.server_info["new_app"]["status"] = "error"
            self.logger.error("新実装テストアプリ作成失敗", error=str(e))
            raise
    
    def run_parallel_test(self):
        """
        並行テスト実行
        既存app.py（5000）と新実装（5001）の並行稼働テスト
        """
        print("🚀 Raspberry Pi Dashboard 段階的実装テスト開始")
        print("=" * 60)
        
        # 既存サーバー確認
        existing_running = self.check_existing_server()
        
        if existing_running:
            print("✅ 既存app.py (5000ポート): 稼働中")
            print("📊 既存API: http://localhost:5000/api/sensor")
        else:
            print("⚠️  既存app.py (5000ポート): 停止中または接続不可")
            print("💡 sudo systemctl start raspberry-pi-api-server で起動してください")
        
        print("-" * 60)
        
        # 新実装起動
        try:
            app = self.create_test_app()
            
            print("🆕 新実装app (5001ポート): 起動準備完了")
            print("🔍 ヘルスチェック: http://localhost:5001/health")
            print("📈 移行ステータス: http://localhost:5001/migration-status")
            print("📋 ダッシュボード: http://localhost:5001/")
            
            if existing_running:
                print("⚡ 並行稼働モード: 既存(5000) + 新実装(5001)")
            else:
                print("🔧 単体テストモード: 新実装(5001)のみ")
            
            print("-" * 60)
            print("📝 テスト項目:")
            print("  1. ヘルスチェック確認")
            print("  2. ダッシュボード表示確認")
            print("  3. 移行ステータス確認")
            print("  4. エラーハンドリング確認")
            
            if existing_running:
                print("  5. 既存APIとの互換性確認")
            
            print("=" * 60)
            print("🛑 停止: Ctrl+C")
            print("💾 実装ログ: logs/内を確認")
            print("📚 実装計画: docs/Structural_Improvement/FINAL_IMPLEMENTATION_PLAN_V2.md")
            
            # Graceful shutdown設定
            def signal_handler(sig, frame):
                print("\n🛑 テストサーバー停止中...")
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            
            # Flaskアプリ起動
            app.run(
                host='0.0.0.0',
                port=5001,
                debug=True,
                use_reloader=False  # テストモードでは無効
            )
            
        except Exception as e:
            self.logger.error("並行テスト実行エラー", error=str(e))
            print(f"❌ テスト実行エラー: {str(e)}")
            raise

def run_health_check() -> Dict[str, Any]:
    """
    簡易ヘルスチェック実行
    """
    logger = get_logger("health_check")
    results = {}
    
    # 既存app.py確認
    try:
        response = requests.get("http://localhost:5000/api/sensor", timeout=3)
        results["existing_app"] = {
            "status": "running" if response.status_code == 200 else "error",
            "port": 5000
        }
    except:
        results["existing_app"] = {"status": "stopped", "port": 5000}
    
    # 新実装確認（起動されている場合）
    try:
        response = requests.get("http://localhost:5001/health", timeout=3)
        results["new_app"] = {
            "status": "running" if response.status_code == 200 else "error",
            "port": 5001
        }
    except:
        results["new_app"] = {"status": "stopped", "port": 5001}
    
    return results

def main():
    """
    メイン実行関数
    """
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # ヘルスチェックのみ実行
        results = run_health_check()
        print("🏥 サーバーヘルスチェック結果:")
        for server, info in results.items():
            status_icon = "✅" if info["status"] == "running" else "❌"
            print(f"  {status_icon} {server} (:{info['port']}): {info['status']}")
        return
    
    # 通常の並行テスト実行
    test_manager = TestServerManager()
    test_manager.run_parallel_test()

if __name__ == "__main__":
    main()