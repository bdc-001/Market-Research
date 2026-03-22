# 📊 Financial Assistant - Quick Reference

## What You Have Now

A complete **automated stock screening system** that:

✅ Runs daily at 9 AM (weekdays)  
✅ Analyzes ALL companies in your chosen industry  
✅ Filters based on YOUR investment criteria  
✅ Generates detailed reports with top picks  
✅ Delivers to your preferred channel  

---

## 🚀 Quick Start Commands

### Install OpenClaw
```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

### Run Screening Now (Don't Wait!)
```bash
cd c:\Users\HP\OpenClaw\Stock Research\Market Research
.\assistant.ps1 run
```

### View Latest Report
```bash
.\assistant.ps1 report
```

### Check Status
```bash
.\assistant.ps1 status
```

### Edit Your Criteria
```bash
.\assistant.ps1 config
```

---

## 📁 Your Files

```
financial-assistant/
├── 📄 README.md                    ← Complete setup guide
├── ⚙️ openclaw.json                ← OpenClaw configuration
├── 🎯 screening_config.json        ← YOUR screening criteria (EDIT THIS!)
├── 🔧 assistant.ps1                ← Helper script for easy management
├── 📚 skills/
│   ├── stock_screener/SKILL.md     ← Screening logic
│   └── data_extractor/SKILL.md     ← Data extraction logic
└── 📊 reports/                     ← Your daily reports appear here
```

---

## 🎯 Customize Your Screening

Edit `screening_config.json` to set:

### 1. Industry/Sector
```json
{
  "industry": "Technology",        ← Change this!
  "sector": "Software - Application"
}
```

**Popular Industries:**
- Technology
- Healthcare  
- Financial Services
- Consumer Cyclical
- Energy
- Industrials

### 2. Filters (What Makes a Stock "Good"?)

**Current defaults:**
- Market cap > $500M
- P/E ratio: 5-35
- Revenue growth > 15%
- Profit margin > 10%
- ROE > 15%
- Debt-to-Equity < 1.5
- Positive free cash flow

**Adjust these values** based on your strategy!

### 3. Scoring Weights (What Matters Most?)

```json
{
  "scoring": {
    "weights": {
      "valuation": 20,      ← How important is price?
      "growth": 30,         ← Prioritize growth?
      "profitability": 25,  ← Or profits?
      "financialHealth": 15,
      "analyst": 10
    }
  }
}
```

---

## 📅 Automation Schedule

**Default:** Every weekday at 9:00 AM IST

**Change it:** Edit `openclaw.json` → `cron.jobs[0].schedule`

```json
"schedule": "0 9 * * 1-5"  ← Cron format
```

**Examples:**
- `0 18 * * 1-5` = 6 PM weekdays
- `0 12 * * *` = 12 PM daily
- `30 15 * * 1,3,5` = 3:30 PM Mon/Wed/Fri

---

## 📨 Delivery Options

Choose where to receive reports:

### Option 1: File System (Default)
Reports saved to: `reports/daily_screening_{date}.md`

### Option 2: Telegram
1. Create bot via @BotFather
2. Add token to `openclaw.json`
3. Enable in `screening_config.json`

### Option 3: Discord
1. Create Discord bot
2. Add to server
3. Configure in `openclaw.json`

### Option 4: Slack
1. Create Slack app
2. Get tokens
3. Configure in `openclaw.json`

---

## 💡 Example Strategies

### Value Investing
```json
{
  "peRatio": { "max": 15 },
  "pbRatio": { "max": 1.5 },
  "dividendYield": { "min": 3 }
}
```

### Growth Investing
```json
{
  "revenueGrowth1Y": { "min": 25 },
  "earningsGrowth1Y": { "min": 20 },
  "profitMargin": { "min": 15 }
}
```

### Dividend Investing
```json
{
  "dividendYield": { "min": 4 },
  "payoutRatio": { "max": 60 },
  "freeCashFlow": { "positive": true }
}
```

---

## 🔥 Advanced Usage

### Multiple Industries
Create multiple config files:
- `screening_config_tech.json`
- `screening_config_healthcare.json`
- `screening_config_finance.json`

Run each with different schedules!

### Interactive Analysis
```bash
openclaw agent --session financial_screener --message "From today's results, show me only stocks under $10B market cap"
```

### Portfolio Monitoring
```bash
openclaw agent --session financial_screener --message "I own AAPL, MSFT, NVDA. Check them against my criteria and flag any concerns."
```

### Historical Tracking
```bash
openclaw agent --session financial_screener --message "Compare this week's top picks with last month's. Which stocks keep appearing?"
```

---

## 🛠️ Troubleshooting

### Screening Doesn't Run
```bash
openclaw doctor                    # Check health
openclaw gateway --status          # Check if running
```

### No Companies Pass Filters
→ Your criteria might be too strict  
→ Try relaxing some thresholds  
→ Check if industry has enough companies  

### Browser Issues
→ Ensure browser tool is enabled in `openclaw.json`  
→ Set `headless: false` to see what's happening  
→ Check logs: `logs/openclaw.log`  

---

## 📈 What a Report Looks Like

```markdown
# Daily Stock Screening Report
**Date**: February 12, 2026
**Industry**: Technology
**Companies Analyzed**: 247
**Companies Passed**: 18

## Top Stock Picks

### 1. Example Corp (EXMP)
**Score**: 87/100
**Price**: $125.50
**Market Cap**: $15.2B

**Key Metrics**:
- P/E: 22.5
- Revenue Growth: 28.5%
- Profit Margin: 18.2%
- ROE: 24.8%

**Why It Passed**:
- Strong revenue growth
- Excellent profitability
- Low debt levels

**Recommendation**: BUY
```

---

## 🎯 Next Steps

1. ✅ **Install OpenClaw** (if not already)
2. ✅ **Customize** `screening_config.json` with YOUR criteria
3. ✅ **Test** the workflow: `.\assistant.ps1 run`
4. ✅ **Review** the generated report
5. ✅ **Adjust** criteria based on results
6. ✅ **Set up** delivery channel (Telegram/Discord/Slack)
7. ✅ **Let it run** automatically every day!

---

## 📚 Resources

- **Full Guide**: `README.md`
- **Workflow**: `.agent/workflows/daily-stock-screening.md`
- **Skills**: `skills/*/SKILL.md`
- **OpenClaw Docs**: https://docs.openclaw.ai

---

## 🤝 Share Your Criteria!

Once you dial in your perfect screening criteria, you can:
- Share config files with friends
- Create strategy-specific configs
- Track performance over time
- Build a library of proven strategies

---

**Ready to find your next winning stock? Let's go! 🚀📈**
