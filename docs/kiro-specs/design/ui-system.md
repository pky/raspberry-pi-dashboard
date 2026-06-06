# UI/UXシステム詳細設計

## ハイブリッドUI構成

### 二重UI戦略
```
PyQt5 ネイティブGUI (メインインターフェース)
├── 用途: 日常使用・リアルタイム監視
├── 表示: フルスクリーン・タッチ最適化
├── 更新: 2分間隔自動更新
└── 特徴: 高応答性・オフライン対応

Flask Web UI (管理・テスト用)
├── 用途: 管理・監視・テスト実行
├── 表示: ブラウザ経由・レスポンシブ
├── 更新: リアルタイム・API駆動
└── 特徴: リモートアクセス・多機能
```

## PyQt5 ネイティブGUI

### アーキテクチャ設計
```python
# メインGUIアーキテクチャ (dashboard.py)
class RaspberryPiDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUI()
        self.setupThreads()
        self.setupTimers()
    
    # マルチスレッド設計
    def setupThreads(self):
        # APIデータ取得スレッド
        self.api_thread = APIThread()
        self.api_thread.data_ready.connect(self.updateUI)
        
        # センサーデータスレッド  
        self.sensor_thread = SensorThread()
        self.sensor_thread.sensor_data.connect(self.updateSensorDisplay)
        
        # カレンダーデータスレッド
        self.calendar_thread = CalendarThread()
        self.calendar_thread.events_ready.connect(self.updateCalendarDisplay)
```

### Material Design統合
```python
# Material Icons フォント統合
class MaterialIconsSetup:
    def __init__(self):
        self.icon_font = self.loadMaterialIcons()
    
    def loadMaterialIcons(self):
        """Material Icons フォント読み込み"""
        font_path = "/path/to/raspberry-pi-dashboard/static/fonts/MaterialIcons-Regular.ttf"
        font_id = QFontDatabase.addApplicationFont(font_path)
        
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            return QFont(font_family, 24)
        else:
            logging.warning("Material Icons font loading failed")
            return QFont("Arial", 24)  # フォールバック
    
    def getIcon(self, icon_name):
        """アイコン取得"""
        icon_map = {
            'temperature': '\ue1ff',      # thermostat
            'humidity': '\ue3f7',         # opacity  
            'co2': '\ue429',             # air
            'calendar': '\ue8df',        # today
            'settings': '\ue8b8',        # settings
            'refresh': '\ue5d5'          # refresh
        }
        
        return icon_map.get(icon_name, '\ue86f')  # help (default)

# アイコン統合ボタンクラス
class MaterialButton(QPushButton):
    def __init__(self, icon_name, text=""):
        super().__init__()
        self.material_icons = MaterialIconsSetup()
        
        icon_text = self.material_icons.getIcon(icon_name)
        
        if text:
            self.setText(f"{icon_text} {text}")
        else:
            self.setText(icon_text)
            
        self.setFont(self.material_icons.icon_font)
        self.setStyleSheet("""
            MaterialButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 16px;
            }
            MaterialButton:hover {
                background-color: #1976D2;
            }
            MaterialButton:pressed {
                background-color: #0D47A1;
            }
        """)
```

### タッチインターフェース最適化
```python
# タッチ最適化設定
class TouchOptimizedWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setupTouchHandling()
    
    def setupTouchHandling(self):
        """タッチ処理設定"""
        # タッチイベント有効化
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        
        # ジェスチャー認識
        self.grabGesture(Qt.PanGesture)
        self.grabGesture(Qt.TapGesture)
        self.grabGesture(Qt.TapAndHoldGesture)
    
    def event(self, event):
        """タッチイベント処理"""
        if event.type() == QEvent.TouchBegin:
            return self.handleTouchBegin(event)
        elif event.type() == QEvent.TouchUpdate:
            return self.handleTouchUpdate(event)
        elif event.type() == QEvent.TouchEnd:
            return self.handleTouchEnd(event)
        elif event.type() == QEvent.Gesture:
            return self.handleGesture(event)
        
        return super().event(event)
    
    def handleTouchBegin(self, event):
        """タッチ開始処理"""
        # タッチフィードバック (視覚的反応)
        self.setStyleSheet(self.styleSheet() + "background-color: rgba(33, 150, 243, 0.1);")
        return True
    
    def handleTouchEnd(self, event):
        """タッチ終了処理"""  
        # スタイルリセット
        self.setStyleSheet(self.styleSheet().replace("background-color: rgba(33, 150, 243, 0.1);", ""))
        return True

# タッチ最適化レイアウト
MIN_TOUCH_TARGET = 44  # 44px minimum (Apple HIG準拠)

def createTouchButton(text, callback):
    """タッチ最適化ボタン作成"""
    button = MaterialButton("", text)
    button.setMinimumSize(MIN_TOUCH_TARGET, MIN_TOUCH_TARGET)
    button.clicked.connect(callback)
    return button
```

