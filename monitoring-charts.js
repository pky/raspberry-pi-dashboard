/**
 * monitoring-charts.js - システム監視データグラフ表示
 * 
 * Chart.jsを使用してシステムメトリクスの時系列グラフを表示
 */

class MonitoringChartsManager {
    constructor() {
        this.charts = {};
        this.currentTimeRange = '1h';
        this.refreshInterval = null;
        this.isAutoRefreshEnabled = false;
        this.isInitialized = false;
        this.dataCache = new Map(); // データキャッシュ
        this.performanceMetrics = {
            renderTimes: [],
            apiResponseTimes: [],
            lastOptimized: null
        };
        
        // Chart.jsの初期設定
        this.initializeChartDefaults();
    }
    
    /**
     * Chart.jsのデフォルト設定
     */
    initializeChartDefaults() {
        if (typeof Chart !== 'undefined') {
            Chart.defaults.font.family = 'Arial, sans-serif';
            Chart.defaults.font.size = 12;
            Chart.defaults.color = '#666';
        }
    }
    
    /**
     * チャートシステムの初期化
     */
    async initialize() {
        if (this.isInitialized) {
            return;
        }
        
        try {
            // Chart.jsの読み込み確認
            if (typeof Chart === 'undefined') {
                throw new Error('Chart.js is not loaded');
            }
            
            console.log('監視チャートシステム初期化開始...');
            
            // チャートコンテナ作成
            this.createChartContainers();
            
            // 初期データ読み込み
            await this.loadChartsData();
            
            // 自動更新開始
            this.startAutoRefresh();
            
            this.isInitialized = true;
            console.log('監視チャートシステム初期化完了');
            
        } catch (error) {
            console.error('チャートシステム初期化エラー:', error);
            throw error;
        }
    }
    
