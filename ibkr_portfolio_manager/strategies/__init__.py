#!/usr/bin/env python3
"""
Strategies Package for IBKR Portfolio Manager
Collection of trading strategies for automated trading
"""

# Import all available strategies
from .moving_average import MovingAverageCrossoverStrategy
from .rsi_strategy import (
    RSIMeanReversionStrategy,
    create_conservative_rsi,
    create_aggressive_rsi,
    create_scalping_rsi
)

# Version info
__version__ = "1.0.0"
__author__ = "IBKR Portfolio Manager"

# Available strategies registry
AVAILABLE_STRATEGIES = {
    # Moving Average Strategies
    'ma_cross_10_20': lambda: MovingAverageCrossoverStrategy(fast_period=10, slow_period=20),
    'ma_cross_5_15': lambda: MovingAverageCrossoverStrategy(fast_period=5, slow_period=15),
    'ma_cross_20_50': lambda: MovingAverageCrossoverStrategy(fast_period=20, slow_period=50),
    
    # RSI Strategies
    'rsi_standard': lambda: RSIMeanReversionStrategy(),
    'rsi_conservative': create_conservative_rsi,
    'rsi_aggressive': create_aggressive_rsi,
    'rsi_scalping': create_scalping_rsi,
}

# Strategy categories
STRATEGY_CATEGORIES = {
    'Trend Following': ['ma_cross_10_20', 'ma_cross_5_15', 'ma_cross_20_50'],
    'Mean Reversion': ['rsi_standard', 'rsi_conservative', 'rsi_aggressive', 'rsi_scalping'],
}

def get_strategy(name: str):
    """Get a strategy instance by name"""
    if name in AVAILABLE_STRATEGIES:
        return AVAILABLE_STRATEGIES[name]()
    else:
        available = ', '.join(AVAILABLE_STRATEGIES.keys())
        raise ValueError(f"Strategy '{name}' not found. Available: {available}")

def list_strategies() -> dict:
    """List all available strategies with descriptions"""
    strategies = {}
    
    for name, strategy_factory in AVAILABLE_STRATEGIES.items():
        try:
            strategy = strategy_factory()
            strategies[name] = {
                'name': strategy.name,
                'description': strategy.description,
                'parameters': strategy.parameters
            }
        except Exception as e:
            strategies[name] = {'error': str(e)}
    
    return strategies

def get_strategies_by_category(category: str) -> list:
    """Get strategies by category"""
    if category in STRATEGY_CATEGORIES:
        return [get_strategy(name) for name in STRATEGY_CATEGORIES[category]]
    else:
        available_categories = ', '.join(STRATEGY_CATEGORIES.keys())
        raise ValueError(f"Category '{category}' not found. Available: {available_categories}")

# Quick factory functions for common use cases
def create_trend_following_portfolio():
    """Create a portfolio of trend-following strategies"""
    return [
        get_strategy('ma_cross_10_20'),
        get_strategy('ma_cross_5_15'),
    ]

def create_mean_reversion_portfolio():
    """Create a portfolio of mean-reversion strategies"""
    return [
        get_strategy('rsi_standard'),
        get_strategy('rsi_conservative'),
    ]

def create_balanced_portfolio():
    """Create a balanced portfolio with both trend and mean reversion"""
    return [
        get_strategy('ma_cross_10_20'),   # Trend following
        get_strategy('rsi_standard'),     # Mean reversion
    ]

def create_conservative_portfolio():
    """Create a conservative portfolio with lower risk settings"""
    return [
        get_strategy('ma_cross_20_50'),   # Slower MA for fewer signals
        get_strategy('rsi_conservative'), # More extreme RSI levels
    ]

def create_aggressive_portfolio():
    """Create an aggressive portfolio for active trading"""
    return [
        get_strategy('ma_cross_5_15'),    # Faster MA for more signals
        get_strategy('rsi_aggressive'),   # Less extreme RSI levels
        get_strategy('rsi_scalping'),     # Fast RSI for scalping
    ]

# Export main classes and functions
__all__ = [
    # Strategy classes
    'MovingAverageCrossoverStrategy',
    'RSIMeanReversionStrategy',
    
    # RSI factory functions
    'create_conservative_rsi',
    'create_aggressive_rsi', 
    'create_scalping_rsi',
    
    # Utility functions
    'get_strategy',
    'list_strategies',
    'get_strategies_by_category',
    
    # Portfolio factory functions
    'create_trend_following_portfolio',
    'create_mean_reversion_portfolio',
    'create_balanced_portfolio',
    'create_conservative_portfolio',
    'create_aggressive_portfolio',
    
    # Registry
    'AVAILABLE_STRATEGIES',
    'STRATEGY_CATEGORIES',
]

if __name__ == "__main__":
    # Demo when run directly
    print("🚀 IBKR Portfolio Manager - Available Strategies")
    print("=" * 60)
    
    print("\n📊 Strategy Categories:")
    for category, strategy_names in STRATEGY_CATEGORIES.items():
        print(f"\n{category}:")
        for name in strategy_names:
            try:
                strategy = get_strategy(name)
                print(f"  • {name}: {strategy.description}")
            except Exception as e:
                print(f"  • {name}: Error - {e}")
    
    print("\n🎯 Quick Portfolio Examples:")
    portfolios = {
        'Balanced': create_balanced_portfolio(),
        'Conservative': create_conservative_portfolio(),
        'Aggressive': create_aggressive_portfolio(),
    }
    
    for portfolio_name, strategies in portfolios.items():
        print(f"\n{portfolio_name} Portfolio:")
        for strategy in strategies:
            print(f"  • {strategy.name}: {strategy.description}")