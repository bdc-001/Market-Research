import yfinance as yf
from .common import BaseAgent, setup_gemini
import pandas as pd

class TechnicalAgent(BaseAgent):
    """
    The Chartist: Analyzes Price Action & Trends using YFinance.
    """
    def __init__(self):
        super().__init__("Technical Analyst", "Chartist")

    def run(self, ticker: str) -> str:
        # Get last 1 year data
        try:
            # Add .NS suffix if not present (Assumption for Indian Markets)
            search_ticker = f"{ticker}.NS" if not ticker.endswith(".NS") and not ticker.endswith(".BO") else ticker
            
            data = yf.download(search_ticker, period="1y", interval="1d", progress=False)
            
            if data.empty:
                return f"⚠️ Unable to fetch market data for {ticker}. Analysis skipped."
            
            # Simple Technical Checks
            current_price = data['Close'].iloc[-1]
            sma_50 = data['Close'].rolling(window=50).mean().iloc[-1]
            sma_200 = data['Close'].rolling(window=200).mean().iloc[-1]
            
            # RSI Calculation
            delta = data['Close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # Trend Check
            trend = "Uptrend" if current_price > sma_200 else "Downtrend"
            cross = "Bullish Cross" if sma_50 > sma_200 else "Bearish"
            
            prompt = f"""
            Analyze these technical indicators for {ticker}:
            
            **Current Price**: ₹{current_price:.2f}
            **50-Day MA**: ₹{sma_50:.2f}
            **200-Day MA**: ₹{sma_200:.2f}
            **Trend**: {trend} ({cross})
            **RSI (14)**: {rsi:.2f}
            
            **High (52w)**: ₹{data['High'].max():.2f}
            **Low (52w)**: ₹{data['Low'].min():.2f}
            
            **Task**: Provide an Entry Strategy.
            - Is it a Buy Zone, Hold/Breakout Candidate, or Sell Area?
            - What are the key support levels to watch?
            - Write concise, actionable advice for a long-term investor looking for entry.
            """
            
            response = self.model.generate_content(prompt)
            return response.text
             
        except Exception as e:
            return f"Technical Analysis Failed: {str(e)}"
