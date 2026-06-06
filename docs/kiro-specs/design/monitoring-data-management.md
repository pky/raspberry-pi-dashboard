# 監視データ管理システム設計書（JSONファイル+logrotate方式）

## 📋 概要

RaspberryPi Dashboard における監視グラフデータの管理システム詳細設計。JSONファイル方式によるChart.js統合と、logrotateによる1ヶ月ローテーション・自動クリーンアップを実現し、軽量かつ効率的な監視システムを構築する。

## 🎯 設計目標

- **軽量システム**: JSONファイル方式による高速読み込み
- **長期保存**: 1ヶ月間のグラフデータ保持（圧縮により実容量900KB）
- **自動管理**: logrotateによる完全自動ローテーション
- **リアルタイム表示**: Chart.js直接読み込みによる即座なグラフ更新

## 🏗️ アーキテクチャ設計

### システム構成図
```
┌─────────────────────────────────────────────────┐
│            JSONファイル監視システム                │
├─────────────────────────────────────────────────┤
│                                                 │
│  [monitoring_collector.py] → [metrics.json]     │
│         ↓                          ↓            │
│  [5分間隔データ収集] → [JSONファイル蓄積] → [Chart.js] │
│         ↓                          ↓            │
│  [logrotate] → [日次ローテーション] → [1ヶ月保持]    │
│                                                 │
└─────────────────────────────────────────────────┘
             ↓              ↓              ↓
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    現在データ    │ │   過去データ     │ │  センサーログ    │
│  metrics.json   │ │ metrics.json.N.gz│ │ co2_data_*.json │
│   (~100KB)      │ │   (~25KB各)      │ │temp_humidity_*  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### ファイル構成とローテーション
```
# グラフ表示用JSONファイル（メイン）
static/data/
├── metrics.json              # 現在データ（非圧縮・Chart.js直読み）
├── metrics.json.1            # 1日前（非圧縮・delaycompress）
├── metrics.json.2.gz         # 2日前以降（gzip圧縮）
├── metrics.json.3.gz         # ～30日保持（logrotate管理）
└── ...metrics.json.30.gz     # 30日後自動削除

# センサーログファイル（30日保持）
logs/
├── co2_data_2025-08-21.json     # 現在のCO2ログ
├── co2_data_2025-08-20.json.gz  # 過去のCO2ログ（圧縮）
├── temp_humidity_2025-08-21.json # 現在の温湿度ログ
└── temp_humidity_2025-08-20.json.gz # 過去の温湿度ログ（圧縮）
```

## 📊 データ管理仕様

### 1. JSONファイル監視データ収集

#### データ収集システム
- **実行間隔**: 5分間隔（cron設定）
- **収集スクリプト**: `scripts/monitoring_collector.py`
- **データソース**: ログファイル（CO2・温湿度）+ システムメトリクス
- **出力形式**: `static/data/metrics.json`（Chart.js直読み用）

#### データポイント構造
```json
{
  "timestamp": "2025-08-21T00:30:01.942954",
  "cpu_percent": 25.4,
  "memory_percent": 68.2,
  "cpu_temperature": 52.3,
  "room_temperature": 22.1,
  "humidity": 45.8,
  "co2_ppm": 420,
  "disk_used_gb": 8.3,
  "disk_percent": 3.5
}
```

### 2. logrotateによる自動ローテーション

#### 保存期間定義
- **JSONデータ**: 30日間保持（`rotate 30`）
- **センサーログ**: 30日間保持（`rotate 30`）
- **圧縮設定**: `compress + delaycompress`（1日前まで非圧縮）

#### ローテーション処理フロー
```
データ収集 → [metrics.json] → [日次ローテーション] → [30日後削除]
    ↓              ↓                ↓               
