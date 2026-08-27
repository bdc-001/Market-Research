"""
Buffett-Dalio Financial Analyst - Multi-Agent V3
Features: 7-Agent Council, Technical Analysis, Clean Reports.
"""

import sys
import os
import time
import json
import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from markdown import markdown
from xhtml2pdf import pisa
from io import BytesIO

# ── Bootstrap Turso credentials from Streamlit secrets → env vars ────────────
# This allows turso_db.py (used by agents) to read them via os.environ
for _key in ("TURSO_URL", "TURSO_TOKEN"):
    _val = st.secrets.get(_key, "")
    if _val:
        os.environ[_key] = _val

# Import Agents
from agents.research_agent import ResearchAgent
from orchestrator import AgentOrchestrator
from report_store import load_report, save_report, picks_to_records
import financial_analyst_cli as analyst # Keep old screening logic for now


# Page Config
st.set_page_config(
    page_title="Financial Intelligence",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",  # Collapsed by default on mobile
)

# Premium Glassmorphism & Micro-Animation CSS
st.markdown("""
<style>
  /* ── Google Fonts: Outfit & Inter ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Outfit:wght@500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

  /* ── Global Reset & Font System ── */
  html, body, [class*="css"] {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
      letter-spacing: -0.01em;
  }

  code, pre, .stCodeBlock {
      font-family: 'JetBrains Mono', monospace !important;
  }

  /* ── Animated Gradient Background ── */
  .stApp {
      background: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                  radial-gradient(circle at 85% 85%, rgba(236, 72, 153, 0.12) 0%, transparent 45%),
                  radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 60%),
                  linear-gradient(145deg, #090814 0%, #110e2e 50%, #0c0a1f 100%);
      background-attachment: fixed;
      min-height: 100vh;
      color: #f1f5f9;
  }

  /* ── Main Container Padding ── */
  .block-container {
      padding-top: 1.25rem !important;
      padding-bottom: 3rem !important;
      padding-left: clamp(0.75rem, 3vw, 2.5rem) !important;
      padding-right: clamp(0.75rem, 3vw, 2.5rem) !important;
      max-width: 1400px !important;
  }

  /* ── Keyframe Animations ── */
  @keyframes gradientShimmer {
      0% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
      100% { background-position: 0% 50%; }
  }

  @keyframes pulseLive {
      0%, 100% {
          box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
          transform: scale(1);
      }
      50% {
          box-shadow: 0 0 0 8px rgba(34, 197, 94, 0);
          transform: scale(1.05);
      }
  }

  @keyframes floatCard {
      0% { transform: translateY(0px); }
      50% { transform: translateY(-3px); }
      100% { transform: translateY(0px); }
  }

  @keyframes subtleGlow {
      0%, 100% { border-color: rgba(99, 102, 241, 0.3); }
      50% { border-color: rgba(168, 85, 247, 0.6); }
  }

  /* ── Animated Headers ── */
  .main-header {
      font-family: 'Outfit', sans-serif !important;
      font-size: clamp(1.75rem, 4.5vw, 2.75rem);
      font-weight: 900;
      letter-spacing: -0.03em;
      background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc, #f472b6, #38bdf8);
      background-size: 300% 300%;
      animation: gradientShimmer 8s ease infinite;
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 0.15rem;
      line-height: 1.15;
  }

  .header-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 12px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.3);
      color: #c7d2fe;
      backdrop-filter: blur(8px);
  }

  .live-dot {
      width: 7px;
      height: 7px;
      background-color: #22c55e;
      border-radius: 50%;
      animation: pulseLive 2s infinite cubic-bezier(0.45, 0, 0.55, 1);
  }

  /* ── Glassmorphic Cards ── */
  .glass-panel {
      background: rgba(26, 22, 53, 0.55);
      border: 1px solid rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-radius: 16px;
      padding: 1.25rem;
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .glass-panel:hover {
      border-color: rgba(129, 140, 248, 0.3);
      box-shadow: 0 14px 40px -10px rgba(99, 102, 241, 0.25);
      transform: translateY(-2px);
  }

  /* ── Modern Tabs ── */
  .stTabs [data-baseweb="tab-list"] {
      gap: 6px;
      background: rgba(18, 15, 38, 0.75);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 14px;
      padding: 6px;
      backdrop-filter: blur(12px);
      flex-wrap: wrap;
  }

  .stTabs [data-baseweb="tab"] {
      font-size: clamp(0.75rem, 2vw, 0.88rem);
      font-weight: 600;
      padding: 9px 14px;
      border-radius: 10px;
      color: rgba(226, 232, 240, 0.7);
      background: transparent;
      border: none;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      min-height: 42px;
  }

  .stTabs [data-baseweb="tab"]:hover {
      color: #ffffff;
      background: rgba(255, 255, 255, 0.06);
  }

  .stTabs [aria-selected="true"] {
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.95), rgba(168, 85, 247, 0.95)) !important;
      color: #ffffff !important;
      box-shadow: 0 4px 20px -2px rgba(99, 102, 241, 0.5);
  }

  /* ── Primary & Secondary Buttons ── */
  .stButton > button {
      width: 100%;
      padding: 13px 20px;
      font-size: 0.95rem;
      font-weight: 700;
      font-family: 'Outfit', sans-serif;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%);
      background-size: 200% auto;
      color: #ffffff;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 18px rgba(99, 102, 241, 0.35);
      min-height: 48px;
  }

  .stButton > button:hover {
      background-position: right center;
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(139, 92, 246, 0.6);
      border-color: rgba(255, 255, 255, 0.3);
  }

  .stButton > button:active {
      transform: translateY(0);
      box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3);
  }

  .stButton > button[kind="secondary"] {
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: none;
  }

  .stButton > button[kind="secondary"]:hover {
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.25);
  }

  /* ── Input Fields & Selectboxes ── */
  .stTextInput > div > div > input,
  .stSelectbox > div > div,
  .stTextArea > div > div > textarea {
      background: rgba(18, 15, 38, 0.8) !important;
      border: 1px solid rgba(255, 255, 255, 0.12) !important;
      border-radius: 12px !important;
      color: #f8fafc !important;
      font-size: 0.95rem;
      padding: 12px 16px;
      min-height: 48px;
      transition: all 0.2s ease;
  }

  .stTextInput > div > div > input:focus,
  .stTextArea > div > div > textarea:focus {
      border-color: #818cf8 !important;
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
      background: rgba(26, 22, 53, 0.95) !important;
  }

  /* ── Metric Cards ── */
  [data-testid="metric-container"] {
      background: rgba(24, 20, 48, 0.65);
      border: 1px solid rgba(255, 255, 255, 0.09);
      backdrop-filter: blur(12px);
      border-radius: 14px;
      padding: 16px;
      transition: all 0.25s ease;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.25);
  }

  [data-testid="metric-container"]:hover {
      border-color: rgba(99, 102, 241, 0.35);
      transform: translateY(-2px);
      box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
  }

  [data-testid="metric-container"] label {
      color: rgba(203, 213, 225, 0.7) !important;
      font-size: 0.8rem;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
  }

  [data-testid="metric-container"] [data-testid="metric-value"] {
      color: #ffffff !important;
      font-family: 'Outfit', sans-serif;
      font-size: clamp(1.2rem, 3.5vw, 1.6rem);
      font-weight: 800;
  }

  /* ── Expanders ── */
  .streamlit-expanderHeader {
      background: rgba(26, 22, 53, 0.75) !important;
      border: 1px solid rgba(255, 255, 255, 0.08) !important;
      border-radius: 12px !important;
      color: #f8fafc !important;
      font-weight: 600;
      font-size: 0.92rem;
      padding: 14px 18px !important;
      min-height: 50px;
      transition: all 0.2s ease;
  }

  .streamlit-expanderHeader:hover {
      background: rgba(35, 30, 70, 0.85) !important;
      border-color: rgba(129, 140, 248, 0.3) !important;
  }

  .streamlit-expanderContent {
      background: rgba(16, 13, 34, 0.6) !important;
      border-radius: 0 0 12px 12px !important;
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-top: none;
      padding: 16px !important;
  }

  /* ── Status Widget ── */
  [data-testid="stStatus"] {
      background: rgba(22, 18, 46, 0.85) !important;
      border: 1px solid rgba(99, 102, 241, 0.25) !important;
      backdrop-filter: blur(12px) !important;
      border-radius: 14px !important;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4) !important;
  }
  [data-testid="stStatus"] * { color: rgba(241, 245, 249, 0.9) !important; }

  /* ── DataFrames & Tables ── */
  .stDataFrame {
      border-radius: 14px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.08);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  }

  .stDataFrame th {
      background: linear-gradient(135deg, rgba(99, 102, 241, 0.35), rgba(139, 92, 246, 0.25)) !important;
      color: #ffffff !important;
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      font-size: 0.85rem;
      letter-spacing: 0.03em;
  }

  .stDataFrame td {
      color: rgba(241, 245, 249, 0.9);
      border-color: rgba(255, 255, 255, 0.05);
  }

  /* ── Alerts & Notifications ── */
  .stAlert {
      border-radius: 14px !important;
      border: 1px solid rgba(255, 255, 255, 0.08) !important;
      backdrop-filter: blur(12px) !important;
      padding: 14px 18px !important;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
  }
  .stSuccess { background: rgba(34, 197, 94, 0.12) !important; border-color: rgba(34, 197, 94, 0.3) !important; color: #86efac !important; }
  .stInfo    { background: rgba(59, 130, 246, 0.12) !important; border-color: rgba(59, 130, 246, 0.3) !important; color: #93c5fd !important; }
  .stWarning { background: rgba(245, 158, 11, 0.12) !important; border-color: rgba(245, 158, 11, 0.3) !important; color: #fde047 !important; }
  .stError   { background: rgba(239, 68, 68, 0.12)  !important; border-color: rgba(239, 68, 68, 0.3) !important; color: #fca5a5 !important; }

  /* ── Download Action Button ── */
  .stDownloadButton > button {
      background: linear-gradient(135deg, #059669 0%, #10b981 50%, #34d399 100%) !important;
      border: 1px solid rgba(255, 255, 255, 0.2) !important;
      color: #ffffff !important;
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      border-radius: 12px;
      box-shadow: 0 4px 18px rgba(16, 185, 129, 0.35);
  }

  .stDownloadButton > button:hover {
      box-shadow: 0 8px 25px rgba(16, 185, 129, 0.55);
      transform: translateY(-2px);
  }

  /* ── Custom Scrollbar ── */
  ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
  }
  ::-webkit-scrollbar-track {
      background: rgba(15, 12, 41, 0.6);
  }
  ::-webkit-scrollbar-thumb {
      background: rgba(99, 102, 241, 0.35);
      border-radius: 4px;
  }
  ::-webkit-scrollbar-thumb:hover {
      background: rgba(99, 102, 241, 0.6);
  }

  /* ── Responsive adjustments ── */
  @media (max-width: 640px) {
      .block-container {
          padding-left: 0.5rem !important;
          padding-right: 0.5rem !important;
      }
      .stTabs [data-baseweb="tab"] {
          font-size: 0.68rem;
          padding: 7px 8px;
      }
  }
</style>
""", unsafe_allow_html=True)

