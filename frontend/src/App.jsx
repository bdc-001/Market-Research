import React, { useState, useEffect } from 'react';
import './App.css';
import Sectors from './components/Sectors';
import StockAnalysis from './components/StockAnalysis';
import TopPicks from './components/TopPicks';
import QuantumPicks from './components/QuantumPicks';
import GlobalMarkets from './components/GlobalMarkets';
import MarketNews from './components/MarketNews';
import ReportLibrary from './components/ReportLibrary';

export default function App() {
  const [selectedSection, setSelectedSection] = useState('Sector Analysis');
  const [isDarkTheme, setIsDarkTheme] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle('dark-theme', isDarkTheme);
  }, [isDarkTheme]);

  const navOptions = [
    { name: "Sector Analysis", icon: "analytics" },
    { name: "Stock Analysis", icon: "domain" },
    { name: "Top Picks", icon: "stars" },
    { name: "QuanTum Picks", icon: "electric_bolt" },
    { name: "Global Markets", icon: "public" },
    { name: "Market News", icon: "newspaper" },
    { name: "Report Library", icon: "folder_open" }
  ];

  const sectionMeta = {
    "Sector Analysis": { title: "Sector Intelligence", desc: "Multi-Agent Deep Dive: Trends, Valuation & Institutional Positioning" },
    "Stock Analysis": { title: "Stock Analysis", desc: "Deep-dive 7-Agent research memorandum on Indian equities" },
    "Top Picks": { title: "Top Picks", desc: "Automated screening for best risk-reward opportunities across industries" },
    "QuanTum Picks": { title: "QuanTum Picks", desc: "Multi-factor algorithmic engine: Technical + Fundamental + Sentiment" },
    "Global Markets": { title: "Global Markets", desc: "Emerging and developed markets macroeconomic intelligence" },
    "Market News": { title: "Market News", desc: "Real-time news stream with automated sentiment scoring" },
    "Report Library": { title: "Report Library", desc: "Historical archive of generated memos, PDFs, and sector deep dives" }
  };

  const renderActiveSection = () => {
    switch (selectedSection) {
      case "Sector Analysis": return <Sectors />;
      case "Stock Analysis": return <StockAnalysis />;
      case "Top Picks": return <TopPicks />;
      case "QuanTum Picks": return <QuantumPicks />;
      case "Global Markets": return <GlobalMarkets />;
      case "Market News": return <MarketNews />;
      case "Report Library": return <ReportLibrary />;
      default: return <Sectors />;
    }
  };

  return (
    <div className="app-container">
      {/* ── Left Navigation Sidebar ────────────────────────── */}
      <aside className="sidebar">
        <div>
          <div className="brand-section">
            <div className="brand-logo">Q</div>
            <div className="brand-text">
              <h1>QuanTum</h1>
              <p>Financial Intelligence</p>
            </div>
          </div>
          <span className="version-badge">Enterprise v3.5</span>
          
          <div style={{ height: "24px" }}></div>
          <div className="status-title">WORKSPACE</div>
          
          <nav className="nav-menu">
            {navOptions.map((opt) => (
              <div 
                key={opt.name} 
                className={`nav-item ${selectedSection === opt.name ? 'active' : ''}`}
                onClick={() => setSelectedSection(opt.name)}
              >
                <span className="material-symbols-rounded nav-icon">{opt.icon}</span>
                <span>{opt.name}</span>
              </div>
            ))}
          </nav>
        </div>

        {/* System Status Tracker */}
        <div className="status-card">
          <div className="status-title">SYSTEM STATUS</div>
          <div className="status-row">
            <div className="status-label">
              <span className="animate-pulse-dot"></span>
              <span>7-Agent Council</span>
            </div>
            <span className="status-badge">READY</span>
          </div>
          <div className="status-row">
            <div className="status-label">
              <span className="animate-pulse-dot"></span>
              <span>Gemini 3.5 Intelligence</span>
            </div>
            <span className="status-badge">ONLINE</span>
          </div>
          <div className="status-row">
            <div className="status-label">
              <span className="animate-pulse-dot"></span>
              <span>Turso Cloud Sync</span>
            </div>
            <span className="status-badge">CONNECTED</span>
          </div>
        </div>
      </aside>

      {/* ── Main Dashboard Panel ──────────────────────────── */}
      <main className="main-content">
        <header className="top-bar">
          <div className="page-header">
            <h2>{sectionMeta[selectedSection].title}</h2>
            <p>{sectionMeta[selectedSection].desc}</p>
          </div>
          <div className="top-bar-actions">
            <button
              className="icon-btn"
              onClick={() => setIsDarkTheme(!isDarkTheme)}
              title="Toggle Theme"
            >
              <span className="material-symbols-rounded">
                {isDarkTheme ? 'light_mode' : 'dark_mode'}
              </span>
            </button>
            <button className="icon-btn" title="Notifications">
              <span className="material-symbols-rounded">notifications</span>
            </button>
            <div className="avatar-btn" title="Arsalaan Mohammed">A</div>
          </div>
        </header>

        {/* Render Workspace Area */}
        <div className="page-enter" key={selectedSection} style={{ flexGrow: 1 }}>
          {renderActiveSection()}
        </div>
      </main>
    </div>
  );
}
