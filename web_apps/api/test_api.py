"""
テスト結果API Blueprint
Blueprint統合システム対応版
"""

import os
import json
import glob
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request
import subprocess
import threading

# Blueprint作成
test_bp = Blueprint('test', __name__, url_prefix='/api/simple-test')

@test_bp.route('/results')
def simple_test_results():
    """シンプルなテスト結果API"""
    try:
        # reportsディレクトリからテスト結果を検索
        reports_dir = Path("reports")
        if not reports_dir.exists():
            reports_dir.mkdir(exist_ok=True)
        
        json_reports = list(reports_dir.glob("test_results*.json"))
        
        if not json_reports:
            return jsonify({
                "status": "not_found",
                "message": "テスト結果が見つかりません",
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "error": 0,
                    "skipped": 0,
                    "duration": "0.00s"
                },
                "tests": []
            })
        
        # 最新のファイルを取得
        latest_report = max(json_reports, key=lambda f: f.stat().st_mtime)
        
        with open(latest_report, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 結果を標準化
        summary = data.get('summary', {})
        tests = data.get('tests', [])
        
        # ステータスを決定
        if summary.get('failed', 0) > 0:
            status = "fail"
        elif summary.get('error', 0) > 0:
            status = "warning"
        else:
            status = "pass"
        
        return jsonify({
            "status": status,
            "timestamp": datetime.fromtimestamp(latest_report.stat().st_mtime).isoformat(),
            "summary": {
                "total": summary.get('total', 0),
                "passed": summary.get('passed', 0),
                "failed": summary.get('failed', 0),
                "error": summary.get('error', 0),
                "skipped": summary.get('skipped', 0),
                "duration": summary.get('duration', '0.00s')
            },
            "tests": [
                {
                    "name": test.get('name', 'Unknown Test'),
                    "outcome": test.get('status', 'unknown'),
                    "duration": f"{test.get('duration', 0):.3f}s" if isinstance(test.get('duration'), (int, float)) else str(test.get('duration', '0.000s')),
                    "details": test.get('error', '') if test.get('error') else ''
                }
                for test in tests
            ]
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'テスト結果の取得に失敗しました: {str(e)}',
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
                'error': 0,
                'skipped': 0,
                'duration': '0.00s'
            },
            'tests': [],
            'error_details': str(e)
        }), 500