### リアルタイム状態表示
```python
# 状態インジケーター
class StatusIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.status = "unknown"
        self.setFixedSize(16, 16)
    
    def setStatus(self, status):
        """状態更新 (ok, warning, error, offline)"""
        self.status = status
        self.update()  # 再描画トリガー
    
    def paintEvent(self, event):
        """状態インジケーター描画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        colors = {
            "ok": QColor(76, 175, 80),      # Green
            "warning": QColor(255, 152, 0),  # Orange  
            "error": QColor(244, 67, 54),    # Red
            "offline": QColor(158, 158, 158) # Gray
        }
        
        color = colors.get(self.status, colors["offline"])
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(), 1))
        painter.drawEllipse(2, 2, 12, 12)

# データ表示ウィジェット
class SensorDataWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setupUI()
    
    def setupUI(self):
        """センサーデータUI構築"""
        layout = QVBoxLayout()
        
        # 温度表示
        self.temp_layout = QHBoxLayout()
        self.temp_icon = QLabel()
        self.temp_icon.setText("🌡️")
        self.temp_icon.setFont(QFont("Arial", 24))
        
        self.temp_value = QLabel("--.-°C")
        self.temp_value.setFont(QFont("Arial", 20, QFont.Bold))
        
        self.temp_status = StatusIndicator()
        
        self.temp_layout.addWidget(self.temp_icon)
        self.temp_layout.addWidget(self.temp_value)
        self.temp_layout.addWidget(self.temp_status)
        self.temp_layout.addStretch()
        
        layout.addLayout(self.temp_layout)
        
        # CO2表示 (同様の構造)
        self.co2_layout = QHBoxLayout()
        self.co2_icon = QLabel("🌬️")
        self.co2_icon.setFont(QFont("Arial", 24))
        
        self.co2_value = QLabel("--- ppm")
        self.co2_value.setFont(QFont("Arial", 20, QFont.Bold))
        
        self.co2_status = StatusIndicator()
        self.co2_level = QLabel("---")
        self.co2_level.setFont(QFont("Arial", 14))
        
        self.co2_layout.addWidget(self.co2_icon)
        self.co2_layout.addWidget(self.co2_value)
        self.co2_layout.addWidget(self.co2_status)
        self.co2_layout.addWidget(self.co2_level)
        self.co2_layout.addStretch()
        
        layout.addLayout(self.co2_layout)
        self.setLayout(layout)
    
    def updateSensorData(self, data):
        """センサーデータ更新"""
        # 温度表示更新
        if 'temperature' in data:
            self.temp_value.setText(f"{data['temperature']:.1f}°C")
            temp_status = "ok" if 15 <= data['temperature'] <= 30 else "warning"
            self.temp_status.setStatus(temp_status)
        
        # CO2表示更新
        if 'co2' in data:
            co2_data = data['co2']
            self.co2_value.setText(f"{co2_data['ppm']} ppm")
            self.co2_level.setText(co2_data['message'])
            
            status_map = {
                "GOOD": "ok",
                "MODERATE": "warning", 
                "POOR": "warning",
                "VERY_POOR": "error"
            }
            self.co2_status.setStatus(status_map.get(co2_data['level'], "offline"))
```

### フルスクリーン・自動起動設定
```python
# フルスクリーンダッシュボード設定
class FullscreenDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupFullscreen()
    
    def setupFullscreen(self):
        """フルスクリーン設定"""
        # ウィンドウフラグ設定
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowStaysOnTopHint |
            Qt.X11BypassWindowManagerHint
        )
        
        # 画面サイズ取得・設定
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        self.setGeometry(screen_geometry)
        
        # フルスクリーン表示
        self.showFullScreen()
        
        # カーソル非表示 (30秒後)
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.hideCursor)
        self.cursor_timer.start(30000)
    
    def hideCursor(self):
        """カーソル非表示"""
        self.setCursor(Qt.BlankCursor)
    
    def mouseMoveEvent(self, event):
        """マウス移動でカーソル再表示"""
        self.setCursor(Qt.ArrowCursor)
        self.cursor_timer.start(30000)  # タイマーリセット
        super().mouseMoveEvent(event)

# 自動起動設定 (systemd service)
```ini
# /etc/systemd/system/raspberry-pi-native-dashboard.service
[Unit]
Description=Raspberry Pi Native Dashboard (PyQt5)
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
User=pi
Environment=DISPLAY=:0
WorkingDirectory=/path/to/raspberry-pi-dashboard
ExecStart=/usr/bin/python3 dashboard.py
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

