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


class TestMarkupHelpers(unittest.TestCase):
    """The exclusion must not hide a real comment sitting next to a block."""

    def test_style_and_script_bodies_are_excluded(self):
        self.assertNotIn("keep", markup("<style>/* keep */</style>"))
        self.assertNotIn("keep", markup("<script>// keep\n</script>"))

    def test_markup_outside_a_block_survives(self):
        self.assertIn("<!-- x -->",
                      markup("<style>a{}</style><!-- x --><script></script>"))
