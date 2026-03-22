# Financial Assistant Helper Script
# Quick commands for managing your stock screening assistant

param(
    [Parameter(Position=0)]
    [ValidateSet('run', 'status', 'report', 'config', 'test', 'help')]
    [string]$Command = 'help',
    
    [Parameter(Position=1)]
    [string]$ConfigFile = 'screening_config.json'
)

$AssistantPath = "c:\Users\HP\OpenClaw\Stock Research\Market Research"
$ReportsPath = "$AssistantPath\reports"

function Show-Help {
    Write-Host @"
Financial Assistant Helper Script
==================================

Usage: .\assistant.ps1 [command] [options]

Commands:
  run [config]     - Run screening now (default: screening_config.json)
  status          - Check gateway and cron status
  report [date]   - View latest or specific report
  config          - Edit screening configuration
  test            - Test browser and data extraction
  help            - Show this help message

Examples:
  .\assistant.ps1 run                          # Run with default config
  .\assistant.ps1 run screening_config_tech.json  # Run with specific config
  .\assistant.ps1 report                       # View latest report
  .\assistant.ps1 report 2026-02-12           # View specific date
  .\assistant.ps1 status                       # Check system status
  .\assistant.ps1 test                         # Test setup

"@
}

function Run-Screening {
    param([string]$Config)
    
    Write-Host "🔍 Running stock screening..." -ForegroundColor Cyan
    Write-Host "Configuration: $Config" -ForegroundColor Gray
    
    $message = "Run the daily stock screening workflow using $Config. Analyze all companies in the configured industry, apply filters, and generate a comprehensive report."
    
    openclaw agent --session financial_screener --message $message
}

function Show-Status {
    Write-Host "📊 System Status" -ForegroundColor Cyan
    Write-Host "================" -ForegroundColor Cyan
    
    Write-Host "`nRunning health check..." -ForegroundColor Gray
    openclaw doctor
    
    Write-Host "`nRecent screening sessions:" -ForegroundColor Gray
    openclaw sessions list | Select-String "financial_screener"
}

function Show-Report {
    param([string]$Date)
    
    if (-not $Date) {
        # Get latest report
        $latestReport = Get-ChildItem -Path $ReportsPath -Filter "daily_screening_*.md" | 
            Sort-Object LastWriteTime -Descending | 
            Select-Object -First 1
        
        if ($latestReport) {
            Write-Host "📈 Latest Report: $($latestReport.Name)" -ForegroundColor Cyan
            Write-Host "=" * 50 -ForegroundColor Cyan
            Get-Content $latestReport.FullName | Write-Host
        } else {
            Write-Host "❌ No reports found in $ReportsPath" -ForegroundColor Red
        }
    } else {
        $reportFile = "$ReportsPath\daily_screening_$Date.md"
        if (Test-Path $reportFile) {
            Write-Host "📈 Report for $Date" -ForegroundColor Cyan
            Write-Host "=" * 50 -ForegroundColor Cyan
            Get-Content $reportFile | Write-Host
        } else {
            Write-Host "❌ Report not found: $reportFile" -ForegroundColor Red
        }
    }
}

function Edit-Config {
    Write-Host "📝 Opening screening configuration..." -ForegroundColor Cyan
    $configPath = "$AssistantPath\screening_config.json"
    
    if (Test-Path $configPath) {
        code $configPath
    } else {
        Write-Host "❌ Configuration file not found: $configPath" -ForegroundColor Red
    }
}

function Test-Setup {
    Write-Host "🧪 Testing Financial Assistant Setup" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    
    Write-Host "`n1. Checking OpenClaw installation..." -ForegroundColor Yellow
    try {
        $version = openclaw --version
        Write-Host "   ✅ OpenClaw installed: $version" -ForegroundColor Green
    } catch {
        Write-Host "   ❌ OpenClaw not installed" -ForegroundColor Red
        return
    }
    
    Write-Host "`n2. Checking configuration files..." -ForegroundColor Yellow
    $requiredFiles = @(
        "$AssistantPath\openclaw.json",
        "$AssistantPath\screening_config.json",
        "$AssistantPath\skills\stock_screener\SKILL.md",
        "$AssistantPath\skills\data_extractor\SKILL.md"
    )
    
    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            Write-Host "   ✅ Found: $(Split-Path $file -Leaf)" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Missing: $file" -ForegroundColor Red
        }
    }
    
    Write-Host "`n3. Testing browser tool..." -ForegroundColor Yellow
    Write-Host "   Opening test page..." -ForegroundColor Gray
    openclaw agent --message "Open browser and navigate to https://finviz.com. Take a screenshot and confirm the page loaded successfully."
    
    Write-Host "`n4. Testing data extraction..." -ForegroundColor Yellow
    Write-Host "   Extracting sample data..." -ForegroundColor Gray
    openclaw agent --session financial_screener --message "Extract financial data for ticker AAPL using the data_extractor skill. Show me the key metrics."
    
    Write-Host "`n✅ Test complete!" -ForegroundColor Green
    Write-Host "Review the output above to ensure everything is working." -ForegroundColor Gray
}

# Main script logic
switch ($Command) {
    'run' {
        Run-Screening -Config $ConfigFile
    }
    'status' {
        Show-Status
    }
    'report' {
        Show-Report -Date $ConfigFile  # Reusing param for date
    }
    'config' {
        Edit-Config
    }
    'test' {
        Test-Setup
    }
    'help' {
        Show-Help
    }
    default {
        Show-Help
    }
}
