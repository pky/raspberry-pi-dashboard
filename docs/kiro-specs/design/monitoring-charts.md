# グラフ表示システム設計書

## 概要

既存の5分間隔監視システムデータを活用し、Web管理画面でリアルタイム時系列グラフ表示機能を実装する。Chart.jsを使用したレスポンシブ設計により、タッチパネル対応の直感的なデータ可視化を提供。

## アーキテクチャ設計

### システム構成

```
[既存監視システム] → [データ収集・キャッシュ] → [新API] → [Chart.js] → [Web管理画面]
         ↓                    ↓              ↓           ↓
[5分間隔cron]      [InMemoryCache]    [/api/metrics/history]  [system_monitor.html]
[simple_api_test]   [24時間分]        [JSON API]             [タッチ対応グラフ]
```

### データフロー

1. **データ収集**: 既存cronシステム(5分間隔) + simple_system_monitor.py
2. **データ蓄積**: 新規InMemoryCache (24時間分, 288ポイント)
3. **API提供**: `/api/metrics/history` エンドポイント
4. **フロントエンド**: Chart.js時系列グラフ + 自動更新

## バックエンド設計

### 新規APIエンドポイント

**エンドポイント**: `GET /api/metrics/history`

**パラメータ**:
- `timeRange`: `1h|6h|12h|24h` (デフォルト: 1h)
- `metrics`: カンマ区切りメトリクス名 (オプション)

**レスポンス形式**:
```json
{
  "timeRange": "1h",
  "interval": "5m",
  "dataPoints": 12,
  "data": {
    "timestamps": ["2025-08-20T10:00:00Z", "2025-08-20T10:05:00Z"],
    "metrics": {
      "cpu_percent": [45.2, 48.1],
      "memory_percent": [22.5, 23.1],
      "cpu_temperature": [46.1, 46.3],
      "room_temperature": [25.8, 25.9],
      "humidity": [65.2, 65.5],
      "co2_ppm": [650, 680],
      "disk_used_gb": [28.5, 28.5],
      "network_bytes_sent": [1024000, 1025000]
    }
  },
  "thresholds": {
    "co2_warning": [1000, 1500, 3000],
    "cpu_temperature_warning": 70,
    "cpu_percent_warning": 80
  }
}
```

### データキャッシュシステム

**ファイル**: `monitoring_data_cache.py` (新規作成)

```python
class MonitoringDataCache:
    def __init__(self, max_hours=24):
        self.max_points = max_hours * 12  # 5分間隔 = 12ポイント/時間
        self.data_storage = deque(maxlen=self.max_points)
        self.lock = threading.Lock()
    
    def add_data_point(self, metrics_data):
        """5分間隔で呼び出される"""
        
    def get_time_range_data(self, time_range):
        """指定期間のデータを取得"""
        
    def get_latest_data(self, count=12):
        """最新N件のデータを取得"""
```

**統合ポイント**:
- `simple_system_monitor.py` 拡張: データキャッシュ連携
- `sensor.py` 統合: 温湿度・CO2データの組み込み
- `app.py` 拡張: 新APIエンドポイント追加

## フロントエンド設計

### Chart.js実装

**ファイル**: `static/js/monitoring-charts.js` (新規作成)

**主要クラス**:
```javascript
class MonitoringCharts {
    constructor() {
        this.charts = {};
        this.updateInterval = 5 * 60 * 1000; // 5分
        this.currentTimeRange = '1h';
    }
    
    initializeCharts() {
        // Chart.js初期化
    }
    
    updateCharts() {
        // データ取得・グラフ更新
    }
    
    switchTimeRange(range) {
        // 表示期間切り替え
    }
}
```

**グラフ設定**:
- **タイプ**: Line Chart with Time Scale
- **アニメーション**: 軽量設定 (新データポイント追加時のみ)
- **レスポンシブ**: タッチ対応、ズーム・パン機能
- **更新方式**: 差分データ追加 (全データ再描画回避)

### HTML構造拡張

**ファイル**: `system_monitor.html` 拡張

```html
<!-- 既存システム情報の下に追加 -->
<div class="monitoring-charts-section">
    <div class="charts-header">
        <h3>📊 システム監視グラフ</h3>
        <div class="time-range-selector">
            <button data-range="1h" class="active">1時間</button>
            <button data-range="6h">6時間</button>
            <button data-range="12h">12時間</button>
            <button data-range="24h">24時間</button>
        </div>
    </div>
    
    <div class="charts-grid">
        <div class="chart-container">
            <canvas id="systemMetricsChart"></canvas>
        </div>
        <div class="chart-container">
            <canvas id="sensorDataChart"></canvas>
        </div>
    </div>
</div>
```

## UI/UX設計

