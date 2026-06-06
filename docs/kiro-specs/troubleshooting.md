# Raspberry Pi Dashboard - トラブルシューティング

## SSH接続プロンプト表示遅延問題 (2025-08-14)

### 🔍 症状
- SSH接続時のプロンプト表示が異常に遅い（約10秒）
- 一昨日まで正常だったが突然発生
- IPアドレス直接指定でも同様の遅延

### 🔍 調査結果
**真の原因**: `.bashrc`のダッシュボード自動起動設定
- `sleep 8` + `sleep 2` = 10秒の遅延がSSH接続時に発生
- ログイン時にXorg起動とChromium設定が自動実行される設定
- 2025-08-14 00:03に`.bashrc`が作成・変更されていた

**問題のあった設定**:
```bash
# Dashboard Auto Start (Language Bar KILLER Edition)
if [[ $(tty) =~ /dev/tty[0-9]+ ]] || [[ $(tty) =~ /dev/pts/[0-9]+ ]]; then
    clear
    
    if ! pgrep -x Xorg > /dev/null; then
        sudo startx > /dev/null 2>&1 &
    fi
    
    sleep 8  # ← 8秒の遅延
    
    # ... Chromium設定 ...
    
    sleep 2  # ← さらに2秒の遅延
    clear
fi
```

### 🛠️ 解決手順
1. **バックアップ作成**:
   ```bash
   cp ~/.bashrc ~/.bashrc.backup.20250814
   ```

2. **問題設定の削除**:
   ```bash
   sed -i '/# Dashboard Auto Start/,/# ダッシュボード切り替え方法:/d' ~/.bashrc
   ```

3. **結果確認**:
   ```bash
   time ssh pi@192.168.x.x "echo 'Test'"
   # 結果: 0.023秒（10秒 → 0.023秒に大幅改善）
   ```

### ✅ 解決結果
- SSH接続時間: 10秒 → 0.023秒に改善
- 正常な接続速度に復旧
- バックアップファイル保存済み

### ⚠️ 注意事項
- 自動起動設定は削除したため、必要に応じて手動でダッシュボード起動
- バックアップから復元可能: `~/.bashrc.backup.20250814`
- 今後の自動起動設定追加時は、SSH接続への影響を考慮する

### 📝 学習事項
- シェル設定ファイル（.bashrc）の変更はSSH接続性能に直接影響
- 自動起動スクリプト内のsleepコマンドは慎重に使用
- TTY判定での条件分岐でもSSH接続時に実行される場合がある