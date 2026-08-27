"""
QuanTum Financial Intelligence — Enterprise Multi-Agent Terminal
Features: 7-Agent Council, Technical & Fundamental Quant Engine, Global Markets, Report Archive.
Theme: Clean Enterprise White & Purple (Figtree Typography)
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
    page_title="QuanTum • Financial Intelligence",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enterprise White & Purple CSS (Figtree Font) ─────────────────────────────
st.markdown("""
<style>
  /* ── Google Fonts: Figtree & JetBrains Mono ── */
  @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

  /* ── Global Reset & Typography ── */
  html, body, [class*="css"], [class*="st-"], [data-testid="stSidebar"], .stMarkdown, .stButton, input, select, textarea, p, h1, h2, h3, h4, h5, h6, span, div, label, li {
      font-family: 'Figtree', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      letter-spacing: -0.01em;
  }

  code, pre, .stCodeBlock, .stCodeBlock code {
      font-family: 'JetBrains Mono', monospace !important;
  }

  /* ── App Canvas Background ── */
  .stApp {
      background-color: #ffffff;
      background-image: radial-gradient(at 100% 0%, rgba(124, 58, 237, 0.04) 0px, transparent 50%),
                        radial-gradient(at 0% 100%, rgba(139, 92, 246, 0.03) 0px, transparent 50%);
      color: #0f172a;
      min-height: 100vh;
  }

  /* ── Main Container Padding ── */
  .block-container {
      padding-top: 2rem !important;
      padding-bottom: 3rem !important;
      padding-left: clamp(1.5rem, 4vw, 4rem) !important;
      padding-right: clamp(1.5rem, 4vw, 4rem) !important;
      max-width: 1440px !important;
  }

  /* Compact the top header space */
  header[data-testid="stHeader"] {
      height: 2.5rem !important;
  }

  /* ── Animations ── */
  @keyframes pulseLive {
      0%, 100% {
          box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.6);
          transform: scale(1);
      }
      50% {
          box-shadow: 0 0 0 6px rgba(34, 197, 94, 0);
          transform: scale(1.08);
      }
  }

  @keyframes purpleGlow {
      0%, 100% { box-shadow: 0 4px 14px rgba(124, 58, 237, 0.25); }
      50% { box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4); }
  }

  /* ── Left Sidebar Enterprise Navigation ── */
  [data-testid="stSidebar"] {
      background-color: #f8fafc !important;
      border-right: 1px solid #e2e8f0 !important;
      padding: 1rem 0.5rem !important;
  }

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
      color: #0f172a !important;
  }

  /* Brand Header Container */
  .sidebar-brand-container {
      padding: 0.75rem 0.75rem 1.25rem 0.75rem;
      border-bottom: 1px solid #e2e8f0;
      margin-bottom: 1.25rem;
  }

  .sidebar-brand-header {
      display: flex;
      align-items: center;
      gap: 10px;
  }

  .brand-icon-box {
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
      box-shadow: 0 4px 12px rgba(124, 58, 237, 0.35);
      color: #ffffff;
  }

  .brand-text-title {
      font-size: 1.15rem;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.15;
  }

  .brand-text-sub {
      font-size: 0.75rem;
      font-weight: 600;
      color: #64748b;
  }

  .brand-tag {
      display: inline-block;
      margin-top: 8px;
      font-size: 0.65rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 3px 8px;
      border-radius: 6px;
      background: #f5f3ff;
      color: #7c3aed;
      border: 1px solid #ddd6fe;
  }

  /* ── Sidebar Radio Navigation Items ── */
  [data-testid="stSidebar"] .stRadio > label {
      font-size: 0.75rem !important;
      font-weight: 700 !important;
      color: #64748b !important;
      text-transform: uppercase !important;
      letter-spacing: 0.06em !important;
      padding-left: 6px !important;
      margin-bottom: 8px !important;
  }

  [data-testid="stSidebar"] .stRadio > div {
      gap: 6px !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {
      background: #ffffff !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 10px !important;
      padding: 10px 14px !important;
      margin: 2px 0 !important;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
      cursor: pointer !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
      width: 100% !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {
      background: #f5f3ff !important;
      border-color: #c4b5fd !important;
      transform: translateX(3px) !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
      color: #334155 !important;
      font-weight: 600 !important;
      font-size: 0.88rem !important;
  }

  /* Hide raw radio circles for cleaner navbar look */
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] input[type="radio"] + div {
      border-color: #7c3aed !important;
  }

  /* ── Sidebar Status Card ── */
  .sidebar-status-card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 14px;
      margin-top: 1.5rem;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  }

  .status-header-text {
      font-size: 0.72rem;
      font-weight: 700;
      color: #64748b;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
  }

  .status-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 5px 0;
      font-size: 0.78rem;
  }

  .status-left {
      display: flex;
      align-items: center;
      gap: 7px;
      color: #334155;
      font-weight: 500;
  }

  .status-val-pill {
      font-size: 0.7rem;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 9999px;
      background: #f0fdf4;
      color: #16a34a;
      border: 1px solid #bbf7d0;
  }

  .live-pulse-dot {
      width: 7px;
      height: 7px;
      background-color: #22c55e;
      border-radius: 50%;
      display: inline-block;
      animation: pulseLive 2s infinite cubic-bezier(0.45, 0, 0.55, 1);
  }

  /* ── Main View Header ── */
  .enterprise-hero-header {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 2px 6px -1px rgba(0, 0, 0, 0.04);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
  }

  .main-title-text {
      font-size: clamp(1.4rem, 3vw, 1.85rem);
      font-weight: 800;
      color: #0f172a;
      letter-spacing: -0.02em;
      line-height: 1.2;
      margin: 0;
  }

  .main-subtitle-text {
      font-size: 0.85rem;
      color: #64748b;
      margin-top: 3px;
      font-weight: 500;
  }

  .badge-chip-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
  }

  .badge-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: #f5f3ff;
      border: 1px solid #ddd6fe;
      color: #6d28d9;
  }

  /* ── Enterprise Cards & Panels ── */
  .enterprise-panel {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 1.5rem;
      margin-bottom: 1.25rem;
      box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
      transition: all 0.25s ease;
  }

  .enterprise-panel:hover {
      border-color: #c4b5fd;
      box-shadow: 0 10px 25px -5px rgba(124, 58, 237, 0.08);
  }

  /* ── Buttons (Purple Theme) ── */
  .stButton > button {
      width: 100%;
      padding: 12px 20px;
      font-size: 0.95rem;
      font-weight: 700;
      font-family: 'Figtree', sans-serif !important;
      border-radius: 10px;
      border: none;
      background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
      color: #ffffff !important;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      box-shadow: 0 4px 14px rgba(124, 58, 237, 0.3);
      min-height: 46px;
  }

  .stButton > button:hover {
      background: linear-gradient(135deg, #6d28d9 0%, #5b21b6 100%) !important;
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(124, 58, 237, 0.45);
  }

  .stButton > button:active {
      transform: translateY(0);
  }

  .stButton > button[kind="secondary"] {
      background: #ffffff !important;
      border: 1px solid #cbd5e1 !important;
      color: #334155 !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
  }

  .stButton > button[kind="secondary"]:hover {
      background: #f8fafc !important;
      border-color: #94a3b8 !important;
      color: #0f172a !important;
  }

  /* ── Input Fields & Selectboxes ── */
  .stTextInput > div > div > input,
  .stSelectbox > div > div,
  .stTextArea > div > div > textarea {
      background: #ffffff !important;
      border: 1px solid #cbd5e1 !important;
      border-radius: 10px !important;
      color: #0f172a !important;
      font-size: 0.95rem !important;
      font-weight: 500 !important;
      padding: 10px 14px !important;
      min-height: 46px !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02) !important;
      transition: all 0.2s ease !important;
  }

  .stTextInput > div > div > input:focus,
  .stSelectbox > div > div:focus-within,
  .stTextArea > div > div > textarea:focus {
      border-color: #7c3aed !important;
      box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15) !important;
  }

  /* ── Selectbox Dropdown Container ── */
  .stSelectbox [data-baseweb="select"] > div {
      background: #ffffff !important;
      border-color: #cbd5e1 !important;
      border-radius: 10px !important;
      min-height: 46px !important;
  }
  .stSelectbox [data-baseweb="select"] * { color: #0f172a !important; font-weight: 500; }
  .stSelectbox svg { fill: #64748b !important; }

  /* ── Metric Cards ── */
  [data-testid="metric-container"] {
      background: #ffffff !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 12px !important;
      padding: 14px 16px !important;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
      transition: all 0.2s ease !important;
  }

  [data-testid="metric-container"]:hover {
      border-color: #c4b5fd !important;
      box-shadow: 0 6px 16px rgba(124, 58, 237, 0.08) !important;
      transform: translateY(-1px);
  }

  [data-testid="metric-container"] label {
      color: #64748b !important;
      font-size: 0.78rem !important;
      font-weight: 700 !important;
      text-transform: uppercase !important;
      letter-spacing: 0.04em !important;
  }

  [data-testid="metric-container"] [data-testid="metric-value"] {
      color: #0f172a !important;
      font-size: clamp(1.2rem, 3vw, 1.55rem) !important;
      font-weight: 800 !important;
  }

  /* ── Expanders ── */
  .streamlit-expanderHeader {
      background: #f8fafc !important;
      border: 1px solid #e2e8f0 !important;
      border-radius: 10px !important;
      color: #0f172a !important;
      font-weight: 600 !important;
      font-size: 0.92rem !important;
      padding: 12px 16px !important;
      min-height: 46px !important;
      transition: all 0.2s ease !important;
  }

  .streamlit-expanderHeader:hover {
      background: #f1f5f9 !important;
      border-color: #cbd5e1 !important;
  }

  .streamlit-expanderContent {
      background: #ffffff !important;
      border-radius: 0 0 10px 10px !important;
      border: 1px solid #e2e8f0 !important;
      border-top: none !important;
      padding: 16px !important;
  }

  /* ── Status Widget ── */
  [data-testid="stStatus"] {
      background: #f8fafc !important;
      border: 1px solid #cbd5e1 !important;
      border-radius: 12px !important;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04) !important;
  }
  [data-testid="stStatus"] * { color: #0f172a !important; }

  /* ── Tables & DataFrames ── */
  .stDataFrame {
      border-radius: 12px !important;
      overflow: hidden !important;
      border: 1px solid #e2e8f0 !important;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
  }

  .stDataFrame th {
      background: #f5f3ff !important;
      color: #5b21b6 !important;
      font-weight: 700 !important;
      font-size: 0.85rem !important;
      letter-spacing: 0.02em !important;
      border-bottom: 2px solid #ddd6fe !important;
  }

  .stDataFrame td {
      color: #1e293b !important;
      border-color: #f1f5f9 !important;
  }

  /* ── Sub-Tabs (e.g. Horizon Tabs) ── */
  .stTabs [data-baseweb="tab-list"] {
      gap: 4px;
      background: #f1f5f9;
      border-radius: 10px;
      padding: 4px;
      border: 1px solid #e2e8f0;
  }

  .stTabs [data-baseweb="tab"] {
      font-size: 0.82rem;
      font-weight: 600;
      padding: 8px 14px;
      border-radius: 8px;
      color: #64748b;
      background: transparent;
      border: none;
      transition: all 0.2s ease;
  }

  .stTabs [data-baseweb="tab"]:hover {
      color: #0f172a;
      background: rgba(255, 255, 255, 0.6);
  }

  .stTabs [aria-selected="true"] {
      background: #ffffff !important;
      color: #7c3aed !important;
      font-weight: 700 !important;
      box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
  }

  /* ── Alerts & Notifications ── */
  .stAlert {
      border-radius: 10px !important;
      padding: 12px 16px !important;
      font-weight: 500 !important;
  }
  .stSuccess { background: #f0fdf4 !important; border: 1px solid #bbf7d0 !important; color: #15803d !important; }
  .stInfo    { background: #eff6ff !important; border: 1px solid #bfdbfe !important; color: #1d4ed8 !important; }
  .stWarning { background: #fffbeb !important; border: 1px solid #fde68a !important; color: #b45309 !important; }
  .stError   { background: #fef2f2 !important; border: 1px solid #fecaca !important; color: #b91c1c !important; }

  /* ── Download Action Button ── */
  .stDownloadButton > button {
      background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
      border: none !important;
      color: #ffffff !important;
      font-weight: 700;
      border-radius: 10px;
      box-shadow: 0 4px 14px rgba(5, 150, 105, 0.3) !important;
  }

  .stDownloadButton > button:hover {
      background: linear-gradient(135deg, #047857 0%, #065f46 100%) !important;
      box-shadow: 0 6px 18px rgba(5, 150, 105, 0.45) !important;
      transform: translateY(-1px);
  }

  /* ── General Text Colors ── */
  p, li, span, div {
      color: #334155;
  }
  h1, h2, h3, h4, h5 {
      color: #0f172a;
      font-weight: 700;
  }
  .stCaption, caption {
      color: #64748b !important;
      font-size: 0.8rem;
  }

  /* ── Horizontal rule ── */
  hr { border-color: #e2e8f0 !important; margin: 1.25rem 0; }

  /* ── Mobile Responsive Adjustments ── */
  @media (max-width: 768px) {
      .block-container {
          padding-left: 0.75rem !important;
          padding-right: 0.75rem !important;
      }
      .enterprise-hero-header {
          padding: 1rem;
      }
  }
</style>
""", unsafe_allow_html=True)

# Inject portal-level light theme for BaseWeb popover menus
st.components.v1.html("""
<script>
(function injectLightPortalStyles() {
  const id = 'light-portal-styles';
  if (document.getElementById(id)) return;
  const style = document.createElement('style');
  style.id = id;
  style.textContent = `
    [data-baseweb="popover"] { background: #ffffff !important; border-radius: 10px !important; border: 1px solid #e2e8f0 !important; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1) !important; overflow: hidden !important; }
    [data-baseweb="menu"], ul[data-baseweb="menu"] { background: #ffffff !important; border-radius: 10px !important; padding: 4px !important; }
    [role="option"] { background: transparent !important; color: #334155 !important; border-radius: 6px !important; margin: 1px 4px !important; padding: 9px 12px !important; font-family: 'Figtree', sans-serif !important; }
    [role="option"]:hover { background: #f5f3ff !important; color: #7c3aed !important; }
    [role="option"][aria-selected="true"] { background: #ede9fe !important; color: #6d28d9 !important; font-weight: 700 !important; }
    [data-baseweb="select"] input { color: #0f172a !important; }
    [data-baseweb="tooltip"] { background: #1e1b4b !important; color: #ffffff !important; border-radius: 8px !important; font-family: 'Figtree', sans-serif !important; }
  `;
  try { window.parent.document.head.appendChild(style.cloneNode(true)); } catch(e) {}
  document.head.appendChild(style);
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
            body {{ font-family: Helvetica, sans-serif; font-size: 10pt; line-height: 1.5; color: #1e293b; }}
            h1 {{ color: #6d28d9; border-bottom: 2px solid #7c3aed; padding-bottom: 8px; margin-top: 25px; font-size: 18pt; }}
            h2 {{ color: #7c3aed; margin-top: 20px; border-bottom: 1px solid #e2e8f0; font-size: 14pt; }}
            h3 {{ color: #475569; margin-top: 16px; font-weight: bold; font-size: 11pt; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 9pt; }}
            th, td {{ border: 1px solid #cbd5e1; padding: 8px; text-align: left; }}
            th {{ background-color: #f5f3ff; color: #5b21b6; font-weight: bold; }}
            pre {{ background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 10px; border-radius: 4px; font-size: 8pt; }}
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
    # ── Left Navigation Bar (Sidebar) ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-header">
                <div class="brand-icon-box">💸</div>
                <div>
                    <div class="brand-text-title">QuanTum</div>
                    <div class="brand-text-sub">Financial Intelligence</div>
                </div>
            </div>
            <div>
                <span class="brand-tag">ENTERPRISE v3.5</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        nav_options = [
            "🏭 Sector Analysis",
            "🏢 Stock Analysis",
            "🏆 Top Picks",
            "🤖 QuanTum Picks",
            "🌍 Global Markets",
            "📰 Market News",
            "📚 Report Library"
        ]

        selected_section = st.radio(
            "WORKSPACE NAVIGATION",
            nav_options,
            index=0,
            key="enterprise_nav"
        )

        st.markdown("""
        <div class="sidebar-status-card">
            <div class="status-header-text">SYSTEM STATUS</div>
            <div class="status-row">
                <div class="status-left">
                    <span class="live-pulse-dot"></span>
                    <span>7-Agent Council</span>
                </div>
                <span class="status-val-pill">READY</span>
            </div>
            <div class="status-row">
                <div class="status-left">
                    <span class="live-pulse-dot"></span>
                    <span>Gemini 3.7 Intelligence</span>
                </div>
                <span class="status-val-pill">ONLINE</span>
            </div>
            <div class="status-row">
                <div class="status-left">
                    <span class="live-pulse-dot"></span>
                    <span>Turso Cloud Sync</span>
                </div>
                <span class="status-val-pill">CONNECTED</span>
            </div>
            <hr style="margin:8px 0;border-color:#f1f5f9;">
            <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#94a3b8;font-weight:600;">
                <span>Coverage: NSE & Global</span>
                <span>Pro Suite</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section Hero Banner ───────────────────────────────────────────────────
    section_meta = {
        "🏭 Sector Analysis": ("Sector Intelligence", "Multi-Agent Deep Dive: Trends, Stocks & Institutional Positioning"),
        "🏢 Stock Analysis": ("Investment Memo Council", "Deep dive 7-Agent research memo on Indian equities"),
        "🏆 Top Picks": ("Screen & Rank", "Automated screening for best risk-reward opportunities"),
        "🤖 QuanTum Picks": ("QuanTum Quant Engine", "Multi-factor quant algorithm: Technical + Fundamental + Sentiment"),
        "🌍 Global Markets": ("Global Macro Research", "Emerging and developed markets macroeconomic intelligence"),
        "📰 Market News": ("High-Impact News Pulse", "Real-time news stream with automated sentiment scoring"),
        "📚 Report Library": ("Report Archive & Library", "Historical archive of generated memos, PDFs, and sector deep dives"),
    }

    current_title, current_desc = section_meta.get(selected_section, ("Financial Intelligence", "Enterprise Market Analytics"))

    st.markdown(f"""
    <div class="enterprise-hero-header">
        <div>
            <h1 class="main-title-text">{selected_section}</h1>
            <div class="main-subtitle-text">{current_desc}</div>
        </div>
        <div class="badge-chip-group">
            <div class="badge-chip"><span class="live-pulse-dot"></span><span>Real-Time Engine</span></div>
            <div class="badge-chip"><span>⚡ Multi-Factor AI</span></div>
            <div class="badge-chip"><span>🛡️ Enterprise Security</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 1: Sector Analysis ────────────────────────────────────────────
    if selected_section == "🏭 Sector Analysis":
        st.markdown("### Comprehensive Industry Analysis")
        st.caption("Select an industry sector to initiate a 7-agent deep dive pipeline.")
        
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            selected_sector = st.selectbox("Choose Industry", SECTORS, key="sector_select")
        with col_s2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_sector_btn = st.button("Generate Sector Report", type="primary")
        
        if run_sector_btn:
            from sector_orchestrator import SectorOrchestrator
            
            report_container = st.empty()
            
            with st.status("🏭 Sector Analysis Pipeline Running...", expanded=True) as status:
                def update_progress(msg):
                    st.write(msg)
                
                sector_council = SectorOrchestrator()
                final_report = sector_council.run_sector_analysis(selected_sector, progress_callback=update_progress)
                status.update(label="✅ Comprehensive Sector Report Ready!", state="complete", expanded=False)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"reports/Sector_{selected_sector.replace(' ', '_')}_{timestamp}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
            
            st.success(f"📄 Report Generated: `{filename}`")
            
            # Generate PDF
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
            
            with st.expander("📖 Preview Report (Click to Expand)", expanded=True):
                st.markdown(final_report)

    # ── Section 2: Stock Analysis ─────────────────────────────────────────────
    elif selected_section == "🏢 Stock Analysis":
        st.markdown("### Deep Dive Investment Memo")
        st.caption("Generate a rigorous institutional investment memo using the full 7-Agent Council.")

        col_st1, col_st2 = st.columns([3, 1])
        with col_st1:
            ticker_input = st.text_input("Enter Ticker Symbol (e.g., TATAMOTORS, RELIANCE, INFY)", placeholder="Type symbol...")
        with col_st2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_stock_btn = st.button("Run Council Analysis", type="primary")
        
        if run_stock_btn and ticker_input:
            orchestrator = AgentOrchestrator()
            report_container = st.empty()
            
            with st.status("🚀 Convening the 7-Agent Council...", expanded=True) as status:
                def update_progress(msg):
                    st.write(msg)
                
                final_report = orchestrator.run_analysis_pipeline(ticker_input, progress_callback=update_progress)
                status.update(label="✅ Final Investment Memo Ready!", state="complete", expanded=False)
            
            report_container.markdown(final_report)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/DeepDive_{ticker_input}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
                
            pdf = convert_to_pdf(final_report)
            if pdf:
                st.download_button(
                    "📥 Download Investment Memo (PDF)",
                    pdf,
                    f"{ticker_input}_Memo.pdf",
                    "application/pdf",
                    type="primary"
                )

    # ── Section 3: Top Picks ──────────────────────────────────────────────────
    elif selected_section == "🏆 Top Picks":
        st.markdown("### Screen & Deep Dive Best Opportunities")
        st.caption("Screen industry leaders and run autonomous deep dives on top candidates.")

        col_tp1, col_tp2 = st.columns([3, 1])
        with col_tp1:
            screen_sector = st.selectbox("Choose Industry to Screen", SECTORS, key="screen_selector")
        with col_tp2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_tp_btn = st.button("Find Top Picks", type="primary")
        
        if run_tp_btn:
            with st.status("🔍 Screening Sector...", expanded=True) as status:
                skills = analyst.load_skills()
                model = analyst.setup_gemini()
                screen_prompt = analyst.get_screening_prompt(screen_sector, skills)
                screen_resp = model.generate_content(screen_prompt)
                
                ext_prompt = f"Extract exactly 3 ticker symbols from this text as a comma-separated list. Text: {screen_resp.text}"
                tickers = [t.strip() for t in model.generate_content(ext_prompt).text.split(',')][:3]
                
                st.write(f"🎯 Top Picks Identified: {tickers}")
                
                full_report = f"# Top Picks Report: {screen_sector}\n\n"
                orchestrator = AgentOrchestrator()
                
                for ticker in tickers:
                    st.write(f"🔬 Analyzing {ticker}...")
                    memo = orchestrator.run_analysis_pipeline(ticker, progress_callback=lambda x: None)
                    full_report += f"\n## Analysis: {ticker}\n\n{memo}\n\n---\n\n"
                
                status.update(label="✅ Top Picks Report Generated!", state="complete", expanded=False)
            
            st.markdown(full_report)
            pdf = convert_to_pdf(full_report)
            if pdf:
                st.download_button("📥 Download Top Picks Report (PDF)", pdf, f"{screen_sector}_TopPicks.pdf", "application/pdf", type="primary")

    # ── Section 4: QuanTum Picks ──────────────────────────────────────────────
    elif selected_section == "🤖 QuanTum Picks":
        st.markdown("### QuanTum Multi-Factor Engine")
        st.caption("Technical Analysis + Fundamentals + News Sentiment → Ranked Algorithmic Recommendations")

        with st.expander("⚙️ How the QuanTum Algorithm Works", expanded=False):
            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Technical Score", "35% / Wk", "25% / Yr")
                st.caption("RSI, MACD, SMA50/200 crossovers")
            with col_b:
                st.metric("News Sentiment", "35% / Wk", "20% / Yr")
                st.caption("ET, Moneycontrol, Mint RSS → Gemini AI")
            with col_c:
                st.metric("Fundamental Score", "15% / Wk", "50% / 5Y")
                st.caption("P/E, ROE, Debt/Equity via yfinance")
            with col_d:
                st.metric("Momentum Score", "15% / Wk", "25% / Yr")
                st.caption("Price vs SMA50 & SMA200 trend")

        st.markdown("---")

        col_q1, col_q2 = st.columns([2, 2])
        with col_q1:
            mode = st.radio(
                "Execution Mode",
                ["Fast", "Full"],
                horizontal=True,
                help="Fast: news-discovered stocks plus a trimmed Nifty universe. Full: the entire 80+ stock universe.",
            )
        with col_q2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            run_btn = st.button("🚀 Run QuanTum Engine", type="primary", use_container_width=True)

        cached = load_report("quantum") if not run_btn else None
        if cached:
            st.success(f"Last saved run: {cached['created']} ({cached.get('mode') or 'full'})")
            with st.expander("📖 Last saved report", expanded=False):
                st.markdown(cached["markdown"])
        elif not run_btn:
            st.info("No saved report yet. Click 'Run QuanTum Engine' to generate one.")

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
                st.markdown("### 📊 Ranked Horizon Picks")
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

                with st.expander("📰 News Headlines Used in Sentiment Analysis"):
                    for h in result.get("headlines", [])[:20]:
                        st.markdown(f"- **[{h['source']}]** {h['title']}")

                st.markdown("---")
                st.markdown("### 📝 Full QuanTum Recommendation Report")

                with st.expander("📖 View Full Report", expanded=True):
                    st.markdown(result["report"])

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

    # ── Section 5: Global Markets ─────────────────────────────────────────────
    elif selected_section == "🌍 Global Markets":
        st.markdown("### Global Macroeconomic Research")
        st.caption("Multi-Agent Intelligence across Emerging and Developed financial centers.")

        market_type = st.radio(
            "Select Market Type",
            ["🌏 Emerging Markets", "🇺🇸 Developed Markets"],
            horizontal=True
        )

        if market_type == "🌏 Emerging Markets":
            st.markdown("**Target Geographies**: Brazil, China, India, Indonesia, Turkey")
            
            if st.button("Generate Emerging Markets Report", type="primary"):
                from global_markets_orchestrator import EmergingMarketsOrchestrator
                
                with st.status("🌏 Emerging Markets Analysis Running...", expanded=True) as status:
                    def update_progress(msg):
                        st.write(msg)
                    
                    orchestrator = EmergingMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    status.update(label="✅ Emerging Markets Report Ready!", state="complete", expanded=False)
                
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_EmergingMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"📄 Report Generated: `{filename}`")
                
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "📥 Download Emerging Markets Report (PDF)",
                        pdf,
                        "Emerging_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                with st.expander("📖 Preview Report", expanded=True):
                    st.markdown(final_report)

        else:
            st.markdown("**Target Geographies**: United States, Europe, Japan, UK")
            
            if st.button("Generate Developed Markets Report", type="primary"):
                from global_markets_orchestrator import DevelopedMarketsOrchestrator
                
                with st.status("🇺🇸 Developed Markets Analysis Running...", expanded=True) as status:
                    def update_progress(msg):
                        st.write(msg)
                    
                    orchestrator = DevelopedMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    status.update(label="✅ Developed Markets Report Ready!", state="complete", expanded=False)
                
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_DevelopedMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"📄 Report Generated: `{filename}`")
                
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "📥 Download Developed Markets Report (PDF)",
                        pdf,
                        "Developed_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                with st.expander("📖 Preview Report", expanded=True):
                    st.markdown(final_report)

    # ── Section 6: Market News ────────────────────────────────────────────────
    elif selected_section == "📰 Market News":
        st.markdown("### Real-Time Market News & Sentiment")
        st.caption("Automated ingestion from top financial feeds with AI sentiment classification.")

        col1, col2 = st.columns([2, 1])
        with col1:
            news_scope = st.selectbox(
                "News Scope",
                ["Global (India + World)", "India Only"],
                key="news_scope"
            )
        with col2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("Fetch Latest News", type="primary"):
                st.session_state['refresh_news'] = True

        if st.session_state.get('refresh_news', False):
            from news_tracker_orchestrator import NewsTrackerOrchestrator
            scope = "global" if "Global" in news_scope else "india"

            with st.status("📰 Fetching & Analyzing News Feeds...", expanded=True) as status:
                def update_progress(msg):
                    st.write(msg)

                orchestrator = NewsTrackerOrchestrator()
                organized_news = orchestrator.run_analysis(scope=scope, progress_callback=update_progress)
                status.update(label="✅ News Analysis Complete!", state="complete", expanded=False)

            st.markdown("---")
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
                            st.markdown(f"[Read Full Article]({item['href']})")
            else:
                st.info("No high-impact news found at this time.")

            st.markdown("---")
            st.markdown("### 🟡 Medium-Impact News")
            medium_news = organized_news.get('medium_impact', [])
            if medium_news:
                for item in medium_news[:6]:
                    sentiment = item.get('sentiment', 'NEUTRAL')
                    st.markdown(f"**{item.get('title', 'No Title')}** ({sentiment})")
                    st.caption(item.get('summary', item.get('body', ''))[:200] + "...")
            else:
                st.info("No medium-impact news found.")

            st.session_state['refresh_news'] = False

    # ── Section 7: Report Library ─────────────────────────────────────────────
    elif selected_section == "📚 Report Library":
        st.markdown("### Institutional Report Archive")
        st.caption("Search, preview, and download previously generated research memos and quant reports.")

        reports_dir = 'reports'
        if not os.path.exists(reports_dir):
            st.info("No reports found yet. Generate your first report to populate the archive!")
        else:
            all_files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
            
            if not all_files:
                st.info("No reports found yet. Generate your first report to populate the archive!")
            else:
                col1, col2 = st.columns([1, 2])
                with col1:
                    report_type = st.selectbox(
                        "Filter by Type",
                        ["All", "Sector Reports", "Stock Analysis", "Top Picks", "Other"],
                        key="report_type_filter"
                    )
                with col2:
                    search_term = st.text_input("Search reports", placeholder="Enter ticker or keyword...", key="search_reports")

                filtered_files = []
                for f in all_files:
                    if report_type == "Sector Reports" and not f.startswith("Sector_"):
                        continue
                    elif report_type == "Stock Analysis" and not f.startswith("DeepDive_"):
                        continue
                    elif report_type == "Top Picks" and not f.startswith("Full_Report_"):
                        continue
                    elif report_type == "Other" and (f.startswith("Sector_") or f.startswith("DeepDive_") or f.startswith("Full_Report_")):
                        continue

                    if search_term and search_term.lower() not in f.lower():
                        continue

                    filtered_files.append(f)

                filtered_files.sort(
                    key=lambda x: os.path.getmtime(os.path.join(reports_dir, x)),
                    reverse=True
                )

                st.markdown(f"**Found {len(filtered_files)} Report(s)**")

                for filename in filtered_files:
                    file_path = os.path.join(reports_dir, filename)
                    file_stats = os.stat(file_path)
                    file_size_kb = file_stats.st_size / 1024
                    mod_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M')

                    if filename.startswith("Sector_"):
                        icon, type_label = "🏭", "Sector"
                    elif filename.startswith("DeepDive_"):
                        icon, type_label = "🏢", "Stock Memo"
                    elif filename.startswith("Full_Report_"):
                        icon, type_label = "🏆", "Top Picks"
                    else:
                        icon, type_label = "📄", "Report"

                    with st.expander(f"{icon} **{filename}** ({type_label} • {file_size_kb:.1f} KB • {mod_time})", expanded=False):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

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

                        st.markdown("**Preview:**")
                        preview_text = content[:500] + "..." if len(content) > 500 else content
                        st.markdown(preview_text)

                        with st.expander("📖 View Full Report"):
                            st.markdown(content)


if __name__ == "__main__":
    main()
