/**
 * Raspberry Pi Dashboard JavaScript
 * フロントエンド機能とAPI通信を実装
 */

class Dashboard {
    constructor() {
        this.currentYear = new Date().getFullYear();
        this.currentMonth = new Date().getMonth() + 1;
        this.sensorUpdateInterval = null;
        this.calendarUpdateInterval = null;
        this.calendarData = null;
        this.lastCalendarUpdate = null;
        
        // 月替えボタン連続押下対策
        this.isLoadingCalendar = false;
        this.navigationButtons = null;
        this.currentCalendarRequest = null; // API呼び出しキャンセル用
        
        // 当日マーク更新用のタイマー（問題1対応）
        this.todayUpdateInterval = null;
        this.lastTodayCheck = null;
        
        this.init();
    }
    
    init() {
        console.log('Dashboard initializing...');
        
        // イベントリスナーの設定
        this.setupEventListeners();
        
        // 初期データの読み込み
        this.loadInitialData();
        
        // 定期更新の開始
        this.startPeriodicUpdates();
        
        // 現在時刻の更新（効率的な分単位更新）
        this.updateCurrentTime();
        this.startOptimizedTimeUpdate();
        
        // 当日マーク更新監視開始（問題1対応）
        this.startTodayUpdateMonitor();
        
        console.log('Dashboard initialized');
    }
    
