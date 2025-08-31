#!/usr/bin/env python3
"""
Command Line Interface for IBKR Portfolio Manager
"""

import argparse
import asyncio
import sys
import json
from datetime import datetime
from pathlib import Path

# Import our modules
try:
    from main import IBKRPortfolioManager
    from config import get_config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this from the project directory")
    sys.exit(1)

class IBKRPortfolioCLI:
    def __init__(self):
        self.config = get_config('ibkr')
        self.pm = None
    
    async def connect_manager(self, port=None):
        """Connect to portfolio manager"""
        if port:
            self.config['port'] = port
        
        self.pm = IBKRPortfolioManager(
            host=self.config['host'],
            port=self.config['port'],
            client_id=self.config['client_id']
        )
        
        connected = await self.pm.connect()
        if not connected:
            print(f"❌ Failed to connect to IBKR at {self.config['host']}:{self.config['port']}")
            print("Make sure TWS/Gateway is running with API enabled")
            return False
        
        print(f"✅ Connected to IBKR at {self.config['host']}:{self.config['port']}")
        return True
    
    async def show_summary(self):
        """Show account summary"""
        if not await self.connect_manager():
            return
        
        try:
            print("\n" + "="*60)
            print("📊 ACCOUNT SUMMARY")
            print("="*60)
            
            summary = self.pm.get_account_summary()
            if summary:
                key_metrics = [
                    'NetLiquidation', 'TotalCashValue', 'BuyingPower',
                    'GrossPositionValue', 'UnrealizedPnL', 'RealizedPnL'
                ]
                
                for metric in key_metrics:
                    if metric in summary:
                        value = summary[metric]['value']
                        currency = summary[metric]['currency']
                        print(f"  {metric:20}: {value:>15} {currency}")
            else:
                print("  No account summary available")
                
        finally:
            self.pm.disconnect()
    
    async def show_positions(self, save_to_file=False):
        """Show portfolio positions"""
        if not await self.connect_manager():
            return
        
        try:
            print("\n" + "="*100)
            print("📈 PORTFOLIO POSITIONS")
            print("="*100)
            
            positions_df = self.pm.get_portfolio_positions()
            if not positions_df.empty:
                # Display positions
                print(positions_df.to_string(index=False, float_format='{:.2f}'.format))
                
                # Summary statistics
                total_value = positions_df['Market Value'].sum()
                total_unrealized = positions_df['Unrealized PnL'].sum()
                
                print(f"\n📊 Summary:")
                print(f"  Total Positions: {len(positions_df)}")
                print(f"  Total Market Value: {total_value:,.2f}")
                print(f"  Total Unrealized P&L: {total_unrealized:,.2f}")
                
                if save_to_file:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"positions_{timestamp}.csv"
                    positions_df.to_csv(filename, index=False)
                    print(f"  💾 Saved to: {filename}")
            else:
                print("  No positions found")
                
        finally:
            self.pm.disconnect()
    
    async def show_orders(self):
        """Show open orders"""
        if not await self.connect_manager():
            return
        
        try:
            print("\n" + "="*80)
            print("📋 OPEN ORDERS")
            print("="*80)
            
            orders_df = self.pm.get_open_orders()
            if not orders_df.empty:
                print(orders_df.to_string(index=False))
                print(f"\n  Total Open Orders: {len(orders_df)}")
            else:
                print("  No open orders")
                
        finally:
            self.pm.disconnect()
    
    async def save_snapshot(self, filename=None):
        """Save portfolio snapshot"""
        if not await self.connect_manager():
            return
        
        try:
            print("📸 Taking portfolio snapshot...")
            snapshot_file = self.pm.save_portfolio_snapshot(filename)
            if snapshot_file:
                print(f"✅ Snapshot saved: {snapshot_file}")
                
                # Show file size
                file_size = Path(snapshot_file).stat().st_size
                print(f"   File size: {file_size:,} bytes")
            else:
                print("❌ Failed to save snapshot")
                
        finally:
            self.pm.disconnect()
    
    async def monitor_portfolio(self, interval=30):
        """Start portfolio monitoring"""
        if not await self.connect_manager():
            return
        
        try:
            print(f"🔄 Starting portfolio monitoring (refresh every {interval}s)")
            print("Press Ctrl+C to stop...")
            self.pm.monitor_portfolio(refresh_interval=interval)
        except KeyboardInterrupt:
            print("\n⏹️  Monitoring stopped by user")
        finally:
            self.pm.disconnect()
    
    async def test_connection(self, port=None):
        """Test connection to IBKR"""
        print("🔍 Testing connection to IBKR...")
        
        if await self.connect_manager(port):
            print("✅ Connection successful!")
            
            # Try to get basic info
            try:
                summary = self.pm.get_account_summary()
                if summary:
                    print(f"📊 Account found with {len(summary)} metrics")
                else:
                    print("⚠️  Connected but no account data available")
            except Exception as e:
                print(f"⚠️  Connected but error getting data: {e}")
            
            self.pm.disconnect()
        else:
            print("❌ Connection failed")
            print("\nTroubleshooting tips:")
            print("1. Make sure TWS or IB Gateway is running")
            print("2. Check API settings are enabled (Configure → API → Settings)")
            print("3. Verify the port number (7497 for paper, 7496 for live)")
            print("4. Ensure 'Enable ActiveX and Socket Clients' is checked")

def main():
    parser = argparse.ArgumentParser(description="IBKR Portfolio Manager CLI")
    parser.add_argument('--port', type=int, help='IBKR port (7497 for paper, 7496 for live)')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Test connection command
    subparsers.add_parser('test', help='Test connection to IBKR')
    
    # Summary command
    subparsers.add_parser('summary', help='Show account summary')
    
    # Positions command
    pos_parser = subparsers.add_parser('positions', help='Show portfolio positions')
    pos_parser.add_argument('--save', action='store_true', help='Save positions to CSV file')
    
    # Orders command
    subparsers.add_parser('orders', help='Show open orders')
    
    # Snapshot command
    snap_parser = subparsers.add_parser('snapshot', help='Save portfolio snapshot')
    snap_parser.add_argument('--file', help='Output filename')
    
    # Monitor command
    mon_parser = subparsers.add_parser('monitor', help='Start portfolio monitoring')
    mon_parser.add_argument('--interval', type=int, default=30, help='Refresh interval in seconds')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create CLI instance
    cli = IBKRPortfolioCLI()
    
    # Execute command
    try:
        if args.command == 'test':
            asyncio.run(cli.test_connection(args.port))
        elif args.command == 'summary':
            asyncio.run(cli.show_summary())
        elif args.command == 'positions':
            asyncio.run(cli.show_positions(save_to_file=args.save))
        elif args.command == 'orders':
            asyncio.run(cli.show_orders())
        elif args.command == 'snapshot':
            asyncio.run(cli.save_snapshot(args.file))
        elif args.command == 'monitor':
            asyncio.run(cli.monitor_portfolio(args.interval))
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
    except Exception as e:
        print(f"❌ Error executing command: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())