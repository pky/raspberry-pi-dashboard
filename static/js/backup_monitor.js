/**
 * バックアップ状態監視・リアルタイム更新システム
 * T2.3 バックアップ状態監視機能
 */

class BackupMonitor {
    constructor() {
        this.updateInterval = 30000; // 30秒間隔
        this.intervalId = null;
        this.isMonitoring = false;
        this.lastUpdate = null;
        this.retryCount = 0;
        this.maxRetries = 3;
        
        // WebSocket接続設定（将来拡張用）
        this.wsEnabled = false;
        this.wsConnection = null;
        
        this.init();
    }
    
    init() {
        console.log('BackupMonitor: Initializing backup monitoring system');
        
        // ページ可視性変更の監視
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopMonitoring();
            } else {
                this.startMonitoring();
            }
        });
        
        // ウィンドウフォーカス/ブラー監視
        window.addEventListener('focus', () => this.onWindowFocus());
        window.addEventListener('blur', () => this.onWindowBlur());
        
        // 初期状態確認
        this.checkInitialStatus();
    }
    
    async checkInitialStatus() {
        try {
            const response = await fetch('/api/backup/status');
            const data = await response.json();
            
            if (data.success) {
                this.updateBackupStatus(data.data);
                console.log('BackupMonitor: Initial status loaded successfully');
            }
        } catch (error) {
            console.error('BackupMonitor: Failed to load initial status:', error);
        }
        
        // 監視開始
        this.startMonitoring();
    }
    
    startMonitoring() {
        if (this.isMonitoring) {
            console.log('BackupMonitor: Monitoring already active');
            return;
        }
        
        console.log('BackupMonitor: Starting status monitoring');
        this.isMonitoring = true;
        this.retryCount = 0;
        
        this.intervalId = setInterval(() => {
            this.updateStatus();
        }, this.updateInterval);
        
        // 即座に1回実行
        this.updateStatus();
    }
    
    stopMonitoring() {
        if (!this.isMonitoring) return;
        
        console.log('BackupMonitor: Stopping status monitoring');
        this.isMonitoring = false;
        
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }
    
    async updateStatus() {
        try {
            const [statusResponse, statisticsResponse] = await Promise.all([
                fetch('/api/backup/status'),
                fetch('/api/backup/statistics')
            ]);
            
            // レスポンス確認
            if (!statusResponse.ok) {
                throw new Error(`Status API failed: ${statusResponse.status}`);
            }
            if (!statisticsResponse.ok) {
                throw new Error(`Statistics API failed: ${statisticsResponse.status}`);
            }
            
            const statusData = await statusResponse.json();
            const statsData = await statisticsResponse.json();
            
            if (statusData.success && statsData.success) {
                this.updateBackupStatus(statusData.data);
                this.updateStatistics(statsData.data);
                this.updateLastUpdateTime();
                this.retryCount = 0; // リセット
            } else {
                throw new Error(`API Error: Status=${statusData.success}, Stats=${statsData.success}`);
            }
            
        } catch (error) {
            console.error('BackupMonitor: Status update failed:', error);
            this.handleUpdateError(error);
        }
    }
    
    updateBackupStatus(statusData) {
        // 現在実行中の操作があるかチェック
        const isOperationRunning = statusData.current_operation || 
                                  statusData.backup_in_progress || 
                                  statusData.restore_in_progress;
        
        // プログレスバーの表示制御
        const progressWrapper = document.getElementById('progress-wrapper');
        if (progressWrapper && isOperationRunning) {
            progressWrapper.style.display = 'block';
            
            const progressBar = document.getElementById('progress-bar');
            const operationStatus = document.getElementById('operation-status');
            
            if (progressBar && operationStatus) {
                // プログレス情報を更新
                const progress = statusData.operation_progress || 0;
                const operation = statusData.current_operation || '操作実行中';
                
                progressBar.style.width = `${progress}%`;
                operationStatus.textContent = `${operation} (${progress}%)`;
                
                if (progress < 100) {
                    progressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
                } else {
                    progressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
                }
            }
        } else if (progressWrapper) {
            progressWrapper.style.display = 'none';
        }
        
        // スケジュール状態の更新
        this.updateScheduleStatus(statusData.schedule_status);
        
        // 最新バックアップ状態の更新
        this.updateLatestBackupInfo(statusData.latest_backup);
    }
    
    updateStatistics(statsData) {
        // 統計情報の更新
        const elements = {
            'total-backups': statsData.total_backups || 0,
            'latest-backup': this.formatRelativeTime(statsData.latest_backup_time),
            'total-size': statsData.total_size_formatted || '0B',
            'success-rate': Math.round(statsData.success_rate || 0) + '%'
        };
        
        for (const [elementId, value] of Object.entries(elements)) {
            const element = document.getElementById(elementId);
            if (element) {
                element.textContent = value;
            }
        }
        
        // 成功率に基づく色の変更
        this.updateSuccessRateColor(statsData.success_rate || 0);
    }
    
    updateScheduleStatus(scheduleStatus) {
        // スケジュール状態インジケーター
        const scheduleIndicator = document.getElementById('schedule-status');
        if (scheduleIndicator && scheduleStatus) {
            const isEnabled = scheduleStatus.daily_enabled;
            const nextRun = scheduleStatus.next_run_time;
            
            scheduleIndicator.className = `badge ${isEnabled ? 'bg-success' : 'bg-warning'}`;
            scheduleIndicator.textContent = isEnabled ? 
                `次回実行: ${this.formatRelativeTime(nextRun)}` : 
                'スケジュール無効';
        }
    }
    
    updateLatestBackupInfo(latestBackup) {
        const latestInfo = document.getElementById('latest-backup-info');
        if (latestInfo && latestBackup) {
            const status = latestBackup.status;
            const timestamp = latestBackup.timestamp;
            const sizeFormatted = latestBackup.size_formatted;
            
            latestInfo.innerHTML = `
                <small class="text-muted">
                    最新: ${this.formatRelativeTime(timestamp)}
                    <span class="badge bg-${this.getStatusColor(status)} ms-1">${status}</span>
                    ${sizeFormatted ? `(${sizeFormatted})` : ''}
                </small>
            `;
        }
    }
    
    updateSuccessRateColor(successRate) {
        const element = document.getElementById('success-rate');
        if (!element) return;
        
        const parentCard = element.closest('.stats-card');
        if (!parentCard) return;
        
        // 成功率に基づいて色を変更
        if (successRate >= 95) {
            parentCard.style.background = 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)';
        } else if (successRate >= 80) {
            parentCard.style.background = 'linear-gradient(135deg, #ed8936 0%, #dd6b20 100%)';
        } else {
            parentCard.style.background = 'linear-gradient(135deg, #e53e3e 0%, #c53030 100%)';
        }
    }
    
    updateLastUpdateTime() {
        this.lastUpdate = new Date();
        const lastUpdateElement = document.getElementById('last-status-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `最終更新: ${this.lastUpdate.toLocaleTimeString('ja-JP')}`;
        }
    }
    
    handleUpdateError(error) {
        this.retryCount++;
        console.warn(`BackupMonitor: Update error (retry ${this.retryCount}/${this.maxRetries}):`, error);
        
        if (this.retryCount >= this.maxRetries) {
            console.error('BackupMonitor: Max retries reached, stopping monitoring');
            this.stopMonitoring();
            this.showConnectionError();
        } else {
            // エクスポネンシャルバックオフで再試行
            setTimeout(() => {
                if (this.isMonitoring) {
                    this.updateStatus();
                }
            }, 1000 * Math.pow(2, this.retryCount));
        }
    }
    
    showConnectionError() {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-warning alert-dismissible fade show';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle me-1"></i>
            <strong>接続エラー:</strong> バックアップ状態の監視が停止しました。ページを更新してください。
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container-fluid');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            // 10秒後に自動削除
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, 10000);
        }
    }
    
    onWindowFocus() {
        console.log('BackupMonitor: Window focused, resuming monitoring');
        if (!this.isMonitoring) {
            this.startMonitoring();
        }
        // フォーカス時に即座に更新
        this.updateStatus();
    }
    
    onWindowBlur() {
        console.log('BackupMonitor: Window blurred');
        // バックグラウンドでは監視頻度を下げる
        if (this.isMonitoring) {
            this.stopMonitoring();
            
            // 5分間隔で監視継続
            this.intervalId = setInterval(() => {
                this.updateStatus();
            }, 300000); // 5分
        }
    }
    
    // ユーティリティ関数
    formatRelativeTime(timestamp) {
        if (!timestamp) return 'なし';
        
        const now = new Date();
        const time = new Date(timestamp);
        const diffMs = now - time;
        const diffMinutes = Math.floor(diffMs / (1000 * 60));
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffMinutes < 1) return 'たった今';
        if (diffMinutes < 60) return `${diffMinutes}分前`;
        if (diffHours < 24) return `${diffHours}時間前`;
        if (diffDays < 7) return `${diffDays}日前`;
        
        return time.toLocaleDateString('ja-JP');
    }
    
    formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 MB';
        
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        const k = 1024;
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + units[i];
    }
    
    getStatusColor(status) {
        switch(status) {
            case 'completed': 
            case 'success': return 'success';
            case 'failed': 
            case 'error': return 'danger';
            case 'running': 
            case 'in_progress': return 'primary';
            case 'warning': return 'warning';
            default: return 'secondary';
        }
    }
    
    // 外部から呼び出し可能なメソッド
    forceUpdate() {
        console.log('BackupMonitor: Force update requested');
        this.updateStatus();
    }
    
    restart() {
        console.log('BackupMonitor: Restart requested');
        this.stopMonitoring();
        setTimeout(() => {
            this.startMonitoring();
        }, 1000);
    }
    
    setUpdateInterval(intervalMs) {
        if (intervalMs < 5000) {
            console.warn('BackupMonitor: Minimum interval is 5 seconds');
            intervalMs = 5000;
        }
        
        this.updateInterval = intervalMs;
        console.log(`BackupMonitor: Update interval set to ${intervalMs}ms`);
        
        if (this.isMonitoring) {
            this.restart();
        }
    }
}

