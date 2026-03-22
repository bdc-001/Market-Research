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
import financial_analyst_cli as analyst # Keep old screening logic for now


# Page Config
st.set_page_config(
    page_title="Financial Intelligence",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed",  # Collapsed by default on mobile
)

# Mobile-First CSS
st.markdown("""
<style>
  /* ── Google Font ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  /* ── Global Reset & Font ── */
  html, body, [class*="css"] {
      font-family: 'Inter', sans-serif !important;
  }

  /* ── Background ── */
  .stApp {
      background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
      min-height: 100vh;
  }

  /* ── Main block padding ── */
  .block-container {
      padding-top: 1rem !important;
      padding-left: 0.75rem !important;
      padding-right: 0.75rem !important;
      max-width: 100% !important;
  }

  /* ── Header ── */
  .main-header {
      font-size: clamp(1.4rem, 5vw, 2.2rem);
      font-weight: 800;
      background: linear-gradient(90deg, #f093fb, #f5a623, #4facfe);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 0;
      line-height: 1.2;
  }

  /* ── Tabs — bigger touch targets ── */
  .stTabs [data-baseweb="tab-list"] {
      gap: 2px;
      background: rgba(255,255,255,0.05);
      border-radius: 12px;
      padding: 4px;
      flex-wrap: wrap;
  }
  .stTabs [data-baseweb="tab"] {
      font-size: clamp(0.65rem, 2.5vw, 0.85rem);
      font-weight: 600;
      padding: 8px 10px;
      border-radius: 8px;
      color: rgba(255,255,255,0.6);
      white-space: nowrap;
      min-height: 40px;
  }
  .stTabs [aria-selected="true"] {
      background: linear-gradient(135deg, #667eea, #764ba2) !important;
      color: white !important;
  }

  /* ── Buttons — large touch targets ── */
  .stButton > button {
      width: 100%;
      padding: 14px 16px;
      font-size: 0.95rem;
      font-weight: 700;
      border-radius: 12px;
      border: none;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: white;
      transition: all 0.2s ease;
      min-height: 50px;
  }
  .stButton > button:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
  }
  .stButton > button[kind="secondary"] {
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.2);
  }

  /* ── Input fields ── */
  .stTextInput > div > div > input,
  .stSelectbox > div > div,
  .stTextArea > div > div > textarea {
      background: rgba(255,255,255,0.08) !important;
      border: 1px solid rgba(255,255,255,0.15) !important;
      border-radius: 10px !important;
      color: white !important;
      font-size: 1rem;
      padding: 12px;
      min-height: 48px;
  }

  /* ── Radio buttons ── */
  .stRadio > div {
      gap: 8px;
  }
  .stRadio label {
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.15);
      border-radius: 10px;
      padding: 10px 14px;
      margin: 2px 0;
      cursor: pointer;
      color: rgba(255,255,255,0.85);
      font-weight: 500;
  }

  /* ── Metric cards ── */
  [data-testid="metric-container"] {
      background: rgba(255,255,255,0.07);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 14px;
      padding: 14px;
  }
  [data-testid="metric-container"] label {
      color: rgba(255,255,255,0.6) !important;
      font-size: 0.75rem;
  }
  [data-testid="metric-container"] [data-testid="metric-value"] {
      color: white !important;
      font-size: clamp(1rem, 4vw, 1.4rem);
      font-weight: 700;
  }

  /* ── Expanders ── */
  .streamlit-expanderHeader {
      background: rgba(255,255,255,0.07) !important;
      border-radius: 10px !important;
      color: white !important;
      font-weight: 600;
      font-size: 0.9rem;
      padding: 14px 16px !important;
      min-height: 50px;
  }
  .streamlit-expanderContent {
      background: rgba(255,255,255,0.03) !important;
      border-radius: 0 0 10px 10px !important;
      border: 1px solid rgba(255,255,255,0.08);
  }

  /* ── Info / Success / Warning boxes ── */
  .stAlert {
      border-radius: 12px !important;
      border: none !important;
      padding: 14px 16px !important;
  }
  .stSuccess { background: rgba(34,197,94,0.15) !important; color: #4ade80 !important; }
  .stInfo    { background: rgba(59,130,246,0.15) !important; color: #93c5fd !important; }
  .stWarning { background: rgba(245,158,11,0.15) !important; color: #fcd34d !important; }
  .stError   { background: rgba(239,68,68,0.15)  !important; color: #f87171 !important; }

  /* ── Captions / small text ── */
  .stCaption, caption {
      color: rgba(255,255,255,0.45) !important;
      font-size: 0.78rem;
  }

  /* ── All text ── */
  p, li, span, div {
      color: rgba(255,255,255,0.85);
  }
  h1, h2, h3, h4, h5 {
      color: white;
  }

  /* ── Dataframe / Tables ── */
  .stDataFrame {
      border-radius: 12px;
      overflow: hidden;
      font-size: clamp(0.7rem, 2vw, 0.85rem);
  }
  .stDataFrame table {
      background: rgba(255,255,255,0.05);
  }
  .stDataFrame th {
      background: rgba(102,126,234,0.3) !important;
      color: white !important;
      font-weight: 700;
  }
  .stDataFrame td {
      color: rgba(255,255,255,0.85);
      border-color: rgba(255,255,255,0.08);
  }

  /* ── Status widget ── */
  [data-testid="stStatus"] {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px;
  }

  /* ── Download button special ── */
  .stDownloadButton > button {
      background: linear-gradient(135deg, #11998e, #38ef7d) !important;
      color: #0f0f0f !important;
      font-weight: 700;
      border-radius: 12px;
  }

  /* ── Selectbox: trigger box text ── */
  .stSelectbox [data-baseweb="select"] > div {
      background: rgba(255,255,255,0.08) !important;
      border-color: rgba(255,255,255,0.2) !important;
      border-radius: 10px !important;
      min-height: 48px;
  }
  /* Force all text nodes inside the select trigger to white */
  .stSelectbox [data-baseweb="select"] * { color: white !important; }
  .stSelectbox svg { fill: rgba(255,255,255,0.5) !important; }

  /* ── Status widget ── */
  [data-testid="stStatus"] {
      background: rgba(30,27,58,0.95) !important;
      border: 1px solid rgba(255,255,255,0.15) !important;
      border-radius: 12px !important;
  }
  [data-testid="stStatus"] * { color: rgba(255,255,255,0.85) !important; }

  /* ── Error traceback boxes ── */
  [data-testid="stException"] {
      background: rgba(239,68,68,0.1) !important;
      border: 1px solid rgba(239,68,68,0.3) !important;
      border-radius: 12px !important;
  }
  [data-testid="stException"] * { color: #fca5a5 !important; }

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {
      background: rgba(15,12,41,0.95);
      border-right: 1px solid rgba(255,255,255,0.1);
  }

  /* ── Horizontal rule ── */
  hr { border-color: rgba(255,255,255,0.1) !important; margin: 1rem 0; }

  /* ── Mobile: single-column stacks ── */
  @media (max-width: 640px) {
      .block-container {
          padding-left: 0.5rem !important;
          padding-right: 0.5rem !important;
      }
      .stTabs [data-baseweb="tab"] {
          font-size: 0.6rem;
          padding: 6px 6px;
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
    # Top header row
    col_h1, col_h2 = st.columns([3, 1])
    with col_h1:
        st.markdown('<h1 class="main-header">💸 Financial Intelligence</h1>', unsafe_allow_html=True)
        st.caption("7-Agent AI Council • Quant • Global Markets • News")
    with col_h2:
        st.markdown("<div style='text-align:right;padding-top:10px'><span style='font-size:0.7rem;color:rgba(255,255,255,0.4)'>v3.0 • Indie-Quant</span></div>",
                    unsafe_allow_html=True)

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

        # Universe selector
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("🔍 Scanning **80+ NSE stocks** across Nifty 500 universe (auto-selected)")
        with col2:
            run_btn = st.button("🚀 Run QuanTum Engine", type="primary", use_container_width=True)

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
                result = engine.run(progress_callback=qt_progress)

                if "error" in result:
                    status.update(label=f"❌ Error: {result['error']}", state="error")
                    st.error(result["error"])
                else:
                    status.update(label="✅ QuanTum Engine Complete!", state="complete", expanded=False)

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
