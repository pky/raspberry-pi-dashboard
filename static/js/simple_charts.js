/**
 * シンプル監視チャートシステム - JSONファイル方式
 * static/data/metrics.jsonから直接データ取得する軽量チャートライブラリ
 * 
 * 機能:
 * - JSONファイル直読み (/static/data/metrics.json)
 * - 時間範囲切り替え (1h/6h/12h/24h)
 * - 自動更新 (30秒間隔)
 * - レスポンシブデザイン
 */

console.log('🚀 === SIMPLE_CHARTS.JS FILE LOADED ===');
console.log('📅 File loaded at:', new Date().toISOString());
console.log('🌐 User Agent:', navigator.userAgent);
console.log('📍 Location:', window.location.href);

class SimpleMonitoringCharts {
    constructor() {
        this.charts = {};
        this.currentData = null;
        this.currentRange = '1h';
        this.updateInterval = null;
        this.refreshRate = 300000; // 5分間隔（データ収集間隔に合わせる）
        
        this.init();
    }

    async init() {
        console.log('[SimpleCharts] 初期化開始');
        
        try {
            // DOM読み込み確認
            if (document.readyState === 'loading') {
                console.log('[SimpleCharts] DOM読み込み待機中...');
                await new Promise(resolve => {
                    document.addEventListener('DOMContentLoaded', resolve);
                });
            }
            
            // 初回データ読み込み
            await this.loadData();
            
            // チャート作成
            this.createCharts();
            
            // イベントリスナー設定
            this.setupEventListeners();
            
            // 自動更新開始
            this.startAutoUpdate();
            
            console.log('[SimpleCharts] 初期化完了');
            
        } catch (error) {
            console.error('[SimpleCharts] 初期化エラー:', error);
            this.showError('システムの初期化に失敗しました');
        }
    }

