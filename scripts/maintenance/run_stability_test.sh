#!/bin/bash

# Raspberry Pi Dashboard 安定性テスト実行スクリプト
# 使用方法: ./run_stability_test.sh [hours] [interval]

# デフォルト設定
HOURS=${1:-24}
INTERVAL=${2:-60}
DASHBOARD_URL="http://localhost:5000"

echo "🍓 Raspberry Pi Dashboard 安定性テスト開始"
echo "⏰ テスト時間: ${HOURS}時間"
echo "🔄 チェック間隔: ${INTERVAL}秒"
echo "🌐 ダッシュボードURL: ${DASHBOARD_URL}"
echo

# 仮想環境の確認
if [ ! -d "venv" ]; then
    echo "❌ 仮想環境が見つかりません。setup_project.shを先に実行してください。"
    exit 1
fi

# 仮想環境をアクティベート
source venv/bin/activate

# 必要なパッケージの確認・インストール
echo "📦 依存関係を確認中..."
pip install -q psutil requests

# ダッシュボードサービスの確認
echo "🔍 ダッシュボードサービスの状態を確認中..."
if ! curl -s "${DASHBOARD_URL}/health" > /dev/null; then
    echo "⚠️  ダッシュボードサービスが応答しません。サービスを開始してください："
    echo "   sudo systemctl start raspberry-pi-dashboard"
    echo "   または: python3 app.py"
    exit 1
fi

echo "✅ ダッシュボードサービスが稼働中"

# ログディレクトリの作成
mkdir -p logs/stability

# 安定性テストを開始
echo "🚀 安定性テストを開始します..."
echo "📊 リアルタイムログ: tail -f logs/stability/dashboard.log"
echo "⏹️  テスト停止: Ctrl+C"
echo

# テスト実行
python3 stability_test.py \
    --duration "${HOURS}" \
    --interval "${INTERVAL}" \
    --url "${DASHBOARD_URL}" \
    --memory-threshold 100 \
    --cpu-threshold 85.0 \
    --memory-usage-threshold 90.0

echo
echo "📋 テスト完了。レポートは logs/stability/ に保存されました。"
echo "🔍 詳細確認: ls -la logs/stability/"