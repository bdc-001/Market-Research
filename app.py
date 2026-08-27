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

# ── ElevenLabs-Grade Editorial Design System ──────────────────────────────────
st.markdown("""
<style>
  /* ── Google Fonts: Inter & JetBrains Mono ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

  /* ── ElevenLabs Design Tokens ── */
  :root {
      --canvas: #FAFAFA;
      --surface: #FFFFFF;
      --surface-subtle: #F4F4F5;
      --surface-muted: #ECECEE;
      
      --border: #E4E4E7;
      --border-subtle: #F4F4F5;
      --border-strong: #D4D4D8;
      
      --text-main: #18181B;
      --text-secondary: #52525B;
      --text-muted: #71717A;
      --text-dim: #A1A1AA;
      
      --primary: #18181B;
      --primary-hover: #27272A;
      --primary-active: #09090B;
      
      --brand-purple: #7C3AED;
      --brand-purple-light: #F5F3FF;
      --brand-purple-border: #DDD6FE;
      
      --positive: #16A34A;
      --positive-bg: #F0FDF4;
      --positive-border: #BBF7D0;
      
      --negative: #DC2626;
      --negative-bg: #FEF2F2;
      --negative-border: #FECACA;
      
      --warning: #D97706;
      --warning-bg: #FFFBEB;
      --warning-border: #FDE68A;
      
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 12px;
  }

  /* ── Global Typography & Reset ── */
  html, body, [class*="css"], [class*="st-"], [data-testid="stSidebar"], .stMarkdown, .stButton, input, select, textarea, p, h1, h2, h3, h4, h5, h6, span, div, label, li {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
      letter-spacing: -0.01em;
  }

  code, pre, .stCodeBlock, .stCodeBlock code {
      font-family: 'JetBrains Mono', monospace !important;
  }

  /* ── App Canvas ── */
  .stApp {
      background-color: var(--canvas);
      color: var(--text-main);
      min-height: 100vh;
  }

  /* ── Main Container Spacing ── */
  .block-container {
      padding-top: 1.5rem !important;
      padding-bottom: 3rem !important;
      padding-left: clamp(1.5rem, 4vw, 3.5rem) !important;
      padding-right: clamp(1.5rem, 4vw, 3.5rem) !important;
      max-width: 1360px !important;
  }

  header[data-testid="stHeader"] {
      background: transparent !important;
      height: 2.5rem !important;
  }

  /* ── Pulse Animation ── */
  @keyframes livePulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.4); transform: scale(1); }
      50% { box-shadow: 0 0 0 4px rgba(22, 163, 74, 0); transform: scale(1.05); }
  }

  /* ── Left Sidebar (ElevenLabs Style) ── */
  [data-testid="stSidebar"] {
      background-color: var(--surface) !important;
      border-right: 1px solid var(--border) !important;
      padding: 1.25rem 0.75rem !important;
  }

  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
      color: var(--text-main) !important;
  }

  /* Brand Container */
  .sidebar-brand-container {
      padding: 0.25rem 0.5rem 1rem 0.5rem;
      border-bottom: 1px solid var(--border);
      margin-bottom: 1rem;
  }

  .sidebar-brand-header {
      display: flex;
      align-items: center;
      gap: 10px;
  }

  .brand-icon-box {
      width: 32px;
      height: 32px;
      border-radius: var(--radius-sm);
      background: var(--text-main);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      color: #FFFFFF;
      font-weight: 700;
  }

  .brand-text-title {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text-main);
      letter-spacing: -0.02em;
      line-height: 1.2;
  }

  .brand-text-sub {
      font-size: 0.6875rem;
      font-weight: 500;
      color: var(--text-muted);
  }

  .brand-tag {
      display: inline-block;
      margin-top: 8px;
      font-size: 0.625rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--surface-subtle);
      color: var(--text-secondary);
      border: 1px solid var(--border);
  }

  /* ── Sidebar Navigation (Zero Radio Circles) ── */
  [data-testid="stSidebar"] .stRadio > label {
      font-size: 0.6875rem !important;
      font-weight: 600 !important;
      color: var(--text-dim) !important;
      text-transform: uppercase !important;
      letter-spacing: 0.06em !important;
      padding-left: 8px !important;
      margin-bottom: 6px !important;
  }

  [data-testid="stSidebar"] .stRadio > div {
      gap: 2px !important;
  }

  /* Hide raw radio circles completely */
  [data-testid="stSidebar"] .stRadio [role="radiogroup"] label > div:first-child,
  [data-testid="stSidebar"] .stRadio [data-baseweb="radio"] > div:first-child,
  [data-testid="stSidebar"] .stRadio input[type="radio"] + div {
      display: none !important;
  }

  /* Sidebar Navigation Item */
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {
      background: transparent !important;
      border: 1px solid transparent !important;
      border-radius: var(--radius-sm) !important;
      padding: 7px 10px !important;
      margin: 1px 0 !important;
      transition: all 0.12s ease !important;
      cursor: pointer !important;
      width: 100% !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {
      background: var(--surface-subtle) !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
      color: var(--text-secondary) !important;
      font-weight: 500 !important;
      font-size: 0.84rem !important;
      margin: 0 !important;
  }

  /* Active Sidebar Item */
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input[type="radio"]:checked) {
      background: var(--surface-subtle) !important;
      border-left: 2px solid var(--text-main) !important;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0 !important;
  }

  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] input[type="radio"]:checked + div + div p,
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input[type="radio"]:checked) div[data-testid="stMarkdownContainer"] p {
      color: var(--text-main) !important;
      font-weight: 600 !important;
  }

  /* ── Sidebar System Status Footer ── */
  .sidebar-status-card {
      background: transparent;
      border-top: 1px solid var(--border);
      padding: 12px 4px 0 4px;
      margin-top: 1.25rem;
  }

  .status-header-text {
      font-size: 0.6875rem;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
  }

  .status-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 0;
      font-size: 0.75rem;
  }

  .status-left {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-secondary);
      font-weight: 500;
  }

  .status-val-pill {
      font-size: 0.6875rem;
      font-weight: 500;
      padding: 1px 6px;
      border-radius: 4px;
      background: var(--surface-subtle);
      color: var(--text-secondary);
      border: 1px solid var(--border);
  }

  .live-pulse-dot {
      width: 6px;
      height: 6px;
      background-color: var(--positive);
      border-radius: 50%;
      display: inline-block;
      animation: livePulse 2s infinite cubic-bezier(0.45, 0, 0.55, 1);
  }

  /* ── ElevenLabs Page Header ── */
  .eleven-header {
      padding: 0.5rem 0 1.25rem 0;
      margin-bottom: 1.75rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 16px;
  }

  .eleven-breadcrumb {
      font-size: 0.6875rem;
      font-weight: 600;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 4px;
  }

  .eleven-title {
      font-size: clamp(1.25rem, 2.5vw, 1.5rem);
      font-weight: 600;
      color: var(--text-main);
      letter-spacing: -0.025em;
      line-height: 1.2;
      margin: 0;
  }

  .eleven-subtitle {
      font-size: 0.84rem;
      color: var(--text-secondary);
      margin-top: 4px;
      font-weight: 400;
  }

  .eleven-chips {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
  }

  .eleven-chip {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 3px 9px;
      border-radius: 9999px;
      font-size: 0.6875rem;
      font-weight: 500;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text-secondary);
  }

  /* ── Form Controls & Action Row Alignment ── */
  [data-testid="column"] {
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
  }

  /* Input Fields & Textareas */
  .stTextInput > div > div > input,
  .stSelectbox > div > div,
  .stTextArea > div > div > textarea {
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--radius-sm) !important;
      color: var(--text-main) !important;
      font-size: 0.84rem !important;
      font-weight: 400 !important;
      padding: 8px 12px !important;
      min-height: 38px !important;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
      transition: all 0.12s ease !important;
  }

  .stTextInput > div > div > input:focus,
  .stSelectbox > div > div:focus-within,
  .stTextArea > div > div > textarea:focus {
      border-color: var(--text-main) !important;
      box-shadow: 0 0 0 1px var(--text-main) !important;
  }

  .stSelectbox [data-baseweb="select"] > div {
      background: var(--surface) !important;
      border-color: var(--border) !important;
      border-radius: var(--radius-sm) !important;
      min-height: 38px !important;
  }

  .stSelectbox [data-baseweb="select"] * { color: var(--text-main) !important; font-weight: 400; font-size: 0.84rem; }
  .stSelectbox svg { fill: var(--text-muted) !important; }

  /* Input Labels */
  .stTextInput label, .stSelectbox label, .stTextArea label {
      font-size: 0.78rem !important;
      font-weight: 500 !important;
      color: var(--text-secondary) !important;
      margin-bottom: 4px !important;
  }

  /* ── Buttons (ElevenLabs Style: Ink Primary & Crisp Secondary) ── */
  .stButton > button {
      width: 100%;
      min-height: 38px !important;
      padding: 0 14px !important;
      font-size: 0.84rem !important;
      font-weight: 500 !important;
      border-radius: var(--radius-sm) !important;
      border: 1px solid var(--border) !important;
      background: var(--surface) !important;
      color: var(--text-main) !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
      transition: all 0.12s ease !important;
  }

  .stButton > button:hover {
      background: var(--surface-subtle) !important;
      border-color: var(--border-strong) !important;
      color: var(--text-main) !important;
  }

  .stButton > button[kind="primary"] {
      background: var(--primary) !important;
      color: #FFFFFF !important;
      border: 1px solid var(--primary) !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
  }

  .stButton > button[kind="primary"]:hover {
      background: var(--primary-hover) !important;
      border-color: var(--primary-hover) !important;
      box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12) !important;
  }

  .stButton > button[kind="primary"]:active {
      background: var(--primary-active) !important;
  }

  /* ── Metric Cards ── */
  [data-testid="metric-container"] {
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--radius-md) !important;
      padding: 14px 16px !important;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.02) !important;
      transition: border-color 0.12s ease !important;
  }

  [data-testid="metric-container"]:hover {
      border-color: var(--border-strong) !important;
  }

  [data-testid="metric-container"] label {
      color: var(--text-muted) !important;
      font-size: 0.6875rem !important;
      font-weight: 500 !important;
      text-transform: uppercase !important;
      letter-spacing: 0.04em !important;
  }

  [data-testid="metric-container"] [data-testid="metric-value"] {
      color: var(--text-main) !important;
      font-size: clamp(1.15rem, 2.5vw, 1.4rem) !important;
      font-weight: 600 !important;
      font-variant-numeric: tabular-nums;
  }

  /* ── Expanders ── */
  .streamlit-expanderHeader {
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--radius-sm) !important;
      color: var(--text-main) !important;
      font-weight: 500 !important;
      font-size: 0.84rem !important;
      padding: 10px 14px !important;
      min-height: 38px !important;
      transition: all 0.12s ease !important;
  }

  .streamlit-expanderHeader:hover {
      background: var(--surface-subtle) !important;
      border-color: var(--border-strong) !important;
  }

  .streamlit-expanderContent {
      background: var(--surface) !important;
      border-radius: 0 0 var(--radius-sm) var(--radius-sm) !important;
      border: 1px solid var(--border) !important;
      border-top: none !important;
      padding: 14px 16px !important;
  }

  /* ── Status Widget ── */
  [data-testid="stStatus"] {
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--radius-md) !important;
      box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.03) !important;
  }
  [data-testid="stStatus"] * { color: var(--text-main) !important; }

  /* ── Tables & DataFrames ── */
  .stDataFrame {
      border-radius: var(--radius-md) !important;
      overflow: hidden !important;
      border: 1px solid var(--border) !important;
      background: var(--surface) !important;
  }

  .stDataFrame th {
      background: var(--surface-subtle) !important;
      color: var(--text-secondary) !important;
      font-weight: 500 !important;
      font-size: 0.78rem !important;
      letter-spacing: 0.02em !important;
      border-bottom: 1px solid var(--border) !important;
  }

  .stDataFrame td {
      color: var(--text-main) !important;
      border-color: var(--surface-subtle) !important;
      font-size: 0.8125rem !important;
  }

  /* ── Segmented Tabs (ElevenLabs Style) ── */
  .stTabs [data-baseweb="tab-list"] {
      gap: 2px;
      background: var(--surface-subtle);
      border-radius: var(--radius-md);
      padding: 3px;
      border: 1px solid var(--border);
  }

  .stTabs [data-baseweb="tab"] {
      font-size: 0.8125rem;
      font-weight: 500;
      padding: 5px 12px;
      border-radius: var(--radius-sm);
      color: var(--text-secondary);
      background: transparent;
      border: none;
      transition: all 0.12s ease;
  }

  .stTabs [data-baseweb="tab"]:hover {
      color: var(--text-main);
  }

  .stTabs [aria-selected="true"] {
      background: var(--surface) !important;
      color: var(--text-main) !important;
      font-weight: 600 !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06) !important;
  }

  /* ── Alerts & Notifications ── */
  .stAlert {
      border-radius: var(--radius-sm) !important;
      padding: 10px 14px !important;
      font-weight: 400 !important;
      font-size: 0.84rem !important;
  }
  .stSuccess { background: var(--positive-bg) !important; border: 1px solid var(--positive-border) !important; color: var(--positive) !important; }
  .stInfo    { background: var(--surface-subtle) !important; border: 1px solid var(--border) !important; color: var(--text-main) !important; }
  .stWarning { background: var(--warning-bg) !important; border: 1px solid var(--warning-border) !important; color: var(--warning) !important; }
  .stError   { background: var(--negative-bg) !important; border: 1px solid var(--negative-border) !important; color: var(--negative) !important; }

  /* ── Download Button ── */
  .stDownloadButton > button {
      background: var(--surface) !important;
      border: 1px solid var(--border) !important;
      color: var(--text-main) !important;
      font-weight: 500 !important;
      border-radius: var(--radius-sm) !important;
      font-size: 0.84rem !important;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
  }

  .stDownloadButton > button:hover {
      background: var(--surface-subtle) !important;
      border-color: var(--border-strong) !important;
  }

  /* ── General Text Colors ── */
  p, li, span, div {
      color: var(--text-secondary);
  }
  h1, h2, h3, h4, h5 {
      color: var(--text-main);
      font-weight: 600;
      letter-spacing: -0.02em;
  }
  .stCaption, caption {
      color: var(--text-muted) !important;
      font-size: 0.78rem;
  }

  hr { border-color: var(--border) !important; margin: 1.25rem 0; }

  /* ── Mobile Responsiveness ── */
  @media (max-width: 768px) {
      .block-container {
          padding-left: 1rem !important;
          padding-right: 1rem !important;
      }
      .eleven-header {
          padding: 0.5rem 0 1rem 0;
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
    [data-baseweb="popover"] { background: #FFFFFF !important; border-radius: 8px !important; border: 1px solid #E4E4E7 !important; box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important; overflow: hidden !important; }
    [data-baseweb="menu"], ul[data-baseweb="menu"] { background: #FFFFFF !important; border-radius: 8px !important; padding: 4px !important; }
    [role="option"] { background: transparent !important; color: #52525B !important; border-radius: 6px !important; margin: 1px 4px !important; padding: 8px 12px !important; font-family: 'Inter', sans-serif !important; font-size: 0.84rem !important; }
    [role="option"]:hover { background: #F4F4F5 !important; color: #18181B !important; }
    [role="option"][aria-selected="true"] { background: #ECECEE !important; color: #18181B !important; font-weight: 600 !important; }
    [data-baseweb="select"] input { color: #18181B !important; }
    [data-baseweb="tooltip"] { background: #18181B !important; color: #FFFFFF !important; border-radius: 6px !important; font-family: 'Inter', sans-serif !important; font-size: 0.75rem !important; }
  `;
  try { window.parent.document.head.appendChild(style.cloneNode(true)); } catch(e) {}
  document.head.appendChild(style);
  new MutationObserver(() => {
    if (!document.getElementById(id)) document.head.appendChild(style.cloneNode(true));
  }).observe(document.body, { childList: true, subtree: true });
})();
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
    # ── Left Navigation Bar (ElevenLabs Style) ────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand-container">
            <div class="sidebar-brand-header">
                <div class="brand-icon-box">Q</div>
                <div>
                    <div class="brand-text-title">QuanTum</div>
                    <div class="brand-text-sub">Financial Intelligence</div>
                </div>
            </div>
            <div>
                <span class="brand-tag">Enterprise v3.5</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        nav_options = [
            "Sector Analysis",
            "Stock Analysis",
            "Top Picks",
            "QuanTum Picks",
            "Global Markets",
            "Market News",
            "Report Library"
        ]

        selected_section = st.radio(
            "WORKSPACE",
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
            <hr style="margin:10px 0;border-color:var(--border);">
            <div style="display:flex;justify-content:space-between;font-size:0.6875rem;color:var(--text-dim);font-weight:500;">
                <span>Coverage: NSE & Global</span>
                <span>Pro Suite</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section Page Header ───────────────────────────────────────────────────
    section_meta = {
        "Sector Analysis": ("Sector Intelligence", "Multi-Agent Deep Dive: Trends, Valuation & Institutional Positioning"),
        "Stock Analysis": ("Investment Memo Council", "Deep-dive 7-Agent research memorandum on Indian equities"),
        "Top Picks": ("Screen & Rank", "Automated screening for best risk-reward opportunities across industries"),
        "QuanTum Picks": ("QuanTum Quant Engine", "Multi-factor algorithmic engine: Technical + Fundamental + Sentiment"),
        "Global Markets": ("Global Macro Research", "Emerging and developed markets macroeconomic intelligence"),
        "Market News": ("Market News Pulse", "Real-time news stream with automated sentiment scoring"),
        "Report Library": ("Report Archive & Library", "Historical archive of generated memos, PDFs, and sector deep dives"),
    }

    current_title, current_desc = section_meta.get(selected_section, ("Financial Intelligence", "Enterprise Market Analytics"))

    st.markdown(f"""
    <div class="eleven-header">
        <div>
            <div class="eleven-breadcrumb">WORKSPACE / {selected_section.upper()}</div>
            <h1 class="eleven-title">{current_title}</h1>
            <div class="eleven-subtitle">{current_desc}</div>
        </div>
        <div class="eleven-chips">
            <div class="eleven-chip"><span class="live-pulse-dot"></span><span>Real-Time Engine</span></div>
            <div class="eleven-chip"><span>Multi-Factor AI</span></div>
            <div class="eleven-chip"><span>Enterprise Security</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 1: Sector Analysis ────────────────────────────────────────────
    if selected_section == "Sector Analysis":
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            selected_sector = st.selectbox("Industry Sector", SECTORS, key="sector_select")
        with col_s2:
            run_sector_btn = st.button("Generate Sector Report", type="primary", use_container_width=True)
        
        if run_sector_btn:
            from sector_orchestrator import SectorOrchestrator
            
            report_container = st.empty()
            
            with st.status("Sector Analysis Pipeline Running...", expanded=True) as status:
                def update_progress(msg):
                    st.markdown(f"<pre style='font-family: \"JetBrains Mono\", monospace; font-size: 0.8rem; background: transparent; border: none; padding: 0;'>{msg}</pre>", unsafe_allow_html=True)
                
                sector_council = SectorOrchestrator()
                final_report = sector_council.run_sector_analysis(selected_sector, progress_callback=update_progress)
                status.update(label="Comprehensive Sector Report Ready!", state="complete", expanded=False)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"reports/Sector_{selected_sector.replace(' ', '_')}_{timestamp}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
            
            st.success(f"Report Generated: `{filename}`")
            
            # Generate PDF
            pdf = convert_to_pdf(final_report)
            if pdf:
                st.download_button(
                    "Download Sector Report (PDF)", 
                    pdf, 
                    f"{selected_sector}_Sector_Report.pdf", 
                    "application/pdf",
                    type="primary"
                )
            else:
                st.error("PDF generation failed.")
            
            with st.expander("Preview Report", expanded=True):
                st.markdown(final_report)

    # ── Section 2: Stock Analysis ─────────────────────────────────────────────
    elif selected_section == "Stock Analysis":
        col_st1, col_st2 = st.columns([3, 1])
        with col_st1:
            ticker_input = st.text_input("Ticker Symbol (NSE)", placeholder="e.g. TATAMOTORS, RELIANCE, INFY")
        with col_st2:
            run_stock_btn = st.button("Run Council Analysis", type="primary", use_container_width=True)
        
        if run_stock_btn and ticker_input:
            orchestrator = AgentOrchestrator()
            report_container = st.empty()
            
            with st.status("Convening the 7-Agent Council...", expanded=True) as status:
                def update_progress(msg):
                    st.markdown(f"<pre style='font-family: \"JetBrains Mono\", monospace; font-size: 0.8rem; background: transparent; border: none; padding: 0;'>{msg}</pre>", unsafe_allow_html=True)
                
                final_report = orchestrator.run_analysis_pipeline(ticker_input, progress_callback=update_progress)
                status.update(label="Final Investment Memo Ready!", state="complete", expanded=False)
            
            report_container.markdown(final_report)
            
            # Save Report
            os.makedirs('reports', exist_ok=True)
            filename = f"reports/DeepDive_{ticker_input}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(final_report)
                
            pdf = convert_to_pdf(final_report)
            if pdf:
                st.download_button(
                    "Download Investment Memo (PDF)",
                    pdf,
                    f"{ticker_input}_Memo.pdf",
                    "application/pdf",
                    type="primary"
                )

    # ── Section 3: Top Picks ──────────────────────────────────────────────────
    elif selected_section == "Top Picks":
        col_tp1, col_tp2 = st.columns([3, 1])
        with col_tp1:
            screen_sector = st.selectbox("Industry to Screen", SECTORS, key="screen_selector")
        with col_tp2:
            run_tp_btn = st.button("Find Top Picks", type="primary", use_container_width=True)
        
        if run_tp_btn:
            with st.status("Screening Sector...", expanded=True) as status:
                skills = analyst.load_skills()
                model = analyst.setup_gemini()
                screen_prompt = analyst.get_screening_prompt(screen_sector, skills)
                screen_resp = model.generate_content(screen_prompt)
                
                ext_prompt = f"Extract exactly 3 ticker symbols from this text as a comma-separated list. Text: {screen_resp.text}"
                tickers = [t.strip() for t in model.generate_content(ext_prompt).text.split(',')][:3]
                
                st.write(f"Top Picks Identified: {tickers}")
                
                full_report = f"# Top Picks Report: {screen_sector}\n\n"
                orchestrator = AgentOrchestrator()
                
                for ticker in tickers:
                    st.write(f"Analyzing {ticker}...")
                    memo = orchestrator.run_analysis_pipeline(ticker, progress_callback=lambda x: None)
                    full_report += f"\n## Analysis: {ticker}\n\n{memo}\n\n---\n\n"
                
                status.update(label="Top Picks Report Generated!", state="complete", expanded=False)
            
            st.markdown(full_report)
            pdf = convert_to_pdf(full_report)
            if pdf:
                st.download_button("Download Top Picks Report (PDF)", pdf, f"{screen_sector}_TopPicks.pdf", "application/pdf", type="primary")

    # ── Section 4: QuanTum Picks ──────────────────────────────────────────────
    elif selected_section == "QuanTum Picks":
        with st.expander("Algorithm Architecture & Scoring Model", expanded=False):
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

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        col_q1, col_q2 = st.columns([3, 1])
        with col_q1:
            mode = st.radio(
                "Execution Mode",
                ["Fast", "Full"],
                horizontal=True,
                help="Fast: news-discovered stocks plus a trimmed Nifty universe. Full: the entire 80+ stock universe.",
            )
        with col_q2:
            run_btn = st.button("Run Quant Engine", type="primary", use_container_width=True)

        cached = load_report("quantum") if not run_btn else None
        if cached:
            st.success(f"Last saved run: {cached['created']} ({cached.get('mode') or 'full'})")
            with st.expander("Last saved report", expanded=False):
                st.markdown(cached["markdown"])
        elif not run_btn:
            st.info("No saved report yet. Click 'Run Quant Engine' to generate one.")

        if run_btn:
            from quantum_orchestrator import QuantumEngineOrchestrator
            progress_log = []

            with st.status("QuanTum Engine Running...", expanded=True) as status:
                log_container = st.empty()

                def qt_progress(msg):
                    progress_log.append(msg)
                    log_container.markdown("\n\n".join([
                        f"`{m}`" for m in progress_log[-6:]
                    ]))

                engine = QuantumEngineOrchestrator()
                result = engine.run(progress_callback=qt_progress, fast=(mode == "Fast"))

                if "error" in result:
                    status.update(label=f"Error: {result['error']}", state="error")
                    st.error(result["error"])
                else:
                    status.update(label="QuanTum Engine Complete!", state="complete", expanded=False)
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
                st.markdown("### Ranked Horizon Picks")
                horizon_tab1, horizon_tab2, horizon_tab3 = st.tabs([
                    "This Week", "This Year", "5 Years"
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

                with st.expander("News Headlines Used in Sentiment Analysis"):
                    for h in result.get("headlines", [])[:20]:
                        st.markdown(f"- **[{h['source']}]** {h['title']}")

                st.markdown("---")
                st.markdown("### Full QuanTum Recommendation Report")

                with st.expander("View Full Report", expanded=True):
                    st.markdown(result["report"])

                pdf = convert_to_pdf(result["report"])
                if pdf:
                    st.download_button(
                        "Download QuanTum Report (PDF)",
                        pdf,
                        f"QuanTum_Picks_{datetime.now().strftime('%Y%m%d')}.pdf",
                        "application/pdf",
                        type="primary",
                    )

                st.success(f"Report saved: `{result['report_path']}`")

    # ── Section 5: Global Markets ─────────────────────────────────────────────
    elif selected_section == "Global Markets":
        col_gm1, col_gm2 = st.columns([3, 1])
        with col_gm1:
            market_type = st.radio(
                "Market Region",
                ["Emerging Markets", "Developed Markets"],
                horizontal=True
            )
        with col_gm2:
            run_gm_btn = st.button("Generate Macro Report", type="primary", use_container_width=True)

        if market_type == "Emerging Markets":
            st.caption("Coverage: Brazil, China, India, Indonesia, Turkey")
            if run_gm_btn:
                from global_markets_orchestrator import EmergingMarketsOrchestrator
                
                with st.status("Emerging Markets Analysis Running...", expanded=True) as status:
                    def update_progress(msg):
                        st.markdown(f"<pre style='font-family: \"JetBrains Mono\", monospace; font-size: 0.8rem; background: transparent; border: none; padding: 0;'>{msg}</pre>", unsafe_allow_html=True)
                    
                    orchestrator = EmergingMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    status.update(label="Emerging Markets Report Ready!", state="complete", expanded=False)
                
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_EmergingMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"Report Generated: `{filename}`")
                
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "Download Emerging Markets Report (PDF)",
                        pdf,
                        "Emerging_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                with st.expander("Preview Report", expanded=True):
                    st.markdown(final_report)

        else:
            st.caption("Coverage: United States, Europe, Japan, United Kingdom")
            if run_gm_btn:
                from global_markets_orchestrator import DevelopedMarketsOrchestrator
                
                with st.status("Developed Markets Analysis Running...", expanded=True) as status:
                    def update_progress(msg):
                        st.markdown(f"<pre style='font-family: \"JetBrains Mono\", monospace; font-size: 0.8rem; background: transparent; border: none; padding: 0;'>{msg}</pre>", unsafe_allow_html=True)
                    
                    orchestrator = DevelopedMarketsOrchestrator()
                    final_report = orchestrator.run_analysis(progress_callback=update_progress)
                    status.update(label="Developed Markets Report Ready!", state="complete", expanded=False)
                
                os.makedirs('reports', exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M')
                filename = f"reports/Global_DevelopedMarkets_{timestamp}.md"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(final_report)
                
                st.success(f"Report Generated: `{filename}`")
                
                pdf = convert_to_pdf(final_report)
                if pdf:
                    st.download_button(
                        "Download Developed Markets Report (PDF)",
                        pdf,
                        "Developed_Markets_Report.pdf",
                        "application/pdf",
                        type="primary"
                    )
                
                with st.expander("Preview Report", expanded=True):
                    st.markdown(final_report)

    # ── Section 6: Market News ────────────────────────────────────────────────
    elif selected_section == "Market News":
        col1, col2 = st.columns([3, 1])
        with col1:
            news_scope = st.selectbox(
                "News Feed Scope",
                ["Global (India + World)", "India Only"],
                key="news_scope"
            )
        with col2:
            fetch_btn = st.button("Fetch Latest News", type="primary", use_container_width=True)
            if fetch_btn:
                st.session_state['refresh_news'] = True

        if st.session_state.get('refresh_news', False):
            from news_tracker_orchestrator import NewsTrackerOrchestrator
            scope = "global" if "Global" in news_scope else "india"

            with st.status("Ingesting & Analyzing News Feeds...", expanded=True) as status:
                def update_progress(msg):
                    st.markdown(f"<pre style='font-family: \"JetBrains Mono\", monospace; font-size: 0.8rem; background: transparent; border: none; padding: 0;'>{msg}</pre>", unsafe_allow_html=True)

                orchestrator = NewsTrackerOrchestrator()
                organized_news = orchestrator.run_analysis(scope=scope, progress_callback=update_progress)
                status.update(label="News Analysis Complete!", state="complete", expanded=False)

            st.markdown("---")
            st.markdown("### High-Impact News (Market-Moving)")
            high_news = organized_news.get('high_impact', [])
            if high_news:
                for idx, item in enumerate(high_news[:10]):
                    sentiment = item.get('sentiment', 'NEUTRAL')
                    badge_style = {
                        'BULLISH': 'color: var(--positive); background: var(--positive-bg); border: 1px solid var(--positive-border);',
                        'BEARISH': 'color: var(--negative); background: var(--negative-bg); border: 1px solid var(--negative-border);',
                        'NEUTRAL': 'color: var(--text-secondary); background: var(--surface-subtle); border: 1px solid var(--border);'
                    }.get(sentiment, 'color: var(--text-secondary);')

                    with st.expander(f"{item.get('title', 'No Title')} • [{sentiment}]", expanded=(idx < 3)):
                        st.markdown(f"**Summary**: {item.get('summary', item.get('body', ''))}")
                        st.caption(f"Sentiment: **{item.get('sentiment', 'N/A')}** | Impact: **{item.get('impact', 'N/A')}**")
                        if 'href' in item:
                            st.markdown(f"[Read Full Article]({item['href']})")
            else:
                st.info("No high-impact news found at this time.")

            st.markdown("---")
            st.markdown("### Medium-Impact News")
            medium_news = organized_news.get('medium_impact', [])
            if medium_news:
                for item in medium_news[:6]:
                    sentiment = item.get('sentiment', 'NEUTRAL')
                    st.markdown(f"**{item.get('title', 'No Title')}** — *{sentiment}*")
                    st.caption(item.get('summary', item.get('body', ''))[:200] + "...")
            else:
                st.info("No medium-impact news found.")

            st.session_state['refresh_news'] = False

    # ── Section 7: Report Library ─────────────────────────────────────────────
    elif selected_section == "Report Library":
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
                    search_term = st.text_input("Search Reports", placeholder="Enter ticker or keyword...", key="search_reports")

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

                st.caption(f"Showing {len(filtered_files)} archive item(s)")

                for filename in filtered_files:
                    file_path = os.path.join(reports_dir, filename)
                    file_stats = os.stat(file_path)
                    file_size_kb = file_stats.st_size / 1024
                    mod_time = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M')

                    if filename.startswith("Sector_"):
                        type_label = "Sector"
                    elif filename.startswith("DeepDive_"):
                        type_label = "Stock Memo"
                    elif filename.startswith("Full_Report_"):
                        type_label = "Top Picks"
                    else:
                        type_label = "Report"

                    with st.expander(f"{filename} • ({type_label} • {file_size_kb:.1f} KB • {mod_time})", expanded=False):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        col_a, col_b, col_c = st.columns([2, 2, 1])
                        with col_a:
                            pdf = convert_to_pdf(content)
                            if pdf:
                                st.download_button(
                                    "Download PDF",
                                    pdf,
                                    filename.replace('.md', '.pdf'),
                                    "application/pdf",
                                    key=f"pdf_{filename}"
                                )
                        with col_b:
                            st.download_button(
                                "Download Markdown",
                                content,
                                filename,
                                "text/markdown",
                                key=f"md_{filename}"
                            )
                        with col_c:
                            if st.button("Delete", key=f"del_{filename}"):
                                os.remove(file_path)
                                st.rerun()

                        st.markdown("**Preview:**")
                        preview_text = content[:500] + "..." if len(content) > 500 else content
                        st.markdown(preview_text)

                        with st.expander("View Full Report"):
                            st.markdown(content)


if __name__ == "__main__":
    main()

