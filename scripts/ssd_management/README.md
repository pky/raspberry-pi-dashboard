# M.2 SSD 管理システム

M.2 SSD の監視・同期・フォールバック機能を統合管理するスクリプト群です。

## 📁 ファイル構成

```
scripts/ssd_management/
├── data_sync.py           # データ同期システム（メイン）
├── sync_cron.sh           # cron自動実行スクリプト
└── README.md              # このファイル
```

## 🔄 データ同期システム (`data_sync.py`)

### 機能概要
- **重要データ自動同期**: M.2 SSD ↔ microSD間の双方向同期
- **増分同期**: 変更されたファイルのみ同期（チェックサム比較）
- **優先度管理**: データ種別による同期間隔・優先度設定
- **整合性チェック**: ファイル破損・不整合検出
- **cron統合**: 自動化対応

### 重要データ分類

| データ種別 | 優先度 | 同期間隔 | 説明 |
|------------|---------|----------|------|
| credentials | 1 | 5分 | Google認証情報・API証明書 |
| co2_data | 2 | 1時間 | CO2センサーデータベース |
| calendar_cache | 3 | 24時間 | カレンダー・祝日キャッシュ |
| config_files | 2 | 1時間 | アプリケーション設定 |
| systemd_services | 1 | 24時間 | systemdサービス設定 |

### 使用方法

```bash
# レポート表示（デフォルト）
python3 /path/to/raspberry-pi-dashboard/scripts/ssd_management/data_sync.py

# 自動同期実行（間隔チェックあり）
python3 /path/to/raspberry-pi-dashboard/scripts/ssd_management/data_sync.py --auto-sync

# 強制完全同期（間隔無視）
python3 /path/to/raspberry-pi-dashboard/scripts/ssd_management/data_sync.py --force-sync

# レポート表示のみ
python3 /path/to/raspberry-pi-dashboard/scripts/ssd_management/data_sync.py --report
```

### ログファイル
- **実行ログ**: `/path/to/raspberry-pi-dashboard/logs/data_sync.log`
- **同期状態**: `/path/to/raspberry-pi-dashboard/logs/data_sync_status.json`
- **cronログ**: `/path/to/raspberry-pi-dashboard/logs/data_sync_cron.log`

## ⏰ 自動化設定

### cron設定
```bash
# crontab -e で追加
# 15分間隔で自動同期実行
*/15 * * * * /path/to/raspberry-pi-dashboard/scripts/ssd_management/sync_cron.sh

# 毎日午前3時に強制完全同期
0 3 * * * cd /path/to/raspberry-pi-dashboard && /usr/bin/python3 scripts/ssd_management/data_sync.py --force-sync >> logs/data_sync_cron.log 2>&1
```

### systemd統合（オプション）
```bash
# タイマーサービス作成例
sudo systemctl edit --full --force data-sync.timer
sudo systemctl enable data-sync.timer
sudo systemctl start data-sync.timer
```

## 🔍 監視・メンテナンス

### 状況確認
```bash
# 同期状況確認
python3 /path/to/raspberry-pi-dashboard/scripts/ssd_management/data_sync.py --report

# ログ確認
tail -f /path/to/raspberry-pi-dashboard/logs/data_sync.log

# cronログ確認
tail -f /path/to/raspberry-pi-dashboard/logs/data_sync_cron.log
```

### トラブルシューティング

#### 同期エラーの場合
1. バックアップディレクトリの権限確認
2. ディスク容量確認
3. ソースファイルの存在確認
4. ログファイルでエラー詳細確認

#### パフォーマンス問題
1. 同期間隔の調整（`critical_data_paths`設定）
2. 不要ファイルの除外
3. バックアップディレクトリの最適化

## 🛡️ セキュリティ

### アクセス権限
- 認証ファイル: `600` (所有者のみ読み書き)
- systemd設定: `644` (所有者書き込み、グループ・その他読み取り)
- 実行スクリプト: `755` (所有者実行権限付与)

### データ保護
- チェックサム検証による整合性保証
- バックアップファイルの暗号化（将来実装）
- アクセスログ記録

## 🔗 関連システム

### 既存フォールバックシステム
- **手動バックアップ**: `complete_backup_system.sh`
- **緊急復旧**: `complete_emergency_recovery.sh`
- **ベンチマーク**: `scripts/m2_ssd_benchmark.sh`

### 監視システム統合
- システム監視ダッシュボード連携
- API経由での同期状態取得
- アラート通知機能

## 📈 今後の拡張予定

1. **リアルタイム同期**: inotifyを使用したファイル変更即座同期
2. **外部ストレージ対応**: USB・NAS等への同期拡張
3. **Web管理画面**: 同期設定・状況のWeb UI管理
4. **高度な復旧機能**: 部分復旧・時点復旧機能
5. **クラウド同期**: Google Drive・Dropbox等との連携

---

**このシステムは M.2 SSD超高性能システムの一部として、データ保護・システム可用性向上を実現します。**