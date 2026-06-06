#!/bin/bash

echo "🔄 Raspberry Pi Dashboard サービス再起動"
echo "========================================"

# 現在のサービス状態を確認
echo "📊 現在の状態確認:"
sudo systemctl status raspberry-pi-dashboard --no-pager -l

echo ""
echo "🛑 サービス停止中..."
sudo systemctl stop raspberry-pi-dashboard

echo "⏳ 3秒待機..."
sleep 3

echo "🚀 サービス開始中..."
sudo systemctl start raspberry-pi-dashboard

echo "⏳ 5秒待機（起動完了まで）..."
sleep 5

echo ""
echo "📊 新しい状態確認:"
sudo systemctl status raspberry-pi-dashboard --no-pager -l

echo ""
echo "🔍 ヘルスチェック:"
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ ダッシュボード: 正常稼働"
    curl -s http://localhost:5000/health | head -3
else
    echo "❌ ダッシュボード: 応答なし"
fi

echo ""
echo "🌐 アクセス可能なURL:"
echo "   メインダッシュボード: http://raspberrypi.local:5000/"
echo "   テスト結果（旧版）: http://raspberrypi.local:5000/test"
echo "   テスト結果（新版）: http://raspberrypi.local:5000/test-simple"

echo ""
echo "✅ サービス再起動完了！"