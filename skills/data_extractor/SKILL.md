---
name: data_extractor
description: Extracts financial data from web sources and APIs
---

# Data Extractor Skill

You are a data extraction specialist. Your job is to reliably pull financial data from various web sources and structure it for analysis.

## Extraction Strategies

### Strategy 1: Finviz Screener (Fastest)

Finviz provides a comprehensive stock screener with most metrics in one place.

**URL Pattern**: `https://finviz.com/quote.ashx?t=[TICKER]`

**Key Data Points Available**:
- All major valuation metrics (P/E, P/B, P/S, etc.)
- Profitability metrics (Profit Margin, ROE, ROA, etc.)
- Financial health (Current Ratio, Debt/Eq, etc.)
- Growth rates
- Analyst recommendations
- Insider/Institutional ownership

**Extraction Method**:
```javascript
// Navigate to Finviz quote page
// Find the "Snapshot" table
// Extract data from the table cells
// Map to standardized metric names
```

### Strategy 2: Yahoo Finance (Most Reliable)

Yahoo Finance is free and provides comprehensive data.

**URL Patterns**:
- Quote: `https://finance.yahoo.com/quote/[TICKER]`
- Statistics: `https://finance.yahoo.com/quote/[TICKER]/key-statistics`
- Financials: `https://finance.yahoo.com/quote/[TICKER]/financials`
- Analysis: `https://finance.yahoo.com/quote/[TICKER]/analysis`

**Extraction Method**:
```javascript
// Navigate to each tab
// Extract data from tables
// Handle dynamic loading (wait for elements)
// Parse numbers (remove commas, handle B/M/K suffixes)
```

### Strategy 3: API Integration (Advanced)

If available, use financial data APIs:

**Free APIs**:
- Alpha Vantage (free tier: 5 calls/min, 500 calls/day)
- Financial Modeling Prep (250 calls/day free)
- Yahoo Finance API (unofficial, via RapidAPI)

**Example API Call**:
```bash
# Alpha Vantage - Company Overview
curl "https://www.alphavantage.co/query?function=OVERVIEW&symbol=IBM&apikey=YOUR_API_KEY"

# Returns JSON with all fundamental data
```

## Data Normalization

Convert all extracted data to a standard format:

```json
{
  "ticker": "AAPL",
  "companyName": "Apple Inc.",
  "industry": "Technology",
  "sector": "Consumer Electronics",
  "extractedAt": "2026-02-12T09:00:00Z",
  
  "pricing": {
    "currentPrice": 150.25,
    "change": 2.50,
    "changePercent": 1.69,
    "volume": 50000000,
    "avgVolume": 45000000
  },
  
  "valuation": {
    "marketCap": 2500000000000,
    "peRatio": 28.5,
    "forwardPE": 25.2,
    "pbRatio": 35.6,
    "psRatio": 7.2,
    "pegRatio": 2.1,
    "evToEbitda": 22.3
  },
  
  "profitability": {
    "profitMargin": 25.5,
    "operatingMargin": 30.2,
    "grossMargin": 42.0,
    "roe": 147.5,
    "roa": 28.9,
    "roic": 45.2
  },
  
  "growth": {
    "revenueGrowth1Y": 8.5,
    "revenueGrowth3Y": 12.3,
    "earningsGrowth1Y": 10.2,
    "earningsGrowth3Y": 15.8,
    "epsGrowth": 12.5
  },
  
  "financialHealth": {
    "currentRatio": 1.07,
    "quickRatio": 0.95,
    "debtToEquity": 1.73,
    "interestCoverage": 25.5,
    "freeCashFlow": 95000000000,
    "cashAndEquivalents": 48000000000
  },
  
  "dividends": {
    "dividendYield": 0.52,
    "payoutRatio": 15.8,
    "exDividendDate": "2026-02-07"
  },
  
  "ownership": {
    "insiderOwnership": 0.07,
    "institutionalOwnership": 60.5,
    "shortInterest": 0.8
  },
  
  "analysts": {
    "rating": "Buy",
    "targetPrice": 175.00,
    "numAnalysts": 45,
    "buyRatings": 30,
    "holdRatings": 12,
    "sellRatings": 3
  }
}
```

