#!/usr/bin/env python3
"""
Google Calendar API サービスアカウント設定支援スクリプト
サービスアカウントの作成から権限設定まで自動化・ガイド機能

使用方法:
  python3 service_account_setup.py --help
  python3 service_account_setup.py --check
  python3 service_account_setup.py --setup
"""

import os
import sys
import json
import argparse
import logging
from typing import Dict, Any, Optional
from logging_system import get_logger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def check_service_account_setup() -> Dict[str, Any]:
    """
    サービスアカウント設定状況の確認
    
    Returns:
        Dict: 設定状況の詳細
    """
    result = {
        'key_file_exists': False,
        'key_file_valid': False,
        'file_permissions': None,
        'service_account_email': None,
        'project_id': None,
        'recommendations': []
    }
    
    key_file_path = 'credentials/service-account-key.json'
    
    # 秘密鍵ファイルの確認
    if os.path.exists(key_file_path):
        result['key_file_exists'] = True
        
        # ファイル権限の確認
        file_stat = os.stat(key_file_path)
        result['file_permissions'] = oct(file_stat.st_mode)[-3:]
        
        # JSONの有効性確認
        try:
            with open(key_file_path, 'r') as f:
                key_data = json.load(f)
            
            # 必須フィールドの確認
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            
            if all(field in key_data for field in required_fields):
                result['key_file_valid'] = True
                result['service_account_email'] = key_data.get('client_email')
                result['project_id'] = key_data.get('project_id')
                
                if key_data.get('type') != 'service_account':
                    result['recommendations'].append(
                        "⚠️  秘密鍵ファイルのタイプが正しくありません（service_account である必要があります）"
                    )
            else:
                result['recommendations'].append(
                    "❌ 秘密鍵ファイルに必須フィールドが不足しています"
                )
                
        except json.JSONDecodeError:
            result['recommendations'].append("❌ 秘密鍵ファイルのJSONが無効です")
        except Exception as e:
            result['recommendations'].append(f"❌ 秘密鍵ファイル読み込みエラー: {e}")
    else:
        result['recommendations'].append(
            f"❌ サービスアカウント秘密鍵ファイルが見つかりません: {key_file_path}"
        )
    
    # ファイル権限の確認
    if result['key_file_exists'] and result['file_permissions'] != '600':
        result['recommendations'].append(
            f"⚠️  ファイル権限を修正してください: {result['file_permissions']} → 600"
        )
    
    return result

def print_setup_guide():
    """サービスアカウント設定手順を表示"""
    
    self.logger.info("Manual conversion needed: "\n" + "="*80...")  # TODO: 手動変換
    self.logger.debug("Google Calendar API サービスアカウント設定手順")
    self.logger.info("Manual conversion needed: "="*80...")  # TODO: 手動変換
    
    self.logger.info("\n ステップ1: Google Cloud Console でプロジェクト設定")
    self.logger.info("Manual conversion needed: "-" * 50...")  # TODO: 手動変換
    self.logger.info("1. https://console.cloud.google.com/ にアクセス")
    self.logger.info("2. プロジェクトを選択または新規作成")
    self.logger.info("3. 「APIとサービス」→「ライブラリ」")
    self.logger.info("4. 「Google Calendar API」を検索して有効化")
    
    self.logger.info("\n🔐 ステップ2: サービスアカウント作成")
    self.logger.info("Manual conversion needed: "-" * 50...")  # TODO: 手動変換
    self.logger.info("1. 「APIとサービス」→「認証情報」")
    self.logger.info("2. 「認証情報を作成」→「サービスアカウント」")
    self.logger.info("3. サービスアカウント名: 'calendar-reader'")
    self.logger.info("4. 説明: 'Raspberry Pi Calendar Reader'")
    self.logger.info("5. ロール: 不要（最小権限）")
    
    self.logger.info("\n🗝  ステップ3: 秘密鍵の生成・ダウンロード")
    self.logger.info("Manual conversion needed: "-" * 50...")  # TODO: 手動変換
    self.logger.info("1. 作成したサービスアカウントをクリック")
    self.logger.info("2. 「鍵」タブ → 「鍵を追加」→「新しい鍵を作成」")
    self.logger.info("3. キーのタイプ: JSON")
    self.logger.info("4. ダウンロードされたファイルを以下に配置:")
    self.logger.info("→ credentials/service-account-key.json")
    self.logger.info("5. ファイル権限を設定: chmod 600 credentials/service-account-key.json")
    
    self.logger.info("\n📅 ステップ4: カレンダー共有設定")
    self.logger.info("Manual conversion needed: "-" * 50...")  # TODO: 手動変換
    self.logger.info("1. Google Calendar (calendar.google.com) にアクセス")
    self.logger.info("2. 対象カレンダーの設定 → 「特定のユーザーとの共有」")
    self.logger.info("3. サービスアカウントメール（xxxx@project-id.iam.gserviceaccount.com）を追加")
    self.logger.info("4. 権限: 「閲覧権限（すべての予定の詳細）」")
    self.logger.info("5. 保存")
    
    self.logger.success("\n ステップ5: 動作確認")
    self.logger.info("Manual conversion needed: "-" * 50...")  # TODO: 手動変換
    self.logger.info("1. python3 service_account_setup.py --check")
    self.logger.info("2. python3 service_account_setup.py --test")
    self.logger.success("3. 問題なければサービスアカウント移行完了")
    
    self.logger.info("Manual conversion needed: "\n" + "="*80...")  # TODO: 手動変換

