# システムアーキテクチャ設計

## システム構成図

### 🏗️ **統一ログベースアーキテクチャ (2025年8月21日実装完了)**

```
[センサーデータ収集] → [APIサーバー経由] → [統一JSONログ] → [全クライアント統一読み取り]
        ↓                    ↓                 ↓                    ↓
[DHT22 + MH-Z19E] → [Flask APIサーバー] → [monitoring_collector.py] → [static/data/metrics.json]
        ↓                    ↓                 ↓                            ↓
[GPIO4 + UART] → [/api/sensor] → [HTTP取得] → [5分間隔cron実行] → [Web監視グラフ]
                                                                            ↓
                                                                    [システム監視グラフ]
                                                                            ↓
                                                                     [PyQt5 Dashboard]
                                                                            ↓
                                                                   [将来のモバイルアプリ]
```

**統一データアクセス原則 (実装完了)**:
- **Single Source of Truth**: `static/data/metrics.json` (実測値確実取得)
- **実測値保証**: monitoring_collector.py → Flask API → センサー実測値取得 + 自動復旧 + DHT22フォールバック
- **完全統一**: Web監視グラフ・システム監視グラフ・PyQt5 Dashboardが同じJSONファイル読み取り
- **自動復旧**: APIタイムアウト時自動再起動機能
- **リアルタイム性**: 5分間隔更新・2分間隔クライアント読み取り
- **拡張性**: 新しいクライアント追加時もJSONファイル読み取りのみ

**注記**: PyQt5 DashboardはJSONファイル読み取り実装済み（統一アーキテクチャ完成）

### 📊 **データフロー詳細構成**

```
[物理センサー] → [Flask APIサーバー] → [monitoring_collector] → [JSONファイル] → [表示クライアント]
        ↓               ↓                    ↓                 ↓                ↓
[DHT22温湿度] → [/api/sensor取得] → [HTTP localhost:5000] → [metrics.json] → [Web監視グラフ]
[MH-Z19E CO2] → [実測値27°C,64%] → [urllib.request] → [実測値保存] → [システム監視]
        ↓               ↓                    ↓                 ↓                ↓
[GPIO4+UART] → [タイムアウト回避] → [cron */5分実行] → [7日自動削除] → [Dashboard]
```

### 🔄 **システム運用構成**

```
[タッチパネル] ← 直接実行 → [PyQt5 Native GUI] ← JSONファイル → [monitoring_collector]
                                                              ↓
              ← HTTP → [Chromium Browser] ← Web → [Flask Server] → [Google Calendar API]
                                                              ↓            ↓
[RaspberryPi5] → [SHT35センサー] ← GPIO4 ← [Flask Server] → [キャッシュシステム] → [祝日・個人予定]
     ↓         → [MH-Z19E CO2] ← UART ←        ↓
[systemd監視] → [自動再起動] ← [cron監視] ← [ヘルスチェック]
     ↓
[logrotate] → [ログ管理] → [バックアップシステム] → [Git + tar 復旧]
```

## 技術スタック

- **OS**: Raspberry Pi OS (64-bit)
- **バックエンド**: Python 3.11 + Flask + Flask-CORS
- **ネイティブGUI**: PyQt5 + QThread (メインインターフェース)
- **Web GUI**: HTML5 + CSS3 + バニラJavaScript (管理用)
- **システム監視**: systemd + cron + logrotate
- **センサー**: DHT22（GPIO4経由）+ MH-Z19E CO2（UART GPIO14/15経由、実測値取得対応）
- **API**: Google Calendar API v3 + 日本祝日API
- **キャッシュ**: JSON + 24時間自動更新
- **バックアップ**: Git tag + tar.gz 二重化

## M.2 SSD 超高性能システム構成

### ストレージアーキテクチャ
```
Boot Partition (microSD): /boot/firmware - 安全性重視
Root System (M.2 SSD): / - 超高性能実現
```

### 性能指標
- **PiBenchmarks**: 50,252 (microSD比25.4倍向上)
- **HDParm Read**: 782.80 MB/s (8.7倍向上)
- **4k Random Write**: 90,220 IOPS (467.6倍向上)

### 最適化設定
**カーネルパラメーター (`/boot/firmware/cmdline.txt`)**:
```
nvme_core.default_ps_max_latency_us=0 pcie_aspm=off pcie_port_pm=off 
pci=pcie_bus_perf nvme_core.io_queue_depth=2 nvme_core.poll_queues=1
```

**PCIe設定 (`/boot/firmware/config.txt`)**:
```
dtparam=pciex1_gen=3
dtparam=pciex1
```

