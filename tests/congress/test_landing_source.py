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


class TestTheFoldCanAlwaysOpen(unittest.TestCase):
    """Member pages hide the disclosure rows past the fold from the first paint.

    A class on <html>, set by a head script, hides them until the trades
    script gives every row its own ``hidden``. If that class stayed on, the
    folded rows would be gone with no "Show all" button to bring them back,
    so it must come off on every path: the trades script removes it (also
    when it bails out early), and a ``load`` listener removes it when the
    trades script never ran at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = (SRC / "pages" / "members" / "[slug].astro").read_text(
            encoding="utf-8")
        scripts = re.findall(r"<script is:inline>(.*?)</script>", cls.src, re.S)
        cls.head = next((s for s in scripts if 'classList.add("tfold-on")' in s), "")
        cls.trades = next((s for s in scripts if 'getElementById("tfilter")' in s), "")

    def test_the_page_folds(self):
        self.assertTrue(self.head, "the head script that folds the rows is gone")
        self.assertTrue(self.trades, "the trades script is gone")

    def test_the_head_script_lets_go_on_load(self):
        self.assertRegex(
            self.head,
            r'addEventListener\("load",\s*function \(\) \{\s*'
            r'r\.classList\.remove\("tfold-on"\)')

    def test_the_trades_script_lets_go_on_every_path(self):
        self.assertIn('root.classList.remove("tfold-on")', self.trades)
        early = re.search(r"if \(!box \|\|[^)]*\) \{(.*?)\}", self.trades, re.S)
        self.assertIsNotNone(early, "the early return lost its braces")
        self.assertIn("unfold()", early.group(1))
        self.assertRegex(self.trades,
                         r"try \{\s*apply\(\);\s*\} finally \{\s*unfold\(\);")

    def test_one_fold_constant(self):
        # The build decides the first paint's fold; the script must use the
        # same number, read from the page, never a second literal.
        self.assertEqual(len(re.findall(r"const COLLAPSE_AT = \d+;", self.src)), 1)
        self.assertNotRegex(self.trades, r"COLLAPSE_AT\s*=\s*\d")
        self.assertIn('box.getAttribute("data-collapse-at")', self.trades)
        self.assertIn("data-collapse-at={COLLAPSE_AT}", self.src)

    def test_the_budget_check_knows_the_fold_class(self):
        # check-performance counts folded rows as not painted; a renamed
        # class would make every long member page read as over budget.
        check = (REPO_ROOT / "landing" / "scripts" / "check-performance.mjs"
                 ).read_text(encoding="utf-8")
        name = re.search(r'const FOLD_CLASS = "([\w-]+)";', check)
        self.assertIsNotNone(name, "check-performance.mjs lost FOLD_CLASS")
        self.assertIn(f'"trow", folded && "{name.group(1)}"', self.src)
        self.assertIn(f".{name.group(1)} {{\n    display: none;", self.src)


class TestNothingAboveTheGridAppearsLate(unittest.TestCase):
    """/tickers decides its controls and a linked industry before first paint.

    The filter bar, the star toggle and a ``?industry=`` deep link used to be
    applied by the script at the end of the body, after the grid had painted,
    and the grid jumped (CLS up to 0.31 on a phone). A head script now sets
    ``js``, ``has-stars`` and ``data-industry`` on <html> and CSS does the
    rest. Two things must hold: the state comes off on every path, or a
    linked industry would hide stocks with no way back; and the controls
    never carry ``hidden`` again, because Tailwind's ``[hidden]`` rule is
    ``!important`` in a layer and no class can show them over it.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = (SRC / "pages" / "tickers" / "index.astro").read_text(
            encoding="utf-8")
        head = re.search(r"<head>(.*?)</head>", cls.src, re.S)
        cls.head = head.group(1) if head else ""
        scripts = re.findall(r"<script is:inline>(.*?)</script>", cls.src, re.S)
        cls.grid = next((s for s in scripts if 'getElementById("tgrid")' in s), "")

    def test_the_head_decides_before_first_paint(self):
        self.assertIn('r.classList.add("js")', self.head)
        self.assertIn('r.setAttribute("data-industry", want)', self.head)
        self.assertIn('r.classList.add("has-stars")', self.head)
        self.assertIn("set:html={industryRules}", self.head)

    def test_the_head_lets_go_on_load(self):
        listener = re.search(r'addEventListener\("load", function \(\) \{(.*?)\}\);',
                             self.head, re.S)
        self.assertIsNotNone(listener, "the head script lost its load listener")
        self.assertIn('r.removeAttribute("data-industry")', listener.group(1))
        self.assertIn('hasAttribute("data-ready")', listener.group(1))

    def test_the_filter_script_lets_go_on_every_path(self):
        self.assertTrue(self.grid, "the /tickers filter script is gone")
        early = re.search(r"if \(!box \|\|[^{]*\{(.*?)\}", self.grid, re.S)
        self.assertIsNotNone(early, "the early return lost its braces")
        self.assertIn('root.removeAttribute("data-industry")', early.group(1))
        self.assertRegex(self.grid, r'\} finally \{\s*root\.removeAttribute\("data-industry"\);')
        self.assertIn('box.setAttribute("data-ready", "")', self.grid)

    def test_the_controls_never_carry_hidden(self):
        for element in ("tfilter", "tstars"):
            tag = re.search(rf'<[a-z]+\s[^>]*id="{element}"[^>]*>', self.src, re.S)
            self.assertIsNotNone(tag, f"#{element} is gone")
            self.assertNotRegex(tag.group(0), r"\shidden(\s|>|=)",
                                f"#{element} carries `hidden` again")


