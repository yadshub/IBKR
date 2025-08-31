#!/usr/bin/env python3
"""
Moving Average Crossover Strategy
Clean implementation for IBKR Strategy Engine
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List
import logging

# Import base strategy class
from strategy_engine import BaseStrategy, TradingSignal, SignalType

class MovingAverageCrossoverStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy
    
    Generates BUY signal when fast MA crosses above slow MA (Golden Cross)
    Generates SELL signal when fast MA crosses below slow MA (Death Cross)
    """
    
    def __init__(self, fast_period: int = 10, slow_period: int = 20, 
                 position_size_pct: float = 0.05, min_volume: int = 100000):
        
        # Validate parameters
        if fast_period >= slow_period:
            raise ValueError("Fast period must be less than slow period")
        if not 0.01 <= position_size_pct <= 0.20:
            raise ValueError("Position size must be between 1% and 20%")
        
        parameters = {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'position_size_pct': position_size_pct,
            'min_volume': min_volume
        }
        
        name = f"MA_Cross_{fast_period}_{slow_period}"
        description = f"MA Crossover: {fast_period}-day vs {slow_period}-day moving averages"
        
        super().__init__(name, description, parameters)
        
        # Strategy-specific settings
        self.min_confidence = 0.2
        self.max_confidence = 0.8
        
        self.logger.info(f"Initialized MA Crossover: {fast_period}/{slow_period} periods, "
                        f"{position_size_pct:.1%} position size")
    
    async def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        """Generate moving average crossover signals"""
        signals = []
        
        for symbol, df in market_data.items():
            try:
                signal = self._analyze_symbol(symbol, df)
                if signal:
                    signals.append(signal)
                    
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        self.logger.info(f"Generated {len(signals)} signals from {len(market_data)} symbols")
        return signals
    
    def _analyze_symbol(self, symbol: str, df: pd.DataFrame) -> TradingSignal:
        """Analyze a single symbol for crossover signals"""
        
        # Check if we have enough data
        required_periods = self.parameters['slow_period'] + 5
        if len(df) < required_periods:
            self.logger.debug(f"Insufficient data for {symbol}: {len(df)} < {required_periods} bars")
            return None
        
        # Calculate moving averages
        fast_ma = df['close'].rolling(window=self.parameters['fast_period']).mean()
        slow_ma = df['close'].rolling(window=self.parameters['slow_period']).mean()
        
        # Get recent values
        current_fast = fast_ma.iloc[-1]
        current_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]
        
        # Current price and volume
        current_price = df['close'].iloc[-1]
        current_volume = df.get('volume', pd.Series([0])).iloc[-1]
        avg_volume = df.get('volume', pd.Series([0])).tail(20).mean()
        
        # Check volume requirement
        if current_volume < self.parameters['min_volume']:
            self.logger.debug(f"Volume too low for {symbol}: {current_volume}")
            return None
        
        # Detect crossovers
        signal_type, confidence = self._detect_crossover(
            prev_fast, prev_slow, current_fast, current_slow
        )
        
        if signal_type == SignalType.HOLD:
            return None
        
        # Apply additional filters
        confidence = self._apply_filters(symbol, df, confidence, current_volume, avg_volume)
        
        if confidence < self.min_confidence:
            self.logger.debug(f"Confidence too low for {symbol}: {confidence:.2%}")
            return None
        
        # Calculate position size
        quantity = self.calculate_position_size(
            TradingSignal(symbol, signal_type, confidence, current_price, 0, self.name, datetime.now()),
            100000  # Default portfolio value
        )
        
        # Create signal
        signal = TradingSignal(
            symbol=symbol,
            signal=signal_type,
            confidence=confidence,
            price=current_price,
            quantity=quantity,
            strategy_name=self.name,
            timestamp=datetime.now(),
            metadata={
                'fast_ma': round(current_fast, 2),
                'slow_ma': round(current_slow, 2),
                'ma_spread': round(abs(current_fast - current_slow), 2),
                'volume_ratio': round(current_volume / max(avg_volume, 1), 2),
                'crossover_type': 'golden' if signal_type == SignalType.BUY else 'death'
            }
        )
        
        self.logger.info(f"{signal_type.value} signal for {symbol}: "
                        f"price=${current_price:.2f}, confidence={confidence:.1%}")
        
        return signal
    
    def _detect_crossover(self, prev_fast: float, prev_slow: float, 
                         current_fast: float, current_slow: float) -> tuple:
        """Detect MA crossover and calculate base confidence"""
        
        signal_type = SignalType.HOLD
        confidence = 0.0
        
        # Golden Cross: fast MA crosses above slow MA (bullish)
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal_type = SignalType.BUY
            # Confidence based on crossover strength
            spread_pct = (current_fast - current_slow) / current_slow
            confidence = min(self.max_confidence, max(0.1, spread_pct * 20))
            
        # Death Cross: fast MA crosses below slow MA (bearish)
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal_type = SignalType.SELL
            spread_pct = (current_slow - current_fast) / current_fast
            confidence = min(self.max_confidence, max(0.1, spread_pct * 20))
        
        return signal_type, confidence
    
    def _apply_filters(self, symbol: str, df: pd.DataFrame, base_confidence: float,
                      current_volume: float, avg_volume: float) -> float:
        """Apply additional filters to adjust confidence"""
        
        confidence = base_confidence
        
        # Volume filter: boost confidence for high volume
        volume_ratio = current_volume / max(avg_volume, 1)
        if volume_ratio > 1.5:
            confidence *= 1.2  # 20% boost for high volume
        elif volume_ratio < 0.5:
            confidence *= 0.8  # 20% penalty for low volume
        
        # Trend filter: check recent price trend
        recent_prices = df['close'].tail(5)
        if len(recent_prices) >= 5:
            price_trend = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]
            
            # Boost confidence if trend aligns with signal
            if abs(price_trend) > 0.02:  # More than 2% trend
                if (price_trend > 0 and base_confidence > 0):  # Uptrend + BUY
                    confidence *= 1.1
                elif (price_trend < 0 and base_confidence > 0):  # Downtrend + SELL
                    confidence *= 1.1
        
        # Volatility filter: reduce confidence for highly volatile stocks
        if len(df) >= 20:
            returns = df['close'].pct_change().tail(20)
            volatility = returns.std()
            
            if volatility > 0.05:  # High volatility (>5% daily moves)
                confidence *= 0.9
        
        # Cap confidence
        return min(self.max_confidence, max(0.0, confidence))
    
    def get_strategy_info(self) -> Dict:
        """Get strategy information for display"""
        return {
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters,
            'performance': {
                'signals_generated': self.signals_generated,
                'trades_made': self.trades_made,
                'total_pnl': self.total_pnl
            },
            'settings': {
                'enabled': self.enabled,
                'min_confidence': self.min_confidence,
                'max_confidence': self.max_confidence
            }
        }

