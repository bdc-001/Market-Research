import os
import sys
import json
import queue
import threading
import asyncio
from datetime import datetime
from io import BytesIO
from fastapi import FastAPI, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Bootstrap secrets from secrets.toml into environment ──────────────────────
def bootstrap_secrets():
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r") as sf:
                for line in sf:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k in ("TURSO_URL", "TURSO_TOKEN", "GEMINI_API_KEY"):
                            os.environ[k] = v
        except Exception as e:
            print(f"Error loading secrets: {e}")

bootstrap_secrets()

# Import local agent frameworks and modules
from agents.research_agent import ResearchAgent
from orchestrator import AgentOrchestrator
from report_store import load_report, save_report, picks_to_records
import financial_analyst_cli as analyst
from sector_orchestrator import SectorOrchestrator
from quantum_orchestrator import QuantumEngineOrchestrator
from global_markets_orchestrator import EmergingMarketsOrchestrator, DevelopedMarketsOrchestrator
from news_tracker_orchestrator import NewsTrackerOrchestrator

from markdown import markdown
from xhtml2pdf import pisa

app = FastAPI(title="QuanTum API Gateway", version="1.0.0")

# Allow CORS for development (Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    if pisa_status.err:
        return None
    return pdf_buffer.getvalue()

# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/sectors")
def get_sectors():
    sectors_path = "sectors.json"
    if os.path.exists(sectors_path):
        with open(sectors_path, "r") as f:
            return json.load(f)
    return []

@app.get("/api/reports/cached/{kind}")
def get_cached_report(kind: str):
    res = load_report(kind)
    if not res:
        return JSONResponse(status_code=404, content={"error": "Report not found"})
    return res

@app.get("/api/reports")
def list_reports(report_type: str = "All", search: str = ""):
    reports_dir = 'reports'
    if not os.path.exists(reports_dir):
        return []
    all_files = [f for f in os.listdir(reports_dir) if f.endswith('.md')]
    res = []
    for filename in all_files:
        if report_type == "Sector Reports" and not filename.startswith("Sector_"):
            continue
        elif report_type == "Stock Analysis" and not filename.startswith("DeepDive_"):
            continue
        elif report_type == "Top Picks" and not filename.startswith("Full_Report_"):
            continue
        elif report_type != "All" and (filename.startswith("Sector_") or filename.startswith("DeepDive_") or filename.startswith("Full_Report_")):
            # Other category
            if report_type == "Other":
                pass
            else:
                continue

        if search and search.lower() not in filename.lower():
            continue
            
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
            
        res.append({
            "filename": filename,
            "size_kb": round(file_size_kb, 1),
            "mod_time": mod_time,
            "type_label": type_label
        })
        
    res.sort(key=lambda x: x["mod_time"], reverse=True)
    return res

@app.get("/api/reports/content/{filename}")
def get_report_content(filename: str):
    reports_dir = 'reports'
    file_path = os.path.join(reports_dir, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return {"content": content}

@app.delete("/api/reports/{filename}")
def delete_report(filename: str):
    reports_dir = 'reports'
    file_path = os.path.join(reports_dir, filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return {"success": True}
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})
    return JSONResponse(status_code=404, content={"error": "File not found"})

class PdfPayload(BaseModel):
    markdown: str

@app.post("/api/pdf")
def generate_pdf(payload: PdfPayload):
    pdf_bytes = convert_to_pdf(payload.markdown)
    if not pdf_bytes:
        return JSONResponse(status_code=500, content={"error": "PDF generation failed"})
    return Response(content=pdf_bytes, media_type="application/pdf")

@app.get("/api/reports/pdf/{filename}")
def get_report_pdf(filename: str):
    reports_dir = 'reports'
    file_path = os.path.join(reports_dir, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    pdf_bytes = convert_to_pdf(content)
    if not pdf_bytes:
        return JSONResponse(status_code=500, content={"error": "PDF generation failed"})
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename={filename.replace('.md', '.pdf')}"}
    )

# ── SSE Background runner endpoints ───────────────────────────────────────────

