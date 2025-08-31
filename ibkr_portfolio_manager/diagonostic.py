#!/usr/bin/env python3
"""
Dashboard Diagnostic Script
Checks all components and helps fix connection issues
"""

import sys
import importlib
import subprocess
import asyncio
from datetime import datetime

def check_dependencies():
    """Check if all required packages are installed"""
    print("📦 Checking Dependencies...")
    print("-" * 30)
    
    required_packages = [
        ('flask', 'Flask web framework'),
        ('flask_socketio', 'Flask-SocketIO for real-time updates'),
        ('ib_insync', 'Interactive Brokers API'),
        ('pandas', 'Data manipulation'),
        ('numpy', 'Numerical computing')
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package} - {description}")
        except ImportError:
            print(f"❌ {package} - {description} (MISSING)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n💡 To install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    print("✅ All dependencies are installed!")
    return True

async def test_ibkr_connection():
    """Test IBKR connection with all common ports"""
    print("\n🔌 Testing IBKR Connection...")
    print("-" * 30)
    
    try:
        from ib_insync import IB
        
        ports_to_test = [
            (7497, "TWS Paper Trading"),
            (7496, "TWS Live Trading"), 
            (4001, "Gateway Paper Trading"),
            (4000, "Gateway Live Trading")
        ]
        
        host = '127.0.0.1'
        working_connections = []
        
        for port, description in ports_to_test:
            ib = IB()
            try:
                print(f"Testing {description} (port {port})...", end=" ")
                await ib.connectAsync(host, port, clientId=999, timeout=3)
                print("✅ SUCCESS")
                
                # Test basic operations
                try:
                    accounts = ib.managedAccounts()
                    print(f"  📋 Accounts: {accounts}")
                    
                    summary = ib.accountSummary()
                    print(f"  📊 Account summary: {len(summary)} items")
                    
                except Exception as e:
                    print(f"  ⚠️  Connected but limited data access: {e}")
                
                working_connections.append((port, description))
                ib.disconnect()
                
            except asyncio.TimeoutError:
                print("❌ Timeout")
            except ConnectionRefusedError:
                print("❌ Connection refused")
            except Exception as e:
                print(f"❌ Error: {e}")
            
            try:
                ib.disconnect()
            except:
                pass
        
        if working_connections:
            print(f"\n✅ Found {len(working_connections)} working connection(s):")
            for port, desc in working_connections:
                print(f"   Port {port}: {desc}")
            
            recommended_port = working_connections[0][0]
            print(f"\n💡 Recommended port: {recommended_port}")
            return recommended_port
        else:
            print("\n❌ No working IBKR connections found!")
            print("\n📋 Troubleshooting checklist:")
            print("1. ✅ Is TWS or IB Gateway running?")
            print("2. ✅ API enabled? (Configure → API → Settings)")
            print("3. ✅ 'Enable ActiveX and Socket Clients' checked?")
            print("4. ✅ Correct socket port configured?")
            print("5. ✅ 127.0.0.1 in trusted IPs?")
            return None
            
    except ImportError:
        print("❌ ib_insync not installed!")
        print("Install with: pip install ib-insync")
        return None

def check_config():
    """Check configuration settings"""
    print("\n⚙️  Checking Configuration...")
    print("-" * 30)
    
    try:
        from config import get_config
        config = get_config('ibkr')
        
        print(f"Host: {config['host']}")
        print(f"Port: {config['port']}")
        print(f"Client ID: {config['client_id']}")
        print(f"Timeout: {config.get('timeout', 'default')}")
        
        return config
        
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def test_dashboard_components():
    """Test dashboard components"""
    print("\n🌐 Testing Dashboard Components...")
    print("-" * 30)
    
    try:
        # Test Flask import
        import flask
        print(f"✅ Flask {flask.__version__}")
        
        # Test SocketIO import  
        import flask_socketio
        print(f"✅ Flask-SocketIO")
        
        # Test if main dashboard can be imported
        try:
            from ibkr_portfolio_manager.dashboard import app, dashboard
            print("✅ Dashboard app can be imported")
            
            # Test if routes are registered
            routes = [rule.rule for rule in app.url_map.iter_rules()]
            expected_routes = ['/', '/api/connect', '/api/disconnect', '/api/portfolio']
            
            for route in expected_routes:
                if route in routes:
                    print(f"✅ Route {route} registered")
                else:
                    print(f"❌ Route {route} missing")
            
            return True
            
        except Exception as e:
            print(f"❌ Error importing dashboard: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Missing web framework components: {e}")
        return False

def create_test_config(recommended_port=None):
    """Create a test configuration"""
    if not recommended_port:
        recommended_port = 7497  # Default to paper trading
    
    config_content = f'''"""
Test Configuration for IBKR Portfolio Manager
Generated by diagnostic script at {datetime.now()}
"""

import os

# IBKR Connection Settings
IBKR_CONFIG = {{
    'host': os.getenv('IBKR_HOST', '127.0.0.1'),
    'port': int(os.getenv('IBKR_PORT', '{recommended_port}')),
    'client_id': int(os.getenv('IBKR_CLIENT_ID', '1')),
    'timeout': 10
}}

# Monitoring Settings
MONITORING_CONFIG = {{
    'refresh_interval': 30,
    'save_snapshots': True,
    'snapshot_interval': 300,
    'snapshot_directory': 'snapshots',
    'log_directory': 'logs'
}}

# Logging Configuration
LOGGING_CONFIG = {{
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'log_to_file': True,
    'log_filename': 'ibkr_portfolio.log',
    'max_log_size_mb': 10,
    'backup_count': 5
}}

# Display Configuration
DISPLAY_CONFIG = {{
    'currency_format': '{{:,.2f}}',
    'percentage_format': '{{:.2%}}',
    'show_account_details': True,
    'show_unrealized_pnl': True,
    'show_realized_pnl': True,
    'max_display_positions': 50
}}

def get_config(section: str = None):
    """Get configuration settings"""
    all_configs = {{
        'ibkr': IBKR_CONFIG,
        'monitoring': MONITORING_CONFIG,
        'logging': LOGGING_CONFIG,
        'display': DISPLAY_CONFIG
    }}
    
    if section:
        return all_configs.get(section, {{}})
    return all_configs

# Create necessary directories
import os
os.makedirs('snapshots', exist_ok=True)
os.makedirs('logs', exist_ok=True)
'''
    
    try:
        with open('config.py', 'w') as f:
            f.write(config_content)
        print(f"✅ Created config.py with port {recommended_port}")
        return True
    except Exception as e:
        print(f"❌ Error creating config.py: {e}")
        return False

async def main():
    """Main diagnostic function"""
    print("🔍 IBKR Portfolio Dashboard Diagnostic")
    print("=" * 50)
    print(f"Time: {datetime.now()}")
    print(f"Python: {sys.version}")
    print()
    
    # Step 1: Check dependencies
    deps_ok = check_dependencies()
    
    if not deps_ok:
        print("\n❌ Please install missing dependencies first!")
        return
    
    # Step 2: Test IBKR connection
    recommended_port = await test_ibkr_connection()
    
    # Step 3: Check current config
    current_config = check_config()
    
    # Step 4: Test dashboard components
    dashboard_ok = test_dashboard_components()
    
    # Step 5: Create/update config if needed
    if recommended_port and (not current_config or current_config.get('port') != recommended_port):
        print(f"\n💡 Creating optimized config with port {recommended_port}...")
        create_test_config(recommended_port)
    
    # Step 6: Final recommendations
    print(f"\n🎯 Final Recommendations:")
    print("-" * 30)
    
    if deps_ok and recommended_port and dashboard_ok:
        print("✅ All systems ready!")
        print(f"🚀 Start dashboard: python standalone_dashboard.py")
        print(f"🌐 Open browser: http://localhost:5000")
        print(f"🔌 Use port {recommended_port} in dashboard")
    else:
        print("❌ Issues found. Please fix the above problems first.")
        
        if not deps_ok:
            print("   - Install missing Python packages")
        if not recommended_port:
            print("   - Fix IBKR TWS/Gateway connection")
        if not dashboard_ok:
            print("   - Fix dashboard import issues")

if __name__ == "__main__":
    asyncio.run(main())