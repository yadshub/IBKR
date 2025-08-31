"""
Enhanced data handler for IBKR Portfolio Dashboard
Better handling of account summary, positions, and data formatting
"""

import asyncio
from datetime import datetime
import pandas as pd
from typing import Dict, List, Any, Optional
from ib_insync import *

class EnhancedDataHandler:
    """Enhanced data handler with better IBKR data processing"""
    
    def __init__(self, ib_connection):
        self.ib = ib_connection
        self.logger = None
    
    def get_account_summary_enhanced(self) -> Dict[str, Any]:
        """Get enhanced account summary with better error handling"""
        try:
            print("🔍 Getting account summary...")
            
            # Get account summary using different methods
            summary_dict = {}
            
            # Method 1: Try accountSummary()
            try:
                account_summary = self.ib.accountSummary()
                print(f"📊 Account summary retrieved: {len(account_summary)} items")
                
                for item in account_summary:
                    summary_dict[item.tag] = {
                        'value': item.value,
                        'currency': item.currency,
                        'account': item.account
                    }
                    print(f"  {item.tag}: {item.value} {item.currency}")
                    
            except Exception as e:
                print(f"⚠️ Method 1 (accountSummary) failed: {e}")
            
            # Method 2: Try accountValues() if accountSummary failed
            if not summary_dict:
                try:
                    print("🔄 Trying alternative method (accountValues)...")
                    account_values = self.ib.accountValues()
                    print(f"📊 Account values retrieved: {len(account_values)} items")
                    
                    for item in account_values:
                        summary_dict[item.tag] = {
                            'value': item.value,
                            'currency': item.currency,
                            'account': item.account
                        }
                        print(f"  {item.tag}: {item.value} {item.currency}")
                        
                except Exception as e:
                    print(f"⚠️ Method 2 (accountValues) failed: {e}")
            
            # Method 3: Try specific account value requests
            if not summary_dict:
                try:
                    print("🔄 Trying specific account requests...")
                    
                    # Get managed accounts first
                    accounts = self.ib.managedAccounts()
                    print(f"📋 Managed accounts: {accounts}")
                    
                    if accounts:
                        account = accounts[0]  # Use first account
                        
                        # Request specific values
                        specific_tags = [
                            'NetLiquidation', 'TotalCashValue', 'BuyingPower',
                            'GrossPositionValue', 'UnrealizedPnL', 'RealizedPnL'
                        ]
                        
                        for tag in specific_tags:
                            try:
                                values = [v for v in self.ib.accountValues() if v.tag == tag and v.account == account]
                                if values:
                                    val = values[0]
                                    summary_dict[tag] = {
                                        'value': val.value,
                                        'currency': val.currency,
                                        'account': val.account
                                    }
                                    print(f"  {tag}: {val.value} {val.currency}")
                            except Exception as tag_error:
                                print(f"    ⚠️ Failed to get {tag}: {tag_error}")
                                
                except Exception as e:
                    print(f"⚠️ Method 3 (specific requests) failed: {e}")
            
            # Add some computed values if we have basic data
            if 'NetLiquidation' in summary_dict and 'TotalCashValue' in summary_dict:
                try:
                    net_liq = float(summary_dict['NetLiquidation']['value'])
                    cash = float(summary_dict['TotalCashValue']['value'])
                    invested = net_liq - cash
                    
                    summary_dict['InvestedAmount'] = {
                        'value': str(invested),
                        'currency': summary_dict['NetLiquidation']['currency'],
                        'account': summary_dict['NetLiquidation']['account']
                    }
                    print(f"  Computed InvestedAmount: {invested}")
                except Exception as e:
                    print(f"⚠️ Error computing invested amount: {e}")
            
            print(f"✅ Final summary has {len(summary_dict)} items")
            return summary_dict
            
        except Exception as e:
            print(f"❌ Error in get_account_summary_enhanced: {e}")
            return {}
    
    def get_portfolio_positions_enhanced(self) -> pd.DataFrame:
        """Get enhanced portfolio positions with better formatting"""
        try:
            print("🔍 Getting portfolio positions...")
            
            positions = self.ib.positions()
            print(f"📈 Found {len(positions)} positions")
            
            if not positions:
                print("ℹ️ No positions found")
                return pd.DataFrame()
            
            portfolio_data = []
            
            for i, pos in enumerate(positions):
                try:
                    contract = pos.contract
                    print(f"  Processing position {i+1}: {contract.symbol}")
                    
                    # Get additional contract details
                    symbol = contract.symbol
                    sec_type = contract.secType
                    exchange = contract.exchange or contract.primaryExchange or 'SMART'
                    currency = contract.currency
                    
                    # Position details
                    position_size = pos.position
                    market_price = pos.marketPrice if pos.marketPrice else 0.0
                    market_value = pos.marketValue if pos.marketValue else 0.0
                    average_cost = pos.averageCost if pos.averageCost else 0.0
                    unrealized_pnl = pos.unrealizedPNL if pos.unrealizedPNL else 0.0
                    realized_pnl = pos.realizedPNL if pos.realizedPNL else 0.0
                    
                    print(f"    {symbol}: {position_size} shares @ ${market_price:.2f}")
                    
                    portfolio_data.append({
                        'Symbol': symbol,
                        'SecType': sec_type,
                        'Exchange': exchange,
                        'Currency': currency,
                        'Position': position_size,
                        'Market Price': market_price,
                        'Market Value': market_value,
                        'Average Cost': average_cost,
                        'Unrealized PnL': unrealized_pnl,
                        'Realized PnL': realized_pnl,
                        'Account': pos.account
                    })
                    
                except Exception as pos_error:
                    print(f"    ⚠️ Error processing position {i+1}: {pos_error}")
                    continue
            
            df = pd.DataFrame(portfolio_data)
            print(f"✅ Portfolio DataFrame created with {len(df)} positions")
            
            # Add computed columns
            if not df.empty:
                try:
                    # Calculate percentage change
                    df['Pct Change'] = df.apply(
                        lambda row: ((row['Market Price'] - row['Average Cost']) / row['Average Cost'] * 100) 
                        if row['Average Cost'] > 0 else 0, axis=1
                    )
                    
                    # Calculate position weight (approximate)
                    total_abs_value = df['Market Value'].abs().sum()
                    if total_abs_value > 0:
                        df['Weight %'] = (df['Market Value'].abs() / total_abs_value * 100).round(2)
                    else:
                        df['Weight %'] = 0
                        
                    print("✅ Added computed columns: Pct Change, Weight %")
                    
                except Exception as e:
                    print(f"⚠️ Error adding computed columns: {e}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error in get_portfolio_positions_enhanced: {e}")
            return pd.DataFrame()
    
    def get_open_orders_enhanced(self) -> pd.DataFrame:
        """Get enhanced open orders information"""
        try:
            print("🔍 Getting open orders...")
            
            orders = self.ib.openOrders()
            print(f"📋 Found {len(orders)} open orders")
            
            if not orders:
                return pd.DataFrame()
            
            orders_data = []
            for order in orders:
                try:
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
                except Exception as order_error:
                    print(f"⚠️ Error processing order: {order_error}")
                    continue
            
            df = pd.DataFrame(orders_data)
            print(f"✅ Orders DataFrame created with {len(df)} orders")
            return df
            
        except Exception as e:
            print(f"❌ Error in get_open_orders_enhanced: {e}")
            return pd.DataFrame()

