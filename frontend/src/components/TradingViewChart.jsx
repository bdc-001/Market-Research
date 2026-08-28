import React, { useEffect, useRef } from 'react';

export default function TradingViewChart({ symbol = "NIFTY" }) {
  const container = useRef();

  useEffect(() => {
    if (!container.current) return;
    container.current.innerHTML = '';
    
    // Format symbol properly (e.g., RELIANCE -> NSE:RELIANCE)
    let formattedSymbol = symbol;
    if (symbol && !symbol.includes(":")) {
      formattedSymbol = `NSE:${symbol}`;
    }

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      "autosize": true,
      "symbol": formattedSymbol,
      "interval": "D",
      "timezone": "Asia/Kolkata",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "enable_publishing": false,
      "hide_side_toolbar": false,
      "allow_symbol_change": true,
      "calendar": false,
      "support_host": "https://www.tradingview.com"
    });
    
    container.current.appendChild(script);
  }, [symbol]);

  return (
    <div className="tradingview-container" style={{ width: "100%", height: "480px", borderRadius: "10px", overflow: "hidden", border: "1px solid var(--border)" }}>
      <div ref={container} style={{ width: "100%", height: "100%" }}>
        <div className="tradingview-widget-container__widget"></div>
      </div>
    </div>
  );
}
