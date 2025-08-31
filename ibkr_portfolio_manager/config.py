"""
Configuration file for IBKR Portfolio Manager
"""

import os
from typing import Dict, Any

# IBKR Connection Settings
IBKR_CONFIG = {
    'host': os.getenv('IBKR_HOST', '127.0.0.1'),
    'port': int(os.getenv('IBKR_PORT', '7496')),  # 7497 for TWS paper, 7496 for TWS live
    'client_id': int(os.getenv('IBKR_CLIENT_ID', '1')),
    'timeout': 10
}

# Monitoring Settings
MONITORING_CONFIG = {
    'refresh_interval': 30,  # seconds between portfolio updates
    'save_snapshots': True,
    'snapshot_interval': 300,  # seconds between automatic snapshots (5 minutes)
    'snapshot_directory': 'snapshots',
    'log_directory': 'logs'
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_to_file': True,
    'log_filename': 'ibkr_portfolio.log',
    'max_log_size_mb': 10,
    'backup_count': 5
}

# Portfolio Display Settings
DISPLAY_CONFIG = {
    'currency_format': '{:,.2f}',
    'percentage_format': '{:.2%}',
    'show_account_details': True,
    'show_unrealized_pnl': True,
    'show_realized_pnl': True,
    'max_display_positions': 50
}

# Alert Configuration (for future implementation)
ALERT_CONFIG = {
    'enable_alerts': False,
    'email_alerts': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'email': '',  # Your email
        'password': '',  # App password
        'recipients': []  # List of recipient emails
    },
    'alert_thresholds': {
        'daily_loss_threshold': -1000,  # Alert if daily loss exceeds this
        'position_change_threshold': 0.05,  # Alert if position changes by 5%
        'margin_threshold': 0.8  # Alert if margin usage exceeds 80%
    }
}

# Data Export Settings
EXPORT_CONFIG = {
    'auto_export': False,
    'export_format': 'json',  # json, csv, excel
    'export_frequency': 'daily',  # hourly, daily, weekly
    'include_historical_data': True
}

# Risk Management Settings (for future implementation)
RISK_CONFIG = {
    'max_position_size_pct': 0.1,  # Max 10% of portfolio in single position
    'max_daily_loss_pct': 0.02,   # Max 2% daily loss
    'max_sector_exposure_pct': 0.25,  # Max 25% in single sector
    'enable_position_limits': False
}

def get_config(section: str = None) -> Dict[str, Any]:
    """
    Get configuration settings
    
    Args:
        section: Specific section to retrieve ('ibkr', 'monitoring', 'logging', etc.)
                If None, returns all configs
    
    Returns:
        Dictionary containing configuration settings
    """
    all_configs = {
        'ibkr': IBKR_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'logging': LOGGING_CONFIG,
        'display': DISPLAY_CONFIG,
        'alerts': ALERT_CONFIG,
        'export': EXPORT_CONFIG,
        'risk': RISK_CONFIG
    }
    
    if section:
        return all_configs.get(section, {})
    return all_configs

def update_config(section: str, key: str, value: Any):
    """Update a configuration value"""
    configs = {
        'ibkr': IBKR_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'logging': LOGGING_CONFIG,
        'display': DISPLAY_CONFIG,
        'alerts': ALERT_CONFIG,
        'export': EXPORT_CONFIG,
        'risk': RISK_CONFIG
    }
    
    if section in configs and key in configs[section]:
        configs[section][key] = value
        return True
    return False

# Environment-specific overrides
def load_environment_config():
    """Load configuration from environment variables"""
    env_mappings = [
        ('IBKR_HOST', 'ibkr', 'host'),
        ('IBKR_PORT', 'ibkr', 'port'),
        ('IBKR_CLIENT_ID', 'ibkr', 'client_id'),
        ('MONITORING_REFRESH_INTERVAL', 'monitoring', 'refresh_interval'),
        ('LOG_LEVEL', 'logging', 'level'),
    ]
    
    for env_var, section, key in env_mappings:
        if os.getenv(env_var):
            value = os.getenv(env_var)
            # Convert to appropriate type
            if key in ['port', 'client_id', 'refresh_interval']:
                value = int(value)
            update_config(section, key, value)

# Load environment config on import
load_environment_config()

# Create necessary directories
os.makedirs(MONITORING_CONFIG['snapshot_directory'], exist_ok=True)
os.makedirs(MONITORING_CONFIG['log_directory'], exist_ok=True)