# Test function to diagnose data issues
async def diagnose_data_issues():
    """Diagnose data retrieval issues"""
    print("🔍 IBKR Data Diagnostic Test")
    print("=" * 50)
    
    try:
        # Import and connect
        from main import IBKRPortfolioManager
        from config import get_config
        
        config = get_config('ibkr')
        pm = IBKRPortfolioManager(
            host=config['host'],
            port=config['port'],
            client_id=999  # Different client ID for testing
        )
        
        print(f"🔌 Connecting to {config['host']}:{config['port']}...")
        
        if await pm.connect():
            print("✅ Connected successfully!")
            
            # Create enhanced data handler
            handler = EnhancedDataHandler(pm.ib)
            
            # Test account summary
            print("\n📊 Testing Account Summary...")
            print("-" * 30)
            summary = handler.get_account_summary_enhanced()
            
            if summary:
                print(f"✅ Got {len(summary)} summary items:")
                key_metrics = ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 
                              'UnrealizedPnL', 'RealizedPnL']
                
                for metric in key_metrics:
                    if metric in summary:
                        print(f"  ✅ {metric}: {summary[metric]['value']} {summary[metric]['currency']}")
                    else:
                        print(f"  ❌ {metric}: Not found")
                        
                # Show all available metrics
                print(f"\n📋 All available metrics:")
                for key in sorted(summary.keys()):
                    print(f"  - {key}: {summary[key]['value']}")
                    
            else:
                print("❌ No account summary data retrieved!")
                
                # Try basic connection test
                print("\n🧪 Basic Connection Test:")
                try:
                    accounts = pm.ib.managedAccounts()
                    print(f"  Managed accounts: {accounts}")
                    
                    if accounts:
                        print("  ✅ Account access working")
                        
                        # Try getting any account values
                        all_values = pm.ib.accountValues()
                        print(f"  📊 Total account values available: {len(all_values)}")
                        
                        # Show first 10 values
                        for i, val in enumerate(all_values[:10]):
                            print(f"    {val.tag}: {val.value} {val.currency}")
                            
                    else:
                        print("  ❌ No account access")
                        
                except Exception as e:
                    print(f"  ❌ Basic test failed: {e}")
            
            # Test positions
            print("\n📈 Testing Positions...")
            print("-" * 30)
            positions_df = handler.get_portfolio_positions_enhanced()
            
            if not positions_df.empty:
                print(f"✅ Got {len(positions_df)} positions")
                print(positions_df.to_string())
            else:
                print("ℹ️ No positions found (this might be normal)")
            
            # Test orders
            print("\n📋 Testing Orders...")
            print("-" * 30)
            orders_df = handler.get_open_orders_enhanced()
            
            if not orders_df.empty:
                print(f"✅ Got {len(orders_df)} open orders")
                print(orders_df.to_string())
            else:
                print("ℹ️ No open orders (this is normal)")
            
            pm.disconnect()
            print("\n✅ Diagnostic complete!")
            
        else:
            print("❌ Connection failed!")
            
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Running IBKR Data Diagnostic...")
    asyncio.run(diagnose_data_issues())