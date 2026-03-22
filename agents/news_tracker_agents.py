"""
High-Impact News Tracker Agents
Multi-agent pipeline for aggregating, classifying, and summarizing market news.
"""
from agents.common import BaseAgent, setup_gemini
from duckduckgo_search import DDGS
from datetime import datetime

class NewsAggregatorAgent(BaseAgent):
    """Scrapes latest financial news from multiple sources."""
    
    def __init__(self):
        super().__init__("News Aggregator", "News Scraper")
    
    def search_news(self, query, max_results=10):
        """Searches for news using DuckDuckGo."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return results
        except:
            return []
    
    def run(self, scope="global") -> list:
        """Aggregates news from multiple queries."""
        
        queries = []
        if scope == "india" or scope == "global":
            queries.extend([
                "India stock market news today",
                "Nifty Sensex latest news",
                "Indian company earnings news"
            ])
        
        if scope == "global":
            queries.extend([
                "US stock market news Federal Reserve",
                "global markets breaking news",
                "China economy news"
            ])
        
        all_news = []
        for query in queries:
            news_items = self.search_news(query, max_results=5)
            all_news.extend(news_items)
        
        # Return top 20 unique items
        seen_titles = set()
        unique_news = []
        for item in all_news:
            if item['title'] not in seen_titles:
                seen_titles.add(item['title'])
                unique_news.append(item)
                if len(unique_news) >= 20:
                    break
        
        return unique_news


class ImpactClassifierAgent(BaseAgent):
    """Classifies news by market impact level."""
    
    def __init__(self):
        super().__init__("Impact Classifier", "News Analyst")
    
    def run(self, news_list: list) -> list:
        """Classifies each news item as HIGH/MEDIUM/LOW impact."""
        
        classified_news = []
        
        for item in news_list:
            title = item.get('title', '')
            body = item.get('body', '')
            
            prompt = f"""
            Classify this news headline by market impact:
            
            **Headline**: {title}
            **Summary**: {body}
            
            **Classification Criteria**:
            - HIGH: Central bank decisions, major earnings surprises, geopolitical shocks, large M&A
            - MEDIUM: Sector policy changes, FII flows, IPO news, regulatory updates
            - LOW: General commentary, minor announcements
            
            **Output**: Return ONLY one word: HIGH, MEDIUM, or LOW
            """
            
            try:
                response = self.model.generate_content(prompt).text.strip().upper()
                impact = response if response in ['HIGH', 'MEDIUM', 'LOW'] else 'MEDIUM'
            except:
                impact = 'MEDIUM'
            
            classified_news.append({
                **item,
                'impact': impact
            })
        
        return classified_news


class SentimentAnalyzerAgent(BaseAgent):
    """Determines if news is Bullish, Bearish, or Neutral."""
    
    def __init__(self):
        super().__init__("Sentiment Analyzer", "Sentiment Specialist")
    
    def run(self, news_list: list) -> list:
        """Adds sentiment analysis to each news item."""
        
        analyzed_news = []
        
        for item in news_list:
            title = item.get('title', '')
            body = item.get('body', '')
            
            prompt = f"""
            Analyze market sentiment for this news:
            
            **Headline**: {title}
            **Summary**: {body}
            
            **Output**: Return ONLY one word: BULLISH, BEARISH, or NEUTRAL
            """
            
            try:
                response = self.model.generate_content(prompt).text.strip().upper()
                sentiment = response if response in ['BULLISH', 'BEARISH', 'NEUTRAL'] else 'NEUTRAL'
            except:
                sentiment = 'NEUTRAL'
            
            analyzed_news.append({
                **item,
                'sentiment': sentiment
            })
        
        return analyzed_news


class NewsSummarizerAgent(BaseAgent):
    """Creates concise 2-sentence summaries."""
    
    def __init__(self):
        super().__init__("News Summarizer", "Editor")
    
    def run(self, news_list: list) -> list:
        """Generates summaries for high-impact news."""
        
        summarized_news = []
        
        for item in news_list:
            # Only summarize HIGH and MEDIUM impact news
            if item.get('impact') in ['HIGH', 'MEDIUM']:
                title = item.get('title', '')
                body = item.get('body', '')
                
                prompt = f"""
                Summarize this news in exactly 2 sentences:
                
                **Headline**: {title}
                **Details**: {body}
                
                **Format**: Provide a concise, factual 2-sentence summary suitable for investors.
                """
                
                try:
                    summary = self.model.generate_content(prompt).text.strip()
                except:
                    summary = body[:200] + "..."
                
                item['summary'] = summary
            else:
                item['summary'] = item.get('body', '')[:150] + "..."
            
            summarized_news.append(item)
        
        return summarized_news