## Flask Web UI

### レスポンシブWebデザイン
```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Raspberry Pi Dashboard</title>
    
    <!-- Material Design Lite -->
    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
    <link rel="stylesheet" href="https://code.getmdl.io/1.3.0/material.indigo-pink.min.css">
    <script defer src="https://code.getmdl.io/1.3.0/material.min.js"></script>
    
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="mdl-layout mdl-js-layout mdl-layout--fixed-header">
        <header class="mdl-layout__header">
            <div class="mdl-layout__header-row">
                <span class="mdl-layout-title">🥧 Raspberry Pi Dashboard</span>
                <div class="mdl-layout-spacer"></div>
                <nav class="mdl-navigation mdl-layout--large-screen-only">
                    <a class="mdl-navigation__link" href="#sensors">センサー</a>
                    <a class="mdl-navigation__link" href="#calendar">カレンダー</a>
                    <a class="mdl-navigation__link" href="#system">システム</a>
                </nav>
            </div>
        </header>
        
        <main class="mdl-layout__content">
            <!-- センサーデータカード -->
            <section id="sensors" class="section--center mdl-grid">
                <div class="mdl-card mdl-cell mdl-cell--6-col mdl-shadow--2dp">
                    <div class="mdl-card__title">
                        <h2 class="mdl-card__title-text">
                            <i class="material-icons">thermostat</i> 温湿度
                        </h2>
                    </div>
                    <div class="mdl-card__supporting-text">
                        <div id="temperature-data">
                            <div class="sensor-value">
                                <span id="temperature-value">--.-</span>°C
                                <span id="temperature-status" class="status-indicator"></span>
                            </div>
                            <div class="sensor-value">
                                <span id="humidity-value">--.-</span>%
                                <span id="humidity-status" class="status-indicator"></span>
                            </div>
                            <div class="discomfort-index">
                                不快度指数: <span id="discomfort-value">---</span>
                                <span id="discomfort-level" class="level-badge">---</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="mdl-card mdl-cell mdl-cell--6-col mdl-shadow--2dp">
                    <div class="mdl-card__title">
                        <h2 class="mdl-card__title-text">
                            <i class="material-icons">air</i> CO2濃度
                        </h2>
                    </div>
                    <div class="mdl-card__supporting-text">
                        <div id="co2-data">
                            <div class="sensor-value large">
                                <span id="co2-ppm">---</span> ppm
                                <span id="co2-status" class="status-indicator"></span>
                            </div>
                            <div class="co2-level">
                                <span id="co2-message" class="level-badge">---</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- カレンダーセクション -->
            <section id="calendar" class="section--center mdl-grid">
                <div class="mdl-card mdl-cell mdl-cell--12-col mdl-shadow--2dp">
                    <div class="mdl-card__title">
                        <h2 class="mdl-card__title-text">
                            <i class="material-icons">today</i> 今日の予定
                        </h2>
                    </div>
                    <div class="mdl-card__supporting-text">
                        <div id="today-events">読み込み中...</div>
                    </div>
                </div>
            </section>
            
            <!-- システム監視セクション -->
            <section id="system" class="section--center mdl-grid">
                <div class="mdl-card mdl-cell mdl-cell--12-col mdl-shadow--2dp">
                    <div class="mdl-card__title">
                        <h2 class="mdl-card__title-text">
                            <i class="material-icons">computer</i> システム状態
                        </h2>
                    </div>
                    <div class="mdl-card__supporting-text">
                        <div id="system-metrics">読み込み中...</div>
                    </div>
                    <div class="mdl-card__actions mdl-card--border">
                        <button class="mdl-button mdl-js-button mdl-button--raised" 
                                onclick="runSystemTest()">
                            システムテスト実行
                        </button>
                    </div>
                </div>
            </section>
        </main>
    </div>
    
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
```

