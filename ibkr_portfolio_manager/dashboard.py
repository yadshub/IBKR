#!/usr/bin/env python3
"""
Working IBKR Dashboard - No f-string syntax issues
All JavaScript curly braces properly escaped
"""

from flask import Flask, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import threading
import time
from datetime import datetime

from main import IBKRPortfolioManager
from config import get_config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'working-dashboard-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

class WorkingDashboard:
    def __init__(self):
        self.pm = None
        self.connected = False
        self.monitoring = False
        self.latest_data = {}
        
    async def connect_to_ibkr(self):
        try:
            config = get_config('ibkr')
            print(f"🔌 Connecting to {config['host']}:{config['port']}...")
            
            self.pm = IBKRPortfolioManager(
                host=config['host'],
                port=config['port'],
                client_id=config['client_id']
            )
            
            self.connected = await self.pm.connect()
            
            if self.connected:
                print("✅ Connected!")
                await self.update_data()
                return True
            else:
                print("❌ Connection failed!")
                return False
                
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    async def update_data(self):
        """Update data with comprehensive error handling"""
        if not self.connected or not self.pm:
            return
        
        try:
            print(f"🔄 [{time.strftime('%H:%M:%S')}] Starting data update...")
            
            # Get account summary
            account_summary = {}
            try:
                account_summary = self.pm.get_account_summary()
                if account_summary:
                    print(f"📊 Account summary: {len(account_summary)} items")
                    for key in ['NetLiquidation', 'TotalCashValue', 'BuyingPower']:
                        if key in account_summary:
                            val = account_summary[key]
                            print(f"  ✅ {key}: {val['value']} {val['currency']}")
                else:
                    print("⚠️ No account summary data")
            except Exception as e:
                print(f"❌ Account summary error: {e}")
            
            # Get positions with robust error handling
            positions = []
            positions_errors = []
            
            try:
                print("📈 Getting portfolio positions...")
                raw_positions = self.pm.ib.positions()
                print(f"📈 Found {len(raw_positions)} raw positions")
                
                for i, pos in enumerate(raw_positions):
                    try:
                        print(f"  🔍 Processing position {i+1}...")
                        
                        # Get contract info safely
                        contract = getattr(pos, 'contract', None)
                        if not contract:
                            continue
                        
                        symbol = getattr(contract, 'symbol', f'UNKNOWN_{i+1}')
                        sec_type = getattr(contract, 'secType', 'Unknown')
                        
                        # Get position data safely
                        position_size = getattr(pos, 'position', 0)
                        market_price = getattr(pos, 'marketPrice', None)
                        market_value = getattr(pos, 'marketValue', None)
                        average_cost = getattr(pos, 'averageCost', None)
                        unrealized_pnl = getattr(pos, 'unrealizedPNL', None)
                        
                        # Convert to float with defaults
                        market_price = float(market_price) if market_price is not None else 0.0
                        market_value = float(market_value) if market_value is not None else 0.0
                        average_cost = float(average_cost) if average_cost is not None else 0.0
                        unrealized_pnl = float(unrealized_pnl) if unrealized_pnl is not None else 0.0
                        
                        # Calculate missing values
                        if market_value == 0.0 and market_price > 0 and position_size != 0:
                            market_value = market_price * abs(position_size)
                        
                        if market_price == 0.0 and market_value > 0 and position_size != 0:
                            market_price = market_value / abs(position_size)
                        
                        position_data = {
                            'Symbol': symbol,
                            'SecType': sec_type,
                            'Position': position_size,
                            'Market Price': market_price,
                            'Market Value': market_value,
                            'Average Cost': average_cost,
                            'Unrealized PnL': unrealized_pnl
                        }
                        
                        positions.append(position_data)
                        print(f"    ✅ {symbol}: {position_size} @ ${market_price:.2f}")
                        
                    except Exception as pos_error:
                        error_msg = f"Position {i+1}: {str(pos_error)}"
                        positions_errors.append(error_msg)
                        print(f"    ❌ {error_msg}")
                
                print(f"✅ Processed {len(positions)} positions, {len(positions_errors)} errors")
                
            except Exception as e:
                print(f"❌ Positions error: {e}")
            
            # Update data structure
            self.latest_data = {
                'account_summary': account_summary,
                'positions': positions,
                'last_update': datetime.now().isoformat(),
                'debug_info': {
                    'account_items': len(account_summary),
                    'positions_count': len(positions),
                    'positions_errors': positions_errors,
                    'connected': self.connected,
                    'timestamp': time.strftime('%H:%M:%S')
                }
            }
            
            # Send to clients
            socketio.emit('portfolio_update', self.latest_data)
            print("✅ Data update complete!")
            
        except Exception as e:
            print(f"❌ Critical update error: {e}")

