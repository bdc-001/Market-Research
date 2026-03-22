"""
Buffett-Dalio Stock Screener
Uses Gemini API to analyze stocks based on quality investing principles
"""

import os
import sys
import json
import google.generativeai as genai
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'YOUR_GEMINI_API_KEY_HERE')
SCREENING_CONFIG_PATH = 'screening_config.json'
SKILLS_PATH = 'skills'

def load_config():
    """Load screening configuration"""
    with open(SCREENING_CONFIG_PATH, 'r') as f:
        return json.load(f)

def load_skills():
    """Load skill instructions"""
    skills = {}
    
    # Load stock_screener skill
    with open(f'{SKILLS_PATH}/stock_screener/SKILL.md', 'r', encoding='utf-8') as f:
        skills['stock_screener'] = f.read()
    
    # Load data_extractor skill
    with open(f'{SKILLS_PATH}/data_extractor/SKILL.md', 'r', encoding='utf-8') as f:
        skills['data_extractor'] = f.read()
    
    return skills

def create_screening_prompt(config, skills):
    """Create comprehensive prompt for Gemini"""
    
    prompt = f"""
# Buffett-Dalio Stock Screening Assistant - Indian SME Edition

You are a world-class financial analyst implementing Warren Buffett and Ray Dalio's quality investing principles, specialized in the **Indian Stock Market (NSE/BSE)**.

## Your Mission
Analyze **Indian Small & Medium Enterprises (SMEs) / Small-Caps** in the **Defence** and **Healthcare** sectors. Find exceptional businesses with emerging durable competitive advantages ("Moats").

## Skills Available

### Stock Screener Skill
{skills['stock_screener']}

### Data Extractor Skill  
{skills['data_extractor']}

## Screening Configuration
{json.dumps(config, indent=2)}

## Your Task

1. **Explain the Framework**: Briefly apply the 4-pillar framework to the Indian context (e.g., promoter quality, agile evolution).
2. **Identify & Analyze**: Select 3-4 promising Indian companies in **Defence** or **Healthcare** (Market Cap < ₹20,000 Cr preferred).
   - **Defence Focus**: Niche manufacturing, drones, electronics, export capabilities.
   - **Healthcare Focus**: Specialized diagnostics, niche pharma, hospital chains with regional moats.
3. **Show Scoring**: For each company, show:
   - Financial Physics score (/25)
   - Moat score (/30)
   - Management score (/20) (Focus on Promoter Integrity)
   - Risk & Resilience score (/15)
   - Valuation score (/10)
   - Total score (/100)
4. **Explain Pass/Fail**: Be strict. Does the SME have a *real* moat or just a temporary tailwind?
5. **Generate Report**: Create a comprehensive report.

## Important Notes
- **Context**: Indian Market (INR figures).
- **Red Flags**: Watch for high debt in infra-heavy defence co's, or regulatory issues in pharma.
- **Valuation**: Indian SMEs often trade at high P/E. Be critical - is the premium justified by growth + moat?
- **Promoter Quality**: Critical in Indian SMEs. Look for "Skin in the Game" and clean track records.

## Output Format
Generate a complete Buffett-Dalio Quality Screening Report following the format in the stock_screener skill.

Begin your Indian SME analysis now.
"""
    
    return prompt

def run_screening():
    """Run the Buffett-Dalio screening"""
    
    print("🚀 Buffett-Dalio Stock Screener")
    print("=" * 60)
    print()
    
    # Configure Gemini
    if GEMINI_API_KEY == 'YOUR_GEMINI_API_KEY_HERE':
        print("❌ Please set your GEMINI_API_KEY environment variable")
        print("   Or edit this file and replace YOUR_GEMINI_API_KEY_HERE")
        print()
        print("   Get your API key from: https://makersuite.google.com/app/apikey")
        return
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Load configuration and skills
    print("📋 Loading configuration...")
    config = load_config()
    
    print("🧠 Loading AI skills...")
    skills = load_skills()
    
    print("🎯 Creating screening prompt...")
    prompt = create_screening_prompt(config, skills)
    
    print("🤖 Running Buffett-Dalio analysis with Gemini...")
    print()
    
    # Use Gemini 3 Flash for analysis
    model = genai.GenerativeModel('gemini-3-flash-preview')
    
    # Generate response
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,  # Lower temperature for more analytical responses
            max_output_tokens=8000,
        )
    )
    
    # Print the report
    print(response.text)
    
    # Save report
    timestamp = datetime.now().strftime('%Y-%m-%d')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = os.path.join(base_dir, 'reports', f'buffett_dalio_screening_{timestamp}.md')
    
    os.makedirs(os.path.join(base_dir, 'reports'), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    print()
    print("=" * 60)
    print(f"✅ Report saved to: {report_path}")
    print()

if __name__ == '__main__':
    try:
        run_screening()
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure you have installed: pip install google-generativeai")
