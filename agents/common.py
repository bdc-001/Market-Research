"""
Common Utilities for Agent Ecosystem
"""
import os
import sys
import json
import google.generativeai as genai
from typing import Dict, Any, List

MODEL_NAME = 'gemini-3-flash-preview'


def get_api_key() -> str:
    key = os.getenv('GEMINI_API_KEY')

    # Fallback to Streamlit secrets if environment variable not found
    if not key:
        try:
            import streamlit as st
            key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            pass

    if not key:
        raise ValueError("GEMINI_API_KEY not found in environment")
    return key


def setup_gemini(with_memory: bool = True):
    """
    Returns a Gemini model whose system instruction is GEMINI.md plus every
    rule the critic agent has learned so far. Pass with_memory=False for the
    critic itself, which must reason about the rules rather than obey them.
    """
    genai.configure(api_key=get_api_key())

    instruction = None
    if with_memory:
        try:
            from agents.memory import system_instruction
            instruction = system_instruction()
        except Exception:
            instruction = None

    if instruction:
        return genai.GenerativeModel(MODEL_NAME, system_instruction=instruction)
    return genai.GenerativeModel(MODEL_NAME)

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
