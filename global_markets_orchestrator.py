"""
Global Markets Orchestrators
Coordinates multi-agent pipelines for Emerging and Developed Markets research.
"""
from agents.emerging_markets_agents import EmergingMarketsScout, SectorRotationAnalyst, EmergingMarketsEditor
from agents.developed_markets_agents import DevelopedMarketsScout, EquityValuationAnalyst, DevelopedMarketsEditor

class EmergingMarketsOrchestrator:
    """Orchestrates the Emerging Markets research pipeline."""
    
    def __init__(self):
        print("🌏 Initializing Emerging Markets Council...")
        self.scout = EmergingMarketsScout()
        self.sector_analyst = SectorRotationAnalyst()
        self.editor = EmergingMarketsEditor()
    
    def run_analysis(self, countries=None, progress_callback=None):
        """Runs full emerging markets analysis."""
        
        if countries is None:
            countries = ["Brazil", "China", "Indonesia", "Turkey"]
        
        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"🔄 {msg}")
        
        countries_data = {}
        
        for country in countries:
            update(f"🕵️ Analyzing {country} macro environment...")
            macro_analysis = self.scout.run(country)
            
            update(f"📊 Identifying top sectors in {country}...")
            sector_analysis = self.sector_analyst.run(country)
            
            countries_data[country] = {
                'macro': macro_analysis,
                'sectors': sector_analysis
            }
        
        update("⚖️ Editor: Synthesizing Emerging Markets Report...")
        final_report = self.editor.run(countries_data)
        
        update("✅ Analysis Complete!")
        return final_report


class DevelopedMarketsOrchestrator:
    """Orchestrates the Developed Markets research pipeline."""
    
    def __init__(self):
        print("🇺🇸 Initializing Developed Markets Council...")
        self.scout = DevelopedMarketsScout()
        self.valuation_analyst = EquityValuationAnalyst()
        self.editor = DevelopedMarketsEditor()
    
    def run_analysis(self, regions=None, progress_callback=None):
        """Runs full developed markets analysis."""
        
        if regions is None:
            regions = ["USA", "Europe", "Japan"]
        
        def update(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(f"🔄 {msg}")
        
        regions_data = {}
        
        for region in regions:
            update(f"🕵️ Analyzing {region} macro environment...")
            macro_analysis = self.scout.run(region)
            regions_data[region] = macro_analysis
        
        update("📈 Comparing equity valuations across markets...")
        valuation_comparison = self.valuation_analyst.run(regions)
        
        update("⚖️ Editor: Synthesizing Developed Markets Report...")
        final_report = self.editor.run(regions_data, valuation_comparison)
        
        update("✅ Analysis Complete!")
        return final_report
