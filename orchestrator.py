"""
Multi-Agent Orchestrator (The Council Coordinator)

Ticker → Evidence Acquisition (Python) → role-specific slices → agents.
Bull and Bear receive the same evidence set. Chartist receives a validated
scalar snapshot. Editor JSON is canonical; Python patches the memo verdict.
"""
import uuid
from agents.research_agent import ResearchAgent, MarketScout
from agents.bull_bear_agents import FinancialAgent, BullAgent, BearAgent
from agents.technical_agent import TechnicalAgent
from agents.editor_agent import EditorAgent
from agents.evidence_acquisition import acquire_evidence
from agents.evidence_validator import validate as validate_lineage
from agents.episode_store import write_council_episode
from agents.agent_trace import TraceLog


class AgentOrchestrator:
    def __init__(self):
        print("Initializing Council of Investors...")
        self.researcher = ResearchAgent()
        self.scout = MarketScout()
        self.quant = FinancialAgent()
        self.bull = BullAgent()
        self.bear = BearAgent()
        self.chartist = TechnicalAgent()
        self.editor = EditorAgent()
        self.last_trace = None
        self.last_evidence = None

    def run_analysis_pipeline(self, ticker: str, progress_callback=None, step_callback=None):
        def update_status(msg):
            if progress_callback:
                progress_callback(msg)
            else:
                print(msg)

        trace = TraceLog("council", f"Council · {ticker}", on_event=step_callback)
        symbol = ticker.strip().upper()

        update_status("Evidence Acquisition: filings, financials, news, prices...")
        trace.begin("evidence")
        package = acquire_evidence(symbol, progress=update_status)
        self.last_evidence = package
        debate_text = package.render("debate")
        hist_text = package.render("historian")
        scout_text = package.render("scout")
        quant_text = package.render("quant")
        index_text = package.render("editor", limit=80)

        def enforce_ids(agent, role, snapshot=None):
            parsed = getattr(agent, "last_parsed", None)
            if parsed is None:
                return
            validate_lineage(parsed, package, role, snapshot=snapshot)
            dropped = parsed.get("invalid_evidence_ids") or []
            if dropped:
                update_status(
                    f"Evidence validator: {role} {parsed.get('validator_status')} "
                    f"(dropped {dropped})"
                )

        trace.add(
            step_id="evidence",
            name="Evidence acquisition",
            kind="python",
            receives_from=["ticker"],
            sends_to=["Historian", "Scout", "Quant", "Bull", "Bear", "Chartist"],
            received=f"ticker={symbol}",
            passed=f"{len(package.items)} items, {len(package.errors)} errors, "
                   f"snapshot_valid={bool((package.market_snapshot or {}).get('valid'))}",
            note="Python only. Agents do not search.",
        )

        update_status("Research Agent: reading the evidence package...")
        trace.begin("research")
        research_data = self.researcher.run(symbol, hist_text)
        enforce_ids(self.researcher, "historian")
        trace.add_agent(
            self.researcher,
            step_id="research",
            name="Historian (Research)",
            receives_from=["Evidence store"],
            sends_to=["Editor"],
            received=hist_text,
        )

        update_status("Market Scout: reading news and competitors...")
        trace.begin("scout")
        market_data = self.scout.run(symbol, scout_text)
        enforce_ids(self.scout, "scout")
        trace.add_agent(
            self.scout,
            step_id="scout",
            name="Market Scout",
            receives_from=["Evidence store"],
            sends_to=["Editor"],
            received=scout_text,
        )

        update_status("Financial Agent: scoring supplied metrics...")
        trace.begin("financial")
        quant_verdict = self.quant.run(symbol, quant_text)
        enforce_ids(self.quant, "quant")
        trace.add_agent(
            self.quant,
            step_id="financial",
            name="Quant (Financials)",
            receives_from=["Evidence store"],
            sends_to=["Editor"],
            received=quant_text,
        )

        update_status("Bull Agent: arguing from the shared evidence set...")
        trace.begin("bull")
        bull_case = self.bull.run(symbol, debate_text)
        enforce_ids(self.bull, "debate")
        trace.add_agent(
            self.bull,
            step_id="bull",
            name="Bull",
            receives_from=["Evidence store (shared)"],
            sends_to=["Editor"],
            received=debate_text,
        )

        update_status("Bear Agent: arguing from the same evidence set...")
        trace.begin("bear")
        bear_case = self.bear.run(symbol, debate_text)
        enforce_ids(self.bear, "debate")
        trace.add_agent(
            self.bear,
            step_id="bear",
            name="Bear",
            receives_from=["Evidence store (shared)"],
            sends_to=["Editor"],
            received=debate_text,
        )

        update_status("Technical Analyst: interpreting the Python snapshot...")
        trace.begin("technical")
        technical_outlook = self.chartist.run(
            symbol,
            snapshot=package.market_snapshot,
            id_map=package.label_id_map("market"),
        )
        enforce_ids(self.chartist, "chartist", snapshot=package.market_snapshot)
        snap = getattr(self.chartist, "last_snapshot", None) or {}
        tech_received = "\n".join(f"{k}: {v}" for k, v in snap.items())
        trace.add_agent(
            self.chartist,
            step_id="technical",
            name="Chartist (Technicals)",
            receives_from=["Python technical snapshot"],
            sends_to=["Editor"],
            received=tech_received,
        )

        update_status("Editor Agent: canonical decision then memo...")
        editor_received = (
            f"── ticker ──\n{symbol}\n\n"
            f"── evidence index ──\n{index_text}\n\n"
            f"── from Historian ──\n{research_data}\n\n"
            f"── from Market Scout ──\n{market_data}\n\n"
            f"── from Quant ──\n{quant_verdict}\n\n"
            f"── from Bull ──\n{bull_case}\n\n"
            f"── from Bear ──\n{bear_case}\n\n"
            f"── from Chartist ──\n{technical_outlook}"
        )
        trace.begin("editor")
        final_report = self.editor.run(
            symbol,
            research_data,
            market_data,
            quant_verdict,
            bull_case,
            bear_case,
            technical_outlook,
            evidence_index=index_text,
        )
        enforce_ids(self.editor, "editor")
        trace.add_agent(
            self.editor,
            step_id="editor",
            name="Editor (Memo)",
            receives_from=["Historian", "Scout", "Quant", "Bull", "Bear", "Chartist"],
            sends_to=["UI report"],
            received=editor_received,
        )

        update_status("Analysis Complete!")
        self.last_trace = trace.as_dict()

        try:
            write_council_episode(
                symbol,
                str(uuid.uuid4()),
                {
                    "research": self.researcher,
                    "scout": self.scout,
                    "financial": self.quant,
                    "bull": self.bull,
                    "bear": self.bear,
                    "technical": self.chartist,
                    "editor": self.editor,
                },
                evidence=package.as_dict(),
            )
        except Exception:
            pass

        return final_report
