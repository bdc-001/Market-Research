"""
Common Utilities for Agent Ecosystem
"""
import os
import sys
import json
import google.generativeai as genai
from typing import Dict, Any, List

def setup_gemini():
    """Returns a configured Gemini 3 Flash Preview model."""
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Fallback to Streamlit secrets if environment variable not found
    if not GEMINI_API_KEY:
        try:
            import streamlit as st
            GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
        except:
            pass
    
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in environment")
    
    genai.configure(api_key=GEMINI_API_KEY)
    # Using the powerful new model for reasoning
    return genai.GenerativeModel('gemini-3-flash-preview')

def clean_json(text: str) -> Dict[str, Any]:
    """Extracts JSON from markdown fences."""
    try:
        if "```json" in text:
            raw = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            raw = text.split("```")[1].split("```")[0].strip()
        else:
            raw = text.strip()
        return json.loads(raw)
    except Exception as e:
        print(f"⚠️ JSON Parse Error: {e}")
        return {}

class BaseAgent:
    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role
        self.model = setup_gemini()
        
    def run(self, context: str) -> str:
        """Executes the agent's core task."""
        raise NotImplementedError
