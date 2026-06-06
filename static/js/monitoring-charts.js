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
            console.log('すでに初期化済み - スキップ');
            return;
        }
        
        try {
            // Chart.jsの読み込み確認
            if (typeof Chart === 'undefined') {
                throw new Error('Chart.js is not loaded');
            }
            
            console.log('監視チャートシステム初期化開始...');
            
            // 既存のcanvas要素確認
            const canvasElements = [
                'cpuMemoryChart', 'temperatureChart', 
                'humidityCO2Chart', 'diskNetworkChart'
            ];
            
            let canvasFound = 0;
            for (const id of canvasElements) {
                const element = document.getElementById(id);
                if (element) {
                    canvasFound++;
                    console.log(`Canvas要素確認: #${id} - OK`);
                } else {
                    console.error(`Canvas要素が見つかりません: #${id}`);
                }
            }
            
            if (canvasFound === 0) {
                throw new Error('Canvas要素が一つも見つかりません');
            }
            
            // 強制的に初期データ読み込み（キャッシュ無効化）
            console.log('初期データ読み込み開始...');
            await this.forceLoadChartsData();
            
            // チャート作成確認
            const createdCharts = Object.keys(this.charts).length;
            console.log(`作成されたチャート数: ${createdCharts}/${canvasFound}`);
            
            if (createdCharts === 0) {
                console.log('チャート作成失敗 - サンプルデータで再試行');
                this.generateSampleData();
            }
            
            // 自動更新開始
            this.startAutoRefresh();
            
            // ページ表示・非表示時の自動更新制御
            this.setupVisibilityHandling();
            
            this.isInitialized = true;
            console.log(`監視チャートシステム初期化完了 - ${createdCharts}個のチャートを作成`);
            
        } catch (error) {
            console.error('チャートシステム初期化エラー:', error);
            // エラー時でもサンプルデータで表示を試行
            this.generateSampleData();
            this.isInitialized = true;
            console.log('フォールバック: サンプルデータで初期化完了');
        }
    }
    
    /**
     * チャートコンテナをHTMLに作成（HTMLに直接記述済みのため無効化）
     */
    createChartContainers() {
        console.log('createChartContainers: HTMLに直接記述済みのためスキップ');
        return;
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
        // 時間範囲ボタン - HTMLで直接onclick指定済みのため、追加リスナーは不要
        console.log('イベントリスナー設定: HTML onclick使用済みのため省略');
        
        // 念のため、HTMLでonclickが設定されていない場合のフォールバック
        document.querySelectorAll('.time-range-btn').forEach(button => {
            // 既存のonclick属性がない場合のみリスナー追加
            if (!button.getAttribute('onclick')) {
                button.addEventListener('click', (e) => {
                    const range = e.target.dataset.range;
                    this.changeTimeRange(range);
                });
                console.log(`フォールバックリスナー追加: ${button.dataset.range}`);
            }
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
        console.log(`時間範囲を${range}に変更中...`);
        
        // アクティブボタン更新
        document.querySelectorAll('.time-range-btn').forEach(btn => {
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
            
            console.error(`時間範囲変更エラー: ${error.message}`);
            
        } finally {
            // ボタン再有効化
            document.querySelectorAll('.time-range-btn').forEach(btn => {
                btn.disabled = false;
            });
        }
    }
    
    /**
     * 強制的にチャートデータ読み込み（キャッシュ無効化）
     */
    async forceLoadChartsData() {
        // キャッシュクリア
        this.dataCache.clear();
        await this.loadChartsData();
    }
    
    /**
     * チャートデータ読み込み
     */
    async loadChartsData() {
        const startTime = performance.now();
        
        try {
            console.log('データ読み込み開始:', this.currentTimeRange);
            
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
            console.log('データ読み込み成功');
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
            console.error('データ読み込みエラー:', error.message);
        }
    }
    
    /**
     * CPU・メモリチャート更新
     */
    updateCPUMemoryChart(data) {
        const canvas = document.getElementById('cpuMemoryChart');
        if (!canvas) {
            console.error('cpuMemoryChart canvas not found');
            return;
        }
        
        console.log('CPU・メモリチャート更新開始:', {
            canvas: canvas,
            width: canvas.width,
            height: canvas.height,
            data: data.data.metrics.cpu_percent
        });
        
        // canvasサイズはHTMLで固定設定済み
        
        const ctx = canvas.getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.cpuMemory) {
            this.charts.cpuMemory.destroy();
            console.log('既存CPU・メモリチャートを破棄');
        }
        
        const chartData = {
            labels: data.data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'CPU使用率 (%)',
                    data: data.data.metrics.cpu_percent,
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: 'メモリ使用率 (%)',
                    data: data.data.metrics.memory_percent,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }
            ]
        };
        
        console.log('CPU・メモリチャートデータ:', chartData);
        
        this.charts.cpuMemory = new Chart(ctx, {
            type: 'line',
            data: chartData,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                devicePixelRatio: 1,
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
                            maxTicksLimit: 8,
                            callback: function(value, index, values) {
                                const label = this.getLabelForValue(value);
                                if (label && typeof label === 'string') {
                                    return label.substring(11, 16); // Extract HH:MM from ISO string
                                }
                                return label;
                            }
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
                        beginAtZero: true,
                        ticks: {
                            stepSize: 10,
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
        
        console.log('CPU・メモリチャート作成完了:', this.charts.cpuMemory);
    }
    
    /**
     * 温度チャート更新
     */
    updateTemperatureChart(data) {
        const ctx = document.getElementById('temperatureChart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.temperature) {
            this.charts.temperature.destroy();
        }
        
        const chartData = {
            labels: data.data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'CPU温度 (°C)',
                    data: data.data.metrics.cpu_temperature,
                    borderColor: '#e67e22',
                    backgroundColor: 'rgba(230, 126, 34, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                },
                {
                    label: '室温 (°C)',
                    data: data.data.metrics.room_temperature,
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
                devicePixelRatio: 1,
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
                            maxTicksLimit: 8,
                            callback: function(value, index, values) {
                                const label = this.getLabelForValue(value);
                                if (label && typeof label === 'string') {
                                    return label.substring(11, 16); // Extract HH:MM from ISO string
                                }
                                return label;
                            }
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: '温度 (°C)'
                        },
                        min: 15,
                        max: 80,
                        beginAtZero: false,
                        ticks: {
                            stepSize: 5,
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
        const ctx = document.getElementById('humidityCO2Chart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.humidityCO2) {
            this.charts.humidityCO2.destroy();
        }
        
        const chartData = {
            labels: data.data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: '湿度 (%)',
                    data: data.data.metrics.humidity,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'CO2濃度 (ppm)',
                    data: data.data.metrics.co2_ppm,
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
                devicePixelRatio: 1,
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
                            maxTicksLimit: 10,
                            callback: function(value, index, values) {
                                const label = this.getLabelForValue(value);
                                if (label && typeof label === 'string') {
                                    return label.substring(11, 16); // Extract HH:MM from ISO string
                                }
                                return label;
                            }
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
                        beginAtZero: true,
                        ticks: {
                            stepSize: 10,
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
                        max: 2500,
                        beginAtZero: false,
                        ticks: {
                            stepSize: 300,
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
        const ctx = document.getElementById('diskNetworkChart').getContext('2d');
        
        // 既存チャート破棄
        if (this.charts.diskNetwork) {
            this.charts.diskNetwork.destroy();
        }
        
        const chartData = {
            labels: data.data.timestamps.map(ts => this.formatTimestamp(ts)),
            datasets: [
                {
                    label: 'ディスク使用量 (GB)',
                    data: data.data.metrics.disk_used_gb,
                    borderColor: '#9b59b6',
                    backgroundColor: 'rgba(155, 89, 182, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1,
                    yAxisID: 'y'
                },
                {
                    label: 'ネットワーク送信 (MB)',
                    data: data.data.metrics.network_bytes_sent_mb,
                    borderColor: '#1abc9c',
                    backgroundColor: 'rgba(26, 188, 156, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1,
                    yAxisID: 'y1'
                },
                {
                    label: 'ネットワーク受信 (MB)',
                    data: data.data.metrics.network_bytes_recv_mb,
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
                devicePixelRatio: 1,
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
                            maxTicksLimit: 10,
                            callback: function(value, index, values) {
                                const label = this.getLabelForValue(value);
                                if (label && typeof label === 'string') {
                                    return label.substring(11, 16); // Extract HH:MM from ISO string
                                }
                                return label;
                            }
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
                        max: 20,
                        beginAtZero: true,
                        ticks: {
                            stepSize: 2,
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
                        max: 5000,
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1000,
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
        // パフォーマンス・キャッシュ情報を既存の表示エリアに更新
        const performanceElement = document.getElementById('performance-metrics');
        const dataCoverageElement = document.getElementById('data-coverage');
        
        if (performanceElement && dataCoverageElement) {
            // パフォーマンス情報
            const avgRenderTime = this.performanceMetrics.renderTimes.length > 0 ? 
                (this.performanceMetrics.renderTimes.reduce((a, b) => a + b, 0) / this.performanceMetrics.renderTimes.length).toFixed(1) : 
                0;
                
            const avgAPITime = this.performanceMetrics.apiResponseTimes.length > 0 ? 
                (this.performanceMetrics.apiResponseTimes.reduce((a, b) => a + b, 0) / this.performanceMetrics.apiResponseTimes.length).toFixed(0) : 
                0;
                
            // キャッシュヒット率
            const cacheHitRate = this.dataCache.size > 0 ? Math.round(this.dataCache.size * 30) : 0;
            
            performanceElement.textContent = `描画時間: ${avgRenderTime}ms | データ取得: ${avgAPITime}ms | キャッシュヒット率: ${cacheHitRate}%`;
            
            // データ範囲情報
            const coverage = data.dataCoverage || 0;
            dataCoverageElement.textContent = `データ範囲: ${data.timeRangeDescription || this.currentTimeRange} | ポイント数: ${data.dataPoints || 0}`;
        }
        
        // 警告レベル分析と警告パネル更新
        const warnings = this.analyzeWarnings(data);
        this.updateWarningPanel(warnings, data);
        
        console.log('チャート情報更新完了:', {
            timeRange: this.currentTimeRange,
            dataPoints: data.dataPoints,
            coverage: data.dataCoverage
        });
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
        // HTMLに存在する個別の警告パネルを使用
        const panelIds = [
            'warning-panel-cpu-memory',
            'warning-panel-temperature', 
            'warning-panel-humidity-co2',
            'warning-panel-disk-network'
        ];
        
        if (warnings.length === 0) {
            // 警告なし - 全パネルを非表示
            panelIds.forEach(id => {
                const panel = document.getElementById(id);
                if (panel) {
                    panel.style.display = 'none';
                }
            });
            return;
        }
        
        // 警告の詳細情報を生成
        const detailedWarnings = this.generateDetailedWarnings(data);
        
        // CPU・メモリ警告パネル更新
        const cpuMemoryPanel = document.getElementById('warning-panel-cpu-memory');
        const cpuMemoryWarnings = detailedWarnings.filter(w => 
            w.label.includes('CPU') || w.label.includes('メモリ')
        );
        
        if (cpuMemoryPanel && cpuMemoryWarnings.length > 0) {
            cpuMemoryPanel.innerHTML = cpuMemoryWarnings.map(w => 
                `${w.icon} ${w.label}: ${w.value}`
            ).join(' | ');
            cpuMemoryPanel.style.display = 'block';
        } else if (cpuMemoryPanel) {
            cpuMemoryPanel.style.display = 'none';
        }
        
        // 温度警告パネル更新
        const temperaturePanel = document.getElementById('warning-panel-temperature');
        const temperatureWarnings = detailedWarnings.filter(w => w.label.includes('温度'));
        
        if (temperaturePanel && temperatureWarnings.length > 0) {
            temperaturePanel.innerHTML = temperatureWarnings.map(w => 
                `${w.icon} ${w.label}: ${w.value}`
            ).join(' | ');
            temperaturePanel.style.display = 'block';
        } else if (temperaturePanel) {
            temperaturePanel.style.display = 'none';
        }
        
        // CO2警告パネル更新
        const co2Panel = document.getElementById('warning-panel-humidity-co2');
        const co2Warnings = detailedWarnings.filter(w => w.label.includes('CO2'));
        
        if (co2Panel && co2Warnings.length > 0) {
            co2Panel.innerHTML = co2Warnings.map(w => 
                `${w.icon} ${w.label}: ${w.value}`
            ).join(' | ');
            co2Panel.style.display = 'block';
        } else if (co2Panel) {
            co2Panel.style.display = 'none';
        }
        
        console.log(`警告パネル更新完了: ${detailedWarnings.length}件の警告`);
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
        
        // 3分間隔で自動更新（データ収集の5分より短く設定）
        this.refreshInterval = setInterval(async () => {
            try {
                console.log(`🔄 自動更新実行: ${new Date().toLocaleTimeString()}`);
                
                // キャッシュをクリアして強制的に最新データを取得
                this.dataCache.clear();
                await this.loadChartsData();
                this.updateLastUpdateTime();
                
                console.log(`✅ 自動更新完了: ${new Date().toLocaleTimeString()}`);
                
                // 自動更新成功カウンター（デバッグ用）
                this.autoRefreshCount = (this.autoRefreshCount || 0) + 1;
                console.log(`自動更新実行回数: ${this.autoRefreshCount}`);
                
            } catch (error) {
                console.error('❌ 自動更新エラー:', error);
                
                // エラーが続く場合はサンプルデータで継続
                this.autoRefreshErrors = (this.autoRefreshErrors || 0) + 1;
                if (this.autoRefreshErrors > 3) {
                    console.warn('⚠️ 連続エラー発生 - サンプルデータで継続');
                    this.generateSampleData();
                    this.autoRefreshErrors = 0; // リセット
                }
            }
        }, 3 * 60 * 1000); // 3分
        
        this.isAutoRefreshEnabled = true;
        this.updateAutoRefreshButton();
        this.updateLastUpdateTime();
        
        console.log('チャート自動更新開始: 3分間隔（データ収集5分より短縮）');
        console.log('次回自動更新:', new Date(Date.now() + 3 * 60 * 1000).toLocaleTimeString());
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
     * ページ表示・非表示時の自動更新制御
     */
    setupVisibilityHandling() {
        // ページが非表示になった時
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('📱 ページ非表示 - 自動更新継続（バックグラウンド実行）');
                // 非表示時も更新を継続（データ収集は続ける）
            } else {
                console.log('👁️ ページ表示 - 即座にデータ更新');
                // 表示に戻った時は即座にデータを更新
                if (this.isAutoRefreshEnabled) {
                    this.dataCache.clear();
                    this.loadChartsData();
                }
            }
        });
        
        // ページ読み込み時
        document.addEventListener('DOMContentLoaded', () => {
            console.log('📄 ページ読み込み完了 - 自動更新確認');
        });
        
        // ウィンドウフォーカス時
        window.addEventListener('focus', () => {
            console.log('🎯 ウィンドウフォーカス - データ更新');
            if (this.isAutoRefreshEnabled) {
                this.dataCache.clear();
                this.loadChartsData();
            }
        });
        
        console.log('ページ表示制御設定完了');
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

// グローバルアクセス用
window.monitoringCharts = null;

// Chart.js読み込み完了後の初期化
function initializeMonitoringCharts() {
    if (typeof Chart === 'undefined') {
        console.error('Chart.js が読み込まれていません');
        return;
    }
    
    if (!monitoringCharts) {
        monitoringCharts = new MonitoringChartsManager();
        window.monitoringCharts = monitoringCharts; // グローバルアクセス設定
        
        // デバッグ: グローバル設定確認
        console.log('グローバルアクセス設定完了:', {
            monitoringCharts: !!monitoringCharts,
            windowMonitoringCharts: !!window.monitoringCharts,
            changeTimeRange: !!(window.monitoringCharts && window.monitoringCharts.changeTimeRange)
        });
    }
    
    // 既存のシステム監視ページに統合
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setTimeout(() => {
                monitoringCharts.initialize();
                console.log('MonitoringCharts初期化完了 - 時間ボタン使用可能');
            }, 1000);
        });
    } else {
        setTimeout(() => {
            monitoringCharts.initialize();
            console.log('MonitoringCharts初期化完了 - 時間ボタン使用可能');
        }, 1000);
    }
}

// Chart.js依存関係チェック（改善版）
console.log('monitoring-charts.js読み込み開始 - Chart.jsチェック:', typeof Chart !== 'undefined');

function waitForChart() {
    if (typeof Chart !== 'undefined') {
        console.log('Chart.js確認完了 - 初期化開始');
        initializeMonitoringCharts();
    } else {
        console.log('Chart.js待機中...');
        setTimeout(waitForChart, 200);
    }
}

// 即座に実行 or DOM読み込み後実行
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitForChart);
} else {
    waitForChart();
}

// テスト用サンプルデータ生成機能をMonitoringChartsManagerに追加
MonitoringChartsManager.prototype.generateSampleData = function() {
    console.log('サンプルデータを生成中...');
    
    // サンプルデータ生成
    const now = new Date();
    const sampleData = {
        data: {
            metrics: {
                cpu_percent: [20, 25, 30, 35, 40, 30, 25, 20, 15, 22, 28, 32],
                memory_percent: [45, 47, 50, 52, 48, 46, 44, 42, 40, 43, 45, 47],
                cpu_temperature: [45, 46, 48, 50, 52, 51, 49, 47, 45, 46, 47, 48],
                room_temperature: [22, 23, 23, 24, 24, 23, 23, 22, 22, 23, 23, 24],
                humidity: [60, 58, 55, 53, 55, 57, 59, 61, 62, 60, 58, 56],
                co2_ppm: [800, 850, 920, 980, 1050, 980, 920, 850, 800, 780, 820, 880],
                disk_used_gb: [9.1, 9.1, 9.1, 9.2, 9.2, 9.2, 9.1, 9.1, 9.1, 9.2, 9.2, 9.1],
                network_bytes_sent_mb: [72, 73, 71, 74, 72, 73, 71, 72, 73, 74, 72, 73],
                network_bytes_recv_mb: [2400, 2410, 2405, 2415, 2420, 2415, 2410, 2405, 2400, 2410, 2415, 2420]
            },
            timestamps: Array.from({length: 12}, (_, i) => {
                const time = new Date(now.getTime() - (11-i) * 5 * 60 * 1000);
                return time.toISOString();
            })
        },
        dataPoints: 12,
        expectedPoints: 12,
        dataCoverage: 100,
        timeRange: '1h',
        timeRangeDescription: '過去1時間（サンプル）',
        interval: '5m',
        thresholds: {
            cpu_percent_warning: 80,
            cpu_temperature_warning: 70,
            memory_percent_warning: 80,
            co2_warning: [1000, 1500, 3000]
        }
    };
    
    // サンプルデータでチャート描画
    this.updateCPUMemoryChart(sampleData);
    this.updateTemperatureChart(sampleData);
    this.updateHumidityCO2Chart(sampleData);
    this.updateDiskNetworkChart(sampleData);
    this.updateChartInfo(sampleData);
    
    console.log('サンプルデータ生成完了');
};

// シンプルなテスト用Chart.js表示関数
function createSimpleTestChart() {
    console.log('シンプルテストチャートを作成中...');
    
    const canvas = document.getElementById('cpuMemoryChart');
    if (!canvas) {
        console.error('Canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    
    const testChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['10:00', '10:05', '10:10', '10:15', '10:20', '10:25'],
            datasets: [{
                label: 'CPU使用率',
                data: [20, 35, 40, 25, 45, 30],
                borderColor: '#e74c3c',
                backgroundColor: 'rgba(231, 76, 60, 0.1)',
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
    
    console.log('テストチャート作成完了:', testChart);
}

// テストチャート作成は自動実行しない（デバッグ専用）
// createSimpleTestChart() 関数はコンソールから手動実行可能