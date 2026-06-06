# Raspberry Pi Dashboard - CLAUDE.md

Raspberry Pi 5 上で動作する室内環境センサー + Google Calendar 統合ダッシュボード。
Flask API サーバーと PyQt5 デスクトップ UI の2プロセス構成。

## よく使うコマンド

```bash
# Pi に SSH 接続
ssh [username]@raspberrypi.local

# サービス再起動（APIとUIは別サービス）
sudo systemctl restart raspberry-pi-api-server
sudo systemctl restart raspberry-pi-native-dashboard

# ログ確認
journalctl -u raspberry-pi-api-server -f --no-pager
journalctl -u raspberry-pi-native-dashboard -f --no-pager

# テスト（プロジェクトルートから実行）
python3 -m pytest raspberry-pi-dashboard/tests/ -v

# カレンダーキャッシュ削除（表示がおかしい時）
python3 -c "
from pathlib import Path
for p in list(Path('raspberry-pi-dashboard/cache/personal_events').glob('*.json')) + \
         list(Path('raspberry-pi-dashboard/cache/calendar_priority').glob('*.json')):
    p.unlink(); print('deleted:', p.name)
"
```

## 重要な設計

**2プロセス構成を忘れない**  
`raspberry-pi-api-server`（Flask）と `raspberry-pi-native-dashboard`（PyQt5）は独立したプロセス。APIサーバーを再起動してもUIには反映されない。

**カレンダーキャッシュ優先システム**（`calendar_cache_priority.py`）  
Google Calendar API が失敗・タイムアウトしても既存キャッシュで表示継続する設計。`personal_events/` と `calendar_priority/` の2層キャッシュ。API が0件を返しても既存キャッシュを上書きしない保護あり。表示がおかしい時はキャッシュ削除 → サービス再起動が有効。

**センサーデータは cron 経由**  
`scripts/monitoring_collector.py` が5分間隔で cron 実行 → `static/data/metrics.json` 更新。Flask API はこのファイルを読むだけなのでリアルタイムではない。

**設定は .env で管理**  
`.env` がないとサービスが起動しない。`.env.example` を参照して作成。`credentials/` 以下の認証ファイルも git 管理外なので環境構築時に手動配置が必要。

## ハマりポイント

- **テストの一部はPi実機必須**: SHT35（I2C）・MH-Z19E（UART）を使うテストは実機なしでは失敗する
- **Google Calendar トークン期限切れ**: `credentials/token.json` の有効期限切れで Calendar が表示されなくなる。`calendar_auth.py` で再認証
- **ハードコードパスに注意**: 古いファイルに `/path/to/raspberry-pi-dashboard` が残っている場合がある。`Path(__file__).parent` 系の相対パスに直す
- **weather_logic.py の位置情報**: デフォルトは渋谷区固定。変更は `.env` の `WEATHER_LATITUDE` / `WEATHER_LONGITUDE` / `WEATHER_LOCATION_NAME` で行う

## ディレクトリ構成のポイント

```
raspberry-pi-dashboard/
├── web_apps/          # Flask Blueprint（APIエンドポイント群）
├── ui/                # PyQt5 UIコンポーネント
├── logic/             # ビジネスロジック（UIから切り離し済み）
├── humidifier_control/ # Tapoスマートプラグ制御（独立モジュール）
├── scripts/maintenance/ # 運用スクリプト（ヘルスチェック等）
├── credentials/       # 認証情報（git管理外・手動配置）
├── cache/             # 実行時キャッシュ（git管理外）
└── local/             # 環境固有スクリプト（git管理外）
```

## ブランチ運用

main への直接コミットは避け、feature ブランチで作業して PR でマージ。