    async loadData() {
        try {
            console.log(`[SimpleCharts] JSONファイルデータ読み込み開始: ${this.currentRange}`);
            
            // JSONファイル読み込み
            const response = await fetch(`/static/data/metrics.json?cache_bust=${Date.now()}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: JSONファイル読み込みエラー`);
            }
            
            this.currentData = await response.json();
            
            // データ検証
            if (!this.currentData || !this.currentData.metrics || !Array.isArray(this.currentData.metrics)) {
                throw new Error('JSONファイルからのデータが無効です');
            }
            
            console.log(`[SimpleCharts] JSONファイルデータ読み込み完了: ${this.currentData.metrics.length} データポイント`);
            
            // 状態表示更新
            this.updateStatus();
            
        } catch (error) {
            console.error('[SimpleCharts] JSONファイル読み込みエラー:', error);
            throw error;
        }
    }

    filterDataByRange(data, range) {
        // JSONファイルシステム復元 - 時間範囲フィルタリング + データポイント密度調整 + フォールバック
        if (!data || !data.metrics) {
            console.warn('[SimpleCharts] データがないか、metricsプロパティがありません');
            return [];
        }
        
        console.log(`[SimpleCharts] JSONファイルデータ: ${data.metrics.length}ポイント (時間範囲: ${range})`);
        
        const now = new Date();
        const cutoffTime = new Date(now);
        
        // 時間範囲設定
        switch (range) {
            case '1h':
                cutoffTime.setHours(now.getHours() - 1);
                break;
            case '6h':
                cutoffTime.setHours(now.getHours() - 6);
                break;
            case '12h':
                cutoffTime.setHours(now.getHours() - 12);
                break;
            case '24h':
                cutoffTime.setDate(now.getDate() - 1);
                break;
            default:
                cutoffTime.setHours(now.getHours() - 1);
        }
        
        // 詳細デバッグ情報追加
        console.log(`[SimpleCharts] 現在時刻: ${now.toISOString()}`);
        console.log(`[SimpleCharts] カットオフ時刻: ${cutoffTime.toISOString()}`);
        
        // データフィルタリング
        let filteredData = data.metrics.filter((metric, index) => {
            try {
                const metricTime = new Date(metric.timestamp);
                const isIncluded = metricTime >= cutoffTime;
                
                // 最初の3個と最後の3個のデータについて詳細ログ
                if (index < 3 || index >= data.metrics.length - 3) {
                    console.log(`[SimpleCharts] [${index}] ${metric.timestamp} → ${metricTime.toISOString()} (${isIncluded ? '含む' : '除外'})`);
                }
                
                return isIncluded;
            } catch (e) {
                console.warn('[SimpleCharts] 無効なタイムスタンプ:', metric.timestamp, e);
                return false;
            }
        });
        
        console.log(`[SimpleCharts] フィルタリング結果: ${filteredData.length}ポイント (${range}範囲)`);
        
        // データ不足の場合の処理
        if (filteredData.length === 0) {
            console.warn(`[SimpleCharts] ${range}範囲にデータが存在しません`);
            this.showError(`${range}範囲にデータがありません。データ収集システムを確認してください。`);
            return [];
        } else if (filteredData.length < 3) {
            console.warn(`[SimpleCharts] ${range}範囲のデータが不足 (${filteredData.length}ポイント)`);
            this.showWarning(`${range}範囲のデータが不足しています（${filteredData.length}ポイントのみ）。`);
        } else {
            // 正常にフィルタリングできた場合は警告を非表示
            this.hideWarning();
        }
        
        // データポイント密度調整（5分間隔データ収集前提）
        const thinningFactor = this.getThinningFactor(range, filteredData.length);
        const thinnedData = this.thinData(filteredData, thinningFactor);
        
        console.log(`[SimpleCharts] 間引き後データ: ${thinnedData.length}ポイント (間引き係数: ${thinningFactor})`);
        return thinnedData;
    }

    getThinningFactor(range, dataPointCount) {
        // 時間範囲とデータ点数に基づく間引き係数決定
        // 目標: 1時間 = 12ポイント（5分間隔）、6時間 = 24ポイント（15分間隔）、12時間 = 24ポイント（30分間隔）、24時間 = 24ポイント（1時間間隔）
        let maxPoints;
        
        switch (range) {
            case '1h':
                maxPoints = 12;  // 5分間隔 → 12ポイント
                break;
            case '6h':
                maxPoints = 24;  // 15分間隔相当 → 24ポイント
                break;
            case '12h':
                maxPoints = 24;  // 30分間隔相当 → 24ポイント
                break;
            case '24h':
                maxPoints = 24;  // 1時間間隔相当 → 24ポイント
                break;
            default:
                maxPoints = 12;
        }
        
        // 間引き係数計算（最小値は1、最大値は適切に制限）
        const thinningFactor = Math.max(1, Math.ceil(dataPointCount / maxPoints));
        return Math.min(thinningFactor, 10); // 最大10倍間引きで制限
    }

    thinData(data, thinningFactor) {
        // 間引き係数に基づくデータ間引き
        if (thinningFactor <= 1 || data.length <= 1) {
            return data; // 間引き不要
        }
        
        const thinnedData = [];
        for (let i = 0; i < data.length; i += thinningFactor) {
            thinnedData.push(data[i]);
        }
        
        // 最新のデータポイントを確実に含める
        if (data.length > 0 && thinnedData[thinnedData.length - 1] !== data[data.length - 1]) {
            thinnedData.push(data[data.length - 1]);
        }
        
        return thinnedData;
    }

    createCharts() {
        console.log('[SimpleCharts] チャート作成開始');
        console.log('[SimpleCharts] 元データ:', this.currentData);
        
        try {
            // 既存チャート破棄
            this.destroyCharts();
            
            // データフィルタリング
            let filteredData = this.filterDataByRange(this.currentData, this.currentRange);
            console.log(`[SimpleCharts] フィルター後データ: ${filteredData.length}個`);
            console.log('[SimpleCharts] フィルター後データ詳細:', filteredData);
            
            if (filteredData.length === 0) {
                console.warn(`[SimpleCharts] ${this.currentRange}範囲にデータがありません - 全データを表示`);
                filteredData = this.currentData.metrics.slice(); // 全データを使用
                this.showWarning(`${this.currentRange}範囲のデータが不足しています。利用可能な全データ（${filteredData.length}個、約${Math.round(filteredData.length * 5 / 60)}分間）を表示中。`);
                
                if (filteredData.length === 0) {
                    console.error('[SimpleCharts] データが全くありません');
                    this.showError('監視データがありません');
                    return;
                }
            } else {
                // 正常にフィルタリングできた場合は警告を非表示
                const warningPanel = document.getElementById('chart-warning-panel');
                if (warningPanel) {
                    warningPanel.style.display = 'none';
                }
            }
            
            // 各チャート作成
            console.log('[SimpleCharts] CPUメモリチャート作成開始');
            this.createCpuMemoryChart(filteredData);
            console.log('[SimpleCharts] 温度チャート作成開始');
            this.createTemperatureChart(filteredData);
            console.log('[SimpleCharts] センサーチャート作成開始');
            this.createSensorChart(filteredData);
            console.log('[SimpleCharts] CO2チャート作成開始');
            this.createCo2Chart(filteredData);
            
            console.log('[SimpleCharts] チャート作成完了');
            
        } catch (error) {
            console.error('[SimpleCharts] チャート作成エラー:', error);
            this.showError('グラフの作成に失敗しました');
        }
    }

    createCpuMemoryChart(data) {
        const ctx = document.getElementById('cpuMemoryChart');
        console.log('[SimpleCharts] cpuMemoryChart canvas要素:', ctx);
        if (!ctx) {
            console.warn('[SimpleCharts] cpuMemoryChart要素が見つかりません');
            return;
        }
        
        const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
        console.log('[SimpleCharts] CPUメモリチャート - labels:', labels);
        console.log('[SimpleCharts] CPUメモリチャート - CPU data:', data.map(d => d.cpu_percent));
        console.log('[SimpleCharts] CPUメモリチャート - Memory data:', data.map(d => d.memory_percent));
        
        this.charts.cpuMemory = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'CPU使用率 (%)',
                        data: data.map(d => d.cpu_percent),
                        borderColor: '#FF6384',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        tension: 0.1,
                        fill: true
                    },
                    {
                        label: 'メモリ使用率 (%)',
                        data: data.map(d => d.memory_percent),
                        borderColor: '#36A2EB',
                        backgroundColor: 'rgba(54, 162, 235, 0.1)',
                        tension: 0.1,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: value => value + '%'
                        }
                    },
                    x: {
                        display: true
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: 'CPU・メモリ使用率'
                    }
                }
            }
        });
        console.log('[SimpleCharts] CPUメモリチャート作成成功:', this.charts.cpuMemory);
    }

    createTemperatureChart(data) {
        const ctx = document.getElementById('temperatureChart');
        if (!ctx) {
            console.warn('[SimpleCharts] temperatureChart要素が見つかりません');
            return;
        }
        
        const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
        
        this.charts.temperature = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'CPU温度 (°C)',
                        data: data.map(d => d.cpu_temperature),
                        borderColor: '#FF9F40',
                        backgroundColor: 'rgba(255, 159, 64, 0.1)',
                        tension: 0.1,
                        fill: true
                    },
                    {
                        label: '室温 (°C)',
                        data: data.map(d => d.room_temperature),
                        borderColor: '#4BC0C0',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        tension: 0.1,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: value => value + '°C'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: '温度監視'
                    }
                }
            }
        });
    }

    createSensorChart(data) {
        const ctx = document.getElementById('sensorChart');
        if (!ctx) {
            console.warn('[SimpleCharts] sensorChart要素が見つかりません');
            return;
        }
        
        const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
        
        this.charts.sensor = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '湿度 (%)',
                        data: data.map(d => d.humidity),
                        borderColor: '#9966FF',
                        backgroundColor: 'rgba(153, 102, 255, 0.1)',
                        tension: 0.1,
                        fill: true,
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: value => value + '%'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: '湿度監視'
                    }
                }
            }
        });
    }

    createCo2Chart(data) {
        const ctx = document.getElementById('co2Chart');
        if (!ctx) {
            console.warn('[SimpleCharts] co2Chart要素が見つかりません');
            return;
        }
        
        const labels = data.map(d => new Date(d.timestamp).toLocaleTimeString());
        
        this.charts.co2 = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'CO2濃度 (ppm)',
                        data: data.map(d => d.co2_ppm),
                        borderColor: '#FF6B6B',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        tension: 0.1,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: value => value + ' ppm'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    title: {
                        display: true,
                        text: 'CO2濃度監視'
                    },
                    annotation: {
                        annotations: {
                            line1: {
                                type: 'line',
                                yMin: 1000,
                                yMax: 1000,
                                borderColor: 'orange',
                                borderWidth: 2,
                                label: {
                                    content: '注意レベル (1000ppm)',
                                    enabled: true
                                }
                            },
                            line2: {
                                type: 'line',
                                yMin: 1500,
                                yMax: 1500,
                                borderColor: 'red',
                                borderWidth: 2,
                                label: {
                                    content: '警告レベル (1500ppm)',
                                    enabled: true
                                }
                            }
                        }
                    }
                }
            }
        });
    }

    setupEventListeners() {
        // 時間範囲ボタン
        const rangeButtons = document.querySelectorAll('.time-range-btn');
        console.log(`[SimpleCharts] 時間範囲ボタン検索結果: ${rangeButtons.length}個見つかりました`);
        
        rangeButtons.forEach((btn, index) => {
            console.log(`[SimpleCharts] ボタン${index}: data-range="${btn.dataset.range}", text="${btn.textContent}"`);
            
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log(`[SimpleCharts] ボタンクリック検知: ${btn.dataset.range}`);
                const range = btn.dataset.range;
                if (range) {
                    this.changeTimeRange(range);
                } else {
                    console.error('[SimpleCharts] data-range属性がありません:', btn);
                }
            });
        });

        // 手動更新ボタン
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.manualRefresh();
            });
        }

        console.log('[SimpleCharts] イベントリスナー設定完了');
    }

    changeTimeRange(range) {
        console.log(`[SimpleCharts] 時間範囲変更開始: ${this.currentRange} → ${range}`);
        
        this.currentRange = range;
        
        // ボタン状態更新
        const allButtons = document.querySelectorAll('.time-range-btn');
        console.log(`[SimpleCharts] 全ボタン数: ${allButtons.length}`);
        
        allButtons.forEach(btn => {
            btn.classList.remove('active');
        });
        
        const targetButton = document.querySelector(`[data-range="${range}"]`);
        console.log(`[SimpleCharts] 対象ボタン検索結果:`, targetButton);
        
        if (targetButton) {
            targetButton.classList.add('active');
            console.log(`[SimpleCharts] ボタン状態更新完了: ${range}`);
        } else {
            console.error(`[SimpleCharts] ボタンが見つかりません: [data-range="${range}"]`);
        }
        
        // チャート更新
        console.log(`[SimpleCharts] チャート更新開始: ${range}`);
        this.createCharts();
        console.log(`[SimpleCharts] 時間範囲変更完了: ${range}`);
    }

    async manualRefresh() {
        console.log('[SimpleCharts] 手動更新開始');
        
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '更新中...';
        }
        
        try {
            await this.loadData();
            this.createCharts();
            console.log('[SimpleCharts] 手動更新完了');
        } catch (error) {
            console.error('[SimpleCharts] 手動更新エラー:', error);
            this.showError('データの更新に失敗しました');
        } finally {
            if (refreshBtn) {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '更新';
            }
        }
    }

    startAutoUpdate() {
        // 既存の自動更新停止
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        // 新しい自動更新開始
        this.updateInterval = setInterval(async () => {
            try {
                console.log('[SimpleCharts] 自動更新実行');
                await this.loadData();
                this.createCharts();
            } catch (error) {
                console.error('[SimpleCharts] 自動更新エラー:', error);
            }
        }, this.refreshRate);
        
        console.log(`[SimpleCharts] 自動更新開始 (${this.refreshRate/1000}秒間隔)`);
    }

    destroyCharts() {
        Object.keys(this.charts).forEach(key => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                delete this.charts[key];
            }
        });
    }

    updateStatus() {
        const statusElement = document.getElementById('chart-status');
        if (statusElement && this.currentData) {
            const lastUpdate = new Date(this.currentData.last_updated);
            const dataPoints = this.currentData.total_points || 0;
            
            statusElement.innerHTML = `
                <span class="status-ok">✅ 正常動作中</span> | 
                最終更新: ${lastUpdate.toLocaleString()} | 
                データ数: ${dataPoints}件
            `;
        }
    }

    showError(message) {
        const warningPanel = document.getElementById('chart-warning-panel');
        if (warningPanel) {
            warningPanel.style.display = 'block';
            warningPanel.className = 'alert alert-danger';
            warningPanel.innerHTML = `<strong>エラー:</strong> ${message}`;
        }
        console.error('[SimpleCharts] エラー表示:', message);
    }

    showWarning(message) {
        const warningPanel = document.getElementById('chart-warning-panel');
        if (warningPanel) {
            warningPanel.style.display = 'block';
            warningPanel.className = 'alert alert-warning';
            warningPanel.innerHTML = `<strong>警告:</strong> ${message}`;
        }
        console.warn('[SimpleCharts] 警告表示:', message);
    }

    hideWarning() {
        const warningPanel = document.getElementById('chart-warning-panel');
        if (warningPanel) {
            warningPanel.style.display = 'none';
        }
    }

    destroy() {
        console.log('[SimpleCharts] システム停止');
        
        // 自動更新停止
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        // チャート破棄
        this.destroyCharts();
    }
}

