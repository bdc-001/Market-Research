"""
Critic agent — converts one run's outcomes into permanent rules.

The pipeline learns in two places. Numbers are handled by WeightLearner, which
adjusts factor weights. Everything a number cannot express — a headline type
that keeps misleading the scanner, a report habit that misleads the reader — is
handled here: the critic writes short imperative rules into
`memory/learned_rules.md`, which is prepended to every later model call.

The critic runs with `with_memory=False` so it can reason about the current
rules instead of merely obeying them.
"""
import json
import logging

from agents.common import setup_gemini, clean_json
from agents.skill_loader import load_skill_body
from agents import memory
from agents.quantum_learning import accuracy_summary

logger = logging.getLogger(__name__)

MAX_NEW_RULES = 3


class CriticAgent:

    def run(self, week_picks=None, verification=None, ics=None,
            regime: str = "", progress_callback=None) -> dict:
        """
        Reviews the run and appends any rules worth keeping.
        Never raises: a failed critique must not fail the pipeline.
        """
        def update(msg):
            if progress_callback:
                progress_callback(msg)

        try:
            memory.restore_rules()
            context = self._context(week_picks, verification, ics, regime)
            if not context:
                return {"rules": [], "summary": "Nothing to review yet."}

            skill = load_skill_body("critic")
            model = setup_gemini(with_memory=False)
            response = model.generate_content(
                f"{skill}\n\n## Run under review\n\n{context}\n\n"
                f"## Rules already learned\n\n"
                f"{chr(10).join(memory.load_rules()) or '(none yet)'}\n"
            )
            payload = clean_json(response.text)
            rules = payload.get("rules", [])[:MAX_NEW_RULES]

            written = memory.append_rules(
                [self._format(r) for r in rules if r.get("text")]
            )

            if written:
                update(f"Critic added {len(written)} rule(s) to memory")
            return {"rules": written, "summary": payload.get("summary", "")}

        except Exception as exc:
            logger.debug("critic skipped: %s", exc)
            return {"rules": [], "summary": ""}

    @staticmethod
    def _format(rule: dict) -> str:
        category = (rule.get("category") or "General").strip()
        return f"Rule [0] - {category}: {rule.get('text', '').strip()}"

    def _context(self, week_picks, verification, ics, regime) -> str:
        parts = []

        if regime:
            parts.append(f"Market regime: {regime}")

        accuracy = accuracy_summary()
        if accuracy:
            parts.append(
                f"Verified signals: {accuracy['samples']}, "
                f"hit rate {accuracy['hit_rate']:.0%}, "
                f"average alpha {accuracy['avg_alpha']:.2f}%"
            )

        if verification:
            parts.append(
                f"Signals verified this run: {verification.get('verified', 0)}"
            )

        if ics:
            ranked = sorted(ics.items(), key=lambda kv: kv[1], reverse=True)
            parts.append(
                "Factor information coefficients: "
                + ", ".join(f"{f} {v:+.2f}" for f, v in ranked)
            )

        if week_picks is not None and not week_picks.empty:
            columns = [c for c in ["ticker", "composite_score", "conviction",
                                   "event_type", "news_catalyst"]
                       if c in week_picks.columns]
            rows = week_picks.head(5)[columns].to_dict("records")
            parts.append("This week's top picks:\n" + json.dumps(rows, default=str, indent=1))

        # Without outcome data there is nothing to generalise from.
        if not accuracy and not ics:
            return ""
        return "\n\n".join(parts)