### タッチパネル最適化CSS
```css
/* static/css/style.css */
/* タッチデバイス最適化 */
@media (hover: none) and (pointer: coarse) {
    /* タッチターゲット最小サイズ */
    .mdl-button, .mdl-navigation__link, .touchable {
        min-height: 44px;
        min-width: 44px;
        padding: 12px 16px;
    }
    
    /* タップ時ハイライト無効化 */
    * {
        -webkit-tap-highlight-color: transparent;
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        -khtml-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    /* スクロール最適化 */
    .mdl-layout__content {
        -webkit-overflow-scrolling: touch;
        scroll-behavior: smooth;
    }
}

/* センサーデータ表示 */
.sensor-value {
    display: flex;
    align-items: center;
    margin: 10px 0;
    font-size: 1.8em;
    font-weight: bold;
}

.sensor-value.large {
    font-size: 2.5em;
}

.status-indicator {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    margin-left: 10px;
    display: inline-block;
}

.status-indicator.ok { background-color: #4CAF50; }
.status-indicator.warning { background-color: #FF9800; }
.status-indicator.error { background-color: #F44336; }
.status-indicator.offline { background-color: #9E9E9E; }

.level-badge {
    background-color: #2196F3;
    color: white;
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 0.8em;
    margin-left: 10px;
}

/* レスポンシブ調整 */
@media screen and (max-width: 768px) {
    .mdl-card {
        margin: 8px;
    }
    
    .sensor-value {
        font-size: 1.5em;
    }
    
    .sensor-value.large {
        font-size: 2em;
    }
}

/* ダークモード (オプション) */
@media (prefers-color-scheme: dark) {
    .mdl-layout__header {
        background-color: #1976D2;
    }
    
    .mdl-card {
        background-color: #424242;
        color: #fff;
    }
}
```