## Google Calendar サービスアカウント認証

### 認証アーキテクチャ
- **旧方式**: OAuth認証 (手動更新・7日制限)
- **新方式**: サービスアカウント認証 (24時間無人運用)

### セキュリティ設計
- **秘密鍵**: `credentials/service-account-key.json` (600権限)
- **権限**: Calendar読み取り専用
- **監視**: 認証状態継続監視・自動復旧

## ハイブリッドUI構成

### PyQt5 ネイティブGUI
- **表示**: フルスクリーン・タッチ最適化
- **データ**: 2分間隔自動更新（JSONファイル読み取り）
- **スレッド**: UI/データ/センサー分離

### Flask Web UI
- **機能**: 管理画面・テスト実行
- **アクセス**: ブラウザ経由
- **API**: RESTful設計 (15エンドポイント)

## センサー統合システム

### DHT22 温湿度センサー
- **接続**: GPIO4
- **データ**: 温度・湿度・不快度指数
- **更新**: 5分間隔（monitoring_collector経由）
- **安定性向上**: 部分取得対応・3回試行・フォールバック機構（2025年8月実装完了）

### MH-Z19E CO2センサー
- **接続**: UART (GPIO14/15)
- **データ**: CO2濃度・4段階警告
- **通信**: 9600bps・CRC検証
- **更新**: 5分間隔（monitoring_collector経由）

### 🔧 **SHT35センサー安定性向上システム（2025年8月実装）**

**問題**: 湿度データが定期的にシミュレーション値45%になる現象

**根本原因**:
- SHT35センサーの部分的読み取り失敗（温度または湿度の片方のみ取得失敗）
- 従来は両方揃わないと失敗扱い → 0値 → monitoring_collectorで45%シミュレーション値

**改善内容**:
```python
# 改善前: 両方必須
if temp is not None and humid is not None:
    # 成功処理
else:
    # 失敗 → 0値 → シミュレーション値

# 改善後: 部分取得対応
if temp is not None or humid is not None:
    # 有効な値のみ保存、無効な値のみ0値
    # 片方だけでも実測値として使用可能
```

**技術改善**:
- **試行回数**: 2回 → 3回に増加
- **部分取得対応**: 片方のみ取得成功でも有効値として保存
- **段階的処理**: 両方成功時即完了、片方成功時追加試行
- **フォールバック強化**: APIタイムアウト時のセンサー直読み安定化

**効果**:
- **Before**: 湿度45%シミュレーション値が頻発
- **After**: 実測値61.5%を安定取得（2025年8月21日テスト確認）
- **安定性**: 湿度シミュレーション値発生率大幅削減
- **信頼性**: APIサーバー障害時もセンサー実測値継続取得

## システム監視アーキテクチャ

### systemd自動化
- **API Server**: `raspberry-pi-api-server.service`
- **Native GUI**: `raspberry-pi-native-dashboard.service`
- **復旧**: 失敗時自動再起動

### cron監視スケジュール
- **5分間隔**: システム監視データ収集（JSONファイル直接出力）
- **毎日2:00**: 統合テスト実行
- **毎日3:00**: ログローテーション

## 統一ログベースシステム監視アーキテクチャ

### 🎯 **統一データアクセスアーキテクチャ**
- **データ収集**: `scripts/monitoring_collector.py` (5分間隔cron実行)
- **統一ストレージ**: `static/data/metrics.json` (Single Source of Truth)
- **Web監視グラフ**: Chart.js v3.9.1による直接JSON読み込み
- **PyQt5 Dashboard**: JSONファイル直接読み取り（2分間隔）
- **将来のモバイルアプリ**: 同じJSONファイル読み取り対応
- **データ保持**: 7日間・自動クリーンアップ

### 🏆 **統一アーキテクチャの利点**
- **設計美**: Single Source of Truth で統一性確保
- **パフォーマンス**: API呼び出しオーバーヘッドなし
- **信頼性**: APIサーバー障害時もデータアクセス可能
- **拡張性**: 新クライアント追加時も既存JSONファイル読み取り
- **独立性**: 各クライアントがサーバーに依存しない

### 監視項目
- **システム**: CPU使用率・メモリ使用率・CPU温度
- **センサー**: 室温・湿度・CO2濃度（実データ）
- **ストレージ**: ディスク使用量・使用率
- **ネットワーク**: 送受信データ量・稼働時間

### グラフ表示機能
- **時間範囲**: 1時間・6時間・12時間・24時間選択
- **リアルタイム**: 5分間隔自動更新
- **データ整合性**: 原子的ファイル書き込み保証

