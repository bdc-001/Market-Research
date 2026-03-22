<#
.SYNOPSIS
    Registers the Monday 9AM QuanTum Weekly Report cron jobs in OpenClaw.
    Run this once after OpenClaw gateway is started.

.DESCRIPTION
    Creates two cron jobs:
      1. quantum-weekly-whatsapp  → delivers to your WhatsApp number
      2. quantum-weekly-telegram  → delivers to your Telegram chat

    Schedule: Every Monday at 09:00 IST (03:30 UTC)

.HOW TO RUN
    1. Start the OpenClaw gateway:  openclaw gateway start
    2. Set your contacts below (WHATSAPP_NUMBER, TELEGRAM_CHAT_ID)
    3. Run:  .\register_weekly_cron.ps1
#>

# ===================== CONFIGURE THESE =====================
$WHATSAPP_NUMBER = "+916289253227"      # WhatsApp number (confirmed by user)
$TELEGRAM_CHAT_ID = "919547183"       # Telegram chat ID (personal ID)
#                                         # Tip: Message @userinfobot to get your ID.
# ===========================================================

$SCRIPT_DIR = "C:\Users\HP\OpenClaw\Stock Research\Market Research"
$RUNNER = "$SCRIPT_DIR\weekly_report_runner.py"

# The prompt OpenClaw's isolated agent receives
$AGENT_MESSAGE = @"
Run the QuanTum Weekly Financial Report pipeline now.

Steps:
1. Set environment: `$env:GEMINI_API_KEY = (Get-Content 'C:\Users\HP\OpenClaw\Stock Research\Market Research\.streamlit\secrets.toml' | Select-String 'GEMINI_API_KEY' | ForEach-Object { (`$_ -split '""')[1] })`
2. Run: `py '$RUNNER'`
3. Take the entire printed output (starting from *Weekly Financial Intelligence Report*) and deliver it to the requesting channel.
4. Do not add commentary — just send the formatted report.
"@

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  QuanTum Weekly Cron Registration" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# Validate placeholders
if ($WHATSAPP_NUMBER -match "XXXXXXXXXX") {
    Write-Host "⚠️  WARNING: You haven't set WHATSAPP_NUMBER in this script." -ForegroundColor Yellow
    Write-Host "   Edit register_weekly_cron.ps1 and replace +91XXXXXXXXXX with your number." -ForegroundColor Yellow
    $skipWhatsApp = $true
}
else {
    $skipWhatsApp = $false
}

if ($TELEGRAM_CHAT_ID -eq "YOUR_CHAT_ID") {
    Write-Host "⚠️  WARNING: You haven't set TELEGRAM_CHAT_ID in this script." -ForegroundColor Yellow
    Write-Host "   Edit register_weekly_cron.ps1 and replace YOUR_CHAT_ID with your Telegram ID." -ForegroundColor Yellow
    Write-Host "   Tip: Message @userinfobot on Telegram to get your chat ID." -ForegroundColor Gray
    $skipTelegram = $true
}
else {
    $skipTelegram = $false
}

Write-Host ""

# ── Register WhatsApp cron ────────────────────────────────────────────────────
if (-not $skipWhatsApp) {
    Write-Host "📱 Registering WhatsApp cron job..." -ForegroundColor Green
    openclaw cron add `
        --name "Quantum Weekly Report (WhatsApp)" `
        --cron "30 3 * * 1" `
        --tz "Asia/Kolkata" `
        --session isolated `
        --message $AGENT_MESSAGE `
        --announce `
        --channel whatsapp `
        --to $WHATSAPP_NUMBER

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Registered! Fires every Monday at 09:00 IST." -ForegroundColor Green
    }
    else {
        Write-Host "   Failed. Is the OpenClaw gateway running?" -ForegroundColor Red
    }
}
else {
    Write-Host "⏭️  Skipping WhatsApp registration (no number configured)." -ForegroundColor Yellow
}

Write-Host ""

# ── Register Telegram cron ────────────────────────────────────────────────────
if (-not $skipTelegram) {
    Write-Host "✈️  Registering Telegram cron job..." -ForegroundColor Blue
    openclaw cron add `
        --name "Quantum Weekly Report (Telegram)" `
        --cron "31 3 * * 1" `
        --tz "Asia/Kolkata" `
        --session isolated `
        --message $AGENT_MESSAGE `
        --announce `
        --channel telegram `
        --to $TELEGRAM_CHAT_ID

    if ($LASTEXITCODE -eq 0) {
        Write-Host "   Registered! Fires every Monday at 09:01 IST." -ForegroundColor Blue
    }
    else {
        Write-Host "   Failed. Is the OpenClaw gateway running?" -ForegroundColor Red
    }
}
else {
    Write-Host "⏭️  Skipping Telegram registration (no chat ID configured)." -ForegroundColor Yellow
}

Write-Host ""

# ── List all cron jobs to confirm ────────────────────────────────────────────
Write-Host "📋 Current cron jobs:" -ForegroundColor Cyan
openclaw cron list

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  Done! To test immediately (without waiting for Monday):" -ForegroundColor Cyan
Write-Host "  openclaw cron run <job-id-from-above>" -ForegroundColor White
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""
