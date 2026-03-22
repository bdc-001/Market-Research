@echo off
REM Gemini API Key Setup Script
REM This script will help you set up your Gemini API key

echo ========================================
echo   Gemini API Key Setup
echo ========================================
echo.
echo Step 1: Get your API key
echo   - Opening Google AI Studio in your browser...
echo   - Sign in with your Google account
echo   - Click "Create API Key" or copy existing key
echo.

start https://aistudio.google.com/app/apikey

echo.
echo Step 2: Enter your API key below
echo.
set /p GEMINI_KEY="Paste your Gemini API key here: "

echo.
echo Step 3: Setting up environment variable...

REM Set for current session
set GEMINI_API_KEY=%GEMINI_KEY%

REM Set permanently for user
setx GEMINI_API_KEY "%GEMINI_KEY%"

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo Your Gemini API key has been set.
echo.
echo Next steps:
echo   1. Close this window
echo   2. Open a NEW PowerShell window
echo   3. Run: python run_screening.py
echo.
echo Press any key to exit...
pause >nul
