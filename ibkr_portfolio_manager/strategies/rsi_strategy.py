#!/usr/bin/env python3
"""
RSI Mean Reversion Strategy
Relative Strength Index strategy for IBKR Strategy Engine
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Import base strategy class
from strategy_engine import BaseStrategy, TradingSignal, SignalType

class RSIMeanReversionStrategy(BaseStrategy):
    """
    RSI Mean Reversion Strategy
    
    The RSI (Relative Strength Index) measures if a stock is overbought or oversold:
    - RSI > 70: Overbought (likely to fall) → SELL signal
    - RSI < 30: Oversold (likely to rise) → BUY signal
    - RSI 30-70: Neutral zone → No signal
    
    This is a "mean reversion" strategy - it assumes prices will return to average levels.
    """
    
    def __init__(self, rsi_period: int = 14, oversold_threshold: float = 30, 
                 overbought_threshold: float = 70, position_size_pct: float = 0.03,
                 min_volume: int = 100000):
        
        # Validate parameters
        if not 2 <= rsi_period <= 50:
            raise ValueError("RSI period must be between 2 and 50")
        if not 10 <= oversold_threshold < overbought_threshold <= 90:
            raise ValueError("Invalid RSI thresholds")
        if not 0.01 <= position_size_pct <= 0.15:
            raise ValueError("Position size must be between 1% and 15%")
        
        parameters = {
            'rsi_period': rsi_period,
            'oversold_threshold': oversold_threshold,
            'overbought_threshold': overbought_threshold,
            'position_size_pct': position_size_pct,
            'min_volume': min_volume
        }
        
        name = f"RSI_{rsi_period}_{int(oversold_threshold)}_{int(overbought_threshold)}"
        description = f"RSI Mean Reversion: Buy<{oversold_threshold}, Sell>{overbought_threshold}"
        
        super().__init__(name, description, parameters)
        
        # Strategy-specific settings
        self.min_confidence = 0.3
        self.max_confidence = 0.9
        self.extreme_oversold = oversold_threshold - 10  # Very oversold
        self.extreme_overbought = overbought_threshold + 10  # Very overbought
        
        self.logger.info(f"Initialized RSI Strategy: {rsi_period} period, "
                        f"oversold<{oversold_threshold}, overbought>{overbought_threshold}")
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index)
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss over the period
        """
        
        # Calculate price changes
        delta = prices.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains and losses using EMA (smoothing)
        avg_gains = gains.ewm(span=period, adjust=False).mean()
        avg_losses = losses.ewm(span=period, adjust=False).mean()
        
        # Calculate RSI
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    async def generate_signals(self, market_data: Dict[str, pd.DataFrame]) -> List[TradingSignal]:
        """Generate RSI mean reversion signals"""
        signals = []
        
        for symbol, df in market_data.items():
            try:
                signal = self._analyze_symbol(symbol, df)
                if signal:
                    signals.append(signal)
                    
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}")
                continue
        
        self.logger.info(f"Generated {len(signals)} RSI signals from {len(market_data)} symbols")
        return signals
    
    def _analyze_symbol(self, symbol: str, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Analyze a single symbol for RSI signals"""
        
        # Check if we have enough data
        required_periods = self.parameters['rsi_period'] + 20  # Extra buffer for RSI calculation
        if len(df) < required_periods:
            self.logger.debug(f"Insufficient data for {symbol}: {len(df)} < {required_periods} bars")
            return None
        
        # Calculate RSI
        rsi = self.calculate_rsi(df['close'], self.parameters['rsi_period'])
        
        # Get current values
        current_rsi = rsi.iloc[-1]
        current_price = df['close'].iloc[-1]
        current_volume = df.get('volume', pd.Series([0])).iloc[-1]
        
        # Check volume requirement
        if current_volume < self.parameters['min_volume']:
            self.logger.debug(f"Volume too low for {symbol}: {current_volume}")
            return None
        
        # Determine signal type and base confidence
        signal_type, base_confidence = self._determine_signal(current_rsi)
        
        if signal_type == SignalType.HOLD:
            return None
        
        # Apply additional filters to adjust confidence
        confidence = self._apply_filters(symbol, df, rsi, base_confidence, current_volume)
        
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
                'rsi': round(current_rsi, 2),
                'rsi_category': self._get_rsi_category(current_rsi),
                'oversold_threshold': self.parameters['oversold_threshold'],
                'overbought_threshold': self.parameters['overbought_threshold'],
                'signal_strength': self._get_signal_strength(current_rsi),
                'volume': int(current_volume)
            }
        )
        
        self.logger.info(f"{signal_type.value} signal for {symbol}: "
                        f"RSI={current_rsi:.1f}, price=${current_price:.2f}, confidence={confidence:.1%}")
        
        return signal
    
    def _determine_signal(self, rsi: float) -> tuple:
        """Determine signal type and base confidence from RSI value"""
        
        oversold = self.parameters['oversold_threshold']
        overbought = self.parameters['overbought_threshold']
        
        if rsi <= oversold:
            # Oversold → BUY signal (expect price to bounce back up)
            signal_type = SignalType.BUY
            
            # More oversold = higher confidence
            if rsi <= self.extreme_oversold:
                confidence = 0.8  # Very high confidence for extremely oversold
            else:
                # Linear scale: RSI 30 = 0.3 confidence, RSI 20 = 0.6 confidence
                confidence = max(0.3, (oversold - rsi) / oversold * 2)
                
        elif rsi >= overbought:
            # Overbought → SELL signal (expect price to fall back down)
            signal_type = SignalType.SELL
            
            # More overbought = higher confidence
            if rsi >= self.extreme_overbought:
                confidence = 0.8  # Very high confidence for extremely overbought
            else:
                # Linear scale: RSI 70 = 0.3 confidence, RSI 80 = 0.6 confidence
                confidence = max(0.3, (rsi - overbought) / (100 - overbought) * 2)
                
        else:
            # Neutral zone → No signal
            return SignalType.HOLD, 0.0
        
        return signal_type, min(self.max_confidence, confidence)
    
    def _apply_filters(self, symbol: str, df: pd.DataFrame, rsi: pd.Series,
                      base_confidence: float, current_volume: float) -> float:
        """Apply additional filters to adjust confidence"""
        
        confidence = base_confidence
        
        # Volume filter
        avg_volume = df.get('volume', pd.Series([1])).tail(20).mean()
        volume_ratio = current_volume / max(avg_volume, 1)
        
        if volume_ratio > 1.5:
            confidence *= 1.15  # Boost for high volume
        elif volume_ratio < 0.7:
            confidence *= 0.85  # Penalty for low volume
        
        # RSI trend filter: check if RSI is moving in favor of mean reversion
        if len(rsi) >= 5:
            rsi_recent = rsi.tail(5)
            current_rsi = rsi.iloc[-1]
            
            # For BUY signals (oversold), prefer if RSI is starting to rise
            if base_confidence > 0 and current_rsi < 35:  # Oversold region
                if rsi_recent.iloc[-1] > rsi_recent.iloc[-3]:  # RSI rising
                    confidence *= 1.1
            
            # For SELL signals (overbought), prefer if RSI is starting to fall
            elif base_confidence > 0 and current_rsi > 65:  # Overbought region
                if rsi_recent.iloc[-1] < rsi_recent.iloc[-3]:  # RSI falling
                    confidence *= 1.1
        
        # Price momentum filter: penalize if price momentum is too strong against us
        if len(df) >= 10:
            recent_returns = df['close'].pct_change().tail(5).mean()
            
            # If we're buying (oversold) but price is falling fast, reduce confidence
            if base_confidence > 0 and current_rsi < 35 and recent_returns < -0.02:
                confidence *= 0.9
            
            # If we're selling (overbought) but price is rising fast, reduce confidence  
            elif base_confidence > 0 and current_rsi > 65 and recent_returns > 0.02:
                confidence *= 0.9
        
        # Volatility filter: RSI works better in normal volatility environments
        if len(df) >= 20:
            returns = df['close'].pct_change().tail(20)
            volatility = returns.std()
            
            if volatility > 0.06:  # High volatility
                confidence *= 0.85
            elif volatility < 0.02:  # Low volatility  
                confidence *= 1.05
        
        return min(self.max_confidence, max(0.0, confidence))
    
    def _get_rsi_category(self, rsi: float) -> str:
        """Get human-readable RSI category"""
        if rsi <= 20:
            return "Extremely Oversold"
        elif rsi <= 30:
            return "Oversold"
        elif rsi >= 80:
            return "Extremely Overbought"
        elif rsi >= 70:
            return "Overbought"
        elif 40 <= rsi <= 60:
            return "Neutral"
        else:
            return "Trending"
    
    def _get_signal_strength(self, rsi: float) -> str:
        """Get signal strength description"""
        oversold = self.parameters['oversold_threshold']
        overbought = self.parameters['overbought_threshold']
        
        if rsi <= oversold - 10 or rsi >= overbought + 10:
            return "Very Strong"
        elif rsi <= oversold or rsi >= overbought:
            return "Strong"
        else:
            return "Weak"
    
    def get_strategy_info(self) -> Dict:
        """Get strategy information for display"""
        return {
            'name': self.name,
            'description': self.description,
            'type': 'Mean Reversion',
            'parameters': self.parameters,
            'thresholds': {
                'oversold': self.parameters['oversold_threshold'],
                'overbought': self.parameters['overbought_threshold'],
                'extreme_oversold': self.extreme_oversold,
                'extreme_overbought': self.extreme_overbought
            },
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

# Utility function to create common RSI strategy variations
def create_conservative_rsi() -> RSIMeanReversionStrategy:
    """Create a conservative RSI strategy"""
    return RSIMeanReversionStrategy(
        rsi_period=14,
        oversold_threshold=25,  # More extreme levels
        overbought_threshold=75,
        position_size_pct=0.02  # Smaller positions
    )

def create_aggressive_rsi() -> RSIMeanReversionStrategy:
    """Create an aggressive RSI strategy"""
    return RSIMeanReversionStrategy(
        rsi_period=14,
        oversold_threshold=35,  # Less extreme levels
        overbought_threshold=65,
        position_size_pct=0.05  # Larger positions
    )

def create_scalping_rsi() -> RSIMeanReversionStrategy:
    """Create a fast RSI strategy for scalping"""
    return RSIMeanReversionStrategy(
        rsi_period=7,   # Shorter period = more sensitive
        oversold_threshold=20,
        overbought_threshold=80,
        position_size_pct=0.03
    )

# Example usage and testing
async def test_rsi_strategy():
    """Test the RSI strategy"""
    print("🧪 Testing RSI Mean Reversion Strategy...")
    
    # Create sample data with clear overbought/oversold patterns
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Generate sample price data with oscillating pattern
    base_price = 100
    prices = []
    
    for i in range(100):
        # Create oscillating pattern that will trigger RSI signals
        cycle = np.sin(i * 0.2) * 10  # Sine wave pattern
        trend = i * 0.05  # Slight upward trend
        noise = np.random.normal(0, 1)
        
        price = base_price + cycle + trend + noise
        prices.append(max(80, min(120, price)))  # Keep in reasonable range
    
    sample_data = pd.DataFrame({
        'date': dates,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 100)
    })
    
    print(f"📊 Sample data: {len(sample_data)} days")
    print(f"   Price range: ${min(prices):.2f} - ${max(prices):.2f}")
    
    # Test different RSI strategies
    strategies = [
        ("Conservative", create_conservative_rsi()),
        ("Standard", RSIMeanReversionStrategy()),
        ("Aggressive", create_aggressive_rsi()),
        ("Scalping", create_scalping_rsi())
    ]
    
    market_data = {'TEST': sample_data}
    
    for strategy_name, strategy in strategies:
        print(f"\n🔍 Testing {strategy_name} RSI Strategy:")
        print(f"   {strategy.description}")
        
        signals = await strategy.generate_signals(market_data)
        
        print(f"   📈 Generated {len(signals)} signals")
        
        for signal in signals:
            rsi_value = signal.metadata.get('rsi', 0)
            category = signal.metadata.get('rsi_category', '')
            strength = signal.metadata.get('signal_strength', '')
            
            print(f"     {signal.signal.value} @ ${signal.price:.2f} "
                  f"(RSI: {rsi_value:.1f} - {category}, {strength} signal, "
                  f"confidence: {signal.confidence:.1%})")

if __name__ == "__main__":
    import asyncio
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 RSI Mean Reversion Strategy Test")
    print("=" * 50)
    print("RSI Strategy Logic:")
    print("• RSI < 30: Stock is oversold → BUY (expect bounce up)")
    print("• RSI > 70: Stock is overbought → SELL (expect pullback)")
    print("• RSI 30-70: Neutral zone → No signal")
    print()
    
    # Run test
    asyncio.run(test_rsi_strategy())