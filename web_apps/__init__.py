"""
web_apps package
新Blueprint統合システム
"""

import logging
logger = logging.getLogger(__name__)

def register_all_blueprints(app):
    """
    全Blueprint統合登録関数
    Day4実装: System API + Sensor API
    Day8実装: Calendar, CO2, Metrics, SSD API
    """
    
    # System API Blueprint
    try:
        from web_apps.api.system_api import system_bp
        app.register_blueprint(system_bp)
        logger.info("System API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"System API blueprint not found: {e}")
    
    # Sensor API Blueprint
    try:
        from web_apps.api.sensor_api import sensor_bp
        app.register_blueprint(sensor_bp)
        logger.info("Sensor API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Sensor API blueprint not found: {e}")
    
    # Calendar API Blueprint (Day8実装)
    try:
        from web_apps.api.calendar_api import calendar_bp
        app.register_blueprint(calendar_bp)
        logger.info("Calendar API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Calendar API blueprint not found: {e}")
    
    # CO2 API Blueprint (Day8実装)
    try:
        from web_apps.api.co2_api import co2_bp
        app.register_blueprint(co2_bp)
        logger.info("CO2 API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"CO2 API blueprint not found: {e}")
    
    # Metrics API Blueprint (Day8実装)
    try:
        from web_apps.api.metrics_api import metrics_bp
        app.register_blueprint(metrics_bp)
        logger.info("Metrics API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Metrics API blueprint not found: {e}")
    
    # SSD API Blueprint (Day8実装)
    try:
        from web_apps.api.ssd_api import ssd_bp
        app.register_blueprint(ssd_bp)
        logger.info("SSD API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"SSD API blueprint not found: {e}")
    
    # Backup API Blueprint（新Blueprint構成対応）
    try:
        from web_apps.api.backup_api import backup_api
        app.register_blueprint(backup_api, url_prefix='/api/backup')
        logger.info("Backup API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Backup API blueprint not found: {e}")
    
    # Monitoring Blueprint (Day12実装)
    try:
        from web_apps.monitoring.system_monitor_app import monitor_bp
        app.register_blueprint(monitor_bp)
        logger.info("Monitoring blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Monitoring blueprint not found: {e}")
    
    # Dashboard Blueprint (Day13実装)
    try:
        from web_apps.dashboard.dashboard_routes import dashboard_bp
        app.register_blueprint(dashboard_bp)
        logger.info("Dashboard blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Dashboard blueprint not found: {e}")
    
    # Test API Blueprint (system_monitor用)
    try:
        from web_apps.api.test_api import test_bp
        app.register_blueprint(test_bp)
        logger.info("Test API blueprint registered successfully")
    except ImportError as e:
        logger.warning(f"Test API blueprint not found: {e}")
    
    logger.info("All blueprints registered successfully")