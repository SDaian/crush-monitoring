#!/usr/bin/env bash
#
# Dispatch the daily Congress trades refresh from an external scheduler.
#
# GitHub cron runs in UTC and drops runs, so it cannot hold a 09:00 Madrid
# slot. A Raspberry Pi cron runs this script instead; the job itself still
# runs on GitHub's runners. See ROADMAP.md ("Scheduling") for why execution
# stayed on GitHub rather than moving to a self-hosted runner.
#
# Install on the scheduler machine:
#
#   curl -fsSL -o ~/capitol-ledger-dispatch.sh \
#     https://raw.githubusercontent.com/SDaian/crush-monitoring/main/scripts/capitol-ledger-dispatch.sh
#   chmod 700 ~/capitol-ledger-dispatch.sh
#
# Then write a fine-grained token (repo SDaian/crush-monitoring, Actions:
# Read and write) to ~/.capitol-ledger.env as GH_TOKEN=..., mode 600, and
# add to `crontab -e`:
#
#   0 9 * * * $HOME/capitol-ledger-dispatch.sh
#
# The workflow gets scheduled=true, NOT report=true. That distinction is
# load-bearing: `scheduled` sends the morning report while keeping the
# per-day idempotency and the quiet-day skip, while `report` forces
# delivery and would email a duplicate on every quiet day.

set -euo pipefail

REPO="${CL_REPO:-SDaian/crush-monitoring}"
WORKFLOW="${CL_WORKFLOW:-congress-trades.yml}"
REF="${CL_REF:-main}"
ENV_FILE="${CL_ENV_FILE:-$HOME/.capitol-ledger.env}"
LOG="${CL_LOG:-$HOME/capitol-ledger.log}"

log() { echo "$(date -Is) $*" >>"$LOG"; }

if [ ! -r "$ENV_FILE" ]; then
  log "FATAL: cannot read $ENV_FILE — put GH_TOKEN=... in it (chmod 600)"
  exit 1
fi
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

if [ -z "${GH_TOKEN:-}" ]; then
  log "FATAL: GH_TOKEN is empty in $ENV_FILE"
  exit 1
fi

body="/tmp/cl-dispatch.$$"
trap 'rm -f "$body"' EXIT

# Three attempts: a home connection drops, and a missed dispatch means a late
# email. The GitHub fallback cron covers a total failure, but it fires later.
for attempt in 1 2 3; do
  code=$(curl -sS -o "$body" -w '%{http_code}' -X POST \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/$REPO/actions/workflows/$WORKFLOW/dispatches" \
    -d "{\"ref\":\"$REF\",\"inputs\":{\"scheduled\":\"true\"}}") || code=000

  if [ "$code" = "204" ]; then
    log "dispatched OK (attempt $attempt)"
    exit 0
  fi

  # 404 here usually means the token cannot see the repo or lacks Actions
  # write — GitHub hides permission failures behind 404, not 403.
  log "attempt $attempt failed http=$code $(tr -d '\n' <"$body")"
  [ "$attempt" -lt 3 ] && sleep $((attempt * 30))
done

log "GAVE UP after 3 attempts — the 08:20 UTC fallback cron should still run"
exit 1
