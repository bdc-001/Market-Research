"""
Buffett-Dalio Financial Analyst CLI
Interactive tool for industry screening and deep-dive company analysis.
"""

import os
import sys
import json
import time
from datetime import datetime
import google.generativeai as genai

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SCREENING_CONFIG_PATH = 'screening_config.json'
SKILLS_PATH = 'skills'
REPORTS_DIR = 'reports'

def setup_gemini():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not found in environment variables.")
        print("Please run: $env:GEMINI_API_KEY = 'YOUR_KEY'")
        sys.exit(1)
    genai.configure(api_key=GEMINI_API_KEY)
    # Using the Gemini 3 Flash Preview model for deep analysis
    return genai.GenerativeModel('gemini-3-flash-preview')

def load_skills():
    skills = {}
    try:
        with open(f'{SKILLS_PATH}/stock_screener/SKILL.md', 'r', encoding='utf-8') as f:
            skills['stock_screener'] = f.read()
    except:
        skills['stock_screener'] = "Focus on ROE > 15%, Moat, and Management Integrity."
    return skills

def get_screening_prompt(industry, skills):
    return f"""
# Phase 1: Industry Screening ({industry})

**Role**: World-Class Financial Analyst
**Objective**: Identify Top 3 High-Quality Companies in **{industry}**.

## Task
1.  Scan the sector.
2.  Select exactly **3 Companies** fitting the Buffett-Dalio criteria.
3.  **Crucial**: You must output data in two distinct sections separated by "|||SECTION_SEPARATOR|||".

**Section 1: Data (JSON)**
Output a JSON list of the 3 companies with their ticker, score, and key metrics.
```json
[
  {{ "name": "Co", "ticker": "TICK", "score": 90, "revenue_growth": 15, "roe": 25 }},
  ...
]
```

|||SECTION_SEPARATOR|||

**Section 2: Report (Markdown)**
Provide a professional Executive Summary and a Comparison Table. 
**Do NOT** include the JSON here. Just the human-readable report.
Use standard Markdown tables.
"""

def get_deep_dive_prompt(company_name, ticker, industry, skills):
    return f"""
# Phase 2: Deep Dive Analysis - {company_name} ({ticker})

**Objective**: Comprehensive Investment Memo.

## Task
Output detailed analysis in two sections separated by "|||SECTION_SEPARATOR|||".

**Section 1: Financial Data (JSON)**
Provide 5 years of key financial data for plotting.
```json
{{
  "years": ["2020", "2021", "2022", "2023", "2024"],
  "revenue": [100, 120, 150, 180, 200],
  "net_profit": [10, 15, 20, 25, 30],
  "roe": [15, 18, 20, 22, 24]
}}
```

|||SECTION_SEPARATOR|||

**Section 2: Investment Memo (Markdown)**
Write the Deep Dive report (Business Model, Moat, Risks, Valuation).
**Do NOT** explain the JSON. Just write the report.
Ensure tables use clean Markdown syntax.
"""

def main():
    print("🚀 Buffett-Dalio Financial Analyst Interface")
    print("============================================")
    
    model = setup_gemini()
    skills = load_skills()
    
    # 1. Get Industry Selection
    print("\nWhich industry would you like to analyze?")
    print("1. Indian Defence SMEs")
    print("2. Indian Healthcare/Pharma")
    print("3. Green Energy / Power")
    print("4. Custom Input")
    
    choice = input("\nEnter choice (1-4): ")
    if choice == '1': industry = "Indian Defence SMEs"
    elif choice == '2': industry = "Indian Healthcare & Diagnostics"
    elif choice == '3': industry = "Indian Green Energy & Power"
    else: industry = input("Enter Industry Name: ")

    print(f"\n🕵️  Screening {industry} for exceptional businesses...")
    
    # 2. Phase 1: Screening
    screening_response = model.generate_content(get_screening_prompt(industry, skills))
    print("\n✅ Top 3 Candidates Identified:\n")
    print(screening_response.text)
    
    # Extract companies (Simple parsing assumption for the CLI demo)
    # In a full app, we'd parse the JSON strictly.
    # For now, we will ask the AI to generate the full report based on its own findings.
    
    # 3. Phase 2: Deep Dives
    print("\n" + "="*50)
    print(f"📄 Generating Detailed Investment Memos for {industry} Picks...")
    print("==================================================")
    
    final_report = f"# Comprehensive Investment Report: {industry}\n\n"
    final_report += f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n"
    final_report += f"**Strategy**: Buffett-Dalio Quality Framework\n\n"
    final_report += "## Phase 1: Sector Screening\n\n"
    final_report += screening_response.text + "\n\n"
    final_report += "---\n\n"
    
    # We ask the model to extract the tickers it just found to run the loop
    # Ideally we parse JSON, but let's trust the "Thinking" model to follow up or we ask user
    print("Type the tickers of the 3 companies identified above to confirm deep dive:")
    tickers = []
    for i in range(3):
        t = input(f"Company {i+1} Ticker/Name: ")
        tickers.append(t)
    
    for ticker in tickers:
        print(f"\n🔬 Analyzing {ticker} (Deep Dive)... This takes ~30 seconds.")
        deep_dive_prompt = get_deep_dive_prompt(ticker, ticker, industry, skills)
        deep_dive_response = model.generate_content(deep_dive_prompt)
        
        final_report += f"## Phase 2: Deep Dive - {ticker}\n\n"
        final_report += deep_dive_response.text + "\n\n"
        final_report += "---\n\n"
        print(f"✅ Finished analysis for {ticker}")
        time.sleep(2) # Avoid rate limits

    # 4. Save Report
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filename = f"{REPORTS_DIR}/DeepDive_{industry.replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d')}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(final_report)
        
    print("\n" + "="*50)
    print(f"🎉 Analysis Complete! Report saved to:\n📂 {filename}")
    print("==================================================")

if __name__ == "__main__":
    main()
