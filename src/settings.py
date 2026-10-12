"""
Run defaults: the metro and vertical a script uses when none is passed on the command line.
They live in config/defaults.yaml so no script names a vertical itself.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent

with open(ROOT / "config" / "defaults.yaml") as _f:
    _DEFAULTS = yaml.safe_load(_f)

DEFAULT_VERTICAL = _DEFAULTS["vertical"]
DEFAULT_METRO = _DEFAULTS["metro"]