    /**
     * チャートコンテナをHTMLに作成
     */
    createChartContainers() {
        const container = document.querySelector('.container');
        if (!container) {
            throw new Error('Container element not found');
        }
        
        // グラフセクションのHTML
        const chartsHTML = `
            <div class="card" id="monitoring-charts-section" style="margin-top: 20px;">
                <div class="card-title">
                    📊 システム監視グラフ
                    <span id="charts-status" class="status-indicator status-unknown"></span>
                </div>
                <div class="card-content">
                    <!-- 時間範囲選択 -->
                    <div class="chart-controls" style="margin-bottom: 20px; text-align: center;">
                        <div class="time-range-buttons">
                            <button class="btn chart-time-btn active" data-range="1h" title="過去1時間のデータを表示">1時間</button>
                            <button class="btn chart-time-btn" data-range="6h" title="過去6時間のデータを表示">6時間</button>
                            <button class="btn chart-time-btn" data-range="12h" title="過去12時間のデータを表示">12時間</button>
                            <button class="btn chart-time-btn" data-range="24h" title="過去24時間のデータを表示">24時間</button>
                        </div>
                        <div class="chart-actions" style="margin-top: 10px;">
                            <button class="btn refresh-btn" onclick="monitoringCharts.refreshCharts()" title="チャートを手動更新">🔄 更新</button>
                            <button class="btn auto-refresh-btn" onclick="monitoringCharts.toggleAutoRefresh()" title="自動更新のON/OFF切り替え">⏱️ 自動更新</button>
                            <span id="last-update-time" class="last-update-info" style="margin-left: 15px; font-size: 0.9rem; color: #666;"></span>
                        </div>
                    </div>
                    
                    <!-- グラフコンテナ -->
                    <div class="charts-grid">
                        <!-- CPU・メモリグラフ -->
                        <div class="chart-container">
                            <h4 class="chart-title">💻 CPU・メモリ使用率</h4>
                            <canvas id="cpu-memory-chart" width="400" height="200"></canvas>
                        </div>
                        
                        <!-- 温度グラフ -->
                        <div class="chart-container">
                            <h4 class="chart-title">🌡️ 温度推移</h4>
                            <canvas id="temperature-chart" width="400" height="200"></canvas>
                        </div>
                        
                        <!-- 湿度・CO2グラフ -->
                        <div class="chart-container">
                            <h4 class="chart-title">🌬️ 湿度・CO2濃度</h4>
                            <canvas id="humidity-co2-chart" width="400" height="200"></canvas>
                        </div>
                        
                        <!-- ディスク・ネットワークグラフ -->
                        <div class="chart-container">
                            <h4 class="chart-title">💾 ディスク・ネットワーク</h4>
                            <canvas id="disk-network-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                    
                    <!-- 警告ステータスパネル -->
                    <div id="warning-panel" class="warning-panel" style="display: none; margin-bottom: 15px;">
                        <div class="warning-header">⚠️ 警告ステータス</div>
                        <div id="warning-content" class="warning-content"></div>
                    </div>
                    
                    <!-- データ情報 -->
                    <div id="chart-info" class="chart-info" style="margin-top: 15px; text-align: center; color: #666; font-size: 0.9rem;">
                        データ読み込み中...
                    </div>
                </div>
            </div>
        `;
        
        // CSS追加
        const chartCSS = `
            <style>
                .charts-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }
                
                .chart-container {
                    background: #f8f9fa;
                    border-radius: 8px;
                    padding: 15px;
                    border: 1px solid #e9ecef;
                }
                
                .chart-title {
                    margin: 0 0 15px 0;
                    color: #2c3e50;
                    font-size: 1.1rem;
                    text-align: center;
                }
                
                .chart-controls {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 10px;
                }
                
                .time-range-buttons {
                    display: flex;
                    justify-content: center;
                    flex-wrap: wrap;
                    gap: 10px;
                }
                
                .chart-actions {
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    flex-wrap: wrap;
                    gap: 10px;
                }
                
                .chart-time-btn {
                    background: #ecf0f1;
                    color: #2c3e50;
                    min-width: 80px;
                }
                
                .chart-time-btn.active {
                    background: linear-gradient(135deg, #3498db, #2980b9);
                    color: white;
                }
                
                .chart-time-btn:hover {
                    background: #d5dbdb;
                }
                
                .chart-time-btn.active:hover {
                    background: linear-gradient(135deg, #2980b9, #1f5f99);
                }
                
                .chart-time-btn:disabled {
                    opacity: 0.6;
                    cursor: not-allowed;
                    pointer-events: none;
                }
                
                .refresh-btn {
                    background: #27ae60;
                    color: white;
                    border: none;
                }
                
                .refresh-btn:hover {
                    background: #219a52;
                }
                
                .auto-refresh-btn {
                    background: #f39c12;
                    color: white;
                    border: none;
                }
                
                .auto-refresh-btn:hover {
                    background: #e67e22;
                }
                
                .auto-refresh-btn.active {
                    background: #e74c3c;
                }
                
                .auto-refresh-btn.active:hover {
                    background: #c0392b;
                }
                
                .last-update-info {
                    font-weight: normal;
                    padding: 5px 10px;
                    background: #ecf0f1;
                    border-radius: 3px;
                }
                
                .warning-panel {
                    background: linear-gradient(135deg, #f39c12, #e67e22);
                    border-radius: 8px;
                    border: 2px solid #d35400;
                    box-shadow: 0 4px 8px rgba(211, 84, 0, 0.2);
                    animation: warningPulse 2s infinite;
                }
                
                .warning-header {
                    background: rgba(0, 0, 0, 0.1);
                    color: white;
                    padding: 10px 15px;
                    border-radius: 6px 6px 0 0;
                    font-weight: bold;
                    font-size: 1.1rem;
                    text-align: center;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                }
                
                .warning-content {
                    padding: 15px;
                    color: white;
                    font-weight: 500;
                }
                
                .warning-item {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 5px 0;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                }
                
                .warning-item:last-child {
                    border-bottom: none;
                }
                
                .warning-label {
                    font-size: 0.95rem;
                }
                
                .warning-value {
                    font-size: 1.1rem;
                    font-weight: bold;
                }
                
                @keyframes warningPulse {
                    0%, 50%, 100% { 
                        opacity: 1; 
                        transform: scale(1);
                    }
                    25%, 75% { 
                        opacity: 0.9; 
                        transform: scale(1.02);
                    }
                }
                
                .chart-info {
                    padding: 10px;
                    background: #f8f9fa;
                    border-radius: 4px;
                    border: 1px solid #e9ecef;
                }
                
                @media (max-width: 768px) {
                    .charts-grid {
                        grid-template-columns: 1fr;
                        gap: 15px;
                    }
                    
                    .chart-container {
                        min-width: 300px;
                        padding: 10px;
                    }
                    
                    .time-range-buttons {
                        flex-wrap: wrap;
                        gap: 8px;
                    }
                    
                    .chart-time-btn {
                        min-width: 70px;
                        font-size: 0.9rem;
                        padding: 8px 12px;
                    }
                    
                    .chart-actions {
                        flex-direction: column;
                        gap: 8px;
                    }
                    
                    .warning-panel {
                        margin: 10px 0;
                    }
                    
                    .warning-header {
                        font-size: 1rem;
                        padding: 8px 12px;
                    }
                    
                    .warning-content {
                        padding: 12px;
                    }
                    
                    .warning-item {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 5px;
                        padding: 8px 0;
                    }
                }
                
                @media (max-width: 480px) {
                    .chart-container {
                        min-width: 280px;
                        padding: 8px;
                    }
                    
                    .chart-title {
                        font-size: 1rem;
                    }
                    
                    .chart-info {
                        font-size: 0.8rem;
                        line-height: 1.4;
                    }
                }
            </style>
        `;
        
        // スタイル追加
        document.head.insertAdjacentHTML('beforeend', chartCSS);
        
        // グラフセクションを最後のcardの前に挿入
        const lastCard = container.querySelector('.card:last-of-type');
        lastCard.insertAdjacentHTML('beforebegin', chartsHTML);
        
        // イベントリスナー追加
        this.setupEventListeners();
    }
    