// グローバル変数
let simpleMonitoringCharts = null;

// 初期化関数
function initializeSimpleCharts() {
    console.log('[SimpleCharts] 初期化関数実行開始');
    
    // Chart.jsの読み込み確認
    if (typeof Chart === 'undefined') {
        console.error('[SimpleCharts] Chart.jsが読み込まれていません');
        document.getElementById('chart-warning-panel')?.style.setProperty('display', 'block');
        
        // 初期化ステータス更新
        const statusElement = document.getElementById('simple-charts-init-status');
        if (statusElement) {
            statusElement.textContent = '❌ Chart.js読み込み失敗';
        }
        return false;
    }
    
    try {
        // システム初期化
        simpleMonitoringCharts = new SimpleMonitoringCharts();
        
        // グローバル変数として公開（system_monitor.htmlから参照可能にする）
        window.simpleMonitoringCharts = simpleMonitoringCharts;
        
        // 初期化ステータス更新
        const statusElement = document.getElementById('simple-charts-init-status');
        if (statusElement) {
            statusElement.textContent = '✅ 初期化完了';
        }
        
        console.log('[SimpleCharts] ✅ 初期化成功 - グラフシステム利用可能');
        return true;
        
    } catch (error) {
        console.error('[SimpleCharts] ❌ 初期化エラー:', error);
        
        // 初期化ステータス更新
        const statusElement = document.getElementById('simple-charts-init-status');
        if (statusElement) {
            statusElement.textContent = '❌ 初期化エラー';
        }
        return false;
    }
}