@test_bp.route('/stability')
def simple_stability_results():
    """シンプルな安定性テスト結果API"""
    try:
        # logsディレクトリから安定性テスト結果を検索
        stability_logs_dir = Path("logs")
        if not stability_logs_dir.exists():
            stability_logs_dir.mkdir(parents=True, exist_ok=True)
        
        stability_reports = list(stability_logs_dir.glob("stability_report_*.json"))
        
        if not stability_reports:
            return jsonify({
                "status": "not_found",
                "message": "安定性テスト結果が見つかりません",
                "summary": {
                    "duration_hours": 0,
                    "total_checks": 0,
                    "avg_cpu": 0,
                    "avg_memory": 0,
                    "total_errors": 0
                },
                "recommendations": ["安定性テストを実行してください。"]
            })
        
        # 最新のファイルを取得
        latest_report = max(stability_reports, key=lambda f: f.stat().st_mtime)
        
        with open(latest_report, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 結果を標準化
        test_summary = data.get('test_summary', {})
        system_perf = data.get('system_performance', {})
        error_summary = data.get('error_summary', {})
        
        # ステータスを決定
        status = test_summary.get('status', 'unknown').lower()
        if status == 'pass':
            status = 'pass'
        elif status == 'fail':
            status = 'fail'
        else:
            status = 'warning'
        
        return jsonify({
            "status": status,
            "timestamp": datetime.fromtimestamp(latest_report.stat().st_mtime).isoformat(),
            "summary": {
                "duration_hours": test_summary.get('duration_hours', 0),
                "total_checks": test_summary.get('total_checks', 0),
                "avg_cpu": system_perf.get('cpu', {}).get('average', 0),
                "avg_memory": system_perf.get('memory', {}).get('average', 0),
                "total_errors": sum(error_summary.values()) if error_summary else 0
            },
            "recommendations": data.get('recommendations', [])
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'安定性テスト結果の取得に失敗しました: {str(e)}',
            'summary': {
                'duration_hours': 0,
                'total_checks': 0,
                'avg_cpu': 0,
                'avg_memory': 0,
                'total_errors': 0
            },
            'recommendations': [f'エラーが発生しました: {str(e)}'],
            'error_details': str(e)
        }), 500

@test_bp.route('/logs')
def simple_test_logs():
    """シンプルなログAPI"""
    try:
        log_type = request.args.get('type', 'dashboard')
        lines = min(int(request.args.get('lines', 50)), 1000)  # 最大1000行
        
        log_files = {
            "dashboard": "logs/dashboard.log",
            "error": "logs/dashboard_error.log", 
            "performance": "logs/dashboard_performance.log",
            "stability": "logs/stability/dashboard.log"
        }
        
        log_filename = log_files.get(log_type, "logs/dashboard.log")
        log_path = Path(log_filename)
        
        if not log_path.exists():
            return jsonify({
                "status": "not_found",
                "logs": f"ログファイルが見つかりません: {log_filename}",
                "lines": 0
            })
        
        # 最後のN行を取得（Pythonのみで実装）
        with open(log_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            log_content = ''.join(all_lines[-lines:])
        
        return jsonify({
            "status": "success",
            "logs": log_content,
            "lines": len(log_content.split('\n')) - 1,
            "file_size": log_path.stat().st_size,
            "last_modified": datetime.fromtimestamp(log_path.stat().st_mtime).isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'logs': f'ログの読み込みに失敗しました: {str(e)}',
            'lines': 0,
            'error_details': str(e)
        }), 500

@test_bp.route('/run-tests', methods=['POST'])
def run_tests():
    """テスト実行API"""
    try:
        test_type = request.json.get('test_type', 'basic') if request.json else 'basic'
        
        def run_test_async():
            try:
                if test_type == 'basic':
                    # シンプルなAPIテストスクリプトをメイン使用
                    result = subprocess.run([
                        'python3', 'monitoring/simple_api_test.py'
                    ], capture_output=True, text=True, cwd='.', timeout=60)
                elif test_type == 'stability':
                    result = subprocess.run([
                        'python3', 'monitoring/stability_test.py', '--quick'
                    ], capture_output=True, text=True, cwd='.', timeout=400)
                else:
                    return
                
                # 結果をログに記録
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                with open('logs/test_run.log', 'a') as f:
                    f.write(f"\n--- Test Execution {test_type} {timestamp} ---\n")
                    f.write(f"Test Type: {test_type}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Return Code: {result.returncode}\n")
                    f.write(f"Command: python3 monitoring/{'simple_api_test.py' if test_type == 'basic' else 'stability_test.py'}\n")
                    f.write(f"Working Directory: {os.getcwd()}\n")
                    f.write(f"STDOUT:\n{result.stdout}\n")
                    f.write(f"STDERR:\n{result.stderr}\n")
                    
                    # 実行状況の判定
                    if result.returncode == 0:
                        f.write(f"\n✅ Test execution successful\n")
                    else:
                        f.write(f"\n❌ Test execution failed with return code: {result.returncode}\n")
                    
            except Exception as e:
                import traceback
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                with open('logs/test_error.log', 'a') as f:
                    f.write(f"\n--- Test Error {timestamp} ---\n")
                    f.write(f"Test execution error: {str(e)}\n")
                    f.write(f"Error type: {type(e).__name__}\n")
                    f.write(f"Working directory: {os.getcwd()}\n")
                    f.write(f"Test type requested: {test_type}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}\n")
        
        # バックグラウンドでテスト実行
        thread = threading.Thread(target=run_test_async)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'status': 'started',
            'message': f'{test_type}テストを開始しました。結果はlogsフォルダに保存されます。',
            'test_type': test_type,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'テスト開始に失敗しました: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@test_bp.route('/debug')
def simple_debug():
    """シンプルなデバッグAPI"""
    try:
        debug_info = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'working_directory': os.getcwd(),
            'directories': {},
            'files': {},
            'python_path': os.sys.path[:3]  # 最初の3つのパス
        }
        
        # ディレクトリ確認
        for dir_name in ['logs', 'reports', 'logs/stability']:
            dir_path = Path(dir_name)
            debug_info['directories'][dir_name] = {
                'exists': dir_path.exists(),
                'is_dir': dir_path.is_dir() if dir_path.exists() else False
            }
        
        # ファイル確認
        for file_name in ['logs/dashboard.log', 'reports/test_results_20250813_132718.json']:
            file_path = Path(file_name)
            debug_info['files'][file_name] = {
                'exists': file_path.exists(),
                'size': file_path.stat().st_size if file_path.exists() else 0
            }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'status': 'critical_error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500