// グローバルインスタンス
let backupMonitor = null;

// DOM読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', function() {
    // バックアップ管理ページでのみ監視を開始
    if (window.location.pathname === '/backup' || 
        document.getElementById('backup-list')) {
        
        console.log('BackupMonitor: Initializing on backup management page');
        backupMonitor = new BackupMonitor();
        
        // グローバルアクセス用
        window.backupMonitor = backupMonitor;
    }
});

// バックアップ操作完了時に手動で更新をトリガーするヘルパー関数
window.notifyBackupOperationComplete = function(operationType) {
    console.log(`BackupMonitor: Backup operation completed: ${operationType}`);
    if (backupMonitor) {
        // 操作完了後は少し待ってから更新
        setTimeout(() => {
            backupMonitor.forceUpdate();
        }, 2000);
    }
};

// デバッグ用関数（開発環境でのみ使用）
window.debugBackupMonitor = function() {
    if (backupMonitor) {
        console.log('BackupMonitor Debug Info:', {
            isMonitoring: backupMonitor.isMonitoring,
            updateInterval: backupMonitor.updateInterval,
            lastUpdate: backupMonitor.lastUpdate,
            retryCount: backupMonitor.retryCount
        });
    } else {
        console.log('BackupMonitor: Not initialized');
    }
};