### バックアップシステム
- **完全バックアップ**: Git + tar.gz
- **対象**: コード・設定・ログ・認証情報
- **復旧**: 対話式緊急復旧システム

## 📋 ログファイル管理システム (2025年8月最適化完了)

### 🎯 **統一ログ管理アーキテクチャ**

**Single Source of Truth (統一監視データ)**:
```
static/data/metrics.json (92KB)
├── 204データポイント (7日間保持)
├── 5分間隔自動収集 (monitoring_collector.py)
├── Chart.js直接読み込み (Web)
├── PyQt5直接読み込み (Dashboard)
└── 7日自動クリーンアップ (内部管理)
```

### 📁 **アクティブログファイル構成**

**システム運用ログ (logrotate 3日管理)**:
```
logs/
├── dashboard.log              (2.3MB) - PyQt5 GUI運用ログ
├── dashboard_error.log        (85KB)  - PyQt5エラーログ
├── dashboard_performance.log  (366B)  - パフォーマンス計測
├── sensor.log                 (648KB) - センサー初期化・動作ログ
├── collector_cron.log         (172KB) - monitoring_collector実行ログ
└── cache_cron.log            (11KB)  - キャッシュ更新ログ
```

**センサーデータログ (logrotate 3日管理)**:
```
logs/
├── co2_data_2025-08.db       (44KB)  - CO2月次データベース
├── temp_humidity_data_2025-08.db (36KB) - 温湿度月次データベース
├── co2_data_2025-08-21.json  (日次記録) - CO2日次JSONログ
└── temp_humidity_data_2025-08-21.json - 温湿度日次JSONログ
```

**M.2 SSDベンチマークログ**:
```
logs/
├── m2_ssd_benchmark_*.log    (176B各) - SSD性能測定ログ
├── ssd_smart_history.json    - SMART履歴
└── ssd_health_status.json    - SSD健全性状態
```

### ✅ **最適化完了項目**

**削除された重複システム**:
- ❌ `sensor_collect_cron.log` (68KB) - API重複収集ログ削除
- ❌ 重複cron `curl api/sensor/collect` - 5分間隔重複削除
- ❌ `api_tests.log, calendar.log, flask_server.log` - 空ファイル削除

**統一された管理システム**:
- ✅ **metrics.json**: 内部7日クリーンアップ (logrotate除外)
- ✅ **運用ログ**: logrotate 3日ローテーション統一
- ✅ **データ収集**: monitoring_collector.py単一システム化

### 🔧 **ログローテーション設定**

**logrotate設定 (`logrotate-raspberry-pi-dashboard`)**:
```
# アクティブログファイル統一設定（1日1回・3日保存）
# metrics.jsonは内部クリーンアップ機能（7日）により自動管理
/path/to/raspberry-pi-dashboard/logs/dashboard.log
/path/to/raspberry-pi-dashboard/logs/dashboard_error.log
/path/to/raspberry-pi-dashboard/logs/dashboard_performance.log
/path/to/raspberry-pi-dashboard/logs/sensor.log
/path/to/raspberry-pi-dashboard/logs/collector_cron.log
/path/to/raspberry-pi-dashboard/logs/temp_humidity_data_*.json
/path/to/raspberry-pi-dashboard/logs/co2_data_*.json {
    daily
    missingok
    rotate 3
    compress
    delaycompress
    copytruncate
    notifempty
    create 0644 pi pi
}
```

**Cron監視スケジュール (最適化後)**:
```
# 統合データ収集（5分間隔）
*/5 * * * * cd /path/to/raspberry-pi-dashboard && python3 scripts/monitoring_collector.py >> /path/to/raspberry-pi-dashboard/logs/collector_cron.log 2>&1

# 日次システムテスト（午前2時）
0 2 * * * cd /path/to/raspberry-pi-dashboard && python3 monitoring/simple_api_test.py >> /path/to/raspberry-pi-dashboard/logs/daily_test_$(date +%Y%m%d).log 2>&1
```

### 📊 **ログ用途分類**

**デバッグ・運用管理**:
- `dashboard.log` - PyQt5 GUI動作状況・エラー追跡
- `sensor.log` - センサー初期化・動作確認
- `collector_cron.log` - 統合データ収集実行状況

**データアーカイブ**:
- `*.db` - 月次センサーデータベース（長期保存）
- `*_data_*.json` - 日次センサーログ（詳細記録）

**監視データ（リアルタイム）**:
- `static/data/metrics.json` - 統一監視データ（7日・全クライアント共通）