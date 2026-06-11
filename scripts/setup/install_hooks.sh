#!/bin/bash
# git pre-commit フックをインストールする
# 初回セットアップ時に一度だけ実行: bash scripts/setup/install_hooks.sh

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK_SRC="$REPO_ROOT/scripts/setup/pre-commit"
HOOK_DST="$REPO_ROOT/.git/hooks/pre-commit"

cp "$HOOK_SRC" "$HOOK_DST"
chmod +x "$HOOK_DST"
echo "pre-commit フックをインストールしました: $HOOK_DST"
