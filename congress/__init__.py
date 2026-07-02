"""Congressional stock-trade tracker.

Scrapes Periodic Transaction Reports (PTRs) from the two official sources —
the Senate eFD system (efdsearch.senate.gov) and the House Clerk
(disclosures-clerk.house.gov) — normalizes them into one trade schema and
accumulates them into ``docs/data/congress-trades.json`` for the GitHub
Pages tracker at ``docs/trades.html``.

Module layout mirrors ``predictor/``:

- ``normalize``: unified Trade schema, amount brackets, name canonicalization
  and roster join (pure stdlib).
- ``senate`` / ``house``: per-chamber listing + parsing. Parsing functions are
  pure stdlib functions of ``str``/``bytes`` so tests run offline; network
  access goes through ``http`` and PDF extraction lazily imports pdfplumber.
- ``pipeline``: incremental orchestration and JSON generation.
- ``cli``: argparse entry point (``python3 -m congress``).

Only ``congress/http.py`` imports ``requests`` and only
``house.extract_pdf_text`` imports ``pdfplumber`` — everything else runs on
the standard library (see ``congress/requirements.txt``).
"""

__all__ = ["normalize", "senate", "house", "pipeline", "cli"]
