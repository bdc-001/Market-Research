import os
import sys
import json
import queue
import threading
import asyncio
import time
from datetime import date, datetime, timedelta
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
                        if k in ("TURSO_URL", "TURSO_TOKEN", "GEMINI_API_KEY", "MODEL_API_KEY", "NVIDIA_API_KEY"):
                            os.environ[k] = v
        except Exception as e:
            print(f"Error loading secrets: {e}")

bootstrap_secrets()

# Keep the Vercel import graph light. Orchestrators, Gemini, pandas, and
# xhtml2pdf are loaded inside the routes that need them so a slim
# api/requirements.txt can stay under the 500 MB function limit.
from report_store import load_report, save_report, picks_to_records

_HEAVY_UNAVAILABLE = (
    "This host is missing the analysis stack. "
    "The Docker image must install requirements-local.txt "
    "(not the slim Vercel requirements.txt)."
)

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
    try:
        from markdown import markdown
        from xhtml2pdf import pisa
    except ImportError:
        return None
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

def _jsonable(value):
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _horizon_due(ep, days=30):
    raw = ep.get("entry_date") or (ep.get("created_at") or "")[:10]
    try:
        entry = date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        return None
    return (entry + timedelta(days=days)).isoformat()


@app.get("/api/health")
def health():
    from turso_db import is_configured
    return {"ok": True, "runtime": "slim", "turso": is_configured()}


def _editor_open(subject: str) -> str:
    label = f" on {subject}" if subject else ""
    return (
        f"Itachi (Editor): Sir, I will convene the committee{label}. "
        "Agents brief in order. I will place the memo on your desk."
    )


def _sse_from_queue(q):
    def _qget():
        try:
            return q.get(timeout=12)
        except queue.Empty:
            return {"type": "_keepalive"}

    async def sse_generator():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, _qget)
            if item.get("type") == "_keepalive":
                yield ": ping\n\n"
                continue
            yield f"data: {json.dumps(item)}\n\n"
            if item["type"] in ("complete", "error"):
                break

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse_response(work):
    q = queue.Queue()

    def run_pipeline():
        try:
            work(q)
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})

    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


def _brief_stored_episode(q, ticker: str, ep: dict, preds: list):
    q.put({"type": "progress", "message": _editor_open(ticker)})
    time.sleep(0.45)
    lines = {
        "research": "Historian: briefing from the stored evidence file...",
        "financial": "Quant: reading the stored valuation call...",
        "bull": "Bull: filing the upside case...",
        "bear": "Bear: filing the risk case...",
        "technical": "Chartist: filing the tape snapshot...",
        "editor": "Editor: synthesizing the stored council decision...",
        "scout": "Scout: filing the news desk note...",
    }
    for pred in preds:
        agent = pred.get("agent_name") or ""
        q.put({"type": "progress", "message": lines.get(agent, f"{agent}: filing...")})
        time.sleep(0.5)
    decision = (ep.get("final_decision") or "watch").upper()
    q.put({
        "type": "progress",
        "message": (
            f"Itachi (Editor): Sir, {ticker} is already on file. "
            f"Council decision: {decision}. Memo on your desk."
        ),
    })
    q.put({
        "type": "complete",
        "episode_id": ep.get("id"),
        "ticker": ticker,
        "decision": ep.get("final_decision"),
        "stored": True,
        "report": None,
        "filename": None,
    })


@app.get("/api/discovery/episodes")
def discovery_episodes():
    last_exc = None
    rows = []
    turso = False
    for attempt in range(3):
        try:
            from agents.episode_store import list_discovery_council_episodes
            from turso_db import is_configured
            rows = list_discovery_council_episodes(slim=True)
            turso = is_configured()
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(0.45 * (attempt + 1))
    if last_exc is not None:
        return JSONResponse(status_code=500, content={"error": str(last_exc)})
    today = date.today()
    types = {}
    pending_30 = 0
    out = []
    for ep in rows:
        et = ep.get("event_type") or "unclassified"
        types[et] = types.get(et, 0) + 1
        due = _horizon_due(ep, 30)
        if due:
            try:
                if today < date.fromisoformat(due):
                    pending_30 += 1
            except ValueError:
                pass
        item = {
            "id": ep.get("id"),
            "ticker": ep.get("ticker"),
            "source": ep.get("source"),
            "event_type": et,
            "final_decision": ep.get("final_decision"),
            "entry_price": ep.get("entry_price"),
            "entry_date": ep.get("entry_date"),
            "created_at": ep.get("created_at"),
            "event_id": ep.get("event_id"),
            "due_30": due,
        }
        out.append(item)
    return {
        "episodes": _jsonable(out),
        "count": len(out),
        "event_types": types,
        "pending_30": pending_30,
        "lessons": 0,
        "turso": turso,
    }


@app.get("/api/discovery/episodes/{episode_id}")
def discovery_episode_detail(episode_id: str):
    last_exc = None
    for attempt in range(3):
        try:
            from agents.episode_store import (
                fetch_episode,
                fetch_horizon_outcomes,
                fetch_predictions,
            )
            ep = fetch_episode(episode_id, slim=True)
            if not ep:
                return JSONResponse(status_code=404, content={"error": "Episode not found"})
            ep_out = {
                k: ep.get(k)
                for k in (
                    "id", "ticker", "source", "event_type", "final_decision",
                    "entry_price", "entry_date", "created_at", "event_id",
                )
            }
            ep_out["due_30"] = _horizon_due(ep, 30)
            return _jsonable({
                "episode": ep_out,
                "predictions": fetch_predictions(episode_id, slim=True),
                "horizons": fetch_horizon_outcomes(episode_id, slim=True),
            })
        except Exception as exc:
            last_exc = exc
            time.sleep(0.45 * (attempt + 1))
    return JSONResponse(status_code=500, content={"error": str(last_exc)})


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
        return JSONResponse(
            status_code=501,
            content={"error": "PDF generation is not available on this deployment."},
        )
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
        return JSONResponse(
            status_code=501,
            content={"error": "PDF generation is not available on this deployment."},
        )
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename={filename.replace('.md', '.pdf')}"}
    )