@app.get("/api/run/sector")
def run_sector(sector: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": f"Starting Sector Analysis for: {sector}"})
            sector_council = SectorOrchestrator()
            
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            report = sector_council.run_sector_analysis(sector, progress_callback=callback)
            
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"Sector_{sector.replace(' ', '_')}_{timestamp}.md"
            file_path = os.path.join('reports', filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
                
            q.put({
                "type": "complete", 
                "report": report, 
                "filename": filename,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/run/stock")
def run_stock(ticker: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": f"Convening Council for ticker: {ticker}"})
            orchestrator = AgentOrchestrator()
            
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            report = orchestrator.run_analysis_pipeline(ticker, progress_callback=callback)
            
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"DeepDive_{ticker}_{timestamp}.md"
            file_path = os.path.join('reports', filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
                
            q.put({
                "type": "complete", 
                "report": report, 
                "filename": filename,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/run/quantum")
def run_quantum(mode: str = Query("fast")):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": f"Initiating QuanTum Algorithmic Screener (Mode: {mode})"})
            engine = QuantumEngineOrchestrator()
            
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            result = engine.run(progress_callback=callback, fast=(mode == "fast"))
            
            if "error" in result:
                q.put({"type": "error", "message": result["error"]})
            else:
                cache_cols = ["ticker", "composite_score", "conviction", "close",
                              "rsi", "pe_ratio", "roe", "entry_status"]
                
                picks_data = {
                    horizon: picks_to_records(result.get(key), cache_cols)
                    for horizon, key in (("week", "week_picks"),
                                         ("year", "year_picks"),
                                         ("fiveyear", "fiveyear_picks"))
                }
                
                save_report(
                    "quantum",
                    result.get("report", ""),
                    picks=picks_data,
                    mode=mode,
                )
                
                q.put({
                    "type": "complete",
                    "report": result.get("report", ""),
                    "report_path": result.get("report_path", ""),
                    "week_picks": picks_data["week"],
                    "year_picks": picks_data["year"],
                    "fiveyear_picks": picks_data["fiveyear"],
                    "headlines": result.get("headlines", [])[:20]
                })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/run/global-markets")
def run_global_markets(market_type: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": f"Loading Global Macro orchestrator for: {market_type}"})
            
            if market_type == "Emerging Markets":
                orchestrator = EmergingMarketsOrchestrator()
            else:
                orchestrator = DevelopedMarketsOrchestrator()
                
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            report = orchestrator.run_analysis(progress_callback=callback)
            
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"Global_{market_type.replace(' ', '')}_{timestamp}.md"
            file_path = os.path.join('reports', filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(report)
                
            q.put({
                "type": "complete", 
                "report": report, 
                "filename": filename,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/run/news")
def run_news(scope: str = Query("global")):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": f"Connecting news parser. Scope: {scope}"})
            orchestrator = NewsTrackerOrchestrator()
            
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            news_data = orchestrator.run_analysis(scope=scope, progress_callback=callback)
            q.put({"type": "complete", "news": news_data})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/run/top-picks")
def run_top_picks(sector: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            callback("Starting Top Picks screener...")
            skills = analyst.load_skills()
            model = analyst.setup_gemini()
            screen_prompt = analyst.get_screening_prompt(sector, skills)
            screen_resp = model.generate_content(screen_prompt)
            
            ext_prompt = f"Extract exactly 3 ticker symbols from this text as a comma-separated list. Text: {screen_resp.text}"
            tickers = [t.strip() for t in model.generate_content(ext_prompt).text.split(',')][:3]
            
            callback(f"Top Picks identified: {tickers}")
            
            full_report = f"# Top Picks Report: {sector}\n\n"
            orchestrator = AgentOrchestrator()
            
            for ticker in tickers:
                callback(f"Analyzing {ticker}...")
                memo = orchestrator.run_analysis_pipeline(ticker, progress_callback=lambda x: None)
                full_report += f"\n## Analysis: {ticker}\n\n{memo}\n\n---\n\n"
            
            os.makedirs('reports', exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"Full_Report_{sector.replace(' ', '_')}_{timestamp}.md"
            file_path = os.path.join('reports', filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_report)
                
            q.put({
                "type": "complete", 
                "report": full_report, 
                "filename": filename, 
                "tickers": tickers,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    
    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, q.get)
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# ── Mount Frontend Assets ─────────────────────────────────────────────────────

frontend_dist_path = os.path.join("frontend", "dist")
if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")

@app.get("/{catchall:path}")
def serve_spa(catchall: str):
    if catchall.startswith("api/"):
        return JSONResponse(status_code=404, content={"error": "API route not found"})
        
    file_path = os.path.join("frontend", "dist", catchall)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
        
    index_path = os.path.join("frontend", "dist", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
        
    return HTMLResponse(
        status_code=404,
        content="<h2>Frontend assets not compiled yet. Please run <code>npm run build</code> in the frontend folder.</h2>"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