// Chart.js読み込み待機とシステム初期化
function waitForChartJsAndInitialize(maxAttempts = 50, currentAttempt = 0) {
    if (typeof Chart !== 'undefined') {
        console.log(`[SimpleCharts] Chart.js読み込み確認完了 (${currentAttempt + 1}回目)`);
        return initializeSimpleCharts();
    }
    
    if (currentAttempt >= maxAttempts) {
        console.error('[SimpleCharts] Chart.js読み込みタイムアウト');
        const statusElement = document.getElementById('simple-charts-init-status');
        if (statusElement) {
            statusElement.textContent = '❌ Chart.js読み込みタイムアウト';
        }
        return false;
    }
    
    console.log(`[SimpleCharts] Chart.js読み込み待機中... (${currentAttempt + 1}/${maxAttempts})`);
    setTimeout(() => {
        waitForChartJsAndInitialize(maxAttempts, currentAttempt + 1);
    }, 100);
}

// DOM読み込み完了時に初期化（通常の読み込み）
document.addEventListener('DOMContentLoaded', () => {
    console.log('[SimpleCharts] DOMContentLoaded - Chart.js確認開始');
    waitForChartJsAndInitialize();
});

// 動的読み込み時の即座初期化
if (document.readyState === 'loading') {
    console.log('[SimpleCharts] DOM読み込み中 - DOMContentLoadedを待機');
} else {
    console.log('[SimpleCharts] DOM読み込み完了済み - Chart.js確認開始');
    waitForChartJsAndInitialize();
}

// ページ離脱時のクリーンアップ
window.addEventListener('beforeunload', () => {
    if (simpleMonitoringCharts) {
        simpleMonitoringCharts.destroy();
    }
});