"""
Configuration module for Raspberry Pi Dashboard
Handles environment variables, GPIO settings, and API configuration
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Main configuration class"""
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    
    # センサー設定（実測値強制モード）
    SENSOR_FORCE_REAL_VALUES = True  # 必ずTrueに固定
    SENSOR_MAX_RETRIES = 5  # 実測値取得最大試行回数
    SENSOR_SIMULATION_MODE = False  # シミュレーションモード無効
    
    # DHT22 Sensor GPIO configuration
    DHT22_PIN = int(os.environ.get('DHT22_PIN', 4))  # GPIO pin 4 by default
    SENSOR_READ_TIMEOUT = int(os.environ.get('SENSOR_READ_TIMEOUT', 5))  # seconds
    SENSOR_RETRY_COUNT = int(os.environ.get('SENSOR_RETRY_COUNT', 3))
    SENSOR_MAX_RETRIES = int(os.environ.get('SENSOR_MAX_RETRIES', 3))
    SENSOR_RETRY_DELAY = float(os.environ.get('SENSOR_RETRY_DELAY', 2.0))  # seconds
    SENSOR_UPDATE_INTERVAL = int(os.environ.get('SENSOR_UPDATE_INTERVAL', 30))  # seconds
    
    # Google Calendar API configuration
    GOOGLE_CALENDAR_ENABLED = os.environ.get('GOOGLE_CALENDAR_ENABLED', 'true').lower() == 'true'
    GOOGLE_CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials/credentials.json')
    GOOGLE_TOKEN_FILE = os.environ.get('GOOGLE_TOKEN_FILE', 'credentials/token.json')
    GOOGLE_CALENDAR_ID = os.environ.get('GOOGLE_CALENDAR_ID', 'primary')
    GOOGLE_ADDITIONAL_CALENDAR_IDS = [
        cal_id.strip()
        for cal_id in os.environ.get('GOOGLE_ADDITIONAL_CALENDAR_IDS', '').split(',')
        if cal_id.strip()
    ]
    GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    # Dashboard display configuration
    TIMEZONE = os.environ.get('TIMEZONE', 'Asia/Tokyo')
    LANGUAGE = os.environ.get('LANGUAGE', 'ja')
    
    # Touch panel configuration
    TOUCH_PANEL_WIDTH = int(os.environ.get('TOUCH_PANEL_WIDTH', 1024))
    TOUCH_PANEL_HEIGHT = int(os.environ.get('TOUCH_PANEL_HEIGHT', 600))
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/dashboard.log')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10485760))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    
    # System configuration
    AUTO_START_BROWSER = os.environ.get('AUTO_START_BROWSER', 'True').lower() == 'true'
    BROWSER_KIOSK_MODE = os.environ.get('BROWSER_KIOSK_MODE', 'True').lower() == 'true'
    
    @staticmethod
    def validate_config():
        """Validate configuration settings"""
        errors = []

        # Validate GPIO pin
        if not (1 <= Config.DHT22_PIN <= 40):
            errors.append(f"Invalid DHT22_PIN: {Config.DHT22_PIN}. Must be between 1-40")

        # Validate credentials file path
        if not os.path.exists(os.path.dirname(Config.GOOGLE_CREDENTIALS_FILE)):
            errors.append(f"Credentials directory does not exist: {os.path.dirname(Config.GOOGLE_CREDENTIALS_FILE)}")

        # Validate log directory
        if not os.path.exists(os.path.dirname(Config.LOG_FILE)):
            errors.append(f"Log directory does not exist: {os.path.dirname(Config.LOG_FILE)}")

        # Google Calendar 有効時: トークンファイルの存在確認
        if Config.GOOGLE_CALENDAR_ENABLED and not os.path.exists(Config.GOOGLE_TOKEN_FILE):
            errors.append(f"GOOGLE_CALENDAR_ENABLED=true ですが token ファイルが見つかりません: {Config.GOOGLE_TOKEN_FILE}")

        # 追加カレンダー未設定の通知（エラーではなく情報）
        if Config.GOOGLE_CALENDAR_ENABLED and not Config.GOOGLE_ADDITIONAL_CALENDAR_IDS:
            errors.append("INFO: GOOGLE_ADDITIONAL_CALENDAR_IDS が未設定です（primary のみ取得）。家族共有カレンダー等を追加する場合は .env に設定してください")

        return errors

# Development configuration
class DevelopmentConfig(Config):
    """Development environment configuration"""
    DEBUG = True
    
# Production configuration  
class ProductionConfig(Config):
    """Production environment configuration"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    @staticmethod
    def validate_config():
        """Additional production validation"""
        errors = Config.validate_config()
        
        if not ProductionConfig.SECRET_KEY:
            errors.append("SECRET_KEY must be set in production")
            
        return errors

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])