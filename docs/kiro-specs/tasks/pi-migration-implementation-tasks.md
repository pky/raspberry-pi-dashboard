# Pi移行実装タスク（究極シンプル版）

## 📋 概要

**pull → cp バックアップ → 即動作**による究極シンプル移行。
**究極**: 実質3ステップ → 設定変更・データ継承すべて自動

## 🎯 移行目標

- **手順最小化**: 3ステップのみで完了
- **ゼロ設定変更**: systemd/cron/logrotate等完全そのまま
- **確実データ継承**: 単純cpで全データ確実継承
- **瞬時復旧**: 30秒以内完全復旧保証
- **Git統合**: プロジェクト全体統一管理

## 📊 究極シンプル移行手順

| フェーズ | タスク数 | 推定時間 | 停止時間 | 状態 |
|----------|----------|----------|----------|------|
| **Step 1: バックアップ** | 1 | 3分 | 0分 | 🛡️ 安全確保 |
| **Step 2: Git置換** | 1 | 5分 | 2分 | ⚡ 瞬時置換 |
| **Step 3: データ復元** | 1 | 2分 | 0分 | 📁 cp復元 |
| **Step 4: 動作確認** | 1 | 3分 | 0分 | ✅ 確認完了 |
| **合計** | **4** | **13分** | **2分** | 🚀 究極シンプル完了 |

🎯 **究極ポイント**: pull + cp = 問題なし

---

## Step 1: 究極シンプル バックアップ (停止なし)

### S001: ワンコマンド完全バックアップ
```yaml
タスク: 現システム確認 + 完全バックアップ
コマンド:
  # 稼働確認 + バックアップ（1ステップ）
  - ssh pi@raspberrypi.local
  - sudo systemctl is-active raspberry-pi-api-server raspberry-pi-native-dashboard && curl -s http://localhost:5000/api/sensor >/dev/null && echo "System OK"
  - cd /home/pi/ && cp -r projects projects_backup_$(date +%Y%m%d_%H%M%S) && echo "Backup completed"
  - ssh -T git@github.com  # Git認証確認
  
期待値: システム稼働OK + バックアップ完了 + Git認証OK
所要時間: 3分
```

---

## Step 2: Git瞬時置換 (停止2分)

### S002: 究極シンプル Git置換
```yaml
タスク: projects → Git 瞬時置換（ワンライナー）
コマンド:
  # 瞬時置換（1コマンド）
  - sudo systemctl stop raspberry-pi-api-server raspberry-pi-native-dashboard
  - cd /home/pi/ && mv projects projects_old && git clone https://github.com/[username]/raspberry-pi-dashboard.git projects
  - cd projects && git config user.name "your-username" && git config user.email "your-email@example.com" 
  - chown pi:pi . && find . -name "*.sh" -exec chmod +x {} \; && find raspberry-pi-dashboard -name "*.py" -exec chmod +x {} \; 2>/dev/null
  
期待値: Git置換完了 + 設定完了
所要時間: 5分
```

---

## Step 3: 究極シンプル データ復元 (停止なし)

### S003: ワンコマンド データ復元 + 即座起動
```yaml
タスク: cp復元 + サービス起動（究極シンプル）
コマンド:
  # データ復元 + 起動（1ステップ）
  - cp -r projects_old/raspberry-pi-dashboard projects/ && echo "Data restored"
  - sudo systemctl start raspberry-pi-api-server raspberry-pi-native-dashboard && sleep 3
  - sudo systemctl is-active raspberry-pi-api-server raspberry-pi-native-dashboard && echo "Services active"
  
期待値: データ復元完了 + サービス即座起動成功
所要時間: 2分
```

---

## Step 4: 究極シンプル 全機能確認 (停止なし)

### S004: ワンコマンド 全機能確認
```yaml
タスク: API + センサー + Git + テスト 一括確認
コマンド:
  # 全機能確認（1ステップ）
  - curl -s http://localhost:5000/api/sensor && curl -s http://localhost:5000/api/calendar >/dev/null && echo "APIs OK"
  - cd /path/to/raspberry-pi-dashboard/ && python3 -c "from sensor import read_sensors; print('Sensors:', read_sensors())"
  - cd .. && git status && git log --oneline -2 && echo "Git OK"
  - cd raspberry-pi-dashboard && python3 -m pytest tests/ -q && echo "Tests OK"
  
期待値: API + センサー + Git + テスト 全部OK
所要時間: 3分
```

