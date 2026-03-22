#!/usr/bin/env python3
"""
mobile_access.py — Access your Financial Assistant on iPhone
=============================================================
METHOD 1 (Instant, same WiFi): Open Safari on iPhone → http://192.168.1.25:8501
METHOD 2 (Anywhere, ngrok):    Sign up free at ngrok.com, paste token below.

Usage: py mobile_access.py
"""

import socket
import os

# ── Settings ─────────────────────────────────────────────────
STREAMLIT_PORT = 8501

# Optional: Paste your free ngrok token here for global access
# Get it free at: https://dashboard.ngrok.com/get-started/your-authtoken
NGROK_AUTH_TOKEN = ""   # e.g. "2abc123xyz_XXXXXXXXXXXXXXXXXXXXXXX"
# ─────────────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.25"

def print_wifi_access(ip):
    print()
    print("=" * 55)
    print("📱  METHOD 1 — Same WiFi (Instant, No Setup)")
    print("=" * 55)
    print()
    print(f"  ✅  Make sure your iPhone is on the SAME WiFi as this PC")
    print()
    print(f"  📲  Open Safari on iPhone and go to:")
    print()
    print(f"        http://{ip}:{STREAMLIT_PORT}")
    print()
    print("  💡  Tip: Tap Share → 'Add to Home Screen' for an app icon!")
    print()

def start_ngrok_tunnel():
    from pyngrok import ngrok

    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    
    import time
    tunnel = ngrok.connect(STREAMLIT_PORT, "http")
    url = tunnel.public_url.replace("http://", "https://")

    print("=" * 55)
    print("🌐  METHOD 2 — Anywhere in the World (ngrok)")
    print("=" * 55)
    print()
    print("  ✅  App is accessible from ANYWHERE (not just home WiFi)")
    print()
    print(f"  📲  URL:  {url}")
    print()
    print("  (Keep this terminal open. Press Ctrl+C to stop.)")
    print("=" * 55)
    print()

    while True:
        time.sleep(30)

if __name__ == "__main__":
    ip = get_local_ip()
    
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   📱 Financial Assistant — Mobile Access     ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("  Make sure Streamlit is running:")
    print("  > py -m streamlit run app.py")
    print()

    print_wifi_access(ip)

    if NGROK_AUTH_TOKEN:
        try:
            start_ngrok_tunnel()
        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
    else:
        print("=" * 55)
        print("🌐  METHOD 2 — Access From Anywhere (Optional)")
        print("=" * 55)
        print()
        print("  For access outside your home WiFi (free):")
        print()
        print("  Step 1: Sign up free at https://ngrok.com")
        print("  Step 2: Copy your authtoken from:")
        print("          https://dashboard.ngrok.com/get-started/your-authtoken")
        print("  Step 3: Paste it in mobile_access.py:")
        print("          NGROK_AUTH_TOKEN = \"your_token_here\"")
        print("  Step 4: Run: py mobile_access.py")
        print()
        print("  Or run this one-liner to set it up:")
        print("  py -c \"from pyngrok import ngrok; ngrok.set_auth_token('YOUR_TOKEN')\"")
        print("=" * 55)

        input("\nPress Enter to exit...")