# Inject portal-level dark theme via JS (covers BaseWeb dropdown portal outside component tree)
st.components.v1.html("""
<script>
(function injectDarkPortalStyles() {
  const id = 'dark-portal-styles';
  if (document.getElementById(id)) return;
  const style = document.createElement('style');
  style.id = id;
  style.textContent = `
    /* BaseWeb dropdown popup */
    [data-baseweb="popover"] { background: #1a1730 !important; border-radius: 10px !important; border: 1px solid rgba(255,255,255,0.12) !important; box-shadow: 0 8px 32px rgba(0,0,0,0.7) !important; overflow: hidden !important; }
    [data-baseweb="menu"], ul[data-baseweb="menu"] { background: #1a1730 !important; border-radius: 10px !important; padding: 4px !important; }
    [role="option"] { background: transparent !important; color: rgba(255,255,255,0.85) !important; border-radius: 6px !important; margin: 1px 4px !important; padding: 9px 12px !important; }
    [role="option"]:hover { background: rgba(102,126,234,0.25) !important; color: white !important; }
    [role="option"][aria-selected="true"] { background: rgba(102,126,234,0.4) !important; color: white !important; font-weight: 600 !important; }
    [data-baseweb="select"] input { color: white !important; caret-color: white !important; }
    /* Tooltip / notification popovers */
    [data-baseweb="tooltip"] { background: #302b63 !important; color: white !important; border-radius: 8px !important; }
  `;
  // Try appending to parent frame head (Streamlit renders in iframe)
  try { window.parent.document.head.appendChild(style.cloneNode(true)); } catch(e) {}
  document.head.appendChild(style);
  // Re-run on mutations in case Streamlit re-renders
  new MutationObserver(() => {
    if (!document.getElementById(id)) document.head.appendChild(style.cloneNode(true));
  }).observe(document.body, { childList: true, subtree: true });
})()
</script>
""", height=0)

