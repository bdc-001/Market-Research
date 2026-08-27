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

# ── QuanTum Enterprise Design System ──────────────────────────────────────────
st.markdown("""
<style>
  /* ── Google Fonts: Figtree (Primary), JetBrains Mono (Code), Material Symbols ── */
  @import url('https://fonts.googleapis.com/css2?family=Figtree:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,400;1,600&family=JetBrains+Mono:wght@400;500&display=swap');
  @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
  @import url('https://fonts.googleapis.com/css2?family=Material+Icons:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

  :root {
      /* Apple & Material Clean Palette */
      --bg: #FFFFFF;
      --bg-surface: #FFFFFF;
      --bg-subtle: #F8FAFC;
      --bg-hover: #F1F5F9;
      --border: rgba(0, 0, 0, 0.08);
      --border-strong: rgba(0, 0, 0, 0.14);
      --border-focus: #7C3AED;
      
      /* Typography Colors */
      --ink: #0F172A;
      --ink-secondary: #334155;
      --ink-muted: #64748B;
      --ink-subtle: #94A3B8;
      
      /* Brand / Action Identity */
      --brand: #7C3AED;
      --brand-hover: #6D28D9;
      --brand-active: #5B21B6;
      --brand-subtle: #F5F3FF;
      --brand-border: #EDE9FE;
      --brand-glow: rgba(124, 58, 237, 0.12);
      
      /* Semantic Status */
      --green: #10B981;
      --green-subtle: rgba(16, 185, 129, 0.08);
      --green-border: rgba(16, 185, 129, 0.2);
      --red: #EF4444;
      --red-subtle: rgba(239, 68, 68, 0.08);
      --amber: #F59E0B;
      --amber-subtle: rgba(245, 158, 11, 0.08);
      
      /* Apple Radii & Shadows */
      --r-sm: 6px;
      --r-md: 10px;
      --r-lg: 14px;
      --r-pill: 9999px;
      --shadow-apple: 0 1px 2px rgba(0,0,0,0.03), 0 4px 16px rgba(0,0,0,0.02);
      --shadow-elevated: 0 4px 20px rgba(0,0,0,0.05), 0 1px 3px rgba(0,0,0,0.03);
  }

  /* ═══════════════════════════════════════════
     STREAMLIT TOPBAR & SIDEBAR TOGGLE — ZERO TOP GAP
     ═══════════════════════════════════════════ */
  header[data-testid="stHeader"] {
      height: 3.25rem !important;
      background: rgba(255, 255, 255, 0.95) !important;
      backdrop-filter: blur(20px) saturate(180%) !important;
      border-bottom: 1px solid var(--border) !important;
      z-index: 9999 !important;
  }

  footer {
      visibility: hidden !important;
      height: 0 !important;
      display: none !important;
  }

  /* Sidebar toggle button */
  [data-testid="collapsedControl"],
  [data-testid="stSidebarCollapseButton"],
  button[data-testid="stBaseButton-headerNoPadding"] {
      visibility: visible !important;
      display: inline-flex !important;
      opacity: 1 !important;
      color: var(--ink-secondary) !important;
      cursor: pointer !important;
  }
  [data-testid="collapsedControl"] {
      top: 0.5rem !important;
      left: 0.75rem !important;
  }
  [data-testid="collapsedControl"] button,
  [data-testid="stSidebarCollapseButton"] button {
      border: 1px solid var(--border) !important;
      background: var(--bg-surface) !important;
      border-radius: var(--r-sm) !important;
      color: var(--ink-secondary) !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
  }
  [data-testid="collapsedControl"] button:hover,
  [data-testid="stSidebarCollapseButton"] button:hover {
      background: var(--bg-hover) !important;
      border-color: var(--border-strong) !important;
      color: var(--brand) !important;
  }

  /* ═══════════════════════════════════════════
     FIGTREE TYPOGRAPHY SYSTEM
     ═══════════════════════════════════════════ */
  *, *::before, *::after { box-sizing: border-box; }

  html, body, .stApp {
      font-family: 'Figtree', -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      background: var(--bg) !important;
      color: var(--ink);
  }

  p, h1, h2, h3, h4, h5, h6, label, input, textarea, select, 
  .stButton button, .stDownloadButton button, .stTextInput input {
      font-family: 'Figtree', -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif !important;
  }

  code, pre, .stCodeBlock, .stCodeBlock code {
      font-family: 'JetBrains Mono', monospace !important;
  }

  /* Preserve Material icon ligatures */
  [data-testid="stIconMaterial"], 
  .material-symbols-rounded, 
  .material-icons, 
  [class*="material-symbols"], 
  [class*="material-icons"],
  span[translate="no"] {
      font-family: 'Material Symbols Rounded', 'Material Icons' !important;
      font-weight: normal !important;
      font-style: normal !important;
      line-height: 1 !important;
      text-transform: none !important;
      letter-spacing: normal !important;
      display: inline-block !important;
  }

  /* ═══════════════════════════════════════════
     SENSE LAYOUT & SPACING — ZERO TOP WASTAGE
     ═══════════════════════════════════════════ */
  .block-container {
      padding-top: 0.5rem !important;
      padding-bottom: 2.5rem !important;
      padding-left: 2rem !important;
      padding-right: 2rem !important;
      margin-top: 0 !important;
      max-width: 1440px !important;
  }

  .stMarkdown, .stAlert, .stDataFrame,
  .stTextInput, .stSelectbox, .stTextArea,
  .stButton, .stDownloadButton, .stExpander {
      margin-bottom: 0 !important;
  }
  div[data-testid="stVerticalBlock"] > div {
      gap: 0.875rem !important;
  }
  div[data-testid="stHorizontalBlock"] {
      gap: 1.25rem !important;
  }

  [data-testid="column"] {
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
  }

  /* Slim scrollbar */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
      background: #CBD5E1; border-radius: 99px;
  }
  ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

  @keyframes dot-pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.9); }
  }

  /* ═══════════════════════════════════════════
     SIDEBAR — SENSE DOCKED AT TOP
     ═══════════════════════════════════════════ */
  [data-testid="stSidebar"] {
      top: 0 !important;
      height: 100vh !important;
      background: rgba(255, 255, 255, 0.98) !important;
      backdrop-filter: blur(20px) saturate(180%) !important;
      border-right: 1px solid var(--border) !important;
      padding: 0.75rem 0.75rem 1.25rem 0.75rem !important;
      z-index: 10000 !important;
  }
  [data-testid="stSidebar"] > div:first-child {
      padding-top: 0.25rem !important;
  }

  .sidebar-brand-container {
      padding: 0 0.25rem 1.25rem 0.25rem;
      border-bottom: 1px solid var(--border);
      margin-bottom: 1.25rem;
  }
  .sidebar-brand-header {
      display: flex; align-items: center; gap: 10px;
  }
  .brand-icon-box {
      width: 34px; height: 34px; border-radius: var(--r-md);
      background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%);
      display: flex; align-items: center; justify-content: center;
      font-size: 0.9375rem; color: #fff; font-weight: 800;
      box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
      flex-shrink: 0;
  }
  .brand-text-title {
      font-size: 1rem; font-weight: 800;
      color: var(--ink); letter-spacing: -0.02em; line-height: 1.2;
  }
  .brand-text-sub {
      font-size: 0.6875rem; font-weight: 400; color: var(--ink-muted);
      margin-top: 1px;
  }
  .brand-tag {
      display: inline-block; margin-top: 8px;
      font-size: 0.5625rem; font-weight: 700;
      letter-spacing: 0.05em; text-transform: uppercase;
      padding: 2px 8px; border-radius: var(--r-pill);
      background: var(--brand-subtle); color: var(--brand);
      border: 1px solid var(--brand-border);
  }

  /* Radio group label */
  [data-testid="stSidebar"] .stRadio > label {
      font-size: 0.625rem !important; font-weight: 700 !important;
      color: var(--ink-subtle) !important;
      text-transform: uppercase !important; letter-spacing: 0.08em !important;
      padding-left: 8px !important; margin-bottom: 6px !important;
  }
  [data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }

  /* KILL ALL RADIO BUTTONS AND CIRCLES COMPLETELY */
  [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child,
  [data-testid="stSidebar"] [data-testid="stRadio"] [data-baseweb="radio"] > div:first-child,
  [data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"],
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] input,
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] svg,
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] div[class*="stRadioButton"],
  [data-testid="stSidebar"] [data-testid="stRadio"] span[class*="st-"] {
      display: none !important;
      visibility: hidden !important;
      width: 0 !important;
      height: 0 !important;
      margin: 0 !important;
      padding: 0 !important;
      border: none !important;
      opacity: 0 !important;
      position: absolute !important;
      pointer-events: none !important;
  }

  /* Sense Navigation Item */
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label,
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] {
      background: transparent !important;
      border: 1px solid transparent !important;
      border-radius: var(--r-md) !important;
      padding: 9px 12px !important; 
      margin: 2px 0 !important;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
      cursor: pointer !important; 
      width: 100% !important;
      display: flex !important;
      align-items: center !important;
  }
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover,
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:hover {
      background: var(--bg-hover) !important;
  }
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label div[data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
      color: var(--ink-secondary) !important;
      font-weight: 500 !important; 
      font-size: 0.8125rem !important; 
      margin: 0 !important;
      letter-spacing: -0.01em !important;
  }

  /* Active nav item — Sense Blue/Purple Glow */
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked),
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input:checked) {
      background: var(--brand-subtle) !important;
      border-color: var(--brand-border) !important;
  }
  [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) div[data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] .stRadio label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {
      color: var(--brand) !important; 
      font-weight: 700 !important;
  }

  /* Sidebar footer */
  .sidebar-status-card {
      border-top: 1px solid var(--border);
      padding: 14px 4px 0 4px; margin-top: 1.5rem;
  }
  .status-header-text {
      font-size: 0.5625rem; font-weight: 700; color: var(--ink-subtle);
      text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px;
  }
  .status-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 4px 0; font-size: 0.75rem;
  }
  .status-left {
      display: flex; align-items: center; gap: 6px;
      color: var(--ink-secondary); font-weight: 500;
  }
  .status-val-pill {
      font-size: 0.5625rem; font-weight: 700; padding: 2px 7px;
      border-radius: var(--r-pill); letter-spacing: 0.03em;
      background: var(--green-subtle); color: var(--green);
      border: 1px solid var(--green-border);
  }

  /* ═══════════════════════════════════════════
     SENSE FIXED TOPBAR — IN THE TOPBAR DIRECTLY
     ═══════════════════════════════════════════ */
  .sense-topbar-fixed {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 3.25rem;
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: space-between;
      pointer-events: none;
      padding: 0 1.25rem;
  }
  .sense-title-group {
      pointer-events: auto;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-left: 3.75rem; /* room for sidebar collapse button */
  }
  .sense-title {
      font-size: 1.1875rem;
      font-weight: 800;
      color: var(--ink);
      letter-spacing: -0.025em;
      margin: 0;
  }
  .sense-user-actions {
      pointer-events: auto;
      display: flex;
      align-items: center;
      gap: 10px;
      margin-right: 6.5rem; /* room for Streamlit right icons */
  }
  .sense-avatar-btn {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--brand);
      color: #FFF;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 0.6875rem;
      box-shadow: 0 2px 6px rgba(124,58,237,0.25);
  }
  .sense-icon-btn {
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.8125rem;
      color: var(--ink-muted);
  }

  /* Sense Filter Bar */
  .sense-filter-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-top: 0.5rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
  }
  .sense-filters-left {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
  }
  .sense-pill-filter {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: var(--r-md);
      background: var(--bg-surface);
      border: 1px solid var(--border);
      font-size: 0.8125rem;
      font-weight: 500;
      color: var(--ink-secondary);
      cursor: pointer;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  }
  .sense-pill-filter:hover {
      background: var(--bg-hover);
      border-color: var(--border-strong);
  }

  /* ═══════════════════════════════════════════
     SENSE 3-COLUMN CARD GRID
     ═══════════════════════════════════════════ */
  .sense-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
  }
  .sense-card {
      background: var(--bg-surface);
      border: 1px solid var(--border);
      border-radius: var(--r-lg);
      padding: 18px 20px;
      box-shadow: var(--shadow-apple);
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-height: 180px;
  }
  .sense-card:hover {
      border-color: rgba(124, 58, 237, 0.3);
      box-shadow: 0 8px 24px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04);
      transform: translateY(-2px);
  }
  .sense-card-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 14px;
  }
  .sense-card-title {
      font-size: 1rem;
      font-weight: 700;
      color: var(--ink);
      letter-spacing: -0.015em;
      line-height: 1.3;
      margin: 0;
  }
  .sense-card-status {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 0.6875rem;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: var(--r-pill);
  }
  .sense-status-active {
      background: var(--green-subtle);
      color: var(--green);
      border: 1px solid var(--green-border);
  }
  .sense-status-paused {
      background: var(--amber-subtle);
      color: var(--amber);
      border: 1px solid rgba(245, 158, 11, 0.2);
  }
  .sense-status-resuming {
      background: var(--brand-subtle);
      color: var(--brand);
      border: 1px solid var(--brand-border);
  }

  .sense-card-meta {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      padding: 10px 0;
      border-top: 1px solid var(--border);
      border-bottom: 1px solid var(--border);
      margin-bottom: 12px;
  }
  .sense-meta-label {
      font-size: 0.5625rem;
      font-weight: 700;
      color: var(--ink-subtle);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 2px;
  }
  .sense-meta-val {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--ink-secondary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
  }

  .sense-card-footer {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
  }
  .sense-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      border-radius: var(--r-pill);
      font-size: 0.625rem;
      font-weight: 600;
      background: var(--bg-subtle);
      color: var(--ink-muted);
      border: 1px solid var(--border);
  }
  .sense-chip-active {
      background: var(--brand-subtle);
      color: var(--brand);
      border-color: var(--brand-border);
  }

  /* ═══════════════════════════════════════════
     STICKY TOP NAVBAR & SECTION HEADER
     ═══════════════════════════════════════════ */
  .qt-sticky-topbar {
      position: sticky;
      top: 0;
      z-index: 999;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.75rem 1.25rem;
      margin: -1rem -2.5rem 1.5rem -2.5rem;
      background: rgba(255, 255, 255, 0.88);
      backdrop-filter: blur(20px) saturate(180%);
      border-bottom: 1px solid var(--border);
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  }
  .qt-topbar-left {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.8125rem;
      font-weight: 500;
  }
  .qt-topbar-brand {
      color: var(--ink-muted);
      font-weight: 600;
  }
  .qt-topbar-sep {
      color: var(--ink-subtle);
  }
  .qt-topbar-section {
      color: var(--ink);
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 6px;
  }
  .qt-topbar-right {
      display: flex;
      align-items: center;
      gap: 8px;
  }
  .qt-topbar-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 10px;
      border-radius: var(--r-pill);
      font-size: 0.6875rem;
      font-weight: 600;
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      color: var(--ink-secondary);
  }
  .qt-badge-accent {
      background: var(--brand-subtle);
      border-color: var(--brand-border);
      color: var(--brand);
  }

  .qt-header {
      padding: 0.5rem 0 1.5rem 0;
      margin-bottom: 1.75rem;
      border-bottom: 1px solid var(--border);
  }
  .qt-header-content {
      display: flex;
      align-items: center;
      gap: 16px;
  }
  .qt-header-icon-box {
      width: 46px;
      height: 46px;
      border-radius: var(--r-lg);
      background: var(--brand-subtle);
      border: 1px solid var(--brand-border);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.4rem;
      box-shadow: var(--shadow-apple);
      flex-shrink: 0;
  }
  .qt-page-title {
      font-size: 1.625rem;
      font-weight: 800;
      color: var(--ink);
      letter-spacing: -0.03em;
      line-height: 1.1;
      margin: 0;
  }
  .qt-page-sub {
      font-size: 0.875rem;
      color: var(--ink-muted);
      margin-top: 4px;
      font-weight: 400;
      line-height: 1.4;
  }

  /* ═══════════════════════════════════════════
     APPLE BUTTONS & MATERIAL UI CTAS
     ═══════════════════════════════════════════ */
  .stButton > button {
      width: 100%;
      min-height: 38px !important; padding: 0 16px !important;
      font-size: 0.8125rem !important; font-weight: 600 !important;
      border-radius: var(--r-md) !important;
      border: 1px solid var(--border) !important;
      background: var(--bg-surface) !important;
      color: var(--ink-secondary) !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
      cursor: pointer !important;
  }
  .stButton > button:hover {
      background: var(--bg-hover) !important;
      border-color: var(--border-strong) !important;
      color: var(--ink) !important;
      transform: translateY(-1px);
      box-shadow: 0 3px 8px rgba(0,0,0,0.04) !important;
  }
  .stButton > button:active {
      transform: scale(0.985) !important;
  }
  .stButton > button[kind="primary"] {
      background: linear-gradient(180deg, #8B5CF6 0%, #7C3AED 100%) !important;
      color: #FFFFFF !important;
      border: 1px solid #6D28D9 !important;
      box-shadow: 0 1px 2px rgba(124, 58, 237, 0.2), 0 4px 12px rgba(124, 58, 237, 0.15) !important;
  }
  .stButton > button[kind="primary"]:hover {
      background: linear-gradient(180deg, #7C3AED 0%, #6D28D9 100%) !important;
      box-shadow: 0 2px 4px rgba(124, 58, 237, 0.25), 0 6px 16px rgba(124, 58, 237, 0.2) !important;
  }

  /* ═══════════════════════════════════════════
     FORM INPUTS — APPLE/MUI FOCUS
     ═══════════════════════════════════════════ */
  .stTextInput > div > div > input,
  .stSelectbox > div > div,
  .stTextArea > div > div > textarea {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--r-md) !important;
      color: var(--ink) !important;
      font-size: 0.8125rem !important;
      padding: 8px 12px !important;
      min-height: 38px !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02) inset !important;
      transition: all 0.15s ease !important;
  }
  .stTextInput > div > div > input:focus,
  .stSelectbox > div > div:focus-within,
  .stTextArea > div > div > textarea:focus {
      border-color: var(--brand) !important;
      box-shadow: 0 0 0 3px var(--brand-glow) !important;
  }
  .stTextInput > div > div > input::placeholder {
      color: var(--ink-subtle) !important;
      font-weight: 400 !important;
  }
  .stSelectbox [data-baseweb="select"] > div {
      background: var(--bg-surface) !important;
      border-color: var(--border) !important;
      border-radius: var(--r-md) !important;
      min-height: 38px !important;
  }
  .stSelectbox [data-baseweb="select"] * {
      color: var(--ink) !important; font-size: 0.8125rem !important;
  }
  .stSelectbox svg { fill: var(--ink-subtle) !important; }
  .stTextInput label, .stSelectbox label, .stTextArea label {
      font-size: 0.75rem !important; font-weight: 600 !important;
      color: var(--ink-secondary) !important; margin-bottom: 4px !important;
  }

  /* ═══════════════════════════════════════════
     METRIC CARDS — ELEVATED SURFACES
     ═══════════════════════════════════════════ */
  [data-testid="metric-container"] {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--r-lg) !important;
      padding: 16px 20px !important;
      box-shadow: var(--shadow-apple) !important;
      transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
  }
  [data-testid="metric-container"]:hover {
      border-color: var(--brand-border) !important;
      box-shadow: var(--shadow-elevated) !important;
      transform: translateY(-1px);
  }
  [data-testid="metric-container"] label {
      color: var(--ink-muted) !important;
      font-size: 0.6875rem !important; font-weight: 600 !important;
      text-transform: uppercase !important; letter-spacing: 0.05em !important;
  }
  [data-testid="metric-container"] [data-testid="metric-value"] {
      color: var(--ink) !important;
      font-size: 1.375rem !important; font-weight: 700 !important;
      letter-spacing: -0.02em !important;
      font-variant-numeric: tabular-nums;
  }

  /* ═══════════════════════════════════════════
     EXPANDERS & CONTAINERS
     ═══════════════════════════════════════════ */
  .streamlit-expanderHeader {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--r-md) !important;
      color: var(--ink) !important;
      font-weight: 600 !important; font-size: 0.8125rem !important;
      padding: 10px 16px !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.02) !important;
  }
  .streamlit-expanderHeader:hover {
      background: var(--bg-subtle) !important;
  }
  .streamlit-expanderContent {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      border-top: none !important;
      border-radius: 0 0 var(--r-md) var(--r-md) !important;
      padding: 16px 20px !important;
  }

  /* Status widget */
  [data-testid="stStatus"] {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--r-lg) !important;
      box-shadow: var(--shadow-apple) !important;
  }
  [data-testid="stStatus"] * { color: var(--ink) !important; }

  /* ═══════════════════════════════════════════
     DATAFRAMES — MODERN CLEAN TABLE
     ═══════════════════════════════════════════ */
  .stDataFrame {
      border-radius: var(--r-lg) !important;
      overflow: hidden !important;
      border: 1px solid var(--border) !important;
      box-shadow: var(--shadow-apple) !important;
  }
  .stDataFrame th {
      background: var(--bg-subtle) !important;
      color: var(--ink-muted) !important;
      font-weight: 700 !important; font-size: 0.75rem !important;
      text-transform: uppercase !important; letter-spacing: 0.04em !important;
      border-bottom: 1px solid var(--border) !important;
      padding: 10px 14px !important;
  }
  .stDataFrame td {
      color: var(--ink) !important;
      font-size: 0.8125rem !important;
      border-color: var(--bg-subtle) !important;
      padding: 10px 14px !important;
      font-variant-numeric: tabular-nums;
  }
  .stDataFrame tr:hover td {
      background: var(--bg-subtle) !important;
  }

  /* ═══════════════════════════════════════════
     TABS — APPLE SEGMENTED CONTROL STYLE
     ═══════════════════════════════════════════ */
  .stTabs [data-baseweb="tab-list"] {
      gap: 4px; 
      background: var(--bg-subtle);
      border: 1px solid var(--border);
      border-radius: var(--r-md);
      padding: 4px;
  }
  .stTabs [data-baseweb="tab"] {
      font-size: 0.8125rem; font-weight: 500;
      padding: 6px 16px; color: var(--ink-muted);
      background: transparent; border: none;
      border-radius: var(--r-sm); transition: all 0.15s ease;
  }
  .stTabs [data-baseweb="tab"]:hover { color: var(--ink); }
  .stTabs [aria-selected="true"] {
      color: var(--ink) !important; 
      font-weight: 600 !important;
      background: var(--bg-surface) !important;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
  }

  /* ═══════════════════════════════════════════
     ALERTS
     ═══════════════════════════════════════════ */
  .stAlert {
      border-radius: var(--r-md) !important;
      padding: 12px 16px !important;
      font-size: 0.8125rem !important; font-weight: 500 !important;
      box-shadow: var(--shadow-apple) !important;
  }
  .stSuccess { background: var(--green-subtle) !important; border: 1px solid var(--green-border) !important; color: var(--green) !important; }
  .stInfo    { background: var(--bg-subtle) !important; border: 1px solid var(--border) !important; color: var(--ink) !important; }
  .stWarning { background: var(--amber-subtle) !important; border: 1px solid rgba(245, 158, 11, 0.2) !important; color: var(--amber) !important; }
  .stError   { background: var(--red-subtle) !important; border: 1px solid rgba(239, 68, 68, 0.2) !important; color: var(--red) !important; }

  /* Download */
  .stDownloadButton > button {
      background: var(--bg-surface) !important;
      border: 1px solid var(--border) !important;
      color: var(--ink-secondary) !important;
      font-weight: 600 !important; border-radius: var(--r-md) !important;
      font-size: 0.8125rem !important;
      box-shadow: 0 1px 2px rgba(0,0,0,0.03) !important;
  }
  .stDownloadButton > button:hover {
      background: var(--bg-hover) !important;
  }

  /* ═══════════════════════════════════════════
     MARKDOWN REPORT OUTPUT
     ═══════════════════════════════════════════ */
  .stMarkdown h1 { font-size: 1.375rem !important; margin-top: 1.5rem !important; margin-bottom: 0.5rem !important; letter-spacing: -0.02em; }
  .stMarkdown h2 { font-size: 1.125rem !important; margin-top: 1.25rem !important; margin-bottom: 0.4rem !important; letter-spacing: -0.015em; }
  .stMarkdown h3 { font-size: 0.9375rem !important; margin-top: 1rem !important; margin-bottom: 0.3rem !important; }
  .stMarkdown p { font-size: 0.875rem !important; line-height: 1.6 !important; margin-bottom: 0.6rem !important; }
  .stMarkdown li { font-size: 0.875rem !important; line-height: 1.5 !important; }
  .stMarkdown table { font-size: 0.8125rem !important; width: 100% !important; border-collapse: collapse !important; margin: 1rem 0 !important; }
  .stMarkdown table th {
      background: var(--bg-subtle) !important; font-weight: 700 !important;
      padding: 8px 12px !important; border: 1px solid var(--border) !important;
      text-align: left !important; color: var(--ink-muted) !important;
      text-transform: uppercase !important; letter-spacing: 0.04em !important;
  }
  .stMarkdown table td {
      padding: 8px 12px !important; border: 1px solid var(--border) !important;
      color: var(--ink) !important;
  }
  .stMarkdown code {
      background: var(--brand-subtle) !important; color: var(--brand) !important;
      padding: 2px 6px !important; border-radius: 4px !important;
      font-size: 0.8125rem !important;
  }
  .stMarkdown pre {
      background: var(--bg-subtle) !important;
      border: 1px solid var(--border) !important;
      border-radius: var(--r-md) !important;
      padding: 14px !important;
  }
  .stMarkdown blockquote {
      border-left: 3px solid var(--brand) !important;
      padding-left: 14px !important;
      color: var(--ink-muted) !important;
      margin: 1rem 0 !important;
  }

  /* ═══════════════════════════════════════════
     TEXT DEFAULTS
     ═══════════════════════════════════════════ */
  p, li, span, div { color: var(--ink-secondary); }
  h1, h2, h3, h4, h5 {
      color: var(--ink); font-weight: 700; letter-spacing: -0.02em;
  }
  .stCaption, caption { color: var(--ink-subtle) !important; font-size: 0.75rem; }
  hr { border-color: var(--border) !important; margin: 1.5rem 0; }

  /* ═══════════════════════════════════════════
     MOBILE RESPONSIVE
     ═══════════════════════════════════════════ */
  @media (max-width: 768px) {
      .block-container { padding: 1.25rem 1rem 2rem 1rem !important; }
      .qt-page-title { font-size: 1.25rem; }
      [data-testid="stSidebar"] { padding: 1rem 0.5rem !important; }
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
    [data-baseweb="popover"] { background: #FFFFFF !important; border-radius: 8px !important; border: 1px solid #E5E7EB !important; box-shadow: 0 4px 16px rgba(0,0,0,0.06) !important; overflow: hidden !important; }
    [data-baseweb="menu"], ul[data-baseweb="menu"] { background: #FFFFFF !important; border-radius: 8px !important; padding: 4px !important; }
    [role="option"] { background: transparent !important; color: #374151 !important; border-radius: 6px !important; margin: 1px 4px !important; padding: 8px 12px !important; font-family: 'Inter', sans-serif !important; font-size: 0.875rem !important; }
    [role="option"]:hover { background: #F3F4F6 !important; color: #111827 !important; }
    [role="option"][aria-selected="true"] { background: #F5F3FF !important; color: #7C3AED !important; font-weight: 600 !important; }
    [data-baseweb="select"] input { color: #111827 !important; }
    [data-baseweb="tooltip"] { background: #111827 !important; color: #FFFFFF !important; border-radius: 6px !important; font-family: 'Inter', sans-serif !important; font-size: 0.75rem !important; }
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

        nav_icons = {
            "Sector Analysis": "📊  Sector Analysis",
            "Stock Analysis": "🏢  Stock Analysis",
            "Top Picks": "🎯  Top Picks",
            "QuanTum Picks": "⚡  QuanTum Picks",
            "Global Markets": "🌐  Global Markets",
            "Market News": "📰  Market News",
            "Report Library": "📁  Report Library",
        }

        selected_section = st.radio(
            "WORKSPACE",
            nav_options,
            format_func=lambda x: nav_icons.get(x, x),
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
            <div style="display:flex;justify-content:space-between;font-size:0.6875rem;color:var(--ink-4);font-weight:500;">
                <span>Coverage: NSE & Global</span>
                <span>Pro Suite</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Section Page Header (Sense Style) ────────────────────────────────────
    section_meta = {
        "Sector Analysis": ("📊", "Sector Intelligence", "Multi-Agent Deep Dive: Trends, Valuation & Institutional Positioning"),
        "Stock Analysis": ("🏢", "Stock Analysis", "Deep-dive 7-Agent research memorandum on Indian equities"),
        "Top Picks": ("🎯", "Top Picks", "Automated screening for best risk-reward opportunities across industries"),
        "QuanTum Picks": ("⚡", "QuanTum Picks", "Multi-factor algorithmic engine: Technical + Fundamental + Sentiment"),
        "Global Markets": ("🌐", "Global Markets", "Emerging and developed markets macroeconomic intelligence"),
        "Market News": ("📰", "Market News", "Real-time news stream with automated sentiment scoring"),
        "Report Library": ("📁", "Report Library", "Historical archive of generated memos, PDFs, and sector deep dives"),
    }

    current_icon, current_title, current_desc = section_meta.get(
        selected_section, ("⚡", "Financial Intelligence", "Enterprise Market Analytics")
    )

    st.markdown(f"""
    <div class="sense-topbar-fixed">
        <div class="sense-title-group">
            <h1 class="sense-title">{current_icon} {current_title}</h1>
        </div>
        <div class="sense-user-actions">
            <div class="sense-icon-btn" title="Dark mode toggle">🌙</div>
            <div class="sense-icon-btn" title="Notifications">🔔</div>
            <div class="sense-avatar-btn" title="Arsalaan Mohammed">A</div>
        </div>
    </div>

    <div class="sense-filter-bar">
        <div class="sense-filters-left">
            <div class="sense-pill-filter">Status ▾</div>
            <div class="sense-pill-filter">Horizon ▾</div>
            <div class="sense-pill-filter">Agent ▾</div>
            <div class="sense-pill-filter">☡ More Filters</div>
        </div>
        <div class="sense-filters-left">
            <div class="sense-pill-filter">↑↓ Recently updated ▾</div>
            <div class="sense-pill-filter" style="letter-spacing: 2px;">⊞ ≡</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Section 1: Sector Analysis ────────────────────────────────────────────
    if selected_section == "Sector Analysis":
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            selected_sector = st.selectbox("Industry Sector", SECTORS, key="sector_select")
        with col_s2:
            run_sector_btn = st.button("+ Generate Sector Report", type="primary", use_container_width=True)
        
        st.markdown("""
        <div class="sense-grid">
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">Indian Defence & Aerospace</h3>
                    <span class="sense-card-status sense-status-active">● Active</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">AGENT</div><div class="sense-meta-val">7-Agent Council</div></div>
                    <div><div class="sense-meta-label">COVERAGE</div><div class="sense-meta-val">HAL, BEL, BDL</div></div>
                    <div><div class="sense-meta-label">OUTLOOK</div><div class="sense-meta-val">Bullish (+18%)</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Indigenisation</span>
                    <span class="sense-chip">● Orderbook Growth</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">Indian IT & AI Infrastructure</h3>
                    <span class="sense-card-status sense-status-resuming">● Resuming</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">AGENT</div><div class="sense-meta-val">Macro + Tech</div></div>
                    <div><div class="sense-meta-label">COVERAGE</div><div class="sense-meta-val">TCS, INFY, HCL</div></div>
                    <div><div class="sense-meta-label">VALUATION</div><div class="sense-meta-val">P/E 24.5 (Fair)</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Cloud Transformation</span>
                    <span class="sense-chip">● Margin Resilient</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">Banking & Private Credit</h3>
                    <span class="sense-card-status sense-status-active">● Active</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">AGENT</div><div class="sense-meta-val">Credit Analyst</div></div>
                    <div><div class="sense-meta-label">COVERAGE</div><div class="sense-meta-val">HDFCBANK, ICICI</div></div>
                    <div><div class="sense-meta-label">EFFICIENCY</div><div class="sense-meta-val">ROE 17.2%</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Low NPA</span>
                    <span class="sense-chip">● NIM Expansion</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
            run_stock_btn = st.button("+ Run Council Analysis", type="primary", use_container_width=True)
        
        st.markdown("""
        <div class="sense-grid">
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">TATAMOTORS (Tata Motors Ltd)</h3>
                    <span class="sense-card-status sense-status-active">● High Conviction</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">COUNCIL SCORE</div><div class="sense-meta-val">88 / 100</div></div>
                    <div><div class="sense-meta-label">TECHNICALS</div><div class="sense-meta-val">RSI 56.4 (MACD +)</div></div>
                    <div><div class="sense-meta-label">FUNDAMENTALS</div><div class="sense-meta-val">ROE 24.8%</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● EV Transition</span>
                    <span class="sense-chip">● JLR Margin Expansion</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">RELIANCE (Reliance Industries)</h3>
                    <span class="sense-card-status sense-status-paused">● Consolidation</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">COUNCIL SCORE</div><div class="sense-meta-val">76 / 100</div></div>
                    <div><div class="sense-meta-label">TECHNICALS</div><div class="sense-meta-val">Near SMA200</div></div>
                    <div><div class="sense-meta-label">VALUATION</div><div class="sense-meta-val">P/E 26.1</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Jio Growth</span>
                    <span class="sense-chip">● Retail Monetisation</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">INFY (Infosys Limited)</h3>
                    <span class="sense-card-status sense-status-resuming">● Accumulate</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">COUNCIL SCORE</div><div class="sense-meta-val">82 / 100</div></div>
                    <div><div class="sense-meta-label">TECHNICALS</div><div class="sense-meta-val">Above SMA50</div></div>
                    <div><div class="sense-meta-label">YIELD</div><div class="sense-meta-val">Div Yield 2.6%</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Generative AI Deals</span>
                    <span class="sense-chip">● Large Deal TCV</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
            run_tp_btn = st.button("+ Find Top Picks", type="primary", use_container_width=True)
        
        st.markdown("""
        <div class="sense-grid">
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">HAL (Hindustan Aeronautics)</h3>
                    <span class="sense-card-status sense-status-active">● Rank #1</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">SECTOR</div><div class="sense-meta-val">Defence & Aero</div></div>
                    <div><div class="sense-meta-label">COMPOSITE SCORE</div><div class="sense-meta-val">92.4 / 100</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">1 Year (+28%)</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Tejas Mk1A Order</span>
                    <span class="sense-chip">● High ROE (26%)</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">DIXON (Dixon Technologies)</h3>
                    <span class="sense-card-status sense-status-active">● Rank #2</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">SECTOR</div><div class="sense-meta-val">Electronics Mfg</div></div>
                    <div><div class="sense-meta-label">COMPOSITE SCORE</div><div class="sense-meta-val">89.1 / 100</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">Positional (+22%)</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● PLI Scheme</span>
                    <span class="sense-chip">● Mobile Assembly</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">KAYNES (Kaynes Technology)</h3>
                    <span class="sense-card-status sense-status-resuming">● Rank #3</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">SECTOR</div><div class="sense-meta-val">Semiconductor EMS</div></div>
                    <div><div class="sense-meta-label">COMPOSITE SCORE</div><div class="sense-meta-val">86.5 / 100</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">5 Years Compounder</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● OSAT Fab Facility</span>
                    <span class="sense-chip">● 40%+ Revenue CAGR</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
            run_btn = st.button("+ Run Quant Engine", type="primary", use_container_width=True)

        st.markdown("""
        <div class="sense-grid">
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">Weekly Alpha Screener</h3>
                    <span class="sense-card-status sense-status-active">● Active</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">WEIGHTS</div><div class="sense-meta-val">Tech 35% + News 35%</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">1 - 5 Trading Days</div></div>
                    <div><div class="sense-meta-label">UNIVERSE</div><div class="sense-meta-val">Nifty 500 + RSS</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Swing Breakouts</span>
                    <span class="sense-chip">● RSI/MACD Crossover</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">1-Year Positional Compounders</h3>
                    <span class="sense-card-status sense-status-active">● Active</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">WEIGHTS</div><div class="sense-meta-val">Fund 50% + Mom 25%</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">6 - 12 Months</div></div>
                    <div><div class="sense-meta-label">METRICS</div><div class="sense-meta-val">ROE > 18%, P/E Fair</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Quality Growth</span>
                    <span class="sense-chip">● Institutional Inflow</span>
                </div>
            </div>
            <div class="sense-card">
                <div class="sense-card-top">
                    <h3 class="sense-card-title">5-Year Structural Wealth</h3>
                    <span class="sense-card-status sense-status-resuming">● Compounding</span>
                </div>
                <div class="sense-card-meta">
                    <div><div class="sense-meta-label">WEIGHTS</div><div class="sense-meta-val">Fund 60% + Moat 40%</div></div>
                    <div><div class="sense-meta-label">HORIZON</div><div class="sense-meta-val">3 - 5 Years Buy & Hold</div></div>
                    <div><div class="sense-meta-label">RISK</div><div class="sense-meta-val">Low Debt / High ROCE</div></div>
                </div>
                <div class="sense-card-footer">
                    <span class="sense-chip sense-chip-active">● Moat Monopolies</span>
                    <span class="sense-chip">● Multi-Bagger Potential</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

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