# Example usage and testing
async def test_ma_strategy():
    """Test the Moving Average strategy"""
    print("🧪 Testing Moving Average Strategy...")
    
    # Create sample data
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    np.random.seed(42)  # For reproducible results
    
    # Generate sample price data with trend
    base_price = 100
    prices = []
    for i in range(100):
        # Add trend and noise
        trend = i * 0.1  # Slight upward trend
        noise = np.random.normal(0, 2)  # Random noise
        price = base_price + trend + noise
        prices.append(max(50, price))  # Keep prices reasonable
    
    # Create sample DataFrame
    sample_data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': np.random.randint(50000, 500000, 100)
    })
    
    # Create strategy
    strategy = MovingAverageCrossoverStrategy(
        fast_period=10,
        slow_period=20,
        position_size_pct=0.05
    )
    
    print(f"📊 Created strategy: {strategy.name}")
    print(f"📝 Description: {strategy.description}")
    
    # Test signal generation
    market_data = {'TEST': sample_data}
    signals = await strategy.generate_signals(market_data)
    
    print(f"\n📈 Generated {len(signals)} signals:")
    for signal in signals:
        print(f"  {signal.signal.value} TEST @ ${signal.price:.2f} "
              f"(confidence: {signal.confidence:.1%})")
        print(f"    Metadata: {signal.metadata}")
    
    # Show strategy info
    print(f"\n📊 Strategy Info:")
    info = strategy.get_strategy_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

if __name__ == "__main__":
    import asyncio
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Moving Average Strategy Test")
    print("=" * 40)
    
    # Run test
    asyncio.run(test_ma_strategy())