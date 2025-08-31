"""
AI-Powered Market Analysis and Alert System
Includes sentiment analysis, news monitoring, and intelligent alerts
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import re
from textblob import TextBlob

from main import IBKRPortfolioManager

@dataclass
class MarketNews:
    title: str
    summary: str
    url: str
    source: str
    timestamp: datetime
    symbols_mentioned: List[str]
    sentiment_score: float  # -1 (negative) to 1 (positive)
    relevance_score: float  # 0 to 1

@dataclass
class MarketAlert:
    alert_type: str
    symbol: str
    message: str
    priority: str  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: datetime
    data: Dict
    action_suggested: Optional[str] = None

class SentimentAnalyzer:
    """Analyze sentiment from text using multiple approaches"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SentimentAnalyzer")
        
        # Financial keywords with sentiment weights
        self.bullish_keywords = [
            'bullish', 'buy', 'strong buy', 'upgrade', 'outperform', 'rally', 'surge',
            'breakout', 'momentum', 'growth', 'profit', 'earnings beat', 'revenue growth',
            'expansion', 'acquisition', 'partnership', 'innovation', 'breakthrough'
        ]
        
        self.bearish_keywords = [
            'bearish', 'sell', 'strong sell', 'downgrade', 'underperform', 'crash', 'plunge',
            'breakdown', 'decline', 'loss', 'earnings miss', 'revenue decline',
            'contraction', 'bankruptcy', 'lawsuit', 'investigation', 'scandal'
        ]
    
    def analyze_text_sentiment(self, text: str) -> float:
        """Analyze sentiment of text (-1 to 1)"""
        try:
            # Use TextBlob for basic sentiment
            blob = TextBlob(text.lower())
            base_sentiment = blob.sentiment.polarity
            
            # Apply financial keyword weighting
            financial_sentiment = self._calculate_financial_sentiment(text.lower())
            
            # Weighted combination
            combined_sentiment = (base_sentiment * 0.6) + (financial_sentiment * 0.4)
            
            return max(-1.0, min(1.0, combined_sentiment))
            
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return 0.0
    
    def _calculate_financial_sentiment(self, text: str) -> float:
        """Calculate sentiment based on financial keywords"""
        bullish_count = sum(1 for keyword in self.bullish_keywords if keyword in text)
        bearish_count = sum(1 for keyword in self.bearish_keywords if keyword in text)
        
        total_keywords = bullish_count + bearish_count
        if total_keywords == 0:
            return 0.0
        
        sentiment = (bullish_count - bearish_count) / total_keywords
        return sentiment

