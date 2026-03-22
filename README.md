# Financial Assistant - Setup Guide

## Overview

This is your automated stock screening assistant built on OpenClaw. It analyzes companies daily based on your criteria and delivers actionable investment insights.

## What It Does

Every weekday at 9 AM, the assistant will:

1. **Scan** all publicly listed companies in your chosen industry
2. **Extract** comprehensive financial metrics from multiple sources
3. **Filter** companies based on your investment criteria
4. **Score** and rank the best opportunities
5. **Generate** a detailed report with top stock picks
6. **Deliver** the report to your preferred channel (Telegram/Discord/Slack/File)

## Quick Start

### 1. Install OpenClaw

```bash
# Install globally
npm install -g openclaw@latest

# Run onboarding wizard
openclaw onboard --install-daemon
```

During onboarding:
- Choose **Anthropic Claude Opus 4.6** (recommended for financial analysis)
- Set workspace to: `c:\Users\HP\OpenClaw\Stock Research\Market Research`
- Enable browser tool (required for data extraction)

### 2. Configure Your Screening Criteria

Edit `screening_config.json` to customize:

**Industry Selection:**
```json
{
  "screening": {
    "industry": "Technology",  // Change to your preferred industry
    "sector": "Software - Application"
  }
}
```

**Common Industries:**
- Technology
- Healthcare
- Financial Services
- Consumer Cyclical
- Energy
- Industrials
- Real Estate
- Communication Services

**Filter Criteria:**

The default configuration screens for:
- Market cap > $500M
- P/E ratio between 5-35
- Revenue growth > 15%
- Profit margin > 10%
- ROE > 15%
- Debt-to-Equity < 1.5
- Positive free cash flow

**Customize these values** based on your investment strategy!

### 3. Set Up Delivery Channel (Optional)

Choose how you want to receive daily reports:

#### Option A: File System (Default)
Reports saved to: `financial-assistant/reports/daily_screening_{date}.md`

#### Option B: Telegram
1. Create a Telegram bot via @BotFather
2. Get your bot token
3. Update `openclaw.json`:
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_BOT_TOKEN",
      "allowFrom": ["YOUR_USER_ID"]
    }
  }
}
```
4. Update `screening_config.json`:
```json
{
  "output": {
    "delivery": {
      "telegram": {
        "enabled": true,
        "chatId": "YOUR_CHAT_ID"
      }
    }
  }
}
```

#### Option C: Discord
1. Create a Discord bot
2. Add to your server
3. Update `openclaw.json` with bot token and channel ID

#### Option D: Slack
1. Create a Slack app
2. Get bot and app tokens
3. Update `openclaw.json` with credentials

### 4. Start the Gateway

```bash
# Start OpenClaw gateway
openclaw gateway --port 18789 --verbose
```

The gateway will:
- Load your configuration
- Enable the browser tool
- Start the cron scheduler
- Run daily screening at 9 AM

### 5. Test the Workflow

Don't wait until 9 AM! Test it now:

```bash
openclaw agent --session financial_screener --message "Run the daily stock screening workflow using the current screening_config.json"
```

This will:
- Execute the full screening process
- Generate a report
- Save/send based on your delivery settings

## File Structure

```
financial-assistant/
├── openclaw.json                 # Main OpenClaw configuration
├── screening_config.json         # Your screening criteria
├── skills/
│   ├── stock_screener/
│   │   └── SKILL.md             # Stock screening logic
│   └── data_extractor/
│       └── SKILL.md             # Data extraction logic
├── reports/                      # Generated reports
│   ├── daily_screening_2026-02-12.md
│   └── daily_screening_2026-02-13.md
└── logs/
    └── openclaw.log             # System logs
