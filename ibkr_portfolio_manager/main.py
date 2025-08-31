"""
IBKR Portfolio Manager
A Python application to monitor Interactive Brokers portfolio using TWS API
"""


import asyncio
import logging
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional
import json
import time

try:
    from ib_insync import *
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    print("Please install required packages: pip install ib-insync pandas")
    exit(1)

class IBKRPortfolioManager:
    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: int = 1):
        """
        Initialize IBKR Portfolio Manager
        
        Args:
            host: TWS/Gateway host (default: localhost)
            port: TWS/Gateway port (7497 for TWS paper, 7496 for TWS live, 4001 for Gateway paper, 4000 for Gateway live)
            client_id: Unique client ID for this connection
        """
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('ibkr_portfolio.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    async def connect(self) -> bool:
        """Connect to TWS/Gateway"""
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=10)
            self.connected = True
            self.logger.info(f"Connected to IBKR TWS/Gateway at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from TWS/Gateway"""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            self.logger.info("Disconnected from IBKR")
    
    def get_account_summary(self) -> Dict:
        """Get account summary information"""
        if not self.connected:
            self.logger.error("Not connected to IBKR")
            return {}
        
        try:
            # Get account summary
            account_summary = self.ib.accountSummary()
            summary_dict = {}
            
            for item in account_summary:
                summary_dict[item.tag] = {
                    'value': item.value,
                    'currency': item.currency,
                    'account': item.account
                }
            
            return summary_dict
        except Exception as e:
            self.logger.error(f"Error getting account summary: {e}")
            return {}
    
    def get_portfolio_positions(self) -> pd.DataFrame:
        """Get current portfolio positions"""
        if not self.connected:
            self.logger.error("Not connected to IBKR")
            return pd.DataFrame()
        
        try:
            positions = self.ib.positions()
            if not positions:
                self.logger.info("No positions found")
                return pd.DataFrame()
            
            portfolio_data = []
            for pos in positions:
                contract = pos.contract
                portfolio_data.append({
                    'Symbol': contract.symbol,
                    'SecType': contract.secType,
                    'Exchange': contract.exchange,
                    'Currency': contract.currency,
                    'Position': pos.position,
                    'Market Price': pos.marketPrice,
                    'Market Value': pos.marketValue,
                    'Average Cost': pos.averageCost,
                    'Unrealized PnL': pos.unrealizedPNL,
                    'Realized PnL': pos.realizedPNL,
                    'Account': pos.account
                })
            
            df = pd.DataFrame(portfolio_data)
            return df
        except Exception as e:
            self.logger.error(f"Error getting portfolio positions: {e}")
            return pd.DataFrame()
    
    def get_pnl_summary(self) -> Dict:
        """Get P&L summary"""
        if not self.connected:
            self.logger.error("Not connected to IBKR")
            return {}
        
        try:
            pnl_summary = self.ib.pnl()
            if pnl_summary:
                return {
                    'Daily PnL': pnl_summary.dailyPnL,
                    'Unrealized PnL': pnl_summary.unrealizedPnL,
                    'Realized PnL': pnl_summary.realizedPnL,
                    'Position': pnl_summary.position,
                    'Market Value': pnl_summary.marketValue
                }
            return {}
        except Exception as e:
            self.logger.error(f"Error getting PnL summary: {e}")
            return {}
    
    def get_open_orders(self) -> pd.DataFrame:
        """Get open orders"""
        if not self.connected:
            self.logger.error("Not connected to IBKR")
            return pd.DataFrame()
        
        try:
            orders = self.ib.openOrders()
            if not orders:
                self.logger.info("No open orders found")
                return pd.DataFrame()
            
            orders_data = []
            for order in orders:
                contract = order.contract
                orders_data.append({
                    'Order ID': order.orderId,
                    'Symbol': contract.symbol,
                    'Action': order.action,
                    'Order Type': order.orderType,
                    'Total Quantity': order.totalQuantity,
                    'Limit Price': getattr(order, 'lmtPrice', None),
                    'Status': order.orderState.status,
                    'Filled': order.filled,
                    'Remaining': order.remaining,
                    'Account': order.account
                })
            
            df = pd.DataFrame(orders_data)
            return df
        except Exception as e:
            self.logger.error(f"Error getting open orders: {e}")
            return pd.DataFrame()
    
    def monitor_portfolio(self, refresh_interval: int = 30):
        """Monitor portfolio with periodic updates"""
        self.logger.info(f"Starting portfolio monitoring (refresh every {refresh_interval}s)")
        
        try:
            while self.connected:
                print("\n" + "="*80)
                print(f"Portfolio Update - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*80)
                
                # Account Summary
                print("\n📊 ACCOUNT SUMMARY:")
                account_summary = self.get_account_summary()
                key_metrics = ['NetLiquidation', 'TotalCashValue', 'UnrealizedPnL', 'RealizedPnL', 'DayTradesRemaining']
                for metric in key_metrics:
                    if metric in account_summary:
                        print(f"  {metric}: {account_summary[metric]['value']} {account_summary[metric]['currency']}")
                
                # Portfolio Positions
                print("\n📈 PORTFOLIO POSITIONS:")
                positions_df = self.get_portfolio_positions()
                if not positions_df.empty:
                    print(positions_df.to_string(index=False))
                    
                    # Summary stats
                    total_value = positions_df['Market Value'].sum()
                    total_unrealized_pnl = positions_df['Unrealized PnL'].sum()
                    print(f"\n  Total Portfolio Value: {total_value:,.2f}")
                    print(f"  Total Unrealized P&L: {total_unrealized_pnl:,.2f}")
                else:
                    print("  No positions found")
                
                # Open Orders
                print("\n📋 OPEN ORDERS:")
                orders_df = self.get_open_orders()
                if not orders_df.empty:
                    print(orders_df.to_string(index=False))
                else:
                    print("  No open orders")
                
                # Wait for next update
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Portfolio monitoring stopped by user")
        except Exception as e:
            self.logger.error(f"Error in portfolio monitoring: {e}")
    
    def save_portfolio_snapshot(self, filename: Optional[str] = None):
        """Save current portfolio snapshot to file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'portfolio_snapshot_{timestamp}.json'
        
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'account_summary': self.get_account_summary(),
                'positions': self.get_portfolio_positions().to_dict('records'),
                'open_orders': self.get_open_orders().to_dict('records'),
                'pnl_summary': self.get_pnl_summary()
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            self.logger.info(f"Portfolio snapshot saved to {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Error saving portfolio snapshot: {e}")
            return None

# Example usage and main function
async def main():
    """Main function to demonstrate portfolio manager usage"""
    # Initialize portfolio manager
    # Use port 7497 for paper trading, 7496 for live trading
    portfolio_manager = IBKRPortfolioManager(port=7497)  # Paper trading port
    
    # Connect to TWS/Gateway
    if await portfolio_manager.connect():
        try:
            print("Connected successfully!")
            
            # Get account summary
            print("\n📊 Account Summary:")
            account_summary = portfolio_manager.get_account_summary()
            for key, value in account_summary.items():
                print(f"  {key}: {value['value']} {value['currency']}")
            
            # Get portfolio positions
            print("\n📈 Portfolio Positions:")
            positions = portfolio_manager.get_portfolio_positions()
            if not positions.empty:
                print(positions)
            else:
                print("  No positions found")
            
            # Get open orders
            print("\n📋 Open Orders:")
            orders = portfolio_manager.get_open_orders()
            if not orders.empty:
                print(orders)
            else:
                print("  No open orders")
            
            # Save snapshot
            snapshot_file = portfolio_manager.save_portfolio_snapshot()
            if snapshot_file:
                print(f"\n💾 Snapshot saved: {snapshot_file}")
            
            # Option to start monitoring
            response = input("\nStart continuous monitoring? (y/n): ").lower()
            if response == 'y':
                portfolio_manager.monitor_portfolio(refresh_interval=30)
            
        finally:
            portfolio_manager.disconnect()
    else:
        print("Failed to connect to IBKR. Make sure TWS/Gateway is running and properly configured.")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())