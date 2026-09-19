"""Deterministic evidence gate. Below the thresholds the answering model is NEVER called."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Evidence, Hit

ROOT = Path(__file__).resolve().parent.parent
THRESHOLD_FILE = ROOT / "eval" / "thresholds.json"


@dataclass
class GateConfig:
    tau_sem: float = 0.62  # placeholder until calibrated on the evaluation set
    tau_cov: float = 0.50
    calibrated: bool = False
    min_query_terms: int = 2


@dataclass
class GateDecision:
    passed: bool
    reason: str
    top_sem: float
    top_cov: float
    hits: list  # the hits allowed through to the model


def load_config(path: Path = THRESHOLD_FILE) -> GateConfig:
    if path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        return GateConfig(tau_sem=d["tau_sem"], tau_cov=d["tau_cov"], calibrated=bool(d.get("calibrated", True)))
    return GateConfig()


def save_config(cfg: GateConfig, path: Path = THRESHOLD_FILE, note: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    d = asdict(cfg)
    d["note"] = note
    path.write_text(json.dumps(d, indent=2), encoding="utf-8")


def decide(ev: Evidence, cfg: GateConfig) -> GateDecision:
    """Pass only if the best-ranked chunk clears BOTH thresholds. Only chunks that clear the
    semantic threshold are handed to the model, so weakly related text never reaches it."""
    if not ev.hits:
        return GateDecision(False, "no chunks retrieved", 0.0, 0.0, [])
    best: Hit = ev.hits[0]
    ok = best.sem >= cfg.tau_sem and best.coverage >= cfg.tau_cov
    if not ok:
        why = []
        if best.sem < cfg.tau_sem:
            why.append(f"similarity {best.sem:.2f} < {cfg.tau_sem:.2f}")
        if best.coverage < cfg.tau_cov:
            why.append(f"term coverage {best.coverage:.2f} < {cfg.tau_cov:.2f}")
        return GateDecision(False, "; ".join(why), best.sem, best.coverage, [])
    allowed = [h for h in ev.hits if h.sem >= cfg.tau_sem]
    return GateDecision(True, "passed", best.sem, best.coverage, allowed)