# ── SSE Background runner endpoints ───────────────────────────────────────────

@app.get("/api/run/discovery")
def run_discovery(ticker: str = Query(...), fresh: int = Query(0)):
    symbol = ticker.upper().strip()

    def work(q):
        from agents.episode_store import fetch_episode_by_ticker, fetch_predictions
        existing = fetch_episode_by_ticker(symbol, slim=True)
        if existing and not fresh:
            preds = fetch_predictions(existing["id"], slim=True)
            _brief_stored_episode(q, symbol, existing, preds)
            return
        q.put({"type": "progress", "message": _editor_open(symbol)})
        q.put({"type": "progress", "message": "Editor: loading evidence pack (no new radar scan)..."})
        from discovery_council import DiscoveryCouncil
        try:
            result = DiscoveryCouncil().run(ticker=symbol, progress_callback=lambda m: q.put({
                "type": "progress", "message": m,
            }))
        except FileNotFoundError:
            q.put({
                "type": "error",
                "message": (
                    f"Itachi (Editor): Sir, there is no evidence pack for {symbol}. "
                    "Expand a filing first, then I can convene the committee."
                ),
            })
            return
        q.put({
            "type": "complete",
            "episode_id": result.get("episode_id"),
            "ticker": symbol,
            "decision": result.get("decision"),
            "stored": False,
            "report": None,
            "filename": result.get("memo_path"),
        })

    return _sse_response(work)


@app.get("/api/run/discovery-engine")
def run_discovery_engine(
    lookback_days: int = Query(7),
    max_n: int = Query(3),
):
    def work(q):
        q.put({
            "type": "progress",
            "message": (
                "Itachi (Editor): Sir, I will scan SME and microcap filings, "
                "expand evidence, then convene council on new names. "
                "CHAVDA stays episode #1 and is not a rule."
            ),
        })
        from build_discovery_sample import run_sample
        result = run_sample(
            lookback_days=int(lookback_days),
            max_events_to_llm=40,
            max_n=max(1, min(int(max_n), 6)),
            max_per_type=1,
            progress=lambda m: q.put({"type": "progress", "message": m}),
        )
        stored = [r for r in (result.get("results") or []) if r.get("episode_id")]
        q.put({
            "type": "complete",
            "stored": True,
            "episode_id": stored[-1]["episode_id"] if stored else None,
            "decision": stored[-1].get("decision") if stored else None,
            "episodes": [
                {
                    "ticker": r.get("ticker"),
                    "episode_id": r.get("episode_id"),
                    "decision": r.get("decision"),
                }
                for r in stored
            ],
            "picked": result.get("picked") or [],
            "report": None,
            "filename": result.get("inventory_path"),
        })

    return _sse_response(work)


@app.get("/api/run/sector")
def run_sector(sector: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(sector)})
            q.put({"type": "progress", "message": f"Starting Sector Analysis for: {sector}"})
            from sector_orchestrator import SectorOrchestrator
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
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


@app.get("/api/run/stock")
def run_stock(ticker: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(ticker)})
            q.put({"type": "progress", "message": f"Convening Council for ticker: {ticker}"})
            from orchestrator import AgentOrchestrator
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
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


@app.get("/api/run/quantum")
def run_quantum(mode: str = Query("fast")):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(f"QuanTum {mode}")})
            q.put({"type": "progress", "message": f"Initiating QuanTum Algorithmic Screener (Mode: {mode})"})
            from quantum_orchestrator import QuantumEngineOrchestrator
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
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


@app.get("/api/run/global-markets")
def run_global_markets(market_type: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(market_type)})
            q.put({"type": "progress", "message": f"Loading Global Macro orchestrator for: {market_type}"})
            from global_markets_orchestrator import (
                DevelopedMarketsOrchestrator,
                EmergingMarketsOrchestrator,
            )
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
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


@app.get("/api/run/news")
def run_news(scope: str = Query("global")):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(f"news desk ({scope})")})
            q.put({"type": "progress", "message": f"Connecting news parser. Scope: {scope}"})
            from news_tracker_orchestrator import NewsTrackerOrchestrator
            orchestrator = NewsTrackerOrchestrator()
            
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            news_data = orchestrator.run_analysis(scope=scope, progress_callback=callback)
            q.put({"type": "complete", "news": news_data})
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)


@app.get("/api/run/top-picks")
def run_top_picks(sector: str = Query(...)):
    q = queue.Queue()
    
    def run_pipeline():
        try:
            q.put({"type": "progress", "message": _editor_open(sector)})
            def callback(msg):
                q.put({"type": "progress", "message": msg})
                
            callback("Starting Top Picks screener...")
            import financial_analyst_cli as analyst
            from orchestrator import AgentOrchestrator
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
        except ImportError as e:
            q.put({"type": "error", "message": f"{_HEAVY_UNAVAILABLE} ({e})"})
        except Exception as e:
            q.put({"type": "error", "message": str(e)})
            
    threading.Thread(target=run_pipeline, daemon=True).start()
    return _sse_from_queue(q)

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