# Helper: PDF Converter
def convert_to_pdf(markdown_content):
    html_content = markdown(markdown_content, extensions=['tables'])
    styled_html = f"""
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 2cm; }}
            body {{ font-family: Helvetica, sans-serif; font-size: 10pt; line-height: 1.5; color: #333; }}
            h1 {{ color: #1E3A8A; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-top: 30px; }}
            h2 {{ color: #2563EB; margin-top: 25px; border-bottom: 1px solid #ddd; }}
            h3 {{ color: #4B5563; margin-top: 20px; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 9pt; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f3f4f6; color: #1f2937; font-weight: bold; }}
            pre {{ background-color: #f3f4f6; padding: 10px; border-radius: 4px; font-size: 8pt; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(styled_html, dest=pdf_buffer)
    if pisa_status.err: return None
    return pdf_buffer.getvalue()

# Helper: Load Sectors
with open('sectors.json', 'r') as f:
    SECTORS = json.load(f)

# --- Main UI ---
def main():
    # Top header hero row
    col_h1, col_h2 = st.columns([2.8, 1.2])
    with col_h1:
        st.markdown('<h1 class="main-header">💸 Financial Intelligence</h1>', unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:4px;margin-bottom:12px;">
            <div class="header-badge"><span class="live-dot"></span><span>7-Agent AI Council</span></div>
            <div class="header-badge"><span>⚡ Gemini 3.7 Intelligence</span></div>
            <div class="header-badge"><span>🌐 Turso Cloud Synced</span></div>
        </div>
        """, unsafe_allow_html=True)
    with col_h2:
        st.markdown("""
        <div style="text-align:right;padding-top:12px;">
            <div style="display:inline-block;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);padding:6px 12px;border-radius:10px;">
                <span style="font-size:0.72rem;font-weight:600;color:#c7d2fe;">PRO TERMINAL</span>
                <span style="font-size:0.68rem;color:rgba(255,255,255,0.4);margin-left:6px;">v3.5 • Quantum</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏭 Sector Analysis",
        "🏢 Stock Analysis",
        "🏆 Top Picks",
        "🤖 QuanTum Picks",
        "🌍 Global Markets",
        "📰 Market News",
        "📚 Report Library"
    ])

    # --- Tab 1: Sector Analysis ---
    with tab1:
        st.subheader("Comprehensive Industry Analysis")
        st.caption("Multi-Agent Deep Dive: Trends, Stocks, Institutional Positioning")
        
        selected_sector = st.selectbox("Choose Industry", SECTORS, key="sector_select")
        
        if st.button("Generate Sector Report", type="primary"):
            from sector_orchestrator import SectorOrchestrator
            
            report_container = st.empty()
            
            with st.status("🏭 Sector Analysis Pipeline Running...", expanded=True) as status:
                
                def update_progress(msg):
                    st.write(msg)
                
                # Run Sector Orchestrator
                sector_council = SectorOrchestrator()
                final_report = sector_council.run_sector_analysis(selected_sector, progress_callback=update_progress)
                
                status.update(label="✅ Comprehensive Sector Report Ready!", state="complete", expanded=False)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"reports/Sector_{selected_sector.replace(' ', '_')}_{timestamp}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
            
            st.success(f"📄 Report Generated: {filename}")
            
            # Generate PDF (NO frontend display)
            pdf = convert_to_pdf(final_report)
            if pdf:
                st.download_button(
                    "📥 Download Comprehensive Sector Report (PDF)", 
                    pdf, 
                    f"{selected_sector}_Sector_Report.pdf", 
                    "application/pdf",
                    type="primary"
                )
            else:
                st.error("PDF generation failed.")
            
            # Optional: Show preview in expander (collapsed by default)
            with st.expander("📖 Preview Report (Click to Expand)", expanded=False):
                st.markdown(final_report)

    # --- Tab 2: Stock Analysis ---
    with tab2:
        st.subheader("Deep Dive Investment Memo")
        ticker_input = st.text_input("Enter Ticker Symbol (e.g., TATAMOTORS, RELIANCE)", placeholder="Type symbol...")
        
        if st.button("Run Council Analysis", type="primary") and ticker_input:
            orchestrator = AgentOrchestrator()
            report_container = st.empty()
            
            # Progress tracking
            with st.status("🚀 Convening the Council...", expanded=True) as status:
                
                def update_progress(msg):
                    st.write(msg)
                
                # Run the 7-Agent Pipeline
                final_report = orchestrator.run_analysis_pipeline(ticker_input, progress_callback=update_progress)
                status.update(label="✅ Final Investment Memo Ready!", state="complete", expanded=False)
            
            report_container.markdown(final_report)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/DeepDive_{ticker_input}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
                
            pdf = convert_to_pdf(final_report)
            if pdf: st.download_button("📥 Download Investment Memo", pdf, f"{ticker_input}_Memo.pdf", "application/pdf")

    # --- Tab 3: Top Picks ---
    with tab3:
        st.subheader("Screen & Deep Dive Best Opportunities")
        screen_sector = st.selectbox("Choose Industry to Screen", SECTORS, key="screen_selector")
        
        if st.button("Find Top Picks"):
            with st.status("🔍 Screening Sector...", expanded=True) as status:
                # 1. Screen (Legacy logic -> Quick & Best)
                skills = analyst.load_skills()
                model = analyst.setup_gemini()
                screen_prompt = analyst.get_screening_prompt(screen_sector, skills)
                screen_resp = model.generate_content(screen_prompt)
                
                # Extract Tickers
                ext_prompt = f"Extract exactly 3 ticker symbols from this text as a comma-separated list. Text: {screen_resp.text}"
                tickers = [t.strip() for t in model.generate_content(ext_prompt).text.split(',')][:3]
                
                st.write(f"🎯 Top Picks Identified: {tickers}")
                
                # 2. Deep Dive Loop
                full_report = f"# Top Picks Report: {screen_sector}\n\n"
                orchestrator = AgentOrchestrator()
                
                for ticker in tickers:
                    st.write(f"🔬 Analyzing {ticker}...")
                    memo = orchestrator.run_analysis_pipeline(ticker, progress_callback=lambda x: None) # Silent logs
                    full_report += f"\n## Analysis: {ticker}\n\n{memo}\n\n---\n\n"
                
                status.update(label="✅ Top Picks Report Generated!", state="complete", expanded=False)
            
            st.markdown(full_report)
            pdf = convert_to_pdf(full_report)
            if pdf: st.download_button("📥 Download Top Picks Report", pdf, f"{screen_sector}_TopPicks.pdf", "application/pdf")

    # --- Tab 7: Report Library ---
    with tab7:
        st.subheader("📚 Report Archive")
        st.caption("Browse, preview, and download all previously generated reports")
        
        # Check if reports directory exists
        reports_dir = 'reports'
        if not os.path.exists(reports_dir):
            st.info("No reports found yet. Generate your first report!")
        else:
            # Get all markdown files
            all_files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
            
            if not all_files:
                st.info("No reports found yet. Generate your first report!")
            else:
                # Filter options
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    report_type = st.selectbox(
                        "Filter by Type",
                        ["All", "Sector Reports", "Stock Analysis", "Top Picks", "Other"],
                        key="report_type_filter"
                    )
                
                with col2:
                    search_term = st.text_input("Search reports", placeholder="Enter keyword...", key="search_reports")
                
                # Filter files based on selection
                filtered_files = []
                for f in all_files:
                    # Type filtering
                    if report_type == "Sector Reports" and not f.startswith("Sector_"):
                        continue
                    elif report_type == "Stock Analysis" and not f.startswith("DeepDive_"):
                        continue
                    elif report_type == "Top Picks" and not f.startswith("Full_Report_"):
                        continue
                    elif report_type == "Other" and (f.startswith("Sector_") or f.startswith("DeepDive_") or f.startswith("Full_Report_")):
                        continue
                    
                    # Search filtering
                    if search_term and search_term.lower() not in f.lower():
                        continue
                    
                    filtered_files.append(f)
                
                # Sort by modification time (newest first)
                filtered_files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)),
                    reverse=True
                )
                
                st.write(f"**Found {len(filtered_files)} report(s)**")
                
                # Display reports
                for filename in filtered_files:
                    file_path = os.path.join(reports_dir, filename)
                    file_stats = os.stat(file_path)
                    file_size_kb = file_stats.st_size / 1024
                    mod_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                    
                    # Determine report type icon
                    if filename.startswith("Sector_"):
                        icon = "🏭"
                        type_label = "Sector"
                    elif filename.startswith("DeepDive_"):
                        icon = "🏢"
                        type_label = "Stock"
                    elif filename.startswith("Full_Report_"):
                        icon = "🏆"
                        type_label = "Top Picks"
                    else:
                        icon = "📄"
                        type_label = "Other"
                    
                    with st.expander(f"{icon} **{filename}** ({type_label} • {file_size_kb:.1f} KB • {mod_time})", expanded=False):
                        # Read file content
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Action buttons
                        col_a, col_b, col_c = st.columns([2, 2, 1])
                        
                        with col_a:
                            pdf = convert_to_pdf(content)
                            if pdf:
                                st.download_button(
                                    "📥 Download PDF",
                                    pdf,
                                    filename.replace('.md', '.pdf'),
                                    "application/pdf",
                                    key=f"pdf_{filename}"
                                )
                        
                        with col_b:
                            st.download_button(
                                "📝 Download Markdown",
                                content,
                                filename,
                                "text/markdown",
                                key=f"md_{filename}"
                            )
                        
                        with col_c:
                            if st.button("🗑️ Delete", key=f"del_{filename}"):
                                os.remove(file_path)
                                st.rerun()
                        
                        # Preview (first 500 characters)
                        st.markdown("**Preview:**")
                        preview_text = content[:500] + "..." if len(content) > 500 else content
                        st.markdown(preview_text)
                        
                        # Full content in nested expander
                        with st.expander("📖 View Full Report"):
                            st.markdown(content)

    # --- Tab 5: Global Markets ---
    with tab5:
        st.subheader("🌍 Global Market Research")
        st.caption("Multi-Agent Analysis of Emerging & Developed Markets")
        
        market_type = st.radio(
            "Select Market Type",
            ["🌏 Emerging Markets", "🇺🇸 Developed Markets"],
            horizontal=True
        )
        
        if market_type == "🌏 Emerging Markets":
            st.markdown("**Target Markets**: Brazil, China, Indonesia, Turkey")
            
            if st.button("Generate Emerging Markets Report", type="primary"):
                from global_markets_orchestrator import EmergingMarketsOrchestrator
                
                with st.status("🌏 Emerging Markets Analysis Running...", expanded=True) as status:
                    
                    def update_progress(msg):
                        st.write(msg)
                    
                    orchestrator = EmergingMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    
                    status.update(label="✅ Emerging Markets Report Ready!", state="complete", expanded=False)
                
                # Save Report
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_EmergingMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"📄 Report Generated: {filename}")
                
                # PDF Download
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "📥 Download Emerging Markets Report (PDF)",
                        pdf,
                        "Emerging_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                # Preview
                with st.expander("📖 Preview Report", expanded=False):
                    st.markdown(final_report)
        
        else:  # Developed Markets
            st.markdown("**Target Markets**: USA, Europe, Japan")
            
            if st.button("Generate Developed Markets Report", type="primary"):
                from global_markets_orchestrator import DevelopedMarketsOrchestrator
                
                with st.status("🇺🇸 Developed Markets Analysis Running...", expanded=True) as status:
                    
                    def update_progress(msg):
                        st.write(msg)
                    
                    orchestrator = DevelopedMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    
                    status.update(label="✅ Developed Markets Report Ready!", state="complete", expanded=False)
                
                # Save Report
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_DevelopedMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"📄 Report Generated: {filename}")
                
                # PDF Download
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "📥 Download Developed Markets Report (PDF)",
                        pdf,
                        "Developed_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                # Preview
                with st.expander("📖 Preview Report", expanded=False):
                    st.markdown(final_report)

    # --- Tab 6: Market News ---
    with tab6:
        st.subheader("📰 Market News Pulse")
        st.caption("High-Impact News Tracker with Sentiment Analysis")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            news_scope = st.selectbox(
                "News Scope",
                ["Global (India + World)", "India Only"],
                key="news_scope"
            )
        
        with col2:
            if st.button("Fetch Latest News", type="primary"):
                st.session_state['refresh_news'] = True
        
        if st.button("🔄 Refresh News Feed", type="secondary") or st.session_state.get('refresh_news', False):
            from news_tracker_orchestrator import NewsTrackerOrchestrator
            
            scope = "global" if "Global" in news_scope else "india"
            
            with st.status("📰 Fetching & Analyzing News...", expanded=True) as status:
                
                def update_progress(msg):
                    st.write(msg)
                
                orchestrator = NewsTrackerOrchestrator()
                organized_news = orchestrator.run_analysis(scope=scope, progress_callback=update_progress)
                
                status.update(label="✅ News Analysis Complete!", state="complete", expanded=False)
            
            # Display News
            st.markdown("---")
            
            # High Impact News
            st.markdown("### 🔴 High-Impact News (Market-Moving)")
            high_news = organized_news.get('high_impact', [])
            if high_news:
                for idx, item in enumerate(high_news[:10]):
                    sentiment_color = {
                        'BULLISH': '🟢',
                        'BEARISH': '🔴',
                        'NEUTRAL': '🟡'
                    }.get(item.get('sentiment', 'NEUTRAL'), '🟡')
                    
                    with st.expander(f"{sentiment_color} {item.get('title', 'No Title')}", expanded=(idx < 3)):
                        st.markdown(f"**Summary**: {item.get('summary', item.get('body', ''))}")
                        st.caption(f"Sentiment: **{item.get('sentiment', 'N/A')}** | Impact: **{item.get('impact', 'N/A')}**")
                        if 'href' in item:
                            st.markdown(f"[Read More]({item['href']})")
            else:
                st.info("No high-impact news found.")
            
            st.markdown("---")
            
            # Medium Impact News
            st.markdown("### 🟡 Medium-Impact News")
            medium_news = organized_news.get('medium_impact', [])
            if medium_news:
                for item in medium_news[:5]:
                    sentiment = item.get('sentiment', 'NEUTRAL')
                    st.markdown(f"**{item.get('title', 'No Title')}** ({sentiment})")
                    st.caption(item.get('summary', item.get('body', ''))[:200] + "...")
            else:
                st.info("No medium-impact news found.")
            
            # Reset refresh flag
            st.session_state['refresh_news'] = False

    # --- Tab 4: QuanTum Engine ---
    with tab4:
        st.subheader("🤖 QuanTum Engine — AI Stock Picks")
        st.caption("Multi-factor quant algorithm: Technical + Fundamental + News Sentiment → Ranked Recommendations")

        # Algorithm explanation
        with st.expander("⚙️ How the Algorithm Works", expanded=False):
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Technical Score", "35% / Week", "25% / Year")
                st.caption("RSI, MACD, SMA50/200 crossovers")
            with col_b:
                st.metric("News Sentiment", "35% / Week", "20% / Year")
                st.caption("ET, Moneycontrol, Mint RSS → Gemini AI")
            with col_c:
                st.metric("Fundamental Score", "15% / Week", "50% / 5Y")
                st.caption("P/E, ROE, Debt/Equity via yfinance")
            with col_d:
                st.metric("Momentum Score", "15% / Week", "25% / Year")
                st.caption("Price vs SMA50 & SMA200 trend")

        st.markdown("---")

        # Run mode. Fast keeps a phone-triggered run to a few minutes by
        # trimming the long-horizon universe; weekly picks are unaffected
        # because they always come from the news scanner.
        mode = st.radio(
            "Run mode",
            ["Fast", "Full"],
            horizontal=True,
            help="Fast: news-discovered stocks plus a trimmed Nifty universe. "
                 "Full: the entire 80+ stock universe, several minutes longer.",
        )
        run_btn = st.button("🚀 Run QuanTum Engine", type="primary", use_container_width=True)

        # Last completed run, shown instantly so the page is useful on open.
        cached = load_report("quantum") if not run_btn else None
        if cached:
            st.success(f"Last run: {cached['created']} ({cached.get('mode') or 'full'})")
            with st.expander("📖 Last saved report", expanded=False):
                st.markdown(cached["markdown"])
        elif not run_btn:
            st.info("No saved report yet. Tap Run to generate one.")

        if run_btn:
            from quantum_orchestrator import QuantumEngineOrchestrator

            progress_log = []

            with st.status("🤖 QuanTum Engine Running...", expanded=True) as status:
                log_container = st.empty()

                def qt_progress(msg):
                    progress_log.append(msg)
                    log_container.markdown("\n\n".join([
                        f"`{m}`" for m in progress_log[-6:]
                    ]))

                engine = QuantumEngineOrchestrator()
                result = engine.run(progress_callback=qt_progress, fast=(mode == "Fast"))

                if "error" in result:
                    status.update(label=f"❌ Error: {result['error']}", state="error")
                    st.error(result["error"])
                else:
                    status.update(label="✅ QuanTum Engine Complete!", state="complete", expanded=False)
                    cache_cols = ["ticker", "composite_score", "conviction", "close",
                                  "rsi", "pe_ratio", "roe", "entry_status"]
                    save_report(
                        "quantum",
                        result.get("report", ""),
                        picks={
                            horizon: picks_to_records(result.get(key), cache_cols)
                            for horizon, key in (("week", "week_picks"),
                                                 ("year", "year_picks"),
                                                 ("fiveyear", "fiveyear_picks"))
                        },
                        mode=mode.lower(),
                    )

            if "error" not in result:
                # ── Ranked Picks Tables ───────────────────────────────────
                st.markdown("## 📊 Ranked Results")
                horizon_tab1, horizon_tab2, horizon_tab3 = st.tabs([
                    "🗓️ This Week", "📅 This Year", "🏆 5 Years"
                ])

                def show_picks_table(picks_df):
                    display_cols = ["ticker", "final_score", "close", "rsi",
                                    "sma50", "pe_ratio", "roe", "debt_equity"]
                    cols_present = [c for c in display_cols if c in picks_df.columns]
                    styled = picks_df[cols_present].head(10).rename(columns={
                        "ticker": "Stock",
                        "final_score": "Score",
                        "close": "Price (₹)",
                        "rsi": "RSI",
                        "sma50": "SMA50",
                        "pe_ratio": "P/E",
                        "roe": "ROE",
                        "debt_equity": "D/E",
                    })
                    st.dataframe(
                        styled.round(2),
                        use_container_width=True,
                        hide_index=True,
                    )

                with horizon_tab1:
                    st.caption("Top picks for swing trading this week (technical + sentiment dominant)")
                    show_picks_table(result["week_picks"])

                with horizon_tab2:
                    st.caption("Top compounders for 6-12 month positional play")
                    show_picks_table(result["year_picks"])

                with horizon_tab3:
                    st.caption("Structural wealth creators — buy and hold 5 years")
                    show_picks_table(result["fiveyear_picks"])

                # ── News Headlines Used ───────────────────────────────────
                with st.expander("📰 News Headlines Used in Sentiment Analysis"):
                    for h in result.get("headlines", [])[:20]:
                        st.markdown(f"- **[{h['source']}]** {h['title']}")

                # ── Full AI Report ────────────────────────────────────────
                st.markdown("---")
                st.markdown("## 📝 Full QuanTum Recommendation Report")

                with st.expander("📖 View Full Report", expanded=True):
                    st.markdown(result["report"])

                # PDF Download
                pdf = convert_to_pdf(result["report"])
                if pdf:
                    st.download_button(
                        "📥 Download QuanTum Report (PDF)",
                        pdf,
                        f"QuanTum_Picks_{datetime.now().strftime('%Y%m%d')}.pdf",
                        "application/pdf",
                        type="primary",
                    )

                st.success(f"💾 Report saved: `{result['report_path']}`")


if __name__ == "__main__":
    main()