```

## Customization Guide

### Change Screening Time

Edit `openclaw.json`:

```json
{
  "cron": {
    "jobs": [
      {
        "schedule": "0 18 * * 1-5"  // Change to 6 PM
      }
    ]
  }
}
```

Cron format: `minute hour day month weekday`
- `0 9 * * 1-5` = 9 AM, weekdays
- `0 12 * * *` = 12 PM, daily
- `30 15 * * 1,3,5` = 3:30 PM, Mon/Wed/Fri

### Screen Multiple Industries

Create multiple config files:

1. Copy `screening_config.json` to `screening_config_healthcare.json`
2. Edit the new file with different industry and criteria
3. Add a second cron job in `openclaw.json`:

```json
{
  "cron": {
    "jobs": [
      {
        "name": "tech_screening",
        "schedule": "0 9 * * 1-5",
        "message": "Run screening using screening_config.json"
      },
      {
        "name": "healthcare_screening",
        "schedule": "0 10 * * 1-5",
        "message": "Run screening using screening_config_healthcare.json"
      }
    ]
  }
}
```

### Adjust Scoring Weights

In `screening_config.json`, change what matters most:

```json
{
  "scoring": {
    "weights": {
      "valuation": 20,      // How important is valuation?
      "growth": 30,         // Prioritize growth?
      "profitability": 25,  // Or profitability?
      "financialHealth": 15,
      "analyst": 10
    }
  }
}
```

Total must equal 100.

### Add Custom Filters

You can add any financial metric to the filters. Examples:

```json
{
  "filters": {
    "dividendYield": {
      "min": 3,
      "description": "Dividend yield at least 3%"
    },
    "evToEbitda": {
      "min": 0,
      "max": 15,
      "description": "EV/EBITDA under 15"
    },
    "bookValueGrowth": {
      "min": 10,
      "unit": "percent"
    }
  }
}
```

## Advanced Usage

### Interactive Refinement

Chat with the agent to refine results:

```bash
openclaw agent --session financial_screener --message "From today's results, show me only stocks with market cap under $5B"
```

### Historical Analysis

```bash
openclaw agent --session financial_screener --message "Compare this week's top picks with last month's. Which stocks consistently appear?"
```

### Portfolio Monitoring

```bash
openclaw agent --session financial_screener --message "I own AAPL, MSFT, NVDA. Run the screening criteria against my holdings and flag any concerns."
```

### Custom Research

```bash
openclaw agent --session financial_screener --message "Deep dive into the top 3 stocks from today's screening. Analyze their latest 10-K filings and identify key risks."
```

## Monitoring & Maintenance

### Check System Health

```bash
openclaw doctor
```

### View Recent Reports

```bash
# List all reports
ls financial-assistant/reports/

# View latest report
cat financial-assistant/reports/daily_screening_2026-02-12.md
```

### Check Logs

```bash
cat financial-assistant/logs/openclaw.log
```

### Update OpenClaw

```bash
openclaw update --channel stable
```

## Troubleshooting

### Screening Doesn't Run

1. Check gateway is running: `openclaw gateway --status`
2. Verify cron is enabled in `openclaw.json`
3. Check logs for errors

### No Companies Pass Filters

Your criteria might be too strict. Try:
1. Relaxing some filter thresholds
2. Removing some filters temporarily
3. Checking if the industry has enough companies

### Browser Issues

If data extraction fails:
1. Ensure browser tool is enabled
2. Try running with `headless: false` to see what's happening
3. Check if websites have changed their layout
4. Use fallback data sources

### Data Quality Issues

If metrics seem wrong:
1. Verify data source is accessible
2. Check for website layout changes
3. Enable caching to reduce requests
4. Use multiple data sources for validation

## Tips for Best Results

1. **Start Conservative**: Use strict filters initially, then relax as needed
2. **Multiple Strategies**: Run different screening configs for different investment styles
3. **Track Over Time**: Save reports and compare week-over-week
4. **Combine with Research**: Use screening as a starting point, not the final decision
5. **Adjust for Market**: Modify criteria based on bull/bear market conditions
6. **Review Regularly**: Check and update your criteria monthly

## Example Investment Strategies

### Value Investing
```json
{
  "filters": {
    "peRatio": { "max": 15 },
    "pbRatio": { "max": 1.5 },
    "dividendYield": { "min": 3 },
    "debtToEquity": { "max": 0.5 }
  }
}
```

### Growth Investing
```json
{
  "filters": {
    "revenueGrowth1Y": { "min": 25 },
    "earningsGrowth1Y": { "min": 20 },
    "profitMargin": { "min": 15 },
    "roe": { "min": 20 }
  }
}
```

### Dividend Investing
```json
{
  "filters": {
    "dividendYield": { "min": 4 },
    "payoutRatio": { "max": 60 },
    "debtToEquity": { "max": 1.0 },
    "freeCashFlow": { "positive": true }
  }
}
```

### Small Cap Growth
```json
{
  "filters": {
    "marketCap": { "min": 300000000, "max": 2000000000 },
    "revenueGrowth1Y": { "min": 30 },
    "profitMargin": { "min": 12 }
  }
}
```

## Support & Resources

- **OpenClaw Docs**: https://docs.openclaw.ai
- **Workflow**: See `.agent/workflows/daily-stock-screening.md`
- **Skills**: Check `skills/*/SKILL.md` for detailed documentation
- **Community**: Join OpenClaw Discord for help

## Next Steps

1. ✅ Install OpenClaw
2. ✅ Customize `screening_config.json` with your criteria
3. ✅ Set up delivery channel (Telegram/Discord/Slack)
4. ✅ Test the workflow manually
5. ✅ Let it run automatically daily
6. ✅ Review reports and refine criteria
7. ✅ Build your watchlist from top picks

Happy investing! 🚀📈
