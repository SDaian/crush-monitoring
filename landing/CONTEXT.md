# Capitol Gains Landing

The marketing landing page for the politician-trades tracker. Its single job
is converting visitors into email subscribers for trade alerts; every number
it renders comes from real disclosure data.

## Language

**Disclosure**:
A single stock trade reported by a member of Congress — one row in the feed.
_Avoid_: trade alert, transaction, filing (a filing contains many disclosures)

**Filing**:
The report document (a Periodic Transaction Report) a member submits; one
filing may contain many disclosures.
_Avoid_: PTR (in user-facing copy), report

**Filing lag**:
The number of days between a disclosure's trade date and its filing date.
Lag up to 45 days is normal and legal — lag alone is not an accusation.
_Avoid_: delay, late (unless past the deadline)

**Late**:
A disclosure whose filing lag exceeds the 45-day statutory maximum of the
STOCK Act — an indisputable deadline violation. Chosen over the 30-day
awareness rule, which cannot be proven from public data.
_Avoid_: delayed, overdue, slow

**Days late**:
Filing lag minus 45; zero or negative means on time. This is what "Filed N
days late" renders.
_Avoid_: raw filing lag presented as lateness

**On time**:
Filed within the 45-day statutory maximum, even if the lag was weeks long.
_Avoid_: fast, prompt

**Amount bucket**:
The STOCK Act value bracket a disclosure reports (e.g. $1,001–$15,000).
Exact amounts are never disclosed and must never be implied.
_Avoid_: amount, value, size (unqualified)

**Recent disclosures**:
The landing feed: five real disclosures from the trailing window of
filings, distinct members, chosen for variety — a curated window, never
the literal five latest (that claim would need the header "Latest").
_Avoid_: latest disclosures, live feed (in copy; nav label is legacy)
