# コンポーネント詳細設計

## バックエンドコンポーネント

### 1. Flaskアプリケーション (`app.py`)
- REST API エンドポイント提供（15個）
- CORS設定と統合エラーハンドリング
- パフォーマンス監視とログ統合
- 管理画面とテストルート統合

### 2. ネイティブダッシュボード (`dashboard.py`)
- PyQt5ベースのメインGUI
- マルチスレッド設計（センサー・カレンダー・UI分離）
- Material Iconsフォント統合
- リアルタイム状態表示

### 3. センサーモジュール (`sensor.py`)
- SHT35センサーからの温湿度取得（GPIO4）
- MH-Z19E CO2センサーからの濃度取得（UART GPIO14/15）
- 不快度指数・CO2レベル判定計算
- シミュレーション対応・エラーハンドリング・ログ統合

### 4. カレンダーデータ処理 (`calendar_data.py`)
- Google Calendar API認証・トークン自動更新
- 個人予定智能キャッシュ（24時間、空月対応）
- 月別データ取得とAPIレート制限回避

### 5. 祝日システム (`holiday_cache.py`)
- 内閣府公式データ自動取得
- 年次キャッシュ更新（3月1日自動実行）
- 複数年一括管理

### 6. 設定モジュール (`config.py`)
- 環境変数管理・本番/開発環境分離
- GPIO・API・ログ設定統合
- 設定値検証機能

### 7. 監視・テストシステム
- **API監視** (`monitoring/monitor_api.py`): 5分間隔ヘルスチェック
- **安定性テスト** (`monitoring/stability_test.py`): 長時間動作検証
- **統合テストAPI** (`test_api.py`): 管理画面連携

## フロントエンドコンポーネント

### 1. ネイティブGUI (PyQt5)
- フルスクリーン表示・タッチ最適化
- マテリアルデザイン準拠
- リアルタイム状態インジケーター
- 非同期データ更新

### 2. Webダッシュボード
- **メインHTML** (`templates/index.html`): レスポンシブレイアウト
- **管理画面** (`system_monitor.html`): テスト実行・監視機能
- **スタイルシート** (`static/css/style.css`): タッチパネル用UI
- **JavaScript** (`static/js/app.js`): API通信・DOM操作

## システム運用コンポーネント

### 1. systemdサービス
- **`raspberry-pi-api-server.service`**: Flask API自動起動・再起動
- **`raspberry-pi-native-dashboard.service`**: ネイティブGUI自動起動

### 2. cron監視
- **5分間隔**: API監視・自動再起動
- **毎日2:00**: 基本機能テスト実行

### 3. ログ管理
- **logrotate**: 3日ローテーション・自動圧縮
- **統一ログファイル**: 13個のログカテゴリ管理

### 4. バックアップ・復旧
- **`complete_backup_system.sh`**: Mac+RaspberryPi完全バックアップ
- **`complete_emergency_recovery.sh`**: 対話式復旧システム