def test_service_account():
    """サービスアカウント認証テスト"""
    try:
        from service_account_auth import ServiceAccountCalendarAuth
        
        self.logger.info("🧪 サービスアカウント認証テスト開始...")
        
        sa_auth = ServiceAccountCalendarAuth()
        
        # 認証テスト
        if not sa_auth.authenticate():
            self.logger.warning("サービスアカウント認証に失敗しました")
            return False
        
        # 接続テスト
        if not sa_auth.test_connection():
            self.logger.warning("Google Calendar API接続テストに失敗しました")
            return False
        
        # カレンダーデータ取得テスト
        self.logger.info("📅 カレンダーデータ取得テスト...")
        from datetime import datetime
        from calendar_data import CalendarDataManager
        
        manager = CalendarDataManager(auth_method="service_account")
        now = datetime.now()
        result = manager.get_month_events(now.year, now.month)
        
        if result['status'] == 'success':
            self.logger.success("カレンダーデータ取得成功:")
            self.logger.info("個人予定: {result['google_events_count']}件")
            self.logger.info("祝日: {result['holidays_count']}件")
        else:
            self.logger.info("カレンダーデータ取得エラー: {result['error']}")
            return False
        
        self.logger.success("すべてのテストが成功しました！")
        return True
        
    except ImportError as e:
        self.logger.warning("必要なモジュールが見つかりません:", e=e)
        return False
    except Exception as e:
        self.logger.error("テスト実行エラー:", e=e)
        return False

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(
        description="Google Calendar API サービスアカウント設定支援ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--check', 
        action='store_true',
        help='サービスアカウント設定状況を確認'
    )
    
    parser.add_argument(
        '--setup', 
        action='store_true',
        help='設定手順を表示'
    )
    
    parser.add_argument(
        '--test', 
        action='store_true',
        help='サービスアカウント認証・接続テストを実行'
    )
    
    args = parser.parse_args()
    
    if args.check:
        self.logger.debug("サービスアカウント設定状況を確認中...")
        result = check_service_account_setup()
        
        self.logger.info("\n 設定状況:")
        self.logger.success("秘密鍵ファイル存在: {'' if result['key_file_exists'] else ''}")
        self.logger.success("秘密鍵ファイル有効: {'' if result['key_file_valid'] else ''}")
        
        if result['service_account_email']:
            self.logger.info("サービスアカウント: {result['service_account_email']}")
        
        if result['project_id']:
            self.logger.info("プロジェクトID: {result['project_id']}")
        
        if result['file_permissions']:
            self.logger.info("ファイル権限: {result['file_permissions']}")
        
        if result['recommendations']:
            self.logger.warning("\n  推奨事項:")
            for rec in result['recommendations']:
                self.logger.info("", rec=rec)
        
        if result['key_file_valid'] and not result['recommendations']:
            self.logger.success("\n サービスアカウント設定は正常です！")
        
    elif args.test:
        test_service_account()
        
    elif args.setup:
        print_setup_guide()
        
    else:
        parser.print_help()
        
        # デフォルト動作：簡単なステータス表示
        self.logger.info("\n クイック設定チェック:")
        result = check_service_account_setup()
        
        if result['key_file_valid'] and not result['recommendations']:
            self.logger.success("サービスアカウント設定完了")
            self.logger.info("python3 service_account_setup.py --test でテスト実行可能")
        else:
            self.logger.warning("設定が必要です")
            self.logger.debug("python3 service_account_setup.py --setup で手順を確認")

if __name__ == "__main__":
    main()