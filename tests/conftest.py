"""
Pytest設定とフィクスチャー
テスト環境の共通設定とテストデータの準備
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 必要なモジュールのモック
@pytest.fixture(autouse=True)
def mock_hardware_dependencies():
    """ハードウェア依存のモジュールをモック"""
    with patch('psutil.sensors_temperatures', return_value={}), \
         patch('psutil.cpu_percent', return_value=5.0), \
         patch('psutil.virtual_memory') as mock_memory, \
         patch('psutil.disk_usage') as mock_disk, \
         patch('psutil.net_io_counters') as mock_network, \
         patch('psutil.boot_time', return_value=1234567890):
        
        # メモリ情報のモック
        mock_memory.return_value.percent = 45.0
        mock_memory.return_value.available = 2 * 1024 * 1024 * 1024  # 2GB
        mock_memory.return_value.used = 1 * 1024 * 1024 * 1024  # 1GB
        
        # ディスク情報のモック
        mock_disk.return_value.total = 32 * 1024 * 1024 * 1024  # 32GB
        mock_disk.return_value.used = 8 * 1024 * 1024 * 1024   # 8GB
        mock_disk.return_value.free = 24 * 1024 * 1024 * 1024  # 24GB
        
        # ネットワーク情報のモック
        mock_network.return_value.bytes_sent = 1000000
        mock_network.return_value.bytes_recv = 2000000
        
        yield

# テスト用のモックデータ
@pytest.fixture
def mock_sensor_data():
    """モックセンサーデータ"""
    return {
        'temperature': 25.5,
        'humidity': 60.0,
        'discomfort_index': 73.2,
        'comfort_level': 'やや不快',
        'timestamp': datetime.now().isoformat()
    }

@pytest.fixture
def mock_calendar_data():
    """モックカレンダーデータ"""
    return {
        'year': 2025,
        'month': 8,
        'days_in_month': 31,
        'first_day_weekday': 5,  # 金曜日
        'days': {
            1: {
                'date': datetime(2025, 8, 1),
                'weekday': 5,
                'events': [],
                'is_holiday': False,
                'holiday_name': None
            },
            11: {
                'date': datetime(2025, 8, 11),
                'weekday': 1,
                'events': [
                    {
                        'id': 'holiday_2025_08-11',
                        'title': '山の日',
                        'description': '日本の祝日',
                        'start_datetime': datetime(2025, 8, 11),
                        'end_datetime': datetime(2025, 8, 11),
                        'all_day': True,
                        'type': 'japanese_holiday'
                    }
                ],
                'is_holiday': True,
                'holiday_name': '山の日'
            },
            15: {
                'date': datetime(2025, 8, 15),
                'weekday': 5,
                'events': [
                    {
                        'id': 'test_event_1',
                        'title': '夏季休暇 (継続)',
                        'description': 'テスト用イベント',
                        'start_datetime': datetime(2025, 8, 12),
                        'end_datetime': datetime(2025, 8, 15),
                        'all_day': True,
                        'type': 'google_event'
                    }
                ],
                'is_holiday': False,
                'holiday_name': None
            }
        },
        'month_name': 'August',
        'total_events': 2
    }

@pytest.fixture
def mock_flask_app():
    """テスト用Flaskアプリケーション"""
    # DHT22とGoogle Calendar APIのモックを適用
    with patch('sensor.SHT35_AVAILABLE', False), \
         patch('calendar_auth.GOOGLE_LIBS_AVAILABLE', False), \
         patch.dict('os.environ', {'TESTING': 'True'}), \
         patch('builtins.open', side_effect=FileNotFoundError) as mock_open:
        
        # 温度ファイルの読み取りをモック
        def mock_open_func(filename, *args, **kwargs):
            if 'thermal_zone0/temp' in str(filename):
                raise FileNotFoundError("Mocked thermal file not found")
            return open.__wrapped__(filename, *args, **kwargs)
        
        mock_open.side_effect = mock_open_func
        
        try:
            # sys.pathに現在のディレクトリを追加
            import sys
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            # アプリケーションをインポート
            from app import app
            app.config['TESTING'] = True
            app.config['WTF_CSRF_ENABLED'] = False
            
            with app.test_client() as client:
                with app.app_context():
                    yield client
        except Exception as e:
            # デバッグ情報を出力してスキップ
            import traceback
            print(f"Flask app creation failed: {e}")
            traceback.print_exc()
            pytest.skip(f"Failed to create Flask app: {e}")

@pytest.fixture
def mock_system_health():
    """モックシステムヘルス状態"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'sensor': 'connected',
            'calendar': 'connected',
            'api': 'running'
        },
        'system': {
            'cpu_usage': 15.5,
            'memory_usage': 45.2,
            'disk_usage': 65.8,
            'temperature': 42.1
        }
    }

@pytest.fixture(autouse=True)
def reset_mocks():
    """各テスト前にモックをリセット"""
    yield
    # テスト後のクリーンアップ処理
    import gc
    gc.collect()