    /**
     * イベントリスナー設定
     */
    setupEventListeners() {
        // 時間範囲ボタン
        document.querySelectorAll('.chart-time-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const range = e.target.dataset.range;
                this.changeTimeRange(range);
            });
        });
    }
    
    /**
     * 時間範囲変更
     */
    async changeTimeRange(range) {
        // 無効な範囲チェック
        const validRanges = ['1h', '6h', '12h', '24h'];
        if (!validRanges.includes(range)) {
            console.error(`無効な時間範囲: ${range}`);
            return;
        }
        
        const previousRange = this.currentTimeRange;
        this.currentTimeRange = range;
        
        // ローディング状態表示
        document.getElementById('charts-status').className = 'status-indicator status-unknown';
        document.getElementById('chart-info').textContent = `時間範囲を${range}に変更中...`;
        
        // アクティブボタン更新
        document.querySelectorAll('.chart-time-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.disabled = true; // 変更中は無効化
        });
        document.querySelector(`[data-range="${range}"]`).classList.add('active');
        
        try {
            // チャート更新
            await this.loadChartsData();
            
            console.log(`時間範囲変更完了: ${previousRange} → ${range}`);
            
        } catch (error) {
            console.error('時間範囲変更エラー:', error);
            
            // エラー時は元の範囲に戻す
            this.currentTimeRange = previousRange;
            document.querySelectorAll('.chart-time-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            document.querySelector(`[data-range="${previousRange}"]`).classList.add('active');
            
            document.getElementById('chart-info').textContent = `時間範囲変更エラー: ${error.message}`;
            
        } finally {
            // ボタン再有効化
            document.querySelectorAll('.chart-time-btn').forEach(btn => {
                btn.disabled = false;
            });
        }
    }
    
    /**
     * チャートデータ読み込み
     */
    async loadChartsData() {
        const startTime = performance.now();
        
        try {
            document.getElementById('charts-status').className = 'status-indicator status-unknown';
            document.getElementById('chart-info').textContent = 'データ読み込み中...';
            
            // キャッシュキーを生成
            const cacheKey = `${this.currentTimeRange}-${Date.now() - (Date.now() % (5 * 60 * 1000))}`; // 5分単位でキャッシュ
            
            let data;
            if (this.dataCache.has(cacheKey)) {
                data = this.dataCache.get(cacheKey);
                console.log('キャッシュからデータを取得:', cacheKey);
            } else {
                const apiStartTime = performance.now();
                const response = await fetch(`/api/metrics/history?timeRange=${this.currentTimeRange}`);
                const result = await response.json();
                const apiEndTime = performance.now();
                
                // API応答時間を記録
                this.recordAPIResponseTime(apiEndTime - apiStartTime);
                
                if (result.status === 'success') {
                    data = result.data;
                    // キャッシュに保存（最新の3つのエントリのみ保持）
                    if (this.dataCache.size >= 3) {
                        const firstKey = this.dataCache.keys().next().value;
                        this.dataCache.delete(firstKey);
                    }
                    this.dataCache.set(cacheKey, data);
                } else {
                    throw new Error(result.error || 'データ取得に失敗しました');
                }
            }
            
            // チャート作成・更新（パフォーマンス測定）
            const renderStartTime = performance.now();
            this.updateCPUMemoryChart(data);
            this.updateTemperatureChart(data);
            this.updateHumidityCO2Chart(data);
            this.updateDiskNetworkChart(data);
            const renderEndTime = performance.now();
            
            // レンダリング時間を記録
            this.recordRenderTime(renderEndTime - renderStartTime);
            
            // ステータス更新
            document.getElementById('charts-status').className = 'status-indicator status-healthy';
            this.updateChartInfo(data);
            
            // 初回データ読み込み時は最終更新時刻を表示
            if (!this.lastDataLoadTime) {
                this.updateLastUpdateTime();
            }
            this.lastDataLoadTime = new Date();
            
            // パフォーマンス分析
            const totalTime = performance.now() - startTime;
            if (totalTime > 1000) { // 1秒以上かかった場合は警告
                console.warn(`チャート更新が遅延: ${totalTime.toFixed(2)}ms`);
            }
            
        } catch (error) {
            console.error('チャートデータ読み込みエラー:', error);
            document.getElementById('charts-status').className = 'status-indicator status-critical';
            document.getElementById('chart-info').textContent = `エラー: ${error.message}`;
        }
    }
    
    /**
     * CPU・メモリチャート更新
     */
    updateCPUMemoryChart(data) {
        const ctx = document.getElementById('cpu-memory-chart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.cpuMemory) {
            this.charts.cpuMemory.destroy();
        }
        
        const chartData = {
            labels: data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'CPU使用率 (%)',
                    data: data.metrics.cpu_percent,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: 'メモリ使用率 (%)',
                    data: data.metrics.memory_percent,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }
            ]
        };
        
        this.charts.cpuMemory = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '時刻'
                        },
                        ticks: {
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '使用率 (%)'
                        },
                        min: 0,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }
    
    /**
     * 温度チャート更新
     */
    updateTemperatureChart(data) {
        const ctx = document.getElementById('temperature-chart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.temperature) {
            this.charts.temperature.destroy();
        }
        
        const chartData = {
            labels: data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'CPU温度 (°C)',
                    data: data.metrics.cpu_temperature,
                    borderColor: '#e67e22',
                    backgroundColor: 'rgba(230, 126, 34, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: '室温 (°C)',
                    data: data.metrics.room_temperature,
                    borderColor: '#27ae60',
                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }
            ]
        };
        
        this.charts.temperature = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y}°C`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '時刻'
                        },
                        ticks: {
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '温度 (°C)'
                        },
                        ticks: {
                            callback: function(value) {
                                return value + '°C';
                            }
                        }
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }
    
    /**
     * 湿度・CO2チャート更新
     */
    updateHumidityCO2Chart(data) {
        const ctx = document.getElementById('humidity-co2-chart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.humidityCO2) {
            this.charts.humidityCO2.destroy();
        }
        
        const chartData = {
            labels: data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: '湿度 (%)',
                    data: data.metrics.humidity,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'CO2濃度 (ppm)',
                    data: data.metrics.co2_ppm,
                    borderColor: '#e67e22',
                    backgroundColor: 'rgba(230, 126, 34, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y1'
                }
            ]
        };
        
        this.charts.humidityCO2 = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                const unit = context.dataset.label.includes('湿度') ? '%' : 'ppm';
                                return `${context.dataset.label}: ${context.parsed.y}${unit}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '時刻'
                        },
                        ticks: {
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: '湿度 (%)'
                        },
                        min: 0,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'CO2濃度 (ppm)'
                        },
                        min: 400,
                        max: 3000,
                        ticks: {
                            callback: function(value) {
                                return value + 'ppm';
                            }
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }
    
    /**
     * ディスク・ネットワークチャート更新
     */
    updateDiskNetworkChart(data) {
        const ctx = document.getElementById('disk-network-chart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.diskNetwork) {
            this.charts.diskNetwork.destroy();
        }
        
        const chartData = {
            labels: data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'ディスク使用量 (GB)',
                    data: data.metrics.disk_used_gb,
                    borderColor: '#9b59b6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'ネットワーク送信 (MB)',
                    data: data.metrics.network_bytes_sent_mb,
                    borderColor: '#1abc9c',
                    backgroundColor: 'rgba(26, 188, 156, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    yAxisID: 'y1'
                },
                {
                    label: 'ネットワーク受信 (MB)',
                    data: data.metrics.network_bytes_recv_mb,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    yAxisID: 'y1'
                }
            ]
        };
        
        this.charts.diskNetwork = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label;
                            },
                            label: function(context) {
                                let unit = 'MB';
                                if (context.dataset.label.includes('ディスク')) {
                                    unit = 'GB';
                                }
                                return `${context.dataset.label}: ${context.parsed.y}${unit}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: '時刻'
                        },
                        ticks: {
                            maxTicksLimit: 10
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'ディスク使用量 (GB)'
                        },
                        min: 0,
                        ticks: {
                            callback: function(value) {
                                return value + 'GB';
                            }
                        }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'ネットワーク (MB)'
                        },
                        min: 0,
                        ticks: {
                            callback: function(value) {
                                return value + 'MB';
                            }
                        },
                        grid: {
                            drawOnChartArea: false,
                        },
                    }
                },
                interaction: {
                    mode: 'nearest',
                    axis: 'x',
                    intersect: false
                }
            }
        });
    }
    
    /**
     * チャート情報表示更新
     */
    updateChartInfo(data) {
        const infoElement = document.getElementById('chart-info');
        
        // データカバレッジ情報
        const coverage = data.dataCoverage || 0;
        const coverageColor = coverage >= 90 ? '#27ae60' : coverage >= 50 ? '#f39c12' : '#e74c3c';
        
        // 時間情報
        const latestTime = data.timeInfo && data.timeInfo.endTime ? 
            new Date(data.timeInfo.endTime).toLocaleString('ja-JP') : 
            '不明';
        
        const startTime = data.timeInfo && data.timeInfo.startTime ? 
            new Date(data.timeInfo.startTime).toLocaleString('ja-JP') : 
            '不明';
            
        const description = data.timeRangeDescription || data.timeRange;
        
        // 警告レベル分析と警告パネル更新
        const warnings = this.analyzeWarnings(data);
        this.updateWarningPanel(warnings, data);
        
        infoElement.innerHTML = `
            📊 データポイント: ${data.dataPoints}件/${data.expectedPoints || 0}件 
            <span style="color: ${coverageColor}; font-weight: bold;">(${coverage}%)</span> | 
            ⏱️ 期間: ${description} | 
            🔄 更新間隔: ${data.interval} |<br>
            📅 データ範囲: ${startTime} ～ ${latestTime}
        `;
    }
    
    /**
     * 警告レベル分析
     */
    analyzeWarnings(data) {
        const warnings = [];
        const thresholds = data.thresholds || {};
        const metrics = data.data.metrics || {};
        
        // 最新の値を取得
        const getLatestValue = (metricArray) => {
            return metricArray && metricArray.length > 0 ? 
                metricArray[metricArray.length - 1] : null;
        };
        
        // CPU警告チェック
        const latestCPU = getLatestValue(metrics.cpu_percent);
        if (latestCPU !== null && latestCPU >= (thresholds.cpu_percent_warning || 80)) {
            warnings.push(`CPU ${latestCPU}%`);
        }
        
        // メモリ警告チェック
        const latestMemory = getLatestValue(metrics.memory_percent);
        if (latestMemory !== null && latestMemory >= (thresholds.memory_percent_warning || 80)) {
            warnings.push(`メモリ ${latestMemory}%`);
        }
        
        // CPU温度警告チェック
        const latestCPUTemp = getLatestValue(metrics.cpu_temperature);
        if (latestCPUTemp !== null && latestCPUTemp >= (thresholds.cpu_temperature_warning || 70)) {
            warnings.push(`CPU温度 ${latestCPUTemp}°C`);
        }
        
        // CO2警告チェック
        const latestCO2 = getLatestValue(metrics.co2_ppm);
        if (latestCO2 !== null && thresholds.co2_warning) {
            const co2Levels = thresholds.co2_warning;
            if (latestCO2 >= co2Levels[2]) {
                warnings.push(`CO2 危険 ${latestCO2}ppm`);
            } else if (latestCO2 >= co2Levels[1]) {
                warnings.push(`CO2 警告 ${latestCO2}ppm`);
            } else if (latestCO2 >= co2Levels[0]) {
                warnings.push(`CO2 注意 ${latestCO2}ppm`);
            }
        }
        
        return warnings;
    }
    
    /**
     * 警告パネルの更新
     */
    updateWarningPanel(warnings, data) {
        const warningPanel = document.getElementById('warning-panel');
        const warningContent = document.getElementById('warning-content');
        
        if (warnings.length === 0) {
            warningPanel.style.display = 'none';
            return;
        }
        
        // 警告の詳細情報を生成
        const detailedWarnings = this.generateDetailedWarnings(data);
        
        let warningHTML = '';
        detailedWarnings.forEach(warning => {
            warningHTML += `
                <div class="warning-item">
                    <span class="warning-label">${warning.icon} ${warning.label}</span>
                    <span class="warning-value">${warning.value}</span>
                </div>
            `;
        });
        
        warningContent.innerHTML = warningHTML;
        warningPanel.style.display = 'block';
    }
    
    /**
     * 詳細な警告情報を生成
     */
    generateDetailedWarnings(data) {
        const detailedWarnings = [];
        const thresholds = data.thresholds || {};
        const metrics = data.data.metrics || {};
        
        // 最新の値を取得
        const getLatestValue = (metricArray) => {
            return metricArray && metricArray.length > 0 ? 
                metricArray[metricArray.length - 1] : null;
        };
        
        // CPU警告チェック
        const latestCPU = getLatestValue(metrics.cpu_percent);
        if (latestCPU !== null && latestCPU >= (thresholds.cpu_percent_warning || 80)) {
            const level = latestCPU >= 90 ? '危険' : '警告';
            detailedWarnings.push({
                icon: '🔥',
                label: `CPU使用率 ${level}`,
                value: `${latestCPU}%`
            });
        }
        
        // メモリ警告チェック
        const latestMemory = getLatestValue(metrics.memory_percent);
        if (latestMemory !== null && latestMemory >= (thresholds.memory_percent_warning || 80)) {
            const level = latestMemory >= 90 ? '危険' : '警告';
            detailedWarnings.push({
                icon: '🧠',
                label: `メモリ使用率 ${level}`,
                value: `${latestMemory}%`
            });
        }
        
        // CPU温度警告チェック
        const latestCPUTemp = getLatestValue(metrics.cpu_temperature);
        if (latestCPUTemp !== null && latestCPUTemp >= (thresholds.cpu_temperature_warning || 70)) {
            const level = latestCPUTemp >= 80 ? '危険' : '警告';
            detailedWarnings.push({
                icon: '🌡️',
                label: `CPU温度 ${level}`,
                value: `${latestCPUTemp}°C`
            });
        }
        
        // CO2警告チェック
        const latestCO2 = getLatestValue(metrics.co2_ppm);
        if (latestCO2 !== null && thresholds.co2_warning) {
            const co2Levels = thresholds.co2_warning;
            if (latestCO2 >= co2Levels[2]) {
                detailedWarnings.push({
                    icon: '🚨',
                    label: 'CO2濃度 危険',
                    value: `${latestCO2}ppm`
                });
            } else if (latestCO2 >= co2Levels[1]) {
                detailedWarnings.push({
                    icon: '⚠️',
                    label: 'CO2濃度 警告',
                    value: `${latestCO2}ppm`
                });
            } else if (latestCO2 >= co2Levels[0]) {
                detailedWarnings.push({
                    icon: '💛',
                    label: 'CO2濃度 注意',
                    value: `${latestCO2}ppm`
                });
            }
        }
        
        return detailedWarnings;
    }
    
    /**
     * CPU警告レベルの背景色配列を生成
     */
    getCPUBackgroundColors(cpuData) {
        return cpuData.map(value => {
            if (value >= 90) return 'rgba(231, 76, 60, 0.4)';    // 危険: 濃い赤
            if (value >= 80) return 'rgba(231, 76, 60, 0.25)';   // 警告: 薄い赤
            return 'rgba(231, 76, 60, 0.1)';                     // 正常: 透明
        });
    }
    
    /**
     * メモリ警告レベルの背景色配列を生成
     */
    getMemoryBackgroundColors(memoryData) {
        return memoryData.map(value => {
            if (value >= 90) return 'rgba(52, 152, 219, 0.4)';   // 危険: 濃い青
            if (value >= 80) return 'rgba(52, 152, 219, 0.25)';  // 警告: 薄い青
            return 'rgba(52, 152, 219, 0.1)';                    // 正常: 透明
        });
    }
    
    /**
     * CO2警告レベルの背景色配列を生成
     */
    getCO2BackgroundColors(co2Data) {
        return co2Data.map(value => {
            if (value >= 3000) return 'rgba(192, 57, 43, 0.4)';  // 危険: 濃い赤
            if (value >= 1500) return 'rgba(230, 126, 34, 0.3)'; // 警告: オレンジ
            if (value >= 1000) return 'rgba(241, 196, 15, 0.2)'; // 注意: 黄色
            return 'rgba(39, 174, 96, 0.1)';                     // 正常: 緑
        });
    }
    
    /**
     * 温度警告レベルの背景色配列を生成
     */
    getTemperatureBackgroundColors(tempData) {
        return tempData.map(value => {
            if (value >= 80) return 'rgba(231, 76, 60, 0.4)';    // 危険: 濃い赤
            if (value >= 70) return 'rgba(230, 126, 34, 0.3)';   // 警告: オレンジ
            return 'rgba(39, 174, 96, 0.1)';                     // 正常: 緑
        });
    }
    
    /**
     * タイムスタンプフォーマット
     */
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffHours = (now - date) / (1000 * 60 * 60);
        
        if (this.currentTimeRange === '1h' || this.currentTimeRange === '6h') {
            // 短期間は時:分表示
            return date.toLocaleTimeString('ja-JP', { 
                hour: '2-digit', 
                minute: '2-digit' 
            });
        } else {
            // 長期間は月/日 時:分表示
            return date.toLocaleString('ja-JP', { 
                month: 'numeric',
                day: 'numeric',
                hour: '2-digit', 
                minute: '2-digit' 
            });
        }
    }
    
    /**
     * チャート手動更新
     */
    async refreshCharts() {
        console.log('チャート手動更新開始');
        
        // 更新ボタンを一時的に無効化
        const refreshBtn = document.querySelector('.refresh-btn');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '🔄 更新中...';
        }
        
        try {
            await this.loadChartsData();
            this.updateLastUpdateTime();
            console.log('チャート手動更新完了');
        } catch (error) {
            console.error('チャート手動更新エラー:', error);
        } finally {
            // ボタンを再有効化
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 更新';
            }
        }
    }
    
    /**
     * 自動更新開始
     */
    startAutoRefresh() {
        // 既存のインターバルをクリア
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // 5分間隔で自動更新
        this.refreshInterval = setInterval(() => {
            this.loadChartsData();
            this.updateLastUpdateTime();
        }, 5 * 60 * 1000); // 5分
        
        this.isAutoRefreshEnabled = true;
        this.updateAutoRefreshButton();
        this.updateLastUpdateTime();
        
        console.log('チャート自動更新開始: 5分間隔');
    }
    
    /**
     * 自動更新停止
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
            this.isAutoRefreshEnabled = false;
            this.updateAutoRefreshButton();
            console.log('チャート自動更新停止');
        }
    }
    
    /**
     * 自動更新ON/OFF切り替え
     */
    toggleAutoRefresh() {
        if (this.isAutoRefreshEnabled) {
            this.stopAutoRefresh();
        } else {
            this.startAutoRefresh();
        }
    }
    
    /**
     * 自動更新ボタンの表示状態更新
     */
    updateAutoRefreshButton() {
        const button = document.querySelector('.auto-refresh-btn');
        if (button) {
            if (this.isAutoRefreshEnabled) {
                button.classList.add('active');
                button.textContent = '⏹️ 自動更新停止';
                button.title = '自動更新を停止';
            } else {
                button.classList.remove('active');
                button.textContent = '⏱️ 自動更新開始';
                button.title = '5分間隔の自動更新を開始';
            }
        }
    }
    
    /**
     * 最終更新時刻の表示更新
     */
    updateLastUpdateTime() {
        const timeElement = document.getElementById('last-update-time');
        if (timeElement) {
            const now = new Date();
            const timeStr = now.toLocaleTimeString('ja-JP', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            timeElement.textContent = `最終更新: ${timeStr}`;
        }
    }
    
    /**
     * API応答時間を記録
     */
    recordAPIResponseTime(responseTime) {
        this.performanceMetrics.apiResponseTimes.push(responseTime);
        if (this.performanceMetrics.apiResponseTimes.length > 10) {
            this.performanceMetrics.apiResponseTimes.shift();
        }
    }
    
    /**
     * レンダリング時間を記録
     */
    recordRenderTime(renderTime) {
        this.performanceMetrics.renderTimes.push(renderTime);
        if (this.performanceMetrics.renderTimes.length > 10) {
            this.performanceMetrics.renderTimes.shift();
        }
    }
    
    /**
     * パフォーマンス統計を取得
     */
    getPerformanceStats() {
        const apiTimes = this.performanceMetrics.apiResponseTimes;
        const renderTimes = this.performanceMetrics.renderTimes;
        
        const avgAPI = apiTimes.length > 0 ? 
            apiTimes.reduce((a, b) => a + b, 0) / apiTimes.length : 0;
        const avgRender = renderTimes.length > 0 ? 
            renderTimes.reduce((a, b) => a + b, 0) / renderTimes.length : 0;
        
        return {
            avgAPIResponseTime: Math.round(avgAPI),
            avgRenderTime: Math.round(avgRender),
            cacheHitRate: this.dataCache.size > 0 ? 0.2 : 0, // 簡易計算
            totalMetrics: apiTimes.length
        };
    }
    
    /**
     * リソースクリーンアップ
     */
    destroy() {
        // 自動更新停止
        this.stopAutoRefresh();
        
        // チャート破棄
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
        
        this.charts = {};
        this.isInitialized = false;
        
        console.log('監視チャートシステム破棄完了');
    }
}

// グローバルインスタンス
let monitoringCharts = null;

// Chart.js読み込み完了後の初期化
function initializeMonitoringCharts() {
    if (typeof Chart === 'undefined') {
        console.error('Chart.js が読み込まれていません');
        return;
    }
    
    if (!monitoringCharts) {
        monitoringCharts = new MonitoringChartsManager();
    }
    
    // 既存のシステム監視ページに統合
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => monitoringCharts.initialize(), 1000);
        });
    } else {
        setTimeout(() => monitoringCharts.initialize(), 1000);
    }
}

// Chart.js依存関係チェック
if (typeof Chart !== 'undefined') {
    initializeMonitoringCharts();
} else {
    // Chart.jsの読み込み待機
    document.addEventListener('DOMContentLoaded', () => {
        const checkChart = setInterval(() => {
            if (typeof Chart !== 'undefined') {
                clearInterval(checkChart);
                initializeMonitoringCharts();
            }
        }, 100);
    });
}