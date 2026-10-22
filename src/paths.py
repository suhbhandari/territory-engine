"""
Where a run's files live. A run is one metro and vertical.

With no run named, files are in outputs/raw/ and outputs/public/ (the shipped run). With
TE_RUN=<name> set (make <target> RUN=<name>), they are in outputs/raw/<name>/ and
outputs/public/<name>/, so a second run does not overwrite the first. Every step reads
its paths from here.
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

RUN = os.getenv("TE_RUN", "").strip()
if RUN and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", RUN) or RUN in ("runs", "public"):
    raise SystemExit(f"TE_RUN={RUN!r} is not a usable run folder name (letters, digits, - _ . only)")

RAW = ROOT / "outputs" / "raw" / RUN if RUN else ROOT / "outputs" / "raw"
PUBLIC = ROOT / "outputs" / "public" / RUN if RUN else ROOT / "outputs" / "public"