    setupEventListeners() {
        // カレンダーナビゲーション
        this.navigationButtons = {
            prev: document.getElementById('prev-month'),
            next: document.getElementById('next-month')
        };
        
        this.navigationButtons.prev.addEventListener('click', () => {
            this.navigateMonth(-1);
        });
        
        this.navigationButtons.next.addEventListener('click', () => {
            this.navigateMonth(1);
        });
        
        // ページの可視性変更時の処理
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.stopPeriodicUpdates();
            } else {
                this.startPeriodicUpdates();
                this.loadSensorData(); // センサーデータのみ更新
                this.checkCalendarUpdate(); // カレンダーの更新チェック
            }
        });
        
        // 強制リロード機能（タッチパネル用）
        this.setupForceReload();
        
        // 手動更新ボタン（センサーデータ用）
        const refreshButton = document.getElementById('refresh-button');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => {
                this.forceRefreshSensor();
            });
        }
        
        // カレンダー強制更新ボタン
        const calendarRefreshButton = document.getElementById('calendar-refresh-button');
        if (calendarRefreshButton) {
            calendarRefreshButton.addEventListener('click', () => {
                this.forceRefreshCalendar();
            });
        }
    }
    
    async loadInitialData() {
        console.log('Loading initial data...');
        
        // システム状態の確認
        await this.checkSystemHealth();
        
        // センサーデータの読み込み
        await this.loadSensorData();
        
        // カレンダーデータの読み込み
        await this.loadCalendarData();
    }
    
    async checkSystemHealth() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            this.updateSystemStatus(data);
            
        } catch (error) {
            console.error('Health check failed:', error);
            this.updateSystemStatus({
                status: 'unhealthy',
                services: {
                    sensor: 'disconnected',
                    calendar: 'disconnected'
                }
            });
        }
    }
    
    updateSystemStatus(healthData) {
        const statusIndicator = document.getElementById('status-indicator');
        const statusDot = statusIndicator.querySelector('.status-dot');
        const statusText = statusIndicator.querySelector('.status-text');
        
        if (healthData.status === 'healthy') {
            statusDot.classList.add('connected');
            statusText.textContent = 'システム正常';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = 'システムエラー';
        }
    }
    
    async loadSensorData() {
        try {
            // センサーデータAPIからデータを取得
            const response = await fetch('/api/sensor');
            const result = await response.json();
            
            if (result.status === 'success') {
                this.updateSensorDisplay(result.data);
            } else {
                console.error('Sensor API error:', result.error);
                this.updateSensorDisplay({
                    temperature: null,
                    humidity: null,
                    discomfort_index: null,
                    discomfort_level: 'エラー',
                    timestamp: new Date().toISOString()
                });
            }
            
        } catch (error) {
            console.error('Failed to load sensor data:', error);
            this.updateSensorDisplay({
                temperature: null,
                humidity: null,
                discomfort_index: null,
                discomfort_level: 'エラー',
                timestamp: new Date().toISOString()
            });
        }
    }
    
    updateSensorDisplay(sensorData) {
        console.log('Updating sensor display with data:', sensorData);
        
        // 温度
        const tempElement = document.getElementById('temperature-value');
        if (tempElement) {
            const tempText = sensorData.temperature !== null 
                ? `${sensorData.temperature}°C` 
                : '--°C';
            tempElement.textContent = tempText;
            console.log('Updated temperature:', tempText);
        }
        
        // 湿度
        const humidityElement = document.getElementById('humidity-value');
        if (humidityElement) {
            const humidityText = sensorData.humidity !== null 
                ? `${sensorData.humidity}%` 
                : '--%';
            humidityElement.textContent = humidityText;
            console.log('Updated humidity:', humidityText);
        }
        
        // 不快度指数
        const discomfortElement = document.getElementById('discomfort-value');
        const discomfortLevelElement = document.getElementById('discomfort-level');
        const discomfortIconElement = document.querySelector('.discomfort-card .sensor-icon');
        
        if (discomfortElement) {
            const discomfortText = sensorData.discomfort_index !== null 
                ? sensorData.discomfort_index.toString() 
                : '--';
            discomfortElement.textContent = discomfortText;
            console.log('Updated discomfort index:', discomfortText);
        }
        
        if (discomfortLevelElement) {
            const levelText = sensorData.discomfort_level || '--';
            discomfortLevelElement.textContent = levelText;
            console.log('Updated discomfort level:', levelText);
        }
        
        // 不快度指数に応じてアイコンを変更
        if (discomfortIconElement && sensorData.discomfort_index !== null) {
            const discomfortIndex = sensorData.discomfort_index;
            let iconName = 'sentiment_satisfied'; // デフォルト
            
            if (discomfortIndex < 60) {
                iconName = 'ac_unit'; // 寒い（❄️）
            } else if (discomfortIndex < 65) {
                iconName = 'sentiment_neutral'; // 肌寒い（😐）
            } else if (discomfortIndex < 70) {
                iconName = 'sentiment_very_satisfied'; // 快適（😊）
            } else if (discomfortIndex < 75) {
                iconName = 'sentiment_satisfied'; // やや不快（🙂）
            } else if (discomfortIndex < 80) {
                iconName = 'sentiment_dissatisfied'; // 不快（😔）
            } else {
                iconName = 'sentiment_very_dissatisfied'; // 極めて不快（😣）
            }
            
            discomfortIconElement.textContent = iconName;
            console.log('Updated discomfort icon:', iconName);
        }
        
        // タイムスタンプ
        const timestampElement = document.getElementById('sensor-timestamp');
        if (timestampElement && sensorData.timestamp) {
            const date = new Date(sensorData.timestamp);
            const timeText = date.toLocaleString('ja-JP');
            timestampElement.textContent = timeText;
            console.log('Updated timestamp:', timeText);
        }
        
        // CO2データの更新
        const co2Value = sensorData.co2_ppm;
        const co2Level = sensorData.co2_level;
        const co2Color = sensorData.co2_color || 'gray';
        const co2Message = sensorData.co2_message || '';
        
        console.log('CO2 Debug - Value:', co2Value, 'Level:', co2Level, 'Color:', co2Color);
        
        // CO2値を表示（数字のみ、ppmは別要素）
        const co2ValueElement = document.getElementById('co2-value');
        if (co2ValueElement) {
            if (co2Value !== undefined && co2Value !== null) {
                co2ValueElement.textContent = co2Value;
                console.log('Updated CO2 value:', co2Value);
            } else {
                co2ValueElement.textContent = '--';
                console.warn('CO2 value is undefined or null');
            }
        } else {
            console.error('CO2 value element not found');
        }
        
        // CO2レベルを表示
        const co2LevelElement = document.getElementById('co2-level');
        if (co2LevelElement && co2Level) {
            co2LevelElement.textContent = co2Level;
            
            // レベルに応じた色設定
            const colorMap = {
                'green': '#4ade80',
                'yellow': '#facc15',
                'orange': '#fb923c',
                'red': '#f87171',
                'gray': '#9ca3af'
            };
            co2LevelElement.style.color = colorMap[co2Color] || colorMap.gray;
            console.log('Updated CO2 level:', co2Level, 'color:', co2Color);
        }
        
        // CO2アイコンの色を更新
        const co2IconElement = document.getElementById('co2-icon');
        if (co2IconElement) {
            const colorMap = {
                'green': '#4ade80',
                'yellow': '#facc15',
                'orange': '#fb923c',
                'red': '#f87171',
                'gray': '#9ca3af'
            };
            co2IconElement.style.color = colorMap[co2Color] || colorMap.gray;
        }
        
        // CO2警告メッセージ
        const co2WarningElement = document.getElementById('co2-warning-message');
        const co2MessageTextElement = document.getElementById('co2-message-text');
        if (co2WarningElement && co2MessageTextElement) {
            if (co2Message && co2Value >= 1500) {
                co2MessageTextElement.textContent = co2Message;
                co2WarningElement.style.display = 'block';
                co2WarningElement.style.backgroundColor = co2Color === 'red' ? '#f87171' : '#fb923c';
                co2WarningElement.style.color = 'white';
            } else {
                co2WarningElement.style.display = 'none';
            }
        }
        
        // 最終更新時刻を表示
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = `最終更新: ${new Date().toLocaleTimeString('ja-JP')}`;
        }
    }
    
    async loadCalendarData() {
        // 既に読み込み中の場合は現在のリクエストをキャンセル
        if (this.isLoadingCalendar && this.currentCalendarRequest) {
            console.log('Calendar loading in progress, cancelling previous request');
            this.currentCalendarRequest.abort();
            this.currentCalendarRequest = null;
        } else if (this.isLoadingCalendar) {
            console.log('Calendar loading in progress, skipping duplicate request');
            return;
        }
        
        try {
            // 問題2対応: 即座にオフラインデータを表示
            console.log('Loading calendar data with offline-first approach...');
            
            // Step 1: キャッシュ/オフラインデータを即座に表示
            const offlineData = await this.generateOfflineCalendarData();
            if (offlineData) {
                this.calendarData = offlineData;
                this.updateCalendarDisplay();
                console.log('Offline calendar data displayed first - no loading state needed');
            } else {
                // オフラインデータがない場合のみローディング表示
                this.setCalendarLoadingState(true);
            }
            
            // Step 2: API呼び出しを非同期で実行（オフライン表示をブロックしない）
            this.loadLiveCalendarData();
            
        } catch (error) {
            console.error('Failed to initialize calendar data:', error);
            // フォールバック: モックデータを表示
            this.calendarData = this.generateMockCalendarData();
            this.updateCalendarDisplay();
        }
    }
    
    // 問題2対応: オフラインファーストのカレンダーデータ生成
    async generateOfflineCalendarData() {
        const daysInMonth = new Date(this.currentYear, this.currentMonth, 0).getDate();
        const firstDayOfWeek = new Date(this.currentYear, this.currentMonth - 1, 1).getDay();
        
        const days = {};
        
        // 基本的なカレンダー構造を作成
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(this.currentYear, this.currentMonth - 1, day);
            const weekday = date.getDay();
            
            days[day] = {
                date: date,
                weekday: weekday,
                events: [],
                is_holiday: false,
                holiday_name: null
            };
        }
        
        // キャッシュから祝日・個人予定を非同期で読み込み
        try {
            const [holidayData, personalEvents] = await Promise.all([
                this.loadCachedHolidayData(),
                this.loadCachedPersonalEvents()
            ]);
            
            // 祝日をマージ
            if (holidayData && holidayData.holidays) {
                holidayData.holidays.forEach(holiday => {
                    const holidayDate = new Date(holiday.start_datetime);
                    if (holidayDate.getFullYear() === this.currentYear && 
                        holidayDate.getMonth() + 1 === this.currentMonth) {
                        const day = holidayDate.getDate();
                        if (days[day]) {
                            days[day].events.push(holiday);
                            days[day].is_holiday = true;
                            days[day].holiday_name = holiday.title;
                        }
                    }
                });
            }
            
            // 個人予定をマージ
            if (personalEvents && personalEvents.events) {
                personalEvents.events.forEach(event => {
                    const eventDate = new Date(event.start_datetime);
                    if (eventDate.getFullYear() === this.currentYear && 
                        eventDate.getMonth() + 1 === this.currentMonth) {
                        const day = eventDate.getDate();
                        if (days[day]) {
                            days[day].events.push(event);
                        }
                    }
                });
            }
            
        } catch (error) {
            console.log('Failed to load cached data, using basic calendar:', error);
        }
        
        return {
            year: this.currentYear,
            month: this.currentMonth,
            days_in_month: daysInMonth,
            first_day_weekday: firstDayOfWeek,
            days: days,
            offline_mode: true // オフラインモードフラグ
        };
    }
    
    // 問題2対応: ライブAPI呼び出し（非同期）
    async loadLiveCalendarData() {
        try {
            console.log('Loading live calendar data in background...');
            
            // AbortController を使用して API 呼び出しをキャンセル可能にする
            const controller = new AbortController();
            this.currentCalendarRequest = controller;
            
            // カレンダーAPIからデータを取得
            const response = await fetch(`/api/calendar?year=${this.currentYear}&month=${this.currentMonth}`, {
                signal: controller.signal
            });
            
            // リクエストが完了したのでコントローラーをクリア
            this.currentCalendarRequest = null;
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // ライブデータで更新
                this.calendarData = result.data.calendar_data;
                this.lastCalendarUpdate = new Date();
                this.updateCalendarDisplay();
                console.log('Live calendar data updated successfully');
                
                // キャッシュが更新された可能性があるため、再度オフラインデータをチェック
                this.checkForCacheUpdates();
                
            } else {
                console.warn('Live calendar API returned error:', result.error);
                // オフラインデータをそのまま維持
            }
            
        } catch (error) {
            // リクエストがキャンセルされた場合
            if (error.name === 'AbortError') {
                console.log('Live calendar request was cancelled');
                return;
            }
            
            console.warn('Failed to load live calendar data, keeping offline data:', error);
            // オフラインデータをそのまま維持
        } finally {
            // ライブAPIが完了したらローディング状態を終了
            this.setCalendarLoadingState(false);
        }
    }
    
    // キャッシュ更新をチェックして表示を更新
    async checkForCacheUpdates() {
        try {
            // 新しいキャッシュデータを取得
            const updatedOfflineData = await this.generateOfflineCalendarData();
            
            if (updatedOfflineData) {
                // 現在のデータと比較して更新があるかチェック
                const hasUpdates = this.hasCalendarDataChanged(this.calendarData, updatedOfflineData);
                
                if (hasUpdates) {
                    console.log('Cache updates detected, refreshing calendar display');
                    
                    // 更新されたキャッシュデータで表示を更新
                    this.calendarData = updatedOfflineData;
                    this.updateCalendarDisplay();
                    
                    // 画面に更新通知を表示
                    this.showCacheUpdateNotification();
                }
            }
        } catch (error) {
            console.log('Failed to check for cache updates:', error);
        }
    }
    
    // カレンダーデータに変更があるかチェック
    hasCalendarDataChanged(currentData, newData) {
        if (!currentData || !newData) return true;
        
        // イベント数の変化をチェック
        const currentEventCount = this.countTotalEvents(currentData);
        const newEventCount = this.countTotalEvents(newData);
        
        return currentEventCount !== newEventCount;
    }
    
    // 総イベント数をカウント
    countTotalEvents(calendarData) {
        if (!calendarData || !calendarData.days) return 0;
        
        let totalEvents = 0;
        Object.values(calendarData.days).forEach(day => {
            if (day.events) {
                totalEvents += day.events.length;
            }
        });
        
        return totalEvents;
    }
    
    // キャッシュ更新通知を表示
    showCacheUpdateNotification() {
        // 画面上部に更新通知を表示
        const notification = document.createElement('div');
        notification.className = 'cache-update-notification';
        notification.innerHTML = '📅 カレンダーデータが更新されました';
        notification.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            background: #28a745;
            color: white;
            padding: 10px 15px;
            border-radius: 5px;
            z-index: 1000;
            font-size: 14px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        `;
        
        document.body.appendChild(notification);
        
        // 3秒後に自動削除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
    
    // キャッシュされた祝日データを取得（オフライン対応）
    async loadCachedHolidayData() {
        try {
            // 祝日キャッシュJSONファイルから読み込み
            const response = await fetch(`/cache/holidays/holidays_${this.currentYear}.json`);
            if (response.ok) {
                const holidayData = await response.json();
                return holidayData;
            }
        } catch (error) {
            console.log('Cached holiday data not available:', error);
        }
        return null;
    }
    
    // キャッシュされた個人予定データを取得（オフライン対応）  
    async loadCachedPersonalEvents() {
        try {
            // 個人予定キャッシュJSONファイルから読み込み
            const cacheKey = `personal_events_${this.currentYear}_${String(this.currentMonth).padStart(2, '0')}.json`;
            const response = await fetch(`/cache/personal_events/${cacheKey}`);
            if (response.ok) {
                const eventsData = await response.json();
                return eventsData;
            }
        } catch (error) {
            console.log('Cached personal events not available:', error);
        }
        return null;
    }
    
    generateMockCalendarData() {
        const daysInMonth = new Date(this.currentYear, this.currentMonth, 0).getDate();
        const firstDayOfWeek = new Date(this.currentYear, this.currentMonth - 1, 1).getDay();
        
        const days = {};
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(this.currentYear, this.currentMonth - 1, day);
            const weekday = date.getDay(); // 0=日曜, 6=土曜
            
            // 土日祝日判定
            let dayType = 'weekday';
            if (weekday === 0) dayType = 'sunday';
            else if (weekday === 6) dayType = 'saturday';
            
            days[day] = {
                date: date,
                weekday: weekday,
                day_type: dayType,
                events: [],
                is_holiday: false,
                holiday_name: null
            };
            
            // サンプル祝日
            if (day === 1 && this.currentMonth === 1) {
                days[day].is_holiday = true;
                days[day].day_type = 'holiday';
                days[day].holiday_name = '元日';
            }
        }
        
        return {
            year: this.currentYear,
            month: this.currentMonth,
            days_in_month: daysInMonth,
            first_day_weekday: firstDayOfWeek,
            days: days,
            month_name: new Date(this.currentYear, this.currentMonth - 1).toLocaleDateString('ja-JP', { month: 'long' })
        };
    }
    
    updateCalendarDisplay() {
        if (!this.calendarData) return;
        
        // カレンダータイトルの更新
        this.updateCalendarTitle(`${this.calendarData.year}年${this.calendarData.month}月`);
        
        // カレンダーグリッドの更新
        const calendarGrid = document.getElementById('calendar-grid');
        calendarGrid.innerHTML = '';
        
        // 曜日ヘッダー
        const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
        weekdays.forEach(day => {
            const dayHeader = document.createElement('div');
            dayHeader.className = 'calendar-day-header';
            dayHeader.textContent = day;
            dayHeader.style.cssText = `
                background: #4a5568;
                color: white;
                font-weight: 600;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 10px;
                border-radius: 8px;
            `;
            calendarGrid.appendChild(dayHeader);
        });
        
        // 前月の日付を表示
        const firstDayOfWeek = this.calendarData.first_day_weekday;
        const prevMonth = this.currentMonth === 1 ? 12 : this.currentMonth - 1;
        const prevYear = this.currentMonth === 1 ? this.currentYear - 1 : this.currentYear;
        const prevMonthDays = new Date(prevYear, prevMonth, 0).getDate(); // 前月の日数
        
        for (let i = 0; i < firstDayOfWeek; i++) {
            const prevDay = prevMonthDays - firstDayOfWeek + i + 1;
            const prevDate = new Date(prevYear, prevMonth - 1, prevDay);
            
            const prevDayElement = this.createPrevNextMonthDayElement(prevDay, prevDate, 'prev-month');
            calendarGrid.appendChild(prevDayElement);
        }
        
        // 当月の日付表示
        for (let day = 1; day <= this.calendarData.days_in_month; day++) {
            const dayData = this.calendarData.days[day];
            const dayElement = this.createCalendarDayElement(day, dayData);
            calendarGrid.appendChild(dayElement);
        }
        
        // 翌月の日付を表示（グリッドを42日（6週間）で埋める）
        const totalDaysShown = firstDayOfWeek + this.calendarData.days_in_month;
        const remainingDays = 42 - totalDaysShown; // 6週間 * 7日 = 42日
        const nextMonth = this.currentMonth === 12 ? 1 : this.currentMonth + 1;
        const nextYear = this.currentMonth === 12 ? this.currentYear + 1 : this.currentYear;
        
        for (let day = 1; day <= remainingDays; day++) {
            const nextDate = new Date(nextYear, nextMonth - 1, day);
            const nextDayElement = this.createPrevNextMonthDayElement(day, nextDate, 'next-month');
            calendarGrid.appendChild(nextDayElement);
        }
    }
    
    createCalendarDayElement(day, dayData) {
        const dayElement = document.createElement('div');
        dayElement.className = 'calendar-day';
        
        // 今日の日付をハイライト
        const today = new Date();
        const dayDate = new Date(dayData.date);
        if (dayDate.toDateString() === today.toDateString()) {
            dayElement.classList.add('today');
        }
        
        // デバッグ情報
        if (day === 11) {
            console.log('8月11日のデータ:', dayData);
            console.log('day_type:', dayData.day_type);
            console.log('is_holiday:', dayData.is_holiday);
        }
        
        // 土日祝日のスタイル
        if (dayData.day_type) {
            dayElement.classList.add(dayData.day_type);
            if (day === 11) console.log('day_type クラス追加:', dayData.day_type);
        }
        
        // 祝日のスタイル（後方互換性）
        if (dayData.is_holiday) {
            dayElement.classList.add('holiday');
            if (day === 11) console.log('holiday クラス追加');
        }
        
        // イベントがある日のスタイル
        if (dayData.events && dayData.events.length > 0) {
            dayElement.classList.add('has-events');
        }
        
        // 日付番号
        const dayNumber = document.createElement('div');
        dayNumber.className = 'day-number';
        dayNumber.textContent = day;
        dayElement.appendChild(dayNumber);
        
        // 祝日名表示
        if (dayData.holiday_name) {
            const holidayElement = document.createElement('div');
            holidayElement.className = 'day-events';
            holidayElement.textContent = dayData.holiday_name;
            dayElement.appendChild(holidayElement);
        }
        // イベント表示
        else if (dayData.events && dayData.events.length > 0) {
            const eventsElement = document.createElement('div');
            eventsElement.className = 'day-events';
            
            const eventText = dayData.events.length === 1 
                ? dayData.events[0].title 
                : `${dayData.events.length}件`;
            
            eventsElement.textContent = eventText;
            dayElement.appendChild(eventsElement);
        }
        
        return dayElement;
    }
    
    createPrevNextMonthDayElement(day, date, monthType) {
        const dayElement = document.createElement('div');
        dayElement.className = `calendar-day ${monthType}`;
        
        // 土日祝日の判定
        const weekday = date.getDay(); // 0=日曜, 6=土曜
        if (weekday === 0) {
            dayElement.classList.add('sunday');
        } else if (weekday === 6) {
            dayElement.classList.add('saturday');
        }
        
        // 日付番号
        const dayNumber = document.createElement('div');
        dayNumber.className = 'day-number';
        dayNumber.textContent = day;
        dayElement.appendChild(dayNumber);
        
        return dayElement;
    }
    
    updateCalendarTitle(title) {
        document.getElementById('calendar-title').textContent = title;
    }
    
    navigateMonth(direction) {
        // 読み込み中の場合は処理をスキップ
        if (this.isLoadingCalendar) {
            console.log(`Navigation blocked: Calendar loading in progress (${this.currentYear}年${this.currentMonth}月)`);
            return;
        }
        
        const prevMonth = this.currentMonth;
        const prevYear = this.currentYear;
        
        this.currentMonth += direction;
        
        if (this.currentMonth > 12) {
            this.currentMonth = 1;
            this.currentYear++;
        } else if (this.currentMonth < 1) {
            this.currentMonth = 12;
            this.currentYear--;
        }
        
        console.log(`Navigation: ${prevYear}年${prevMonth}月 → ${this.currentYear}年${this.currentMonth}月`);
        this.loadCalendarData();
    }
    
    /**
     * カレンダー読み込み状態の管理
     * @param {boolean} isLoading - 読み込み中かどうか
     */
    setCalendarLoadingState(isLoading) {
        this.isLoadingCalendar = isLoading;
        
        // ボタンの無効化/有効化
        if (this.navigationButtons) {
            this.navigationButtons.prev.disabled = isLoading;
            this.navigationButtons.next.disabled = isLoading;
            
            // 視覚的フィードバック（スタイルクラス追加）
            if (isLoading) {
                this.navigationButtons.prev.classList.add('loading');
                this.navigationButtons.next.classList.add('loading');
                
                // 読み込み中のカーソル表示
                document.body.style.cursor = 'wait';
            } else {
                this.navigationButtons.prev.classList.remove('loading');
                this.navigationButtons.next.classList.remove('loading');
                
                // カーソルを通常に戻す
                document.body.style.cursor = 'default';
            }
        }
        
        // ステータス表示の更新
        this.updateStatusIndicator(isLoading);
        
        // カレンダーグリッドの読み込み状態表示
        this.updateCalendarGridLoadingState(isLoading);
        
        // デバッグ情報
        console.log(`Calendar loading state: ${isLoading ? 'LOADING' : 'READY'}`);
    }
    
    /**
     * ステータスインジケーターを更新
     * @param {boolean} isLoading - 読み込み中かどうか
     */
    updateStatusIndicator(isLoading) {
        const statusIndicator = document.getElementById('status-indicator');
        const statusDot = statusIndicator?.querySelector('.status-dot');
        const statusText = statusIndicator?.querySelector('.status-text');
        
        if (statusIndicator && statusDot && statusText) {
            if (isLoading) {
                statusIndicator.classList.add('loading');
                statusDot.classList.add('loading');
                statusText.textContent = 'カレンダー読み込み中...';
            } else {
                statusIndicator.classList.remove('loading');
                statusDot.classList.remove('loading');
                statusText.textContent = 'Ready';
            }
        }
    }
    
    /**
     * カレンダーグリッドの読み込み状態表示
     * @param {boolean} isLoading - 読み込み中かどうか
     */
    updateCalendarGridLoadingState(isLoading) {
        const calendarGrid = document.getElementById('calendar-grid');
        
        if (!calendarGrid) return;
        
        if (isLoading) {
            // 読み込み中のオーバーレイ表示
            calendarGrid.classList.add('loading-overlay');
            
            // 既存のグリッドを半透明に
            const existingDays = calendarGrid.querySelectorAll('.calendar-day');
            existingDays.forEach(day => {
                day.style.opacity = '0.5';
                day.style.pointerEvents = 'none';
            });
            
        } else {
            // 読み込み完了時の状態復元
            calendarGrid.classList.remove('loading-overlay');
            
            const allDays = calendarGrid.querySelectorAll('.calendar-day');
            allDays.forEach(day => {
                day.style.opacity = '1';
                day.style.pointerEvents = 'auto';
            });
        }
    }
    
    startPeriodicUpdates() {
        // センサーデータを5分ごとに更新
        this.sensorUpdateInterval = setInterval(() => {
            this.loadSensorData();
        }, 300000); // 5分 = 300,000ミリ秒
        
        // カレンダーデータを1日1回更新（午前4時に更新）
        this.calendarUpdateInterval = setInterval(() => {
            this.checkCalendarUpdate();
        }, 3600000); // 1時間ごとにチェック
    }
    
    stopPeriodicUpdates() {
        if (this.sensorUpdateInterval) {
            clearInterval(this.sensorUpdateInterval);
            this.sensorUpdateInterval = null;
        }
        if (this.calendarUpdateInterval) {
            clearInterval(this.calendarUpdateInterval);
            this.calendarUpdateInterval = null;
        }
    }
    
    // カレンダー更新チェック（1日1回、午前4時）
    checkCalendarUpdate() {
        const now = new Date();
        const hour = now.getHours();
        
        // 午前4時台にチェック
        if (hour === 4) {
            // 最後の更新が今日でない場合は更新
            if (!this.lastCalendarUpdate || 
                this.lastCalendarUpdate.toDateString() !== now.toDateString()) {
                console.log('Daily calendar update triggered');
                this.loadCalendarData();
            }
        }
    }
    
    updateCurrentTime() {
        const now = new Date();
        
        // 時刻のフォーマット（秒を除外して軽量化）
        const timeString = now.toLocaleString('ja-JP', {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // 日付のフォーマット
        const dateString = now.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            weekday: 'short'
        });
        
        // ヘッダーの時刻表示を更新
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = timeString;
        }
        
        const dateElement = document.getElementById('current-date');
        if (dateElement) {
            dateElement.textContent = dateString;
        }
    }
    
    startOptimizedTimeUpdate() {
        // 現在の分を保存
        let lastMinute = new Date().getMinutes();
        
        // 効率的な時刻更新：分が変わった時のみ更新
        const checkTimeUpdate = () => {
            const currentMinute = new Date().getMinutes();
            if (currentMinute !== lastMinute) {
                this.updateCurrentTime();
                lastMinute = currentMinute;
            }
        };
        
        // 15秒毎にチェック（最大15秒の遅延で分単位更新を保証）
        setInterval(checkTimeUpdate, 15000);
    }
    
    // タッチパネル用の強制リロード機能
    setupForceReload() {
        // 画面右上隅をタップでページリロード
        let tapCount = 0;
        let tapTimer = null;
        
        document.addEventListener('click', (event) => {
            const x = event.clientX;
            const y = event.clientY;
            const screenWidth = window.innerWidth;
            const screenHeight = window.innerHeight;
            
            // 右上隅の100x100pxエリアをタップ
            if (x > screenWidth - 100 && y < 100) {
                tapCount++;
                
                if (tapTimer) clearTimeout(tapTimer);
                
                if (tapCount >= 3) {
                    // 3回タップでページリロード
                    console.log('Force reload triggered');
                    location.reload();
                } else {
                    // 2秒以内に3回タップしなければリセット
                    tapTimer = setTimeout(() => {
                        tapCount = 0;
                    }, 2000);
                }
            } else {
                tapCount = 0;
            }
        });
        
        // 長押しでデータ強制更新
        let longPressTimer;
        document.addEventListener('touchstart', (event) => {
            longPressTimer = setTimeout(() => {
                console.log('Long press detected - refreshing data');
                this.forceRefreshAll();
            }, 3000); // 3秒長押し
        });
        
        document.addEventListener('touchend', () => {
            if (longPressTimer) clearTimeout(longPressTimer);
        });
    }
    
    // センサーデータの強制更新
    async forceRefreshSensor() {
        console.log('Force refreshing sensor data...');
        
        // 視覚的フィードバック
        const statusIndicator = document.getElementById('status-indicator');
        if (statusIndicator) {
            statusIndicator.style.opacity = '0.5';
            setTimeout(() => {
                statusIndicator.style.opacity = '1';
            }, 1000);
        }
        
        // センサーデータの強制再読み込み
        await this.loadSensorData();
        
        console.log('Force sensor refresh completed');
    }
    
    // カレンダーデータの強制更新
    async forceRefreshCalendar() {
        console.log('Force refreshing calendar data...');
        
        // 視覚的フィードバック
        const calendarTitle = document.getElementById('calendar-title');
        if (calendarTitle) {
            const originalText = calendarTitle.textContent;
            calendarTitle.textContent = '更新中...';
            setTimeout(() => {
                calendarTitle.textContent = originalText;
            }, 2000);
        }
        
        // カレンダーデータの強制再読み込み
        await this.loadCalendarData();
        
        console.log('Force calendar refresh completed');
    }
    
    // 問題1: 当日マーク更新監視システム
    startTodayUpdateMonitor() {
        // 1分間隔で日付変更をチェック
        this.todayUpdateInterval = setInterval(() => {
            this.checkTodayUpdate();
        }, 60000); // 1分間隔
        
        // 初回チェック
        this.lastTodayCheck = new Date();
        console.log('Today update monitor started');
    }
    
    stopTodayUpdateMonitor() {
        if (this.todayUpdateInterval) {
            clearInterval(this.todayUpdateInterval);
            this.todayUpdateInterval = null;
            console.log('Today update monitor stopped');
        }
    }
    
    checkTodayUpdate() {
        const now = new Date();
        
        // 日付が変わった場合のみ更新
        if (this.lastTodayCheck && 
            this.lastTodayCheck.toDateString() !== now.toDateString()) {
            console.log('Date changed detected, updating today highlight');
            this.updateTodayHighlight();
            
            // 月が変わった場合は完全再読み込み
            if (this.lastTodayCheck.getMonth() !== now.getMonth() ||
                this.lastTodayCheck.getFullYear() !== now.getFullYear()) {
                console.log('Month changed, reloading calendar data');
                this.currentYear = now.getFullYear();
                this.currentMonth = now.getMonth() + 1;
                this.loadCalendarData();
            }
        }
        
        this.lastTodayCheck = now;
    }
    
    updateTodayHighlight() {
        if (!this.calendarData) return;
        
        const today = new Date();
        const todayDay = today.getDate();
        const todayMonth = today.getMonth() + 1;
        const todayYear = today.getFullYear();
        
        // 現在表示中の月と一致する場合のみ処理
        if (this.calendarData.year === todayYear && 
            this.calendarData.month === todayMonth) {
            
            // 既存の today クラスを削除
            const existingToday = document.querySelector('.calendar-day.today');
            if (existingToday) {
                existingToday.classList.remove('today');
            }
            
            // 新しい今日の要素に today クラスを追加
            const calendarGrid = document.getElementById('calendar-grid');
            if (calendarGrid) {
                const dayElements = calendarGrid.querySelectorAll('.calendar-day:not(.prev-month):not(.next-month)');
                dayElements.forEach(element => {
                    const dayText = element.querySelector('.day-number');
                    if (dayText && parseInt(dayText.textContent) === todayDay) {
                        element.classList.add('today');
                        console.log(`Today highlight updated: ${todayYear}年${todayMonth}月${todayDay}日`);
                    }
                });
            }
        }
    }
    
    // 長押し時の処理（センサーデータのみ）
    async forceRefreshAll() {
        await this.forceRefreshSensor();
    }
}

// ページ読み込み完了後にダッシュボードを初期化
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});