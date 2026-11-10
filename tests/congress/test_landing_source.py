"""The landing sources must not leak authoring notes into the page source.

Astro strips ``{/* … */}`` comments at build time and **keeps** ``<!-- … -->``
ones. Twenty-five HTML comments in the components once became 686 comments and
132 KB of internal rationale across 124 published pages: every reader who
opened View Source read the design notes.

So this test bans HTML comments in ``.astro`` files outright. Explain the code
in the frontmatter (``// …``) or in a JSX comment; both stay in the repo and
neither reaches a reader. It runs in the offline suite the daily Action runs
before anything else, next to ``test_workflow_paths.py`` — same idea: a rule
that only holds while someone remembers it does not hold.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "landing" / "src"
# CSS and JS blocks are not markup; "<!--" cannot appear there as a comment,
# but a string or a selector could contain it, so they are excluded.
BLOCK = re.compile(r"<(style|script)\b.*?</\1>", re.S | re.I)


def astro_files():
    return sorted(SRC.rglob("*.astro"))


def markup(text: str) -> str:
    return BLOCK.sub(" ", text)


class TestNoHtmlComments(unittest.TestCase):
    def test_the_sources_exist(self):
        # A path typo would make every assertion below vacuously true.
        self.assertTrue(len(astro_files()) > 10, "no .astro sources found")

    def test_no_html_comments_in_astro_markup(self):
        offenders = []
        for path in astro_files():
            body = markup(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"<!--(.*?)-->", body, re.S):
                line = body[: match.start()].count("\n") + 1
                snippet = " ".join(match.group(1).split())[:60]
                offenders.append(
                    f"{path.relative_to(REPO_ROOT)}:{line}: {snippet}")
        self.assertEqual(
            offenders, [],
            "HTML comments ship to the published page. Use {/* … */} in the "
            "markup or // in the frontmatter:\n  " + "\n  ".join(offenders))


class TestTheTrackerDecidesNothing(unittest.TestCase):
    """One scoring implementation: congress/indicators.py.

    The tracker's Featured tab used to recompute the buy/sell/hold read in
    JavaScript, a twin kept in step by a note in CLAUDE.md. It now renders the
    score stored in ai-indicators.json. These tests fail if a decision comes
    back to the page, or if Python casts a vote the page cannot word.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = (SRC / "pages" / "tracker.astro").read_text(encoding="utf-8")

    def test_the_twin_is_gone(self):
        self.assertNotIn("aiScore", self.src)
        self.assertIn("a.score", self.src)

    def test_no_threshold_lives_on_the_page(self):
        # The label cut-offs, the RSI zones and any comparison of two readings.
        for pattern, what in (
            (r"ratio\s*[<>]=?", "a label cut-off"),
            (r"[<>]=?\s*-?0\.(15|5)\b", "a label cut-off"),
            (r"rsi14\s*[<>]\s*\d", "an RSI threshold"),
            (r"\b[<>]\s*(30|70)\b", "an RSI threshold"),
            (r"a\.(price|sma50|sma200|ema8|ema21)\s*[<>]=?\s*a\.", "a comparison of two readings"),
            (r"a\.chg_1[mw]\s*[<>]", "a momentum test"),
        ):
            found = re.search(pattern, self.src)
            self.assertIsNone(
                found, f"tracker.astro decides again ({what}): "
                       f"{found.group(0) if found else ''!r}")

    def test_every_vote_python_can_cast_has_its_words(self):
        from congress import indicators
        full = {"price": 10.0, "ema8": 11.0, "ema21": 10.5, "sma50": 9.0,
                "sma200": 8.0, "rsi14": 50.0, "chg_1m": 1.0, "chg_1w": 1.0}
        cast = {v["key"] for v in indicators.votes(full)}
        block = re.search(r"const VOTE_TEXT = \{(.*?)\n      \};", self.src, re.S)
        self.assertIsNotNone(block, "the tracker lost its VOTE_TEXT table")
        worded = set(re.findall(r"^\s{8}(\w+):", block.group(1), re.M))
        self.assertEqual(worded, cast)


class TestMarkupHelpers(unittest.TestCase):
    """The exclusion must not hide a real comment sitting next to a block."""

    def test_style_and_script_bodies_are_excluded(self):
        self.assertNotIn("keep", markup("<style>/* keep */</style>"))
        self.assertNotIn("keep", markup("<script>// keep\n</script>"))

    def test_markup_outside_a_block_survives(self):
        self.assertIn("<!-- x -->",
                      markup("<style>a{}</style><!-- x --><script></script>"))
