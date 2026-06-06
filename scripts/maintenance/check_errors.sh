#!/bin/bash

echo "🔍 Raspberry Pi Dashboard エラー診断"
echo "===================================="

echo "1. サービス状態確認:"
sudo systemctl status raspberry-pi-dashboard --no-pager -l | tail -10

echo ""
echo "2. アプリケーションログ確認:"
if [ -f "logs/dashboard.log" ]; then
    echo "最新のログ (直近20行):"
    tail -20 logs/dashboard.log
else
    echo "❌ dashboard.log が見つかりません"
fi

echo ""
echo "3. エラーログ確認:"
if [ -f "logs/dashboard_error.log" ]; then
    echo "最新のエラー (直近10行):"
    tail -10 logs/dashboard_error.log
else
    echo "❌ dashboard_error.log が見つかりません"
fi

echo ""
echo "4. システムログ確認:"
echo "systemd ログ (直近10行):"
sudo journalctl -u raspberry-pi-dashboard -n 10 --no-pager

echo ""
echo "5. 手動API テスト:"
echo "ヘルスチェック:"
curl -v http://localhost:5000/health 2>&1 | head -10

echo ""
echo "テスト結果API:"
curl -v http://localhost:5000/api/test/results 2>&1 | head -10

echo ""
echo "6. Python エラー確認:"
echo "手動でアプリケーション起動テスト:"
cd ~/projects/raspberry-pi-dashboard
source venv/bin/activate
timeout 5s python3 -c "
try:
    from app import app
    print('✅ アプリケーションインポート成功')
    from test_api import register_test_routes
    print('✅ test_api インポート成功')
    register_test_routes(app)
    print('✅ テストルート登録成功')
except Exception as e:
    print(f'❌ エラー: {e}')
    import traceback
    traceback.print_exc()
" 2>&1

echo ""
echo "7. ファイル存在確認:"
echo "重要なファイルの存在確認:"
for file in app.py test_api.py error_handler.py logging_config.py system_monitor.py; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file が見つかりません"
    fi
done

echo ""
echo "ログディレクトリ:"
ls -la logs/ 2>/dev/null || echo "❌ logs ディレクトリが見つかりません"

echo ""
echo "テストデータ:"
ls -la reports/ 2>/dev/null || echo "❌ reports ディレクトリが見つかりません"