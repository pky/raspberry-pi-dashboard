#!/bin/bash
# API ヘルスチェック & 自動再起動スクリプト
# systemd timer から5分ごとに呼び出される
# 2回連続失敗（=10分間応答なし）で raspberry-pi-api-server を再起動する

API_URL="http://localhost:5000/api/sensor"
CURL_TIMEOUT=10
FAIL_COUNT_FILE="/tmp/api_healthcheck_fails"
MAX_FAILS=2
SYSLOG_TAG="api-healthcheck"

log() {
    logger -t "$SYSLOG_TAG" "$1"
}

# 現在の失敗カウントを読み込む
if [ -f "$FAIL_COUNT_FILE" ]; then
    fail_count=$(cat "$FAIL_COUNT_FILE")
else
    fail_count=0
fi

# API へ curl を実行
http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$CURL_TIMEOUT" "$API_URL" 2>/dev/null)
curl_exit=$?

if [ "$curl_exit" -eq 0 ] && [ "$http_code" -eq 200 ]; then
    # 成功: 失敗カウントをリセット
    echo 0 > "$FAIL_COUNT_FILE"
    exit 0
fi

# 失敗: カウントを増やす
fail_count=$((fail_count + 1))
echo "$fail_count" > "$FAIL_COUNT_FILE"

if [ "$curl_exit" -ne 0 ]; then
    log "WARNING: API 応答なし (curl exit=$curl_exit, timeout=${CURL_TIMEOUT}s) [失敗 ${fail_count}/${MAX_FAILS}]"
else
    log "WARNING: API 異常レスポンス (HTTP $http_code) [失敗 ${fail_count}/${MAX_FAILS}]"
fi

# 連続失敗が閾値に達したら再起動
if [ "$fail_count" -ge "$MAX_FAILS" ]; then
    log "ERROR: API が ${MAX_FAILS} 回連続で応答しないため raspberry-pi-api-server を再起動します"
    systemctl restart raspberry-pi-api-server
    restart_result=$?
    if [ "$restart_result" -eq 0 ]; then
        log "INFO: raspberry-pi-api-server の再起動が完了しました"
    else
        log "ERROR: raspberry-pi-api-server の再起動に失敗しました (exit=$restart_result)"
    fi
    # 再起動後はカウントリセット
    echo 0 > "$FAIL_COUNT_FILE"
fi
