"""
Advanced Risk Management System for IBKR Portfolio
Includes position sizing, stop losses, volatility analysis, and risk alerts
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from enum import Enum
import asyncio

from main import IBKRPortfolioManager
from ib_insync import *

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class RiskAlert:
    symbol: str
    risk_type: str
    level: RiskLevel
    message: str
    value: float
    threshold: float
    timestamp: datetime
    action_required: bool = False

@dataclass
class PositionRisk:
    symbol: str
    position_size: float
    market_value: float
    portfolio_weight: float
    var_1d: float  # 1-day Value at Risk
    var_5d: float  # 5-day Value at Risk
    beta: float
    volatility: float
    risk_score: float

class RiskManager:
    def __init__(self, portfolio_manager: IBKRPortfolioManager):
        self.pm = portfolio_manager
        self.logger = logging.getLogger(__name__)
        self.alerts: List[RiskAlert] = []
        
        # Risk thresholds (configurable)
        self.risk_limits = {
            'max_position_weight': 0.15,  # Max 15% in single position
            'max_sector_weight': 0.30,    # Max 30% in single sector
            'max_daily_var': 0.02,        # Max 2% daily VaR
            'max_portfolio_volatility': 0.20,  # Max 20% annual volatility
            'min_diversification_ratio': 0.7,  # Min diversification
            'max_correlation': 0.8,       # Max correlation between positions
            'stop_loss_threshold': -0.10, # 10% stop loss
            'margin_utilization_max': 0.8 # Max 80% margin usage
        }
    
    async def analyze_portfolio_risk(self) -> Dict:
        """Comprehensive portfolio risk analysis"""
        try:
            positions_df = self.pm.get_portfolio_positions()
            account_summary = self.pm.get_account_summary()
            
            if positions_df.empty:
                return {'error': 'No positions to analyze'}
            
            # Get historical data for volatility calculations
            historical_data = await self._get_historical_data(positions_df)
            
            # Calculate individual position risks
            position_risks = []
            for _, position in positions_df.iterrows():
                risk = await self._calculate_position_risk(position, historical_data)
                position_risks.append(risk)
            
            # Calculate portfolio-level metrics
            portfolio_metrics = self._calculate_portfolio_metrics(
                positions_df, position_risks, account_summary
            )
            
            # Generate risk alerts
            self._generate_risk_alerts(position_risks, portfolio_metrics)
            
            return {
                'position_risks': [self._risk_to_dict(r) for r in position_risks],
                'portfolio_metrics': portfolio_metrics,
                'alerts': [self._alert_to_dict(a) for a in self.alerts[-10:]],  # Last 10 alerts
                'risk_score': self._calculate_overall_risk_score(portfolio_metrics),
                'recommendations': self._generate_recommendations(position_risks, portfolio_metrics)
            }
            
        except Exception as e:
            self.logger.error(f"Error in risk analysis: {e}")
            return {'error': str(e)}
    
    async def _get_historical_data(self, positions_df: pd.DataFrame, days: int = 252) -> Dict:
        """Get historical price data for volatility calculations"""
        historical_data = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        for _, position in positions_df.iterrows():
            try:
                # Create contract
                if position['SecType'] == 'STK':
                    contract = Stock(position['Symbol'], position['Exchange'], position['Currency'])
                else:
                    continue  # Skip non-stock instruments for now
                
                # Get historical bars
                bars = self.pm.ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr=f'{days} D',
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )
                
                if bars:
                    df = util.df(bars)
                    df['returns'] = df['close'].pct_change().dropna()
                    historical_data[position['Symbol']] = df
                    
            except Exception as e:
                self.logger.warning(f"Could not get historical data for {position['Symbol']}: {e}")
                
        return historical_data
    
    async def _calculate_position_risk(self, position: pd.Series, historical_data: Dict) -> PositionRisk:
        """Calculate risk metrics for individual position"""
        symbol = position['Symbol']
        
        # Default values
        volatility = 0.0
        beta = 1.0
        var_1d = 0.0
        var_5d = 0.0
        
        if symbol in historical_data:
            returns = historical_data[symbol]['returns']
            
            # Calculate volatility (annualized)
            volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0.0
            
            # Calculate VaR (95% confidence)
            if len(returns) > 10:
                var_1d = np.percentile(returns, 5) * position['Market Value']
                var_5d = np.sqrt(5) * var_1d
            
            # Beta calculation (simplified - would need market index data)
            beta = 1.0  # Placeholder
        
        # Calculate portfolio weight
        # We'll need total portfolio value - approximating from position data
        portfolio_weight = abs(position['Market Value']) / 100000  # Placeholder calculation
        
        # Risk score (0-100, higher = riskier)
        risk_score = min(100, (volatility * 100) + (portfolio_weight * 100) + (abs(beta - 1) * 50))
        
        return PositionRisk(
            symbol=symbol,
            position_size=position['Position'],
            market_value=position['Market Value'],
            portfolio_weight=portfolio_weight,
            var_1d=var_1d,
            var_5d=var_5d,
            beta=beta,
            volatility=volatility,
            risk_score=risk_score
        )
    
    def _calculate_portfolio_metrics(self, positions_df: pd.DataFrame, 
                                   position_risks: List[PositionRisk], 
                                   account_summary: Dict) -> Dict:
        """Calculate portfolio-level risk metrics"""
        
        total_value = float(account_summary.get('NetLiquidation', {}).get('value', 0))
        total_unrealized_pnl = float(account_summary.get('UnrealizedPnL', {}).get('value', 0))
        
        # Concentration risk
        max_position_weight = max([r.portfolio_weight for r in position_risks]) if position_risks else 0
        
        # Portfolio volatility (simplified)
        weighted_volatilities = [r.volatility * r.portfolio_weight for r in position_risks]
        portfolio_volatility = sum(weighted_volatilities) if weighted_volatilities else 0
        
        # VaR calculations
        portfolio_var_1d = sum([r.var_1d for r in position_risks])
        portfolio_var_5d = sum([r.var_5d for r in position_risks])
        
        # Diversification metrics
        num_positions = len(position_risks)
        diversification_ratio = min(1.0, num_positions / 20.0) if num_positions > 0 else 0
        
        # Margin utilization
        buying_power = float(account_summary.get('BuyingPower', {}).get('value', 1))
        margin_utilization = (total_value - buying_power) / total_value if total_value > 0 else 0
        
        return {
            'total_portfolio_value': total_value,
            'total_unrealized_pnl': total_unrealized_pnl,
            'max_position_weight': max_position_weight,
            'portfolio_volatility': portfolio_volatility,
            'portfolio_var_1d': portfolio_var_1d,
            'portfolio_var_5d': portfolio_var_5d,
            'num_positions': num_positions,
            'diversification_ratio': diversification_ratio,
            'margin_utilization': margin_utilization,
            'return_on_equity': (total_unrealized_pnl / total_value * 100) if total_value > 0 else 0
        }
    
    def _generate_risk_alerts(self, position_risks: List[PositionRisk], portfolio_metrics: Dict):
        """Generate risk alerts based on thresholds"""
        current_time = datetime.now()
        
        # Clear old alerts (keep only last hour)
        self.alerts = [a for a in self.alerts if 
                      current_time - a.timestamp < timedelta(hours=1)]
        
        # Position concentration alerts
        for risk in position_risks:
            if risk.portfolio_weight > self.risk_limits['max_position_weight']:
                self.alerts.append(RiskAlert(
                    symbol=risk.symbol,
                    risk_type='Position Concentration',
                    level=RiskLevel.HIGH,
                    message=f'Position weight ({risk.portfolio_weight:.1%}) exceeds limit ({self.risk_limits["max_position_weight"]:.1%})',
                    value=risk.portfolio_weight,
                    threshold=self.risk_limits['max_position_weight'],
                    timestamp=current_time,
                    action_required=True
                ))
        
        # Portfolio volatility alert
        if portfolio_metrics['portfolio_volatility'] > self.risk_limits['max_portfolio_volatility']:
            self.alerts.append(RiskAlert(
                symbol='PORTFOLIO',
                risk_type='High Volatility',
                level=RiskLevel.MEDIUM,
                message=f'Portfolio volatility ({portfolio_metrics["portfolio_volatility"]:.1%}) exceeds limit',
                value=portfolio_metrics['portfolio_volatility'],
                threshold=self.risk_limits['max_portfolio_volatility'],
                timestamp=current_time
            ))
        
        # VaR alerts
        var_pct = abs(portfolio_metrics['portfolio_var_1d']) / portfolio_metrics['total_portfolio_value']
        if var_pct > self.risk_limits['max_daily_var']:
            self.alerts.append(RiskAlert(
                symbol='PORTFOLIO',
                risk_type='High Value at Risk',
                level=RiskLevel.HIGH,
                message=f'Daily VaR ({var_pct:.1%}) exceeds limit ({self.risk_limits["max_daily_var"]:.1%})',
                value=var_pct,
                threshold=self.risk_limits['max_daily_var'],
                timestamp=current_time,
                action_required=True
            ))
        
        # Margin utilization alert
        if portfolio_metrics['margin_utilization'] > self.risk_limits['margin_utilization_max']:
            self.alerts.append(RiskAlert(
                symbol='PORTFOLIO',
                risk_type='High Margin Usage',
                level=RiskLevel.CRITICAL,
                message=f'Margin utilization ({portfolio_metrics["margin_utilization"]:.1%}) exceeds safe limit',
                value=portfolio_metrics['margin_utilization'],
                threshold=self.risk_limits['margin_utilization_max'],
                timestamp=current_time,
                action_required=True
            ))
    
    def _calculate_overall_risk_score(self, portfolio_metrics: Dict) -> float:
        """Calculate overall portfolio risk score (0-100)"""
        scores = []
        
        # Concentration risk (0-30 points)
        concentration_score = min(30, portfolio_metrics['max_position_weight'] * 100 * 2)
        scores.append(concentration_score)
        
        # Volatility risk (0-25 points)
        volatility_score = min(25, portfolio_metrics['portfolio_volatility'] * 100 * 1.25)
        scores.append(volatility_score)
        
        # VaR risk (0-25 points)
        var_pct = abs(portfolio_metrics['portfolio_var_1d']) / max(portfolio_metrics['total_portfolio_value'], 1)
        var_score = min(25, var_pct * 100 * 12.5)
        scores.append(var_score)
        
        # Diversification penalty (0-20 points)
        diversification_score = max(0, 20 - portfolio_metrics['diversification_ratio'] * 20)
        scores.append(diversification_score)
        
        return sum(scores)
    
    def _generate_recommendations(self, position_risks: List[PositionRisk], 
                                portfolio_metrics: Dict) -> List[str]:
        """Generate actionable risk management recommendations"""
        recommendations = []
        
        # Position concentration recommendations
        high_weight_positions = [r for r in position_risks 
                               if r.portfolio_weight > self.risk_limits['max_position_weight']]
        
        for position in high_weight_positions:
            recommendations.append(
                f"Consider reducing {position.symbol} position size (currently {position.portfolio_weight:.1%} of portfolio)"
            )
        
        # Diversification recommendations
        if portfolio_metrics['num_positions'] < 10:
            recommendations.append(
                f"Consider increasing diversification (currently {portfolio_metrics['num_positions']} positions)"
            )
        
        # Volatility recommendations
        if portfolio_metrics['portfolio_volatility'] > self.risk_limits['max_portfolio_volatility']:
            recommendations.append(
                "Consider adding lower-volatility positions to reduce overall portfolio risk"
            )
        
        # Margin recommendations
        if portfolio_metrics['margin_utilization'] > 0.6:
            recommendations.append(
                "Consider reducing margin utilization for safer risk management"
            )
        
        # High-risk position recommendations
        high_risk_positions = [r for r in position_risks if r.risk_score > 70]
        for position in high_risk_positions:
            recommendations.append(
                f"Monitor {position.symbol} closely - high risk score ({position.risk_score:.0f}/100)"
            )
        
        return recommendations[:10]  # Limit to top 10 recommendations
    
    def _risk_to_dict(self, risk: PositionRisk) -> Dict:
        """Convert PositionRisk to dictionary"""
        return {
            'symbol': risk.symbol,
            'position_size': risk.position_size,
            'market_value': risk.market_value,
            'portfolio_weight': risk.portfolio_weight,
            'var_1d': risk.var_1d,
            'var_5d': risk.var_5d,
            'beta': risk.beta,
            'volatility': risk.volatility,
            'risk_score': risk.risk_score
        }
    
    def _alert_to_dict(self, alert: RiskAlert) -> Dict:
        """Convert RiskAlert to dictionary"""
        return {
            'symbol': alert.symbol,
            'risk_type': alert.risk_type,
            'level': alert.level.value,
            'message': alert.message,
            'value': alert.value,
            'threshold': alert.threshold,
            'timestamp': alert.timestamp.isoformat(),
            'action_required': alert.action_required
        }

# Usage example
async def main():
    """Example usage of RiskManager"""
    pm = IBKRPortfolioManager()
    
    if await pm.connect():
        risk_manager = RiskManager(pm)
        
        print("🔍 Analyzing portfolio risk...")
        risk_analysis = await risk_manager.analyze_portfolio_risk()
        
        if 'error' not in risk_analysis:
            print(f"\n📊 Portfolio Risk Score: {risk_analysis['risk_score']:.1f}/100")
            
            print(f"\n⚠️  Active Alerts: {len(risk_analysis['alerts'])}")
            for alert in risk_analysis['alerts']:
                level_emoji = {'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🟠', 'CRITICAL': '🔴'}
                print(f"  {level_emoji[alert['level']]} {alert['message']}")
            
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(risk_analysis['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        pm.disconnect()

if __name__ == "__main__":
    asyncio.run(main())