### リアルタイムJavaScript
```javascript
// static/js/app.js
class DashboardApp {
    constructor() {
        this.updateInterval = 30000; // 30秒間隔
        this.init();
    }
    
    init() {
        this.updateSensorData();
        this.updateCalendarData();
        this.updateSystemStatus();
        
        // 定期更新開始
        setInterval(() => {
            this.updateSensorData();
            this.updateCalendarData();
        }, this.updateInterval);
        
        // システム状態は頻度低め (2分間隔)
        setInterval(() => {
            this.updateSystemStatus();
        }, 120000);
    }
    
    async updateSensorData() {
        try {
            const response = await fetch('/api/sensor_data');
            const data = await response.json();
            
            this.updateTemperatureDisplay(data);
            this.updateCO2Display(data);
            
        } catch (error) {
            console.error('センサーデータ更新失敗:', error);
            this.showErrorState();
        }
    }
    
    updateTemperatureDisplay(data) {
        const tempElement = document.getElementById('temperature-value');
        const humidityElement = document.getElementById('humidity-value');
        const discomfortElement = document.getElementById('discomfort-value');
        const discomfortLevelElement = document.getElementById('discomfort-level');
        const tempStatusElement = document.getElementById('temperature-status');
        
        if (data.temperature !== undefined) {
            tempElement.textContent = data.temperature.toFixed(1);
            
            // 温度ステータス設定
            const tempStatus = this.getTemperatureStatus(data.temperature);
            tempStatusElement.className = `status-indicator ${tempStatus}`;
        }
        
        if (data.humidity !== undefined) {
            humidityElement.textContent = data.humidity.toFixed(1);
        }
        
        if (data.discomfort_index) {
            discomfortElement.textContent = data.discomfort_index.value.toFixed(1);
            discomfortLevelElement.textContent = data.discomfort_index.level;
            discomfortLevelElement.style.backgroundColor = this.getDiscomfortColor(data.discomfort_index.color);
        }
    }
    
    updateCO2Display(data) {
        if (!data.co2) return;
        
        const co2Element = document.getElementById('co2-ppm');
        const co2MessageElement = document.getElementById('co2-message');
        const co2StatusElement = document.getElementById('co2-status');
        
        co2Element.textContent = data.co2.ppm;
        co2MessageElement.textContent = data.co2.message;
        co2MessageElement.style.backgroundColor = this.getCO2Color(data.co2.color);
        
        const statusMap = {
            'GOOD': 'ok',
            'MODERATE': 'warning',
            'POOR': 'warning', 
            'VERY_POOR': 'error'
        };
        
        co2StatusElement.className = `status-indicator ${statusMap[data.co2.level] || 'offline'}`;
    }
    
    async updateCalendarData() {
        try {
            const response = await fetch('/api/today_events');
            const data = await response.json();
            
            const eventsContainer = document.getElementById('today-events');
            
            if (data.events && data.events.length > 0) {
                eventsContainer.innerHTML = data.events.map(event => `
                    <div class="event-item">
                        <div class="event-time">${this.formatTime(event.start)}</div>
                        <div class="event-title">${event.summary}</div>
                        ${event.location ? `<div class="event-location">${event.location}</div>` : ''}
                    </div>
                `).join('');
            } else {
                eventsContainer.innerHTML = '<div class="no-events">今日の予定はありません</div>';
            }
            
        } catch (error) {
            console.error('カレンダーデータ更新失敗:', error);
            document.getElementById('today-events').innerHTML = '<div class="error">カレンダーデータの取得に失敗しました</div>';
        }
    }
    
    async updateSystemStatus() {
        try {
            const response = await fetch('/api/system_status');
            const data = await response.json();
            
            const systemContainer = document.getElementById('system-metrics');
            systemContainer.innerHTML = `
                <div class="system-metric">
                    <span class="metric-label">API成功率:</span>
                    <span class="metric-value">${data.api_success_rate || 'N/A'}%</span>
                    <span class="status-indicator ${this.getSystemStatus(data.api_success_rate)}"></span>
                </div>
                <div class="system-metric">
                    <span class="metric-label">稼働時間:</span>
                    <span class="metric-value">${data.uptime || 'N/A'}</span>
                </div>
                <div class="system-metric">
                    <span class="metric-label">メモリ使用率:</span>
                    <span class="metric-value">${data.memory_usage || 'N/A'}%</span>
                </div>
            `;
            
        } catch (error) {
            console.error('システム状態更新失敗:', error);
        }
    }
    
    // ユーティリティメソッド
    getTemperatureStatus(temp) {
        if (temp >= 15 && temp <= 30) return 'ok';
        if (temp >= 10 && temp <= 35) return 'warning';
        return 'error';
    }
    
    getCO2Color(color) {
        const colorMap = {
            'green': '#4CAF50',
            'yellow': '#FFEB3B', 
            'orange': '#FF9800',
            'red': '#F44336'
        };
        return colorMap[color] || '#9E9E9E';
    }
    
    getDiscomfortColor(color) {
        const colorMap = {
            'blue': '#2196F3',
            'lightblue': '#03A9F4',
            'green': '#4CAF50',
            'lightgreen': '#8BC34A',
            'yellow': '#FFEB3B',
            'orange': '#FF9800',
            'red': '#F44336',
            'darkred': '#D32F2F'
        };
        return colorMap[color] || '#9E9E9E';
    }
    
    formatTime(timeString) {
        return new Date(timeString).toLocaleTimeString('ja-JP', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    
    getSystemStatus(successRate) {
        if (successRate >= 95) return 'ok';
        if (successRate >= 80) return 'warning';
        return 'error';
    }
    
    showErrorState() {
        document.querySelectorAll('.status-indicator').forEach(el => {
            el.className = 'status-indicator offline';
        });
    }
}

// システムテスト実行
async function runSystemTest() {
    const button = event.target;
    button.disabled = true;
    button.textContent = 'テスト実行中...';
    
    try {
        const response = await fetch('/api/run_system_test', {
            method: 'POST'
        });
        const result = await response.json();
        
        // テスト結果表示
        alert(`システムテスト完了\n成功率: ${result.success_rate}%\n詳細: ${result.message}`);
        
    } catch (error) {
        alert('システムテスト実行に失敗しました: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = 'システムテスト実行';
    }
}

// アプリケーション初期化
window.addEventListener('DOMContentLoaded', () => {
    new DashboardApp();
});
```

## パフォーマンス最適化

### UI応答性最適化
- **ネイティブGUI**: 2分間隔更新、メインスレッドブロック回避
- **Web UI**: 30秒間隔更新、非同期API通信
- **タッチレスポンス**: <100ms反応時間
- **画面描画**: 60fps維持 (PyQt5)、CSS GPUアクセラレーション (Web)

### メモリ最適化
- **PyQt5**: スレッドプール使用、オブジェクト適切解放
- **Web UI**: DOM操作最小化、不要イベントリスナー削除
- **画像リソース**: 必要最小限、適切形式選択
- **キャッシュ戦略**: データキャッシュ、レンダリング結果キャッシュ

### アクセシビリティ対応
- **キーボード操作**: 全機能キーボードアクセス可能
- **コントラスト**: WCAG AA準拠 (4.5:1以上)
- **フォントサイズ**: 最小14px、スケーラブル設計
- **カラー**: 色覚多様性対応、意味を色だけに依存しない