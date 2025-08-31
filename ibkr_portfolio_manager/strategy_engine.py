#!/usr/bin/env python3
"""
Basic Strategy Engine for IBKR Portfolio Manager
Clean, simple implementation with essential features
"""

import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

# Strategy Engine Imports
from ib_insync import *

# Enums for signal types
class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL" 
    HOLD = "HOLD"

class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

# Data structures for signals and trades
@dataclass
class TradingSignal:
    symbol: str
    signal: SignalType
    confidence: float  # 0.0 to 1.0
    price: float
    quantity: int
    strategy_name: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass 
class Trade:
    trade_id: str
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    price: float
    timestamp: datetime
    strategy: str
    status: OrderStatus = OrderStatus.PENDING
    pnl: float = 0.0

# Base Strategy Class
class BaseStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.enabled = True
        self.signals_generated = 0
        self.trades_made = 0
        self.total_pnl = 0.0
        self.logger = logging.getLogger(f"Strategy.{name}")
    
    async def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        """Generate trading signals - to be implemented by each strategy"""
        raise NotImplementedError("Each strategy must implement generate_signals")
    
    def calculate_position_size(self, signal: TradingSignal, portfolio_value: float) -> int:
        """Calculate position size for a trade"""
        position_size_pct = self.parameters.get('position_size_pct', 0.05)
        position_value = portfolio_value * position_size_pct
        
        if signal.price > 0:
            return max(1, int(position_value / signal.price))
        return 100  # Default fallback

# Simple Moving Average Strategy Implementation  
class MovingAverageStrategy(BaseStrategy):
    """Moving Average Crossover Strategy"""
    
    def __init__(self, fast_period: int = 10, slow_period: int = 20, position_size_pct: float = 0.05):
        parameters = {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'position_size_pct': position_size_pct
        }
        
        description = f"Buy when {fast_period}-day MA crosses above {slow_period}-day MA"
        super().__init__("MovingAverage", description, parameters)
    
    async def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        signals = []
        
        for symbol, df in market_data.items():
            try:
                if len(df) < self.parameters['slow_period'] + 2:
                    continue
                
                # Calculate moving averages
                fast_ma = df['close'].rolling(window=self.parameters['fast_period']).mean()
                slow_ma = df['close'].rolling(window=self.parameters['slow_period']).mean()
                
                # Get last two values to detect crossover
                current_fast = fast_ma.iloc[-1]
                current_slow = slow_ma.iloc[-1]
                prev_fast = fast_ma.iloc[-2]
                prev_slow = slow_ma.iloc[-2]
                
                current_price = df['close'].iloc[-1]
                
                # Check for crossovers
                signal_type = SignalType.HOLD
                confidence = 0.0
                
                # Golden Cross: fast MA crosses above slow MA (bullish)
                if prev_fast <= prev_slow and current_fast > current_slow:
                    signal_type = SignalType.BUY
                    # Confidence based on crossover strength
                    confidence = min(0.8, abs(current_fast - current_slow) / current_slow)
                    
                # Death Cross: fast MA crosses below slow MA (bearish)  
                elif prev_fast >= prev_slow and current_fast < current_slow:
                    signal_type = SignalType.SELL
                    confidence = min(0.8, abs(current_fast - current_slow) / current_fast)
                
                # Only generate signal if confidence is reasonable
                if signal_type != SignalType.HOLD and confidence > 0.1:
                    quantity = self.calculate_position_size(
                        TradingSignal(symbol, signal_type, confidence, current_price, 0, self.name, datetime.now()),
                        100000  # Assume $100k portfolio for now
                    )
                    
                    signal = TradingSignal(
                        symbol=symbol,
                        signal=signal_type,
                        confidence=confidence,
                        price=current_price,
                        quantity=quantity,
                        strategy_name=self.name,
                        timestamp=datetime.now(),
                        metadata={
                            'fast_ma': current_fast,
                            'slow_ma': current_slow,
                            'crossover_strength': abs(current_fast - current_slow)
                        }
                    )
                    
                    signals.append(signal)
                    self.signals_generated += 1
                    
                    self.logger.info(f"Generated {signal_type.value} signal for {symbol}: "
                                   f"confidence={confidence:.2%}, price=${current_price:.2f}")
                
            except Exception as e:
                self.logger.error(f"Error generating signal for {symbol}: {e}")
                continue
        
        return signals