[5分間隔]    [Chart.js読み込み]   [gzip圧縮保存]
```

### 3. Chart.js統合仕様

#### JSONファイル直読み方式
- **データ取得**: `static/data/metrics.json`から直接読み込み
- **時間範囲フィルタ**: JavaScript側でリアルタイム処理
- **パフォーマンス**: HTTPキャッシュ無効化で最新データ保証
- **更新間隔**: 30秒間隔で自動更新

#### Chart.js実装
```javascript
// JSONファイル直読み
async loadData() {
    const response = await fetch(`/static/data/metrics.json?cache_bust=${Date.now()}`);
    this.currentData = await response.json();
    
    // 時間範囲フィルタリング（1h/6h/12h/24h）
    const filteredData = this.filterDataByRange(this.currentData, this.currentRange);
    this.createCharts(filteredData);
}
```

## 🔄 **ログシステム統合仕様 (2025年新導入)**

### 1. logrotate統合システム

#### システム統合概要
```yaml
# 統合前: Python RotatingFileHandler (独自実装)
logging_system_before:
  - Pythonライブラリ依存ログローテーション
  - アプリケーション側でのローテーション管理
  - ファイル別個別設定・管理コスト高

# 統合後: Linux logrotate (標準システム)
logging_system_after:
  - OS標準logrotateシステム統合
  - システムレベルでの統一ログ管理
  - ワイルドカード(*.log)で全ログ自動検出・管理
```

#### logrotate設定統合仕様
```bash
# /etc/logrotate.d/raspberry-pi-dashboard
/path/to/raspberry-pi-dashboard/logs/*.log {
    daily
    rotate 3
    compress
    delaycompress
    copytruncate
    missingok
    notifempty
    create 0644 pi pi
}
```

#### 構造化ログシステム実装
```python
# 旧: print文 (212個)
print(f"データ取得成功: {data}")

# 新: 構造化ログ
self.logger = get_logger("module_name")
self.logger.info("データ取得成功", data=data, status="success")
```

### 2. FileHandler統合仕様
```python
# logging_system.py - 統合後の実装
class LoggingSystem:
    def _setup_file_handler(self):
        # 旧: RotatingFileHandler(削除済み)
        # handler = logging.handlers.RotatingFileHandler(...)
        
        # 新: 標準FileHandler + logrotate統合
        handler = logging.FileHandler(
            self.logs_dir / f'{self.name}.log', 
            encoding='utf-8'
        )
        # logrotateがローテーション・管理を完全自動化
```

## 🔧 技術実装仕様

### 1. DatabaseManagerクラス設計

```python
class DatabaseManager:
    """SQLiteデータベース容量・ローテーション管理"""
    
    # 設定値
    retention_months = 6    # 保存期間（ヶ月）
    cleanup_months = 7      # 削除期間（ヶ月）
    
    # コア機能
    def get_current_month_db_path(db_type)     # 現在月DB取得
    def initialize_monthly_db(db_path, db_type) # 月次DB初期化
    def cleanup_old_databases()                # 古いDB削除
    def migrate_legacy_databases()             # レガシー移行
    def get_chart_data_sources(hours)          # Chart.js統合
```

### 2. レガシーデータベース移行仕様

#### 移行対象
- `logs/co2_data.db` → `logs/co2_data_YYYY-MM.db`（月別分割）
- `logs/temp_humidity_data.db` → `logs/temp_humidity_data_YYYY-MM.db`（月別分割）

#### 移行プロセス
1. **データ読み込み**: 既存単一DBから全レコード取得
2. **月別分類**: タイムスタンプから月を抽出・グループ化
3. **新DB作成**: 月ごとに新データベース作成・データ挿入
4. **バックアップ**: 元ファイルを `backup/` に移動
5. **検証**: データ整合性確認・エラーログ出力

### 3. APIエンドポイント仕様

#### `/api/database/status` (GET)
データベースファイル状態情報
```json
{
  "status": "success",
  "data": {
    "file_sizes_mb": {
      "co2": {"2024-12": 2.45, "2024-11": 8.32},
      "temp_humidity": {"2024-12": 1.87, "2024-11": 6.23}
    },
    "total_sizes_mb": {"co2": 10.77, "temp_humidity": 8.10},
    "grand_total_mb": 18.87,
    "available_months": {
      "co2": ["2024-12", "2024-11", "2024-10"],
      "temp_humidity": ["2024-12", "2024-11", "2024-10"]
    },
    "retention_months": 6,
    "cleanup_months": 7,
    "current_month": "2024-12"
  }
}
```

#### `/api/database/cleanup` (POST)
古いデータベースファイル手動クリーンアップ
```json
{
  "status": "success", 
  "data": {
    "deleted_files": 2,
    "message": "2個のデータベースファイルをクリーンアップしました"
  }
}
```

#### `/api/database/migrate` (POST)
レガシーデータベース移行実行
```json
{
  "status": "success",
  "data": {
    "message": "レガシーデータベースの移行が完了しました"
  }
}
```

## ⚡ パフォーマンス仕様

### 1. ストレージ効率
- **ファイルサイズ見積もり**: 10MB/月（CO2+温度・湿度合計）
  - CO2データ: 5分間隔 × 8760時間/年 × 12bytes/レコード ≈ 6MB/月
  - 温度・湿度: 5分間隔 × 8760時間/年 × 16bytes/レコード ≈ 4MB/月

### 2. クエリパフォーマンス
- **Chart.js データ取得**: 1秒以内（24時間分データ）
- **データベースファイル作成**: 100ms以内
- **レガシー移行**: 1GB未満DBで10秒以内

### 3. インデックス設計
```sql
-- 各テーブル共通インデックス
CREATE INDEX idx_timestamp ON {table_name}(timestamp);
CREATE INDEX idx_created_at ON {table_name}(created_at);
```

## 🛠️ 自動化仕様

### 1. Cronジョブ設定
```bash
# 日次データベース容量チェック・クリーンアップ
0 1 * * * cd /path/to/raspberry-pi-dashboard && python3 -m database_manager --cleanup

# 月次レガシー移行チェック（月初実行）
0 2 1 * * cd /path/to/raspberry-pi-dashboard && python3 -m database_manager --migrate --status
```

### 2. 既存システム統合

#### CO2Logger/TemperatureHumidityLoggerとの統合
```python
# 既存ロガーの初期化時にDatabaseManager統合
class CO2Logger:
    def __init__(self):
        self.db_manager = DatabaseManager()
        # 現在月DBパス自動取得
        self.db_path = self.db_manager.get_current_month_db_path('co2')
        self.db_manager.initialize_monthly_db(self.db_path, 'co2')
```

#### Chart.js直読みAPIとの統合
```python
# /api/metrics/range/<range_type> エンドポイント拡張
def get_metrics_by_range(range_type):
    db_manager = DatabaseManager()
    
    # 複数月データベースから統合取得
    chart_sources = db_manager.get_chart_data_sources(hours)
    # 既存の統合ロジックで処理継続
```

## 🔍 運用・監視仕様

### 1. ログ出力仕様
```python
# DatabaseManager ログレベル
logging.INFO:  "新月次データベース作成: co2_data_2024-12.db"  
logging.INFO:  "クリーンアップ完了: 2ファイル処理"
logging.WARNING: "ファイルサイズ取得エラー: permission denied"
logging.ERROR: "レガシーDB移行エラー: database locked"
```

### 2. 管理コマンドライン
```bash
# 状態確認
python3 database_manager.py --status

# 手動クリーンアップ
python3 database_manager.py --cleanup

# レガシー移行
python3 database_manager.py --migrate

# ログディレクトリ指定
python3 database_manager.py --status --log-dir /custom/logs
```

### 3. Web管理インターフェース
- **system_monitor.html** にデータベース管理セクション追加
- リアルタイムファイルサイズ表示
- ワンクリック手動クリーンアップボタン
- 移行実行進捗表示

## 🚨 エラーハンドリング・回復仕様

### 1. 障害パターンと対処
```python
# ディスク容量不足
if disk_space < 100MB:
    force_cleanup_old_files()
    send_alert("ディスク容量警告")

# データベースロック
try:
    with sqlite3.connect(db_path, timeout=10) as conn:
        # DB操作
except sqlite3.OperationalError:
    retry_with_exponential_backoff()

# 移行失敗
if migration_failed:
    restore_from_backup()
    log_error_details()
```

### 2. データ整合性確保
- **原子的操作**: ファイル移動前の一時ファイル作成
- **ロールバック**: 移行失敗時の元DBファイル復元
- **検証**: レコード数・データサンプル確認

## 🚀 高頻度監視データ収集システム（新設計）

### 1. システム設計目標

**背景**: 現在の5分間隔では温度湿度グラフにシミュレーション値が多く、実測値の詳細な変化を追跡できない。CO2センサーは実測値取得成功（886ppm）しているため、温度湿度も同等の品質を目指す。

**設計方針**:
- **高頻度収集**: 5分→1分間隔（5倍密度向上）
- **タイムアウト最適化**: 応答性向上（10秒→3秒）
- **実測値優先**: シミュレーション値最小化
- **SSD負荷最適化**: 効率的書き込み戦略

### 2. データ収集アーキテクチャ

#### 新データ収集フロー
```
┌─────────────────────────────────────────────────┐
│           高頻度監視データ収集システム           │
├─────────────────────────────────────────────────┤
│                                                 │
│  [1分間隔cron] → [monitoring_collector.py]      │
│         ↓                     ↓                 │
│  [3秒タイムアウト] → [実測値優先取得]             │
│         ↓                     ↓                 │
│  [差分検出] → [変化時のみ書き込み] → [metrics.json] │
│         ↓                     ↓                 │
│  [インメモリ蓄積] → [効率的I/O] → [Chart.js表示]   │
│                                                 │
└─────────────────────────────────────────────────┘
```

#### タイムアウト最適化設定
```python
# 現在設定
SHT35_TIMEOUT = 10  # 10秒
API_TIMEOUT = 5     # 5秒  
RETRY_COUNT = 3     # 3回

# 最適化設定
SHT35_TIMEOUT = 3   # 3秒（7秒短縮）
API_TIMEOUT = 3     # 3秒（2秒短縮）
RETRY_COUNT = 2     # 2回（効率化）
```

### 3. SSD負荷最適化設計

#### 書き込み効率化戦略
```python
class OptimizedDataCollector:
    def __init__(self):
        self.previous_data = None
        self.memory_buffer = []
        self.write_threshold = 5  # 5分分をまとめて書き込み
    
    def collect_and_optimize(self):
        current_data = self.get_sensor_data()
        
        # 差分検出
        if self.has_significant_change(current_data):
            self.memory_buffer.append(current_data)
            
            # 5分分蓄積後に効率的書き込み
            if len(self.memory_buffer) >= self.write_threshold:
                self.write_batch_to_json()
                self.memory_buffer.clear()
```

#### SSD負荷計算
```
現在: 288回/日 × 42KB = 12MB/日
1分間隔: 1,440回/日 × 42KB = 60MB/日
最適化後: 288回/日 × 210KB = 60MB/日（同等）

年間書き込み: 22GB（TBWの0.01%未満）
```

### 4. 実測値優先システム設計

#### データ品質向上ロジック
```python
def get_real_sensor_data():
    """実測値優先取得システム"""
    
    # 1. API経由実測値取得（最優先）
    real_data = get_api_sensor_data(timeout=3)
    if real_data and real_data['status'] == 'success':
        return real_data
    
    # 2. ログファイルから最新実測値取得
    log_data = get_latest_real_from_logs()
    if log_data and not is_simulation_value(log_data):
        return log_data
    
    # 3. フォールバック（最小限シミュレーション）
    return get_fallback_with_cpu_estimation()
```

#### シミュレーション値判定・排除
```python
def is_simulation_value(data):
    """シミュレーション値判定"""
    # SHT35固定シミュレーション値検出
    temp_sim_patterns = [21.0, 26.4]  # CPU温度推定値
    humidity_sim_patterns = [45.0, 70.1]  # 固定シミュレーション値
    
    if data['temperature'] in temp_sim_patterns and \
       data['humidity'] in humidity_sim_patterns:
        return True
    return False
```

### 5. システム性能仕様

#### Pi 5最適化設計
```
CPU使用率: <2%（追加負荷）
メモリ使用: <10MB（バッファリング）
ディスクI/O: 同等（効率化により）
ネットワーク: 軽微（ローカル通信のみ）
センサー負荷: 軽微（3秒タイムアウト）
```

#### 品質目標
```
データ精度: >90%実測値
応答時間: <3秒（センサー読み取り）
障害復旧: <30秒（タイムアウト→復旧）
グラフ更新: 30秒間隔（Chart.js）
```

## 📈 将来拡張仕様

### 1. 高度な自動化
- **予測的クリーンアップ**: ディスク使用量予測による事前削除
- **動的保存期間**: データベースサイズに応じた期間自動調整
- **クラウド同期**: 重要データの自動クラウドバックアップ

### 2. 監視強化
- **Grafana連携**: データベース容量・パフォーマンス監視
- **アラート通知**: 容量警告・移行失敗の自動通知
- **健全性チェック**: 定期的なデータ整合性検証