class TestTheTrackerHoldsItsPlace(unittest.TestCase):
    """The tracker's empty table holds a screen's height until its rows come.

    Without it the signup band below showed, then jumped off screen when the
    rows arrived: CLS 0.196 on a desktop's first visit, 0.263 on a repeat.
    The held space must be released by the first render and by a failed load.
    """

    @classmethod
    def setUpClass(cls):
        cls.src = (SRC / "pages" / "tracker.astro").read_text(encoding="utf-8")

    def test_the_wrapper_starts_pending(self):
        self.assertIn('<div class="tblwrap tbl-pending">', self.src)
        self.assertIn(".tracker .tblwrap.tbl-pending { min-height: 100vh; }", self.src)

    def test_the_space_is_released(self):
        release = 'closest(".tblwrap").classList.remove("tbl-pending")'
        render = re.search(r"function renderRows\(\)\{(.*?)\n      \}", self.src, re.S)
        self.assertIsNotNone(render, "renderRows is gone")
        self.assertIn(release, render.group(1))
        failed = re.search(r'\.catch\(\(\) => \{\s*\$\("countLine"\)(.*?)\}\);', self.src, re.S)
        self.assertIsNotNone(failed, "the trades file lost its failure path")
        self.assertIn(release, failed.group(1))


class TestOnlyHashedFilesAreImmutable(unittest.TestCase):
    """vercel.json lets browsers keep /_astro files for a year, unasked.

    Astro names every file there after a hash of its content, so a changed
    file arrives under a new name and the rule is always right. On any other
    path it would freeze the file: a page or the tracker's daily data would
    stay a year out of date in every browser that had seen it once.
    check-performance.mjs warns if an /_astro name ever lacks its hash.
    """

    def test_immutable_covers_only_the_hashed_folder(self):
        import json
        cfg = json.loads((REPO_ROOT / "landing" / "vercel.json").read_text())
        rules = cfg.get("headers", [])
        immutable = [r["source"] for r in rules
                     if any("immutable" in h["value"] or "max-age=31536000" in h["value"]
                            for h in r["headers"] if h["key"].lower() == "cache-control")]
        self.assertEqual(immutable, ["/_astro/(.*)"])


class TestPrivacyNamesWhatMeasures(unittest.TestCase):
    """Every measurement product the pages load is named on /privacy.

    The privacy page promises to say so before anything about tracking
    changes. Seo.astro is in every page's head, so a product imported there
    runs on every visit; the page must name it.
    """

    PRODUCTS = {
        "@vercel/analytics": "Vercel Web Analytics",
        "@vercel/speed-insights": "Vercel Speed Insights",
    }

    def test_each_product_in_the_head_is_named(self):
        seo = (SRC / "components" / "Seo.astro").read_text(encoding="utf-8")
        privacy = " ".join((SRC / "pages" / "privacy.astro").read_text(
            encoding="utf-8").split())
        imported = set(re.findall(r'from "(@vercel/[\w-]+)', seo))
        self.assertTrue(imported, "Seo.astro imports no measurement product")
        for pkg in imported:
            self.assertIn(pkg, self.PRODUCTS,
                          f"{pkg} runs on every page; add it here and name it on /privacy")
            self.assertIn(self.PRODUCTS[pkg], privacy, f"/privacy does not name {pkg}")


class TestMarkupHelpers(unittest.TestCase):
    """The exclusion must not hide a real comment sitting next to a block."""

    def test_style_and_script_bodies_are_excluded(self):
        self.assertNotIn("keep", markup("<style>/* keep */</style>"))
        self.assertNotIn("keep", markup("<script>// keep\n</script>"))

    def test_markup_outside_a_block_survives(self):
        self.assertIn("<!-- x -->",
                      markup("<style>a{}</style><!-- x --><script></script>"))