### レスポンシブ対応

**デスクトップ**: 2列グラフ表示 (システムメトリクス | センサーデータ)
**iPad**: 1列縦並び表示、タッチ操作最適化
**Mac**: デスクトップと同等、マウス・トラックパッド操作対応

### マルチデバイス設計

- **ボタンサイズ**: 可変サイズ（デスクトップ32px、iPad 44px）
- **グラフ操作**: マウス・タッチ両対応（ホイール/ピンチズーム、ドラッグ/スワイプパン）
- **期間切り替え**: レスポンシブボタン、デバイス別最適化

### カラーパレット

**システムメトリクス**:
- CPU使用率: `#2196F3` (青)
- メモリ使用率: `#4CAF50` (緑)  
- CPU温度: `#FF9800` (オレンジ)

**センサーデータ**:
- 室温: `#F44336` (赤)
- 湿度: `#00BCD4` (シアン)
- CO2濃度: `#9C27B0` (紫)

**警告レベル**:
- 注意: `#FFC107` (黄)
- 警告: `#FF5722` (橙)
- 危険: `#D32F2F` (深赤)

## パフォーマンス設計

### 最適化目標

- **初期描画**: <500ms
- **データ更新**: <200ms
- **メモリ使用**: <50MB追加
- **ネットワーク**: <10KB/更新

### 最適化手法

1. **データ最小化**: 表示期間分のみ取得
2. **差分更新**: 新データポイントのみ追加
3. **キャッシュ活用**: ブラウザキャッシュ + インメモリキャッシュ
4. **レイジーロード**: グラフの遅延初期化

### メモリ管理

- **サーバー側**: 24時間 × 288ポイント = 約50KB/メトリクス
- **ブラウザ側**: 表示中データのみ保持、古いデータは自動削除

## セキュリティ設計

### アクセス制御

- 既存の管理画面と同一セキュリティレベル
- 認証不要（内部ネットワーク前提）
- レート制限: 10req/min (DoS攻撃対策)

### データ保護

- 機密情報なし（システムメトリクスのみ）
- ログ記録: アクセスログのみ
- 暗号化: HTTPSオプション対応

## エラーハンドリング設計

### サーバーサイド

```python
@app.route('/api/metrics/history')
def get_metrics_history():
    try:
        # データ取得・処理
        return jsonify(data)
    except CacheError:
        return jsonify({'error': 'キャッシュエラー', 'data': fallback_data})
    except Exception as e:
        logger.error(f"メトリクス履歴取得エラー: {e}")
        return jsonify({'error': 'データ取得に失敗しました'}), 500
```

### クライアントサイド

```javascript
async function updateCharts() {
    try {
        const response = await fetch('/api/metrics/history');
        const data = await response.json();
        
        if (data.error) {
            showErrorMessage(data.error);
            return;
        }
        
        renderCharts(data);
    } catch (error) {
        console.error('グラフ更新エラー:', error);
        showErrorMessage('データの更新に失敗しました');
    }
}
```

## 実装フェーズ計画

### Phase 1: 基本実装 (3-4時間)

1. **バックエンド**:
   - `monitoring_data_cache.py` 作成
   - `app.py` にAPIエンドポイント追加
   - `simple_system_monitor.py` 拡張

2. **フロントエンド**:
   - Chart.js統合
   - 基本グラフ表示 (CPU・メモリ・温度)
   - 1時間表示のみ

### Phase 2: 機能拡張 (2-3時間)

1. **全センサー統合**:
   - 湿度・CO2データ追加
   - センサーグラフ実装

2. **時間範囲選択**:
   - 6h・12h・24h対応
   - UIコントロール実装

### Phase 3: 最適化・仕上げ (1-2時間)

1. **警告レベル表示**:
   - 閾値ライン描画
   - 危険領域ハイライト

2. **UI最適化**:
   - レスポンシブ調整
   - パフォーマンス最適化

## 既存システムとの統合

### 影響範囲

**変更あり**:
- `app.py`: 新APIエンドポイント追加
- `system_monitor.html`: グラフセクション追加
- `simple_system_monitor.py`: キャッシュ連携追加

**変更なし**:
- 既存監視システム (cron設定)
- センサー読み取りロジック
- systemdサービス設定

### 後方互換性

- 既存API・機能には一切影響なし
- グラフ機能は独立モジュールとして実装
- 無効化も容易 (HTMLコメントアウトのみ)

### テスト計画

1. **Unit Test**: キャッシュシステム・API
2. **Integration Test**: 既存テストスイート実行
3. **Performance Test**: グラフ描画速度・メモリ使用量
4. **UI Test**: タッチパネル操作確認

この設計により、既存システムを保持しながら効果的なデータ可視化機能を追加できます。