class NewsMonitor:
    """Monitor financial news and extract relevant information"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.sentiment_analyzer = SentimentAnalyzer()
        self.logger = logging.getLogger(__name__ + ".NewsMonitor")
        
        # News sources configuration
        self.news_sources = {
            'alpha_vantage': 'https://www.alphavantage.co/query',
            'finnhub': 'https://finnhub.io/api/v1',
            'newsapi': 'https://newsapi.org/v2/everything'
        }
    
    async def get_market_news(self, symbols: List[str], hours_back: int = 24) -> List[MarketNews]:
        """Get relevant market news for specified symbols"""
        all_news = []
        
        try:
            # Get news from multiple sources
            tasks = []
            
            if 'alpha_vantage' in self.api_keys:
                tasks.append(self._get_alpha_vantage_news(symbols, hours_back))
            
            if 'newsapi' in self.api_keys:
                tasks.append(self._get_newsapi_news(symbols, hours_back))
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine results
            for result in results:
                if isinstance(result, list):
                    all_news.extend(result)
                elif isinstance(result, Exception):
                    self.logger.error(f"News source error: {result}")
            
            # Remove duplicates and sort by relevance
            unique_news = self._deduplicate_news(all_news)
            unique_news.sort(key=lambda x: x.relevance_score, reverse=True)
            
            return unique_news[:50]  # Limit to top 50 articles
            
        except Exception as e:
            self.logger.error(f"Error getting market news: {e}")
            return []
    
    async def _get_newsapi_news(self, symbols: List[str], hours_back: int) -> List[MarketNews]:
        """Get news from NewsAPI"""
        if 'newsapi' not in self.api_keys:
            return []
        
        news_items = []
        
        try:
            async with aiohttp.ClientSession() as session:
                for symbol in symbols[:5]:  # Limit API calls
                    params = {
                        'q': f'"{symbol}" OR "{symbol} stock"',
                        'apiKey': self.api_keys['newsapi'],
                        'sortBy': 'publishedAt',
                        'language': 'en',
                        'from': (datetime.now() - timedelta(hours=hours_back)).isoformat()
                    }
                    
                    async with session.get(self.news_sources['newsapi'], params=params) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            for article in data.get('articles', [])[:10]:  # Top 10 per symbol
                                if article['title'] and article['description']:
                                    news_item = self._create_news_item(
                                        article['title'],
                                        article['description'],
                                        article['url'],
                                        article['source']['name'],
                                        article['publishedAt'],
                                        [symbol]
                                    )
                                    news_items.append(news_item)
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
                        
        except Exception as e:
            self.logger.error(f"NewsAPI error: {e}")
        
        return news_items
    
    async def _get_alpha_vantage_news(self, symbols: List[str], hours_back: int) -> List[MarketNews]:
        """Get news from Alpha Vantage"""
        if 'alpha_vantage' not in self.api_keys:
            return []
        
        news_items = []
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'function': 'NEWS_SENTIMENT',
                    'apikey': self.api_keys['alpha_vantage'],
                    'limit': 200
                }
                
                async with session.get(self.news_sources['alpha_vantage'], params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for article in data.get('feed', []):
                            # Check if article mentions our symbols
                            mentioned_symbols = []
                            for symbol in symbols:
                                if symbol.lower() in article['title'].lower() or symbol.lower() in article['summary'].lower():
                                    mentioned_symbols.append(symbol)
                            
                            if mentioned_symbols:
                                news_item = self._create_news_item(
                                    article['title'],
                                    article['summary'],
                                    article['url'],
                                    article['source'],
                                    article['time_published'],
                                    mentioned_symbols
                                )
                                news_items.append(news_item)
                        
        except Exception as e:
            self.logger.error(f"Alpha Vantage error: {e}")
        
        return news_items
    
    def _create_news_item(self, title: str, summary: str, url: str, source: str, 
                         timestamp_str: str, symbols: List[str]) -> MarketNews:
        """Create a MarketNews object"""
        
        # Parse timestamp
        try:
            if 'T' in timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
        except:
            timestamp = datetime.now()
        
        # Analyze sentiment
        full_text = f"{title} {summary}"
        sentiment_score = self.sentiment_analyzer.analyze_text_sentiment(full_text)
        
        # Calculate relevance score
        relevance_score = self._calculate_relevance_score(full_text, symbols)
        
        return MarketNews(
            title=title,
            summary=summary,
            url=url,
            source=source,
            timestamp=timestamp,
            symbols_mentioned=symbols,
            sentiment_score=sentiment_score,
            relevance_score=relevance_score
        )
    
    def _calculate_relevance_score(self, text: str, symbols: List[str]) -> float:
        """Calculate how relevant the news is (0-1)"""
        text_lower = text.lower()
        relevance = 0.0
        
        # Symbol mentions
        for symbol in symbols:
            symbol_mentions = text_lower.count(symbol.lower())
            relevance += min(0.3, symbol_mentions * 0.1)
        
        # Financial keywords
        financial_keywords = ['earnings', 'revenue', 'profit', 'loss', 'guidance', 'forecast',
                             'merger', 'acquisition', 'ipo', 'dividend', 'split', 'buyback']
        
        for keyword in financial_keywords:
            if keyword in text_lower:
                relevance += 0.05
        
        return min(1.0, relevance)
    
    def _deduplicate_news(self, news_items: List[MarketNews]) -> List[MarketNews]:
        """Remove duplicate news items"""
        seen_titles = set()
        unique_items = []
        
        for item in news_items:
            # Create a simplified title for comparison
            simple_title = re.sub(r'[^\w\s]', '', item.title.lower())
            
            if simple_title not in seen_titles:
                seen_titles.add(simple_title)
                unique_items.append(item)
        
        return unique_items

class AlertSystem:
    """Intelligent alert system for portfolio and market events"""
    
    def __init__(self, email_config: Dict[str, str]):
        self.email_config = email_config
        self.logger = logging.getLogger(__name__ + ".AlertSystem")
        self.alert_history: List[MarketAlert] = []
        
        # Alert thresholds
        self.alert_rules = {
            'price_change': 0.05,  # 5% price change
            'volume_spike': 2.0,   # 2x average volume
            'news_sentiment_extreme': 0.7,  # |sentiment| > 0.7
            'position_loss': -0.10,  # 10% position loss
            'margin_call_warning': 0.9  # 90% margin usage
        }
    
    async def check_portfolio_alerts(self, pm: IBKRPortfolioManager, 
                                   news_items: List[MarketNews]) -> List[MarketAlert]:
        """Check for portfolio-related alerts"""
        alerts = []
        
        try:
            # Get current portfolio data
            positions_df = pm.get_portfolio_positions()
            account_summary = pm.get_account_summary()
            
            if positions_df.empty:
                return alerts
            
            # Check position-level alerts
            for _, position in positions_df.iterrows():
                symbol = position['Symbol']
                
                # Large unrealized loss alert
                if position['Unrealized PnL'] < 0:
                    loss_pct = position['Unrealized PnL'] / abs(position['Market Value'])
                    if loss_pct <= self.alert_rules['position_loss']:
                        alerts.append(MarketAlert(
                            alert_type='Position Loss',
                            symbol=symbol,
                            message=f'{symbol} down {abs(loss_pct):.1%} (${position["Unrealized PnL"]:,.2f})',
                            priority='HIGH',
                            timestamp=datetime.now(),
                            data={'loss_pct': loss_pct, 'loss_amount': position['Unrealized PnL']},
                            action_suggested='Consider stop-loss or position review'
                        ))
            
            # Check account-level alerts
            if account_summary:
                # Margin utilization warning
                buying_power = float(account_summary.get('BuyingPower', {}).get('value', 1))
                net_liqui