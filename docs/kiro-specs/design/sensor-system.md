# センサーシステム詳細設計

## CO2センサーシステム (MH-Z19E)

### ハードウェア接続
- **センサー**: MH-Z19E NDIR CO2センサー
- **接続**: UART通信 (GPIO14=TX, GPIO15=RX)
- **電源**: 5V (Raspberry Pi GPIO経由)
- **通信設定**: 9600bps, 8N1

### 通信プロトコル
```python
# CO2濃度読み取りコマンド
READ_COMMAND = [0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79]

# レスポンス形式
# Byte 0: 0xFF (開始バイト)
# Byte 1: 0x86 (コマンド)
# Byte 2-3: CO2濃度 (High/Low byte)
# Byte 4-7: 予約領域
# Byte 8: CRCチェックサム
```

### CO2レベル判定基準
```python
CO2_LEVELS = {
    "GOOD": {"range": [0, 1000], "color": "green", "message": "良好"},
    "MODERATE": {"range": [1001, 1500], "color": "yellow", "message": "注意"},
    "POOR": {"range": [1501, 2000], "color": "orange", "message": "換気推奨"},
    "VERY_POOR": {"range": [2001, float('inf')], "color": "red", "message": "危険"}
}
```

### ファイル構成
- **`mhz19e.py`**: センサードライバー・UART通信
- **`co2_logger.py`**: データロガー・履歴管理
- **`sensor.py`**: 統合センサーモジュール（DHT22+CO2）

## SHT35 温湿度センサーシステム

### ハードウェア接続  
- **センサー**: SHT35 高精度デジタル温湿度センサー
- **接続**: I2C通信 (SDA/SCL)
- **I2Cアドレス**: 0x44 (デフォルト)
- **電源**: 3.3V

### 測定仕様
- **温度範囲**: -40～125°C (±0.2°C精度)  
- **湿度範囲**: 0～100% (±2%精度)
- **サンプリング**: 1秒間隔 (最小)
- **通信**: I2C (より安定した通信)
- **利点**: DHT22比で高精度・安定性向上

### 不快度指数計算
```python
def calculate_discomfort_index(temperature, humidity):
    """
    不快度指数 = 0.81T + 0.01H(0.99T - 14.3) + 46.3
    T: 温度(℃), H: 湿度(%)
    """
    di = 0.81 * temperature + 0.01 * humidity * (0.99 * temperature - 14.3) + 46.3
    
    if di < 55:
        return {"level": "寒い", "color": "blue"}
    elif di < 60:
        return {"level": "肌寒い", "color": "lightblue"}  
    elif di < 65:
        return {"level": "何も感じない", "color": "green"}
    elif di < 70:
        return {"level": "快い", "color": "lightgreen"}
    elif di < 75:
        return {"level": "暑くない", "color": "yellow"}
    elif di < 80:
        return {"level": "やや暑い", "color": "orange"}
    elif di < 85:
        return {"level": "暑くて汗が出る", "color": "red"}
    else:
        return {"level": "暑くてたまらない", "color": "darkred"}
```

## 統合センサー制御システム

### センサー制御アーキテクチャ
```
sensor.py (統合制御)
├── SHT35制御 (adafruit_sht31d)
│   ├── 温度取得 (I2C通信・高精度)
│   ├── 湿度取得 (I2C通信・高精度)  
│   ├── センサーリセット機能
│   └── 不快度指数計算
├── MH-Z19E制御 (mhz19e.py)
│   ├── CO2濃度取得 (2分間隔)
│   ├── CRC検証
│   └── レベル判定
└── データ統合
    ├── JSON形式出力
    ├── エラーハンドリング・リトライ
    └── 統合ログ記録
```

### APIエンドポイント
```python
# 統合センサーデータ
GET /api/sensor_data
{
    "temperature": 25.4,
    "humidity": 55.2, 
    "discomfort_index": {
        "value": 68.5,
        "level": "快い",
        "color": "lightgreen"
    },
    "co2": {
        "ppm": 850,
        "level": "GOOD", 
        "message": "良好",
        "color": "green"
    },
    "timestamp": "2024-08-19T10:30:00"
}

# 個別センサー専用
GET /api/sensor        # SHT35温湿度のみ
GET /api/co2           # CO2のみ  
```

## エラーハンドリング・復旧システム

### センサー障害対応
```python
# SHT35読み取り失敗時
- 5回リトライ (0.5秒間隔)
- I2C通信エラーでセンサーリセット
- 失敗時はシミュレーション値使用
- 連続失敗でアラート送信

# CO2センサー障害対応  
- UART通信エラー検出
- CRCチェックサム検証
- シリアルポート再接続
- シミュレーションモード自動切替
```

### シミュレーションモード
```python
# 開発・テスト用データ生成
SIMULATION_MODE = {
    "temperature": 20 + random.uniform(-5, 10),
    "humidity": 50 + random.uniform(-15, 25),
    "co2_ppm": 400 + random.uniform(0, 1000)
}
```

## データ保存・履歴管理

### CO2データロガー (`co2_logger.py`)
```python
# データ保存形式 (CSV)
timestamp,co2_ppm,level,temperature,humidity
2024-08-19 10:30:00,850,GOOD,25.4,55.2

# ローテーション設定
- 1時間ごとに新ファイル
- 7日間保持 
- 自動圧縮・アーカイブ
```

### 履歴API
```python
GET /api/sensor_history?hours=24  # 24時間履歴
GET /api/co2_trends?days=7        # CO2トレンド分析
```

## 監視・アラートシステム

### 閾値監視
- **CO2**: 2000ppm超過でアラート  
- **温度**: 30°C超過・10°C未満でアラート
- **湿度**: 80%超過・20%未満でアラート
- **センサー**: 5分間データなしでアラート

### アラート配信
- systemdログ記録
- Web管理画面通知
- 自動復旧試行

## 性能・信頼性

### 応答性能
- **データ取得**: <1秒
- **API応答**: <200ms  
- **更新間隔**: 2分 (バランス調整)

### 信頼性指標
- **稼働率**: 99.9% (年間8.7時間ダウン許容)
- **データ精度**: DHT22±0.5°C, MH-Z19E±50ppm
- **復旧時間**: 自動復旧<30秒