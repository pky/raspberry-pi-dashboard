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

## 作業の進め方

**変更は最小差分で行う**  
目的外のファイルを巻き込まない。既存の実装を確認してから手を入れる。表面的なパッチより根本原因の修正を優先する。

**非自明な変更は計画を先に書く**  
複数ファイルをまたぐ変更、設計に影響する変更は、着手前に何をどう変えるか一言まとめてから実装する。

**完了前に検証結果を示す**  
「動くはず」で完了扱いしない。サービス再起動後のログ確認、テスト実行結果、または動作確認の根拠を示してから完了とする。

**差分を一度レビューしてから報告する**  
`git diff` で変更内容を確認し、意図しない変更が混入していないかチェックしてから報告する。

## コミット禁止ファイル

以下は絶対にコミットしない：

- `.env`（環境変数・API キー）
- `credentials/` 以下のすべてのファイル（`token.json`、OAuth クライアント情報など）
- `cache/` 以下の実行時キャッシュ
- `local/` 以下の環境固有スクリプト

コード・ドキュメント・ログ例にも実データ（実際のカレンダーイベント名、センサー値、住所など）や個人情報を書かない。

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

## 再発防止メモ

問題が発生したとき・ユーザーから指摘を受けたときは、同じミスを繰り返さないためのルールをここに追記する。

- **`config.py` 変更後は cron スクリプトを絶対パスで動作確認する**: cron は作業ディレクトリが不定のため、`config.py` の `env_file` は `Path(__file__).parent / '.env'` の絶対パスで指定する。確認は `/tmp` など別ディレクトリから `python3 /path/to/script.py` で行う。