# Global dashboard
dashboard = WorkingDashboard()

# HTML template without f-string conflicts
def get_html():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IBKR Dashboard - Working Version</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    
    <style>
        .status-connected { color: #28a745; font-weight: bold; }
        .status-disconnected { color: #dc3545; font-weight: bold; }
        .status-connecting { color: #ffc107; font-weight: bold; }
        .debug-section { font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; }
        .positive { color: #28a745; font-weight: bold; }
        .negative { color: #dc3545; font-weight: bold; }
        .metric-card { transition: all 0.3s ease; }
        .metric-card:hover { transform: translateY(-2px); }
    </style>
</head>
<body class="bg-light">
    <div class="container-fluid p-4">
        <!-- Header -->
        <div class="row mb-4">
            <div class="col-12 text-center">
                <h1 class="mb-2">📊 IBKR Portfolio Dashboard</h1>
                <p class="text-muted">Working Version - """ + current_time + """</p>
            </div>
        </div>
        
        <!-- Connection Status -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body text-center">
                        <h5>Connection Status: <span id="connectionStatus" class="status-disconnected">Disconnected</span></h5>
                        
                        <button id="connectButton" class="btn btn-success me-2" onclick="connectToIBKR()">
                            🔌 Connect to IBKR
                        </button>
                        <button id="refreshButton" class="btn btn-primary me-2" onclick="refreshData()" disabled>
                            🔄 Refresh Data
                        </button>
                        <button class="btn btn-info me-2" onclick="showDebugInfo()">
                            🔍 Debug Info
                        </button>
                        <button class="btn btn-secondary" onclick="window.open('/api/debug', '_blank')">
                            🔧 Raw Data
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Account Summary -->
        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card bg-primary text-white metric-card">
                    <div class="card-body text-center">
                        <h6>💰 Net Liquidation</h6>
                        <h3 id="netLiquidation">$0.00</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-success text-white metric-card">
                    <div class="card-body text-center">
                        <h6>💵 Total Cash</h6>
                        <h3 id="totalCash">$0.00</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-info text-white metric-card">
                    <div class="card-body text-center">
                        <h6>📈 Buying Power</h6>
                        <h3 id="buyingPower">$0.00</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning text-dark metric-card">
                    <div class="card-body text-center">
                        <h6>📊 Unrealized P&L</h6>
                        <h3 id="unrealizedPnL">$0.00</h3>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Positions Table -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">📋 Portfolio Positions</h6>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead class="table-dark">
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Type</th>
                                        <th>Position</th>
                                        <th>Market Price</th>
                                        <th>Market Value</th>
                                        <th>Unrealized P&L</th>
                                    </tr>
                                </thead>
                                <tbody id="positionsTableBody">
                                    <tr>
                                        <td colspan="6" class="text-center text-muted py-4">
                                            Connect to IBKR to view positions
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Debug Section -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">🔍 Debug Information</h6>
                    </div>
                    <div class="card-body debug-section">
                        <pre id="debugInfo">Click "Debug Info" to view system information</pre>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Status Messages -->
        <div id="messageArea" class="mt-3"></div>
    </div>

    <script>
        console.log('Dashboard JavaScript loading...');
        
        let socket = null;
        let isConnected = false;
        let currentData = null;
        
        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM ready, initializing dashboard...');
            initializeSocket();
            showMessage('Dashboard loaded successfully!', 'success');
        });
        
        // Initialize WebSocket
        function initializeSocket() {
            try {
                socket = io();
                
                socket.on('connect', function() {
                    console.log('WebSocket connected');
                    showMessage('Connected to server', 'info');
                });
                
                socket.on('disconnect', function() {
                    console.log('WebSocket disconnected');
                    showMessage('Disconnected from server', 'warning');
                });
                
                socket.on('portfolio_update', function(data) {
                    console.log('Portfolio update received:', data);
                    updateDashboard(data);
                });
                
            } catch (error) {
                console.error('Socket initialization error:', error);
                showMessage('WebSocket initialization failed: ' + error.message, 'danger');
            }
        }
        
        // Connect to IBKR
        async function connectToIBKR() {
            console.log('Connect button clicked');
            
            const connectButton = document.getElementById('connectButton');
            const statusElement = document.getElementById('connectionStatus');
            
            try {
                connectButton.disabled = true;
                connectButton.textContent = 'Connecting...';
                statusElement.textContent = 'Connecting...';
                statusElement.className = 'status-connecting';
                
                showMessage('Connecting to IBKR...', 'info');
                
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                console.log('Connection result:', result);
                
                if (result.success) {
                    isConnected = true;
                    statusElement.textContent = 'Connected';
                    statusElement.className = 'status-connected';
                    connectButton.textContent = 'Connected';
                    document.getElementById('refreshButton').disabled = false;
                    showMessage('Successfully connected to IBKR!', 'success');
                } else {
                    throw new Error(result.error || 'Connection failed');
                }
                
            } catch (error) {
                console.error('Connection error:', error);
                statusElement.textContent = 'Failed';
                statusElement.className = 'status-disconnected';
                showMessage('Connection failed: ' + error.message, 'danger');
            } finally {
                connectButton.disabled = false;
                connectButton.textContent = 'Connect to IBKR';
            }
        }
        
        // Refresh data
        async function refreshData() {
            if (!isConnected) {
                showMessage('Please connect first', 'warning');
                return;
            }
            
            const refreshButton = document.getElementById('refreshButton');
            
            try {
                refreshButton.disabled = true;
                refreshButton.textContent = 'Refreshing...';
                
                const response = await fetch('/api/refresh', { method: 'POST' });
                const result = await response.json();
                
                if (result.success) {
                    showMessage('Data refreshed!', 'success');
                } else {
                    throw new Error(result.error);
                }
                
            } catch (error) {
                showMessage('Refresh failed: ' + error.message, 'danger');
            } finally {
                refreshButton.disabled = false;
                refreshButton.textContent = 'Refresh Data';
            }
        }
        
        // Show debug info
        async function showDebugInfo() {
            try {
                const response = await fetch('/api/debug');
                const data = await response.json();
                document.getElementById('debugInfo').textContent = JSON.stringify(data, null, 2);
                showMessage('Debug info updated', 'info');
            } catch (error) {
                showMessage('Debug failed: ' + error.message, 'danger');
            }
        }
        
        // Update dashboard
        function updateDashboard(data) {
            console.log('Updating dashboard with data');
            currentData = data;
            
            try {
                // Update account summary
                const summary = data.account_summary || {};
                
                document.getElementById('netLiquidation').textContent = 
                    formatCurrency(summary.NetLiquidation ? summary.NetLiquidation.value : 0);
                document.getElementById('totalCash').textContent = 
                    formatCurrency(summary.TotalCashValue ? summary.TotalCashValue.value : 0);
                document.getElementById('buyingPower').textContent = 
                    formatCurrency(summary.BuyingPower ? summary.BuyingPower.value : 0);
                
                const unrealizedPnL = summary.UnrealizedPnL ? parseFloat(summary.UnrealizedPnL.value) : 0;
                const unrealizedElement = document.getElementById('unrealizedPnL');
                unrealizedElement.textContent = formatCurrency(unrealizedPnL);
                unrealizedElement.className = unrealizedPnL >= 0 ? 'positive' : 'negative';
                
                // Update positions table
                updatePositionsTable(data.positions || []);
                
                showMessage('Dashboard updated: ' + (data.positions ? data.positions.length : 0) + ' positions', 'success');
                
            } catch (error) {
                console.error('Dashboard update error:', error);
                showMessage('Update failed: ' + error.message, 'danger');
            }
        }
        
        // Update positions table
        function updatePositionsTable(positions) {
            const tbody = document.getElementById('positionsTableBody');
            
            if (!positions || positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No positions found</td></tr>';
                return;
            }
            
            tbody.innerHTML = positions.map(function(pos) {
                const unrealizedPnL = pos['Unrealized PnL'] || 0;
                const pnlClass = unrealizedPnL >= 0 ? 'positive' : 'negative';
                
                return '<tr>' +
                    '<td><strong>' + (pos.Symbol || 'N/A') + '</strong></td>' +
                    '<td><span class="badge bg-secondary">' + (pos.SecType || 'N/A') + '</span></td>' +
                    '<td>' + (pos.Position || 0) + '</td>' +
                    '<td>' + formatCurrency(pos['Market Price'] || 0) + '</td>' +
                    '<td>' + formatCurrency(pos['Market Value'] || 0) + '</td>' +
                    '<td class="' + pnlClass + '">' + formatCurrency(unrealizedPnL) + '</td>' +
                    '</tr>';
            }).join('');
        }
        
        // Format currency
        function formatCurrency(value) {
            const num = parseFloat(value) || 0;
            return '$' + num.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        }
        
        // Show messages
        function showMessage(message, type) {
            const messageArea = document.getElementById('messageArea');
            const alertClass = 'alert-' + (type === 'danger' ? 'danger' : 
                                         type === 'success' ? 'success' : 
                                         type === 'warning' ? 'warning' : 'info');
            
            const timestamp = new Date().toLocaleTimeString();
            messageArea.innerHTML = '<div class="alert ' + alertClass + ' alert-dismissible fade show">' +
                '<small>[' + timestamp + ']</small> ' + message +
                '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
            
            setTimeout(function() {
                const alert = messageArea.querySelector('.alert');
                if (alert) alert.remove();
            }, 5000);
        }
        
        console.log('Dashboard JavaScript loaded successfully');
    </script>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    
    return html_template

@app.route('/')
def index():
    return get_html()

@app.route('/api/connect', methods=['POST'])
def connect():
    try:
        print("🔍 API connect called")
        
        async def do_connect():
            return {'success': await dashboard.connect_to_ibkr()}
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(do_connect())
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Connect error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/refresh', methods=['POST'])
def refresh():
    try:
        if not dashboard.connected:
            return jsonify({'success': False, 'error': 'Not connected'})
        
        async def do_refresh():
            await dashboard.update_data()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(do_refresh())
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Refresh error: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug')
def debug():
    try:
        return jsonify({
            'server_time': datetime.now().isoformat(),
            'dashboard_connected': dashboard.connected,
            'latest_data_available': bool(dashboard.latest_data),
            'account_summary_count': len(dashboard.latest_data.get('account_summary', {})),
            'positions_count': len(dashboard.latest_data.get('positions', [])),
            'full_data': dashboard.latest_data
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected')
    emit('status', {'connected': dashboard.connected})

@socketio.on('disconnect')  
def handle_disconnect():
    print('❌ Client disconnected')

if __name__ == '__main__':
    print("🚀 Starting Working IBKR Dashboard...")
    print("📊 URL: http://localhost:5000")
    print("🛡️  No f-string syntax issues!")
    print("✅ Position attribute errors fixed")
    print("🔧 Ready to connect to TWS/Gateway")
    
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n⏹️ Dashboard stopped")
    except Exception as e:
        print(f"❌ Error: {e}")