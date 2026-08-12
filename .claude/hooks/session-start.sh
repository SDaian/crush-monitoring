#!/bin/bash
# SessionStart hook: install what the tests, the build and the live fetch need.
#
# Claude Code on the web starts from a fresh clone, so a session that wants to
# run `congress fetch` or build the landing site would otherwise stop to
# install first. This runs before the session starts, and the container state
# is cached afterwards.
#
# Local sessions skip it. Your machine has its own environment, and a hook that
# reinstalls on every `claude` invocation is a tax.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# 1. Python, in a virtualenv.
#
#    Not `pip install --break-system-packages`: that mixes pip wheels into the
#    Debian-managed tree, and the import then resolves Debian's `cryptography`,
#    which this image ships without its `cffi` dependency. pdfplumber imports
#    pdfminer.six imports cryptography, so the whole House PDF path dies with
#    a pyo3 panic. A clean venv takes cryptography from pip with its own cffi
#    wheel and touches nothing outside the repo.
#
#    The offline suites need none of this (the parsers stay stdlib-importable),
#    but `congress fetch` and `congress holdings` do.
echo "session-start: python virtualenv"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade pip
./.venv/bin/python -m pip install --quiet --disable-pip-version-check \
  -r congress/requirements.txt

# Point the session at the venv. Without this the agent runs the system
# python3 and wonders why `import pdfplumber` fails.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$PWD/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  echo "export VIRTUAL_ENV=\"$PWD/.venv\"" >> "$CLAUDE_ENV_FILE"
fi

# 2. Root npm: Playwright, for the social card renderer and the on-demand
#    UI/API checks. `install`, not `ci`: it is a no-op when the tree already
#    matches, which is what makes a cached container start fast.
#    The browser is preinstalled at PLAYWRIGHT_BROWSERS_PATH, so this must
#    never run `playwright install`.
echo "session-start: root npm dependencies"
npm install --no-audit --no-fund --loglevel=error

# 3. The landing site (Astro + Tailwind). Its build also runs the SEO and copy
#    checks, so this is what makes `npm run build` work inside a session.
echo "session-start: landing npm dependencies"
npm install --prefix landing --no-audit --no-fund --loglevel=error

echo "session-start: done"