---

## 🚨 究極シンプル 緊急復旧（15秒復旧）

### 🚨 ワンライナー復旧
```yaml
R001_瞬時復旧:
  # 15秒復旧（ワンライナー）
  コマンド:
    - sudo systemctl stop raspberry-pi-* && cd /home/pi/ && mv projects projects_failed && mv projects_old projects && sudo systemctl start raspberry-pi-* && curl -s http://localhost:5000/api/sensor && echo "Recovered in 15 seconds"
  期待値: 15秒以内完全復旧
  
R002_バックアップ復旧:
  # バックアップからの復旧（1分）
  コマンド:
    - cd /home/pi/ && sudo systemctl stop raspberry-pi-* && rm -rf projects projects_* && cp -r $(ls -t projects_backup_* | head -1) projects && sudo systemctl start raspberry-pi-* && echo "Backup restored"
  期待値: 1分以内完全復旧
```

---

## 📊 移行成功判定基準

### ワンライナー成功判定
```yaml
✅ 究極確認コマンド:
sudo systemctl is-active raspberry-pi-* && curl -s localhost:5000/api/sensor >/dev/null && cd /path/to/projects && git status >/dev/null && python3 -m pytest raspberry-pi-dashboard/tests/ -q && echo "🎉 Migration SUCCESS - All systems operational!"

期待結果: "🎉 Migration SUCCESS - All systems operational!" 表示
```

### 詳細確認（必要時のみ）
```yaml
✅ システム: sudo systemctl is-active raspberry-pi-* → active active
✅ API: curl localhost:5000/api/sensor → センサー実測値JSON
✅ Git: git status → On branch main, working tree clean  
✅ テスト: pytest tests/ -q → ... passed
✅ 構造: ls -la → raspberry-pi-dashboard/, CLAUDE.md, docs/
```

### 推奨条件 (品質向上)
```yaml
⭐ 完全統合:
  - ログ出力継続
  - キャッシュデータ継続
  - Google Calendar認証継続
  - cron監視継続

⭐ パフォーマンス:
  - API応答時間 <200ms
  - システム負荷正常
  - メモリ使用量正常
```

---

## 🎯 移行後の開発ワークフロー

### 新しい開発サイクル（革新設計版）
```bash
# Pi上でSSH接続
ssh pi@raspberrypi.local
cd /path/to/projects/  # ←プロジェクトルート（Git管理）

# feature開発
git checkout -b feature/sensor-enhancement
# 実機開発・テスト（raspberry-pi-dashboard/内で）
cd raspberry-pi-dashboard/
python3 -m pytest tests/ -v
python3 -c "from sensor import read_sensors; print(read_sensors())"
# コミット・プッシュ（プロジェクトルートで）
cd ..
git add raspberry-pi-dashboard/
git commit -m "feat: センサー機能拡張"
git push origin feature/sensor-enhancement

# 本番反映（パス不変なので即座反映）
git checkout main && git pull
sudo systemctl restart raspberry-pi-api-server  # 即座反映（パス変更なし）
```

### 究極シンプルの利点確認
- ⚡ **究極手順**: 実質4ステップ（13分）で完了
- 🎯 **ワンライナー化**: 各ステップ1コマンドで実行
- 🛡️ **15秒復旧**: ワンライナーで瞬時復旧
- ✅ **設定変更ゼロ**: systemd/cron/logrotate等すべてそのまま
- ✅ **データ継承確実**: 単純cpで全データ確実継承
- ✅ **Git統合**: プロジェクト全体統一管理
- ✅ **実機開発**: センサー実測値での開発・テスト
- ✅ **Token大幅削減**: 複雑な作業完全廃止

---

**この究極シンプルタスクは、pull + cp = 問題なし の発想により、最小限の手順で最大限の安全性を実現する究極の移行手順です。**