# Main Strategy Engine Class
class StrategyEngine:
    """Main engine that manages strategies and executes trades"""
    
    def __init__(self, portfolio_manager):
        self.pm = portfolio_manager
        self.strategies: List[BaseStrategy] = []
        self.trades: List[Trade] = []
        self.signals_history: List[TradingSignal] = []
        self.logger = logging.getLogger("StrategyEngine")
        
        # Safety settings
        self.paper_trading_mode = True  # ALWAYS start in paper mode!
        self.max_trades_per_day = 10
        self.max_position_count = 15
        self.min_signal_confidence = 0.4
        self.max_position_size_pct = 0.10  # Max 10% of portfolio in single position
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        
        self.logger.info("Strategy Engine initialized in PAPER TRADING mode")
    
    def add_strategy(self, strategy: BaseStrategy):
        """Add a trading strategy to the engine"""
        self.strategies.append(strategy)
        self.logger.info(f"Added strategy: {strategy.name} - {strategy.description}")
    
    def remove_strategy(self, strategy_name: str):
        """Remove a strategy by name"""
        self.strategies = [s for s in self.strategies if s.name != strategy_name]
        self.logger.info(f"Removed strategy: {strategy_name}")
    
    def get_strategy_by_name(self, name: str) -> Optional[BaseStrategy]:
        """Get strategy by name"""
        return next((s for s in self.strategies if s.name == name), None)
    
    async def get_market_data(self, symbols: List[str], timeframe: str = '1 day', duration: str = '60 D') -> Dict[str, pd.DataFrame]:
        """Get historical market data for analysis"""
        market_data = {}
        
        for symbol in symbols:
            try:
                self.logger.debug(f"Fetching market data for {symbol}")
                
                # Create stock contract
                contract = Stock(symbol, 'SMART', 'USD')
                
                # Get historical bars
                bars = self.pm.ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr=duration,
                    barSizeSetting=timeframe,
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )
                
                if bars:
                    df = util.df(bars)
                    # Ensure we have the right column names
                    df.columns = [col.lower() for col in df.columns]
                    market_data[symbol] = df
                    self.logger.debug(f"Got {len(df)} bars for {symbol}")
                else:
                    self.logger.warning(f"No historical data received for {symbol}")
                    
            except Exception as e:
                self.logger.error(f"Failed to get market data for {symbol}: {e}")
                continue
        
        return market_data
    
    async def generate_all_signals(self, symbols: List[str]) -> List[TradingSignal]:
        """Generate signals from all enabled strategies"""
        all_signals = []
        
        # Get market data for all symbols
        self.logger.info(f"Fetching market data for {len(symbols)} symbols...")
        market_data = await self.get_market_data(symbols)
        
        if not market_data:
            self.logger.warning("No market data available - cannot generate signals")
            return all_signals
        
        self.logger.info(f"Retrieved market data for {len(market_data)} symbols")
        
        # Run each enabled strategy
        for strategy in self.strategies:
            if not strategy.enabled:
                continue
            
            try:
                self.logger.info(f"Running strategy: {strategy.name}")
                signals = await strategy.generate_signals(market_data)
                
                # Filter by minimum confidence
                filtered_signals = [
                    s for s in signals 
                    if s.confidence >= self.min_signal_confidence
                ]
                
                all_signals.extend(filtered_signals)
                
                self.logger.info(f"Strategy {strategy.name} generated {len(filtered_signals)} signals "
                               f"(filtered from {len(signals)} total)")
                
            except Exception as e:
                self.logger.error(f"Error in strategy {strategy.name}: {e}")
                continue
        
        # Remove duplicate signals for same symbol (keep highest confidence)
        unique_signals = {}
        for signal in all_signals:
            key = f"{signal.symbol}_{signal.signal.value}"
            if key not in unique_signals or signal.confidence > unique_signals[key].confidence:
                unique_signals[key] = signal
        
        final_signals = list(unique_signals.values())
        
        # Sort by confidence (highest first)
        final_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        # Add to history
        self.signals_history.extend(final_signals)
        
        # Keep only last 1000 signals in history
        if len(self.signals_history) > 1000:
            self.signals_history = self.signals_history[-1000:]
        
        self.logger.info(f"Generated {len(final_signals)} unique signals")
        return final_signals
    
    async def execute_signal(self, signal: TradingSignal) -> Optional[Trade]:
        """Execute a trading signal"""
        
        if self.paper_trading_mode:
            self.logger.info(f"PAPER TRADE: {signal.signal.value} {signal.quantity} {signal.symbol} @ ${signal.price:.2f}")
            
            # Create mock trade for paper trading
            trade = Trade(
                trade_id=f"PAPER_{len(self.trades)}",
                symbol=signal.symbol,
                action=signal.signal.value,
                quantity=signal.quantity,
                price=signal.price,
                timestamp=datetime.now(),
                strategy=signal.strategy_name,
                status=OrderStatus.FILLED  # Assume filled for paper trading
            )
            
            self.trades.append(trade)
            self.total_trades += 1
            
            return trade
        
        # LIVE TRADING (only if paper_trading_mode = False)
        try:
            self.logger.info(f"LIVE TRADE: Executing {signal.signal.value} {signal.quantity} {signal.symbol}")
            
            # Create contract
            contract = Stock(signal.symbol, 'SMART', 'USD')
            
            # Create order
            action = 'BUY' if signal.signal == SignalType.BUY else 'SELL'
            order = MarketOrder(action, signal.quantity)
            order.orderRef = f"{signal.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Place order
            ib_trade = self.pm.ib.placeOrder(contract, order)
            
            # Create trade record
            trade = Trade(
                trade_id=str(ib_trade.order.orderId),
                symbol=signal.symbol,
                action=action,
                quantity=signal.quantity,
                price=signal.price,
                timestamp=datetime.now(),
                strategy=signal.strategy_name,
                status=OrderStatus.PENDING
            )
            
            self.trades.append(trade)
            self.total_trades += 1
            
            self.logger.info(f"Order placed: {action} {signal.quantity} {signal.symbol} (Order ID: {trade.trade_id})")
            return trade
            
        except Exception as e:
            self.logger.error(f"Failed to execute trade for {signal.symbol}: {e}")
            return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all strategies"""
        summary = {
            'total_strategies': len(self.strategies),
            'enabled_strategies': len([s for s in self.strategies if s.enabled]),
            'total_signals': len(self.signals_history),
            'total_trades': len(self.trades),
            'paper_trading': self.paper_trading_mode,
            'strategy_performance': {}
        }
        
        # Individual strategy performance
        for strategy in self.strategies:
            summary['strategy_performance'][strategy.name] = {
                'enabled': strategy.enabled,
                'signals_generated': strategy.signals_generated,
                'trades_made': strategy.trades_made,
                'total_pnl': strategy.total_pnl,
                'description': strategy.description
            }
        
        return summary
    
    def get_recent_signals(self, count: int = 10) -> List[TradingSignal]:
        """Get most recent signals"""
        return self.signals_history[-count:] if self.signals_history else []
    
    def get_recent_trades(self, count: int = 10) -> List[Trade]:
        """Get most recent trades"""
        return self.trades[-count:] if self.trades else []
    
    def enable_live_trading(self, confirm_code: str = None):
        """Enable live trading (requires confirmation)"""
        if confirm_code != "ENABLE_LIVE_TRADING_I_UNDERSTAND_THE_RISKS":
            self.logger.warning("Live trading not enabled - confirmation code required")
            return False
        
        self.paper_trading_mode = False
        self.logger.warning("🚨 LIVE TRADING ENABLED! Real money at risk! 🚨")
        return True
    
    def disable_live_trading(self):
        """Disable live trading and return to paper mode"""
        self.paper_trading_mode = True
        self.logger.info("✅ Switched back to PAPER TRADING mode")

# Example usage and testing
async def test_strategy_engine():
    """Test the strategy engine with sample data"""
    print("🧪 Testing Strategy Engine...")
    
    from main import IBKRPortfolioManager
    from config import get_config
    
    # Connect to IBKR
    config = get_config('ibkr')
    pm = IBKRPortfolioManager(
        host=config['host'],
        port=config['port'],
        client_id=999  # Different client ID for testing
    )
    
    if not await pm.connect():
        print("❌ Failed to connect to IBKR")
        return
    
    try:
        print("✅ Connected to IBKR")
        
        # Create strategy engine
        engine = StrategyEngine(pm)
        
        # Add a simple moving average strategy
        ma_strategy = MovingAverageStrategy(fast_period=10, slow_period=20, position_size_pct=0.05)
        engine.add_strategy(ma_strategy)
        
        print(f"📊 Added strategy: {ma_strategy.name}")
        
        # Test with a few symbols
        test_symbols = ['AAPL', 'MSFT', 'GOOGL']
        print(f"🔍 Testing with symbols: {test_symbols}")
        
        # Generate signals
        signals = await engine.generate_all_signals(test_symbols)
        
        print(f"\n📈 Generated {len(signals)} signals:")
        for signal in signals:
            print(f"  {signal.signal.value} {signal.symbol} @ ${signal.price:.2f} "
                  f"(confidence: {signal.confidence:.1%}, qty: {signal.quantity})")
        
        # Test paper trading execution
        if signals:
            print(f"\n💼 Testing paper trade execution...")
            for signal in signals[:2]:  # Execute first 2 signals
                trade = await engine.execute_signal(signal)
                if trade:
                    print(f"  ✅ Paper trade: {trade.action} {trade.quantity} {trade.symbol}")
        
        # Show performance summary
        print(f"\n📊 Performance Summary:")
        perf = engine.get_performance_summary()
        print(f"  Total Strategies: {perf['total_strategies']}")
        print(f"  Total Signals: {perf['total_signals']}")
        print(f"  Total Trades: {perf['total_trades']}")
        print(f"  Paper Trading: {perf['paper_trading']}")
        
        print("\n✅ Strategy Engine test completed!")
        
    finally:
        pm.disconnect()

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 IBKR Strategy Engine")
    print("=" * 50)
    
    # Run test
    asyncio.run(test_strategy_engine())