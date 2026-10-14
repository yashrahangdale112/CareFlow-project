"""CareFlow - shared helper utilities."""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from functools import wraps
from typing import Any, Dict

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _abs(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def load_config(path: str = "config/config.yaml") -> Dict[str, Any]:
    with open(_abs(path), "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_root"] = PROJECT_ROOT
    return cfg


def ensure_dirs(cfg: Dict[str, Any]) -> None:
    for key in ("raw_events", "raw_cases", "processed"):
        os.makedirs(os.path.dirname(_abs(cfg["paths"][key])), exist_ok=True)
    for key in ("outputs", "figures", "models", "reports"):
        os.makedirs(_abs(cfg["paths"][key]), exist_ok=True)


def path_of(cfg: Dict[str, Any], key: str) -> str:
    """Resolve a config path key to an absolute path."""
    if key in cfg["paths"]:
        return _abs(cfg["paths"][key])
    return _abs(key)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def save_json(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(_abs(path)), exist_ok=True)
    with open(_abs(path), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, default=str)


def load_json(path: str) -> Any:
    with open(_abs(path), "r", encoding="utf-8") as fh:
        return json.load(fh)


def timed(label: str):
    """Decorator that logs how long a pipeline stage took."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            log = get_logger("careflow")
            log.info("START  %s", label)
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
            except Exception:
                log.exception("FAILED %s", label)
                raise
            log.info("DONE   %s  (%.2f s)", label, time.time() - t0)
            return result
        return wrapper
    return deco


def save_figure(fig, cfg: Dict[str, Any], filename: str, dpi: int = 150) -> str:
    out = os.path.join(path_of(cfg, "figures"), filename)
    fig.tight_layout()
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    return out
