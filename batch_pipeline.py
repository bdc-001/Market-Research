"""
Batch Pipeline v2.0 - Clean Reports & Data Separation
Runs the full Analyst pipeline, ensuring no raw JSON leaks into reports.
"""

import os
import sys
import json
import time
from datetime import datetime
import financial_analyst_cli as analyst

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except:
        pass

# Helper: Parse function (Matches app.py logic)
def parse_output(response_text):
    """Separates JSON data from Markdown report."""
    parts = response_text.split("|||SECTION_SEPARATOR|||")
    if len(parts) >= 2:
        try:
            return parts[1].strip() # Return only the clean Markdown
        except:
            return response_text
    return response_text.replace("```json", "").replace("```", "") # Fallback cleanup

def run_pipeline(industry):
    print(f"\n🚀 Starting Phase 1: Screening for {industry}...")
    
    # Setup
    model = analyst.setup_gemini()
    skills = analyst.load_skills()
    
    # Phase 1: Screening
    prompt = analyst.get_screening_prompt(industry, skills)
    response = model.generate_content(prompt)
    
    # Clean output
    clean_screen_text = parse_output(response.text)
    
    print("✅ Top Picks Identified. Starting Deep Dives...")
    
    # Extract Tickers (Robust extraction)
    ext_prompt = f"Extract exactly 3 ticker symbols from this text as a comma-separated list (e.g., RELIANCE, TCS, INFY). Text: {clean_screen_text}"
    tickers_resp = model.generate_content(ext_prompt)
    tickers = [t.strip() for t in tickers_resp.text.split(',')][:3]
    
    print(f"🎯 Targets: {tickers}")
    
    # Init Report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    final_report = f"# Investment Memo: {industry}\n\n**Date**: {timestamp}\n**Strategy**: Buffett-Dalio Quality Framework\n\n---\n\n"
    final_report += "## Phase 1: Sector Screening\n\n"
    final_report += clean_screen_text + "\n\n"
    
    # Phase 2: Deep Dives
    for ticker in tickers:
        print(f"🔬 Analyzing {ticker}...")
        deep_prompt = analyst.get_deep_dive_prompt(ticker, ticker, industry, skills)
        deep_resp = model.generate_content(deep_prompt)
        
        clean_deep_text = parse_output(deep_resp.text)
        
        final_report += f"\n## Deep Dive: {ticker}\n\n"
        final_report += clean_deep_text + "\n\n---\n\n"
        time.sleep(1)

    # Save
    os.makedirs('reports', exist_ok=True)
    filename = f"reports/Full_Report_{industry.replace(' ', '_')}_{timestamp}_v2.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_report)
    
    print(f"✅ Report Saved: {filename}")

if __name__ == "__main__":
    industries = ["Indian Defence SMEs", "Indian Healthcare & Diagnostics"]
    for ind in industries:
        run_pipeline(ind)