## Batch Processing

For screening multiple companies:

1. **Get Ticker List**: Extract all tickers from industry screener
2. **Parallel Processing**: Process multiple tickers simultaneously (respect rate limits)
3. **Progress Tracking**: Log progress (e.g., "Processing 45/150 companies...")
4. **Error Recovery**: Continue processing even if some tickers fail
5. **Data Validation**: Check for missing or invalid data

## Caching Strategy

To avoid re-fetching data:

```javascript
// Cache structure
{
  "AAPL": {
    "data": { /* full company data */ },
    "fetchedAt": "2026-02-12T09:00:00Z",
    "expiresAt": "2026-02-12T21:00:00Z"  // Cache for 12 hours
  }
}

// Before fetching:
// 1. Check if ticker exists in cache
// 2. Check if cache is still valid
// 3. If valid, use cached data
// 4. If expired, fetch fresh data
```

## Number Parsing Utilities

Handle various number formats:

```javascript
// Examples to handle:
// "1.5B" -> 1500000000
// "250M" -> 250000000
// "5.2K" -> 5200
// "15.5%" -> 15.5
// "N/A" -> null
// "-" -> null
// "1,234.56" -> 1234.56

function parseFinancialNumber(value) {
  if (!value || value === 'N/A' || value === '-') return null;
  
  // Remove commas
  value = value.replace(/,/g, '');
  
  // Handle percentages
  if (value.includes('%')) {
    return parseFloat(value.replace('%', ''));
  }
  
  // Handle suffixes
  const multipliers = {
    'T': 1e12,
    'B': 1e9,
    'M': 1e6,
    'K': 1e3
  };
  
  const suffix = value.slice(-1);
  if (multipliers[suffix]) {
    return parseFloat(value.slice(0, -1)) * multipliers[suffix];
  }
  
  return parseFloat(value);
}
```

## Error Handling

Common issues and solutions:

1. **Page Not Loading**: Retry up to 3 times with exponential backoff
2. **Element Not Found**: Try alternative selectors or data sources
3. **Invalid Data**: Mark as null and log warning
4. **Rate Limiting**: Add delays (2-3 seconds between requests)
5. **Captcha/Bot Detection**: Use browser with realistic user agent and delays

## Example Extraction Code

```javascript
// Pseudo-code for extracting from Finviz

async function extractFromFinviz(ticker) {
  const url = `https://finviz.com/quote.ashx?t=${ticker}`;
  
  // Navigate to page
  await browser.navigate(url);
  await browser.waitForSelector('.snapshot-table2');
  
  // Extract data from snapshot table
  const data = {};
  const rows = await browser.querySelectorAll('.snapshot-table2 tr');
  
  for (const row of rows) {
    const cells = await row.querySelectorAll('td');
    for (let i = 0; i < cells.length; i += 2) {
      const label = await cells[i].textContent;
      const value = await cells[i + 1].textContent;
      
      // Map to standardized names
      const metricName = mapFinvizLabel(label);
      data[metricName] = parseFinancialNumber(value);
    }
  }
  
  return data;
}

function mapFinvizLabel(label) {
  const mapping = {
    'Market Cap': 'marketCap',
    'P/E': 'peRatio',
    'Forward P/E': 'forwardPE',
    'PEG': 'pegRatio',
    'P/S': 'psRatio',
    'P/B': 'pbRatio',
    'Profit Margin': 'profitMargin',
    'ROE': 'roe',
    'ROA': 'roa',
    'Debt/Eq': 'debtToEquity',
    'Current Ratio': 'currentRatio',
    // ... add all mappings
  };
  
  return mapping[label] || label;
}
```

## Quality Checks

Before returning data, verify:

1. **Completeness**: Are critical metrics present?
2. **Validity**: Are values within reasonable ranges?
3. **Consistency**: Do related metrics make sense together?
4. **Freshness**: Is the data recent?

## Output

Return extracted data in the standardized JSON format shown above, ready for the stock_screener skill to process.
