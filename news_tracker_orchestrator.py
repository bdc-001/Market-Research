"""
News Tracker Orchestrator
Coordinates the high-impact news tracking pipeline.
"""
from agents.news_tracker_agents import NewsAggregatorAgent, ImpactClassifierAgent, SentimentAnalyzerAgent, NewsSummarizerAgent

class NewsTrackerOrchestrator:
    """Orchestrates the News Tracking pipeline."""
    
    def __init__(self):
        print("📰 Initializing News Tracker Council...")
        self.aggregator = NewsAggregatorAgent()
        self.classifier = ImpactClassifierAgent()
        self.sentiment_analyzer = SentimentAnalyzerAgent()
        self.summarizer = NewsSummarizerAgent()
    
    def run_analysis(self, scope="global", progress_callback=None):
        """Runs full news tracking pipeline."""
        
        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"🔄 {msg}")
        
        update("📰 Aggregating latest financial news...")
        raw_news = self.aggregator.run(scope)
        
        if not raw_news:
            return {"high_impact": [], "medium_impact": [], "low_impact": []}
        
        update("🎯 Classifying news by market impact...")
        classified_news = self.classifier.run(raw_news)
        
        update("🧠 Analyzing sentiment (Bullish/Bearish)...")
        sentiment_news = self.sentiment_analyzer.run(classified_news)
        
        update("✍️ Generating concise summaries...")
        final_news = self.summarizer.run(sentiment_news)
        
        # Organize by impact level
        organized_news = {
            'high_impact': [n for n in final_news if n.get('impact') == 'HIGH'],
            'medium_impact': [n for n in final_news if n.get('impact') == 'MEDIUM'],
            'low_impact': [n for n in final_news if n.get('impact') == 'LOW']
        }
        
        update("✅ News Analysis Complete!")
        return organized_news
