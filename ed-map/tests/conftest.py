"""Pytest configuration — make `etl.py` importable without psycopg2 installed.

The parser functions in etl.py don't actually touch the database, but the
module imports psycopg2 at the top. We stub it out before importing etl so
the test suite can run in environments without psycopg2 (e.g. fresh CI).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def _stub_psycopg2() -> None:
    if "psycopg2" in sys.modules:
        return
    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.OperationalError = type("OperationalError", (Exception,), {})

    extras = types.ModuleType("psycopg2.extras")
    extras.execute_values = lambda *a, **kw: None
    extras.RealDictCursor = object

    psycopg2.extras = extras
    sys.modules["psycopg2"] = psycopg2
    sys.modules["psycopg2.extras"] = extras


# Make the package directory (parent of tests/) importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_stub_psycopg2()
