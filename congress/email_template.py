"""Hand-authored, bulletproof HTML email template for the morning report.

Email clients are not browsers: Gmail strips `<head>`/`<style>`, Outlook renders
with Word's engine (no flexbox/grid/`max-width`), and web fonts only reach Apple
Mail. So this template is deliberately old-fashioned — **table-based layout with
inline styles**, a fixed ~600px centered column, web-safe font stacks, and a
hidden preheader. A `@media (prefers-color-scheme: dark)` block is included as a
best-effort nicety (clients that honour it get a dark card; the rest keep the
inline light look). It carries the Capitol Ledger identity via a **text
wordmark** — no hosted image to break.

Pure and offline-tested: every function returns an HTML string from structured
data, no I/O. `render_html` is the single entry point used by
`daily_report.build_report`.
"""

from __future__ import annotations

# --- Capitol Ledger palette (email-safe hex; mirrors the landing tokens) ---
INK = "#14161A"       # near-black text / masthead
PAPER = "#FBFBF9"     # card background
INK_SOFT = "#5A5E66"  # secondary text
STAMP = "#C8102E"     # accent (stamp red)
RULE = "#E3E2DC"      # hairlines
WASH = "#F4F3EE"      # page background / zebra
BUY = "#0A7D33"       # bull green
SELL = "#C0392B"      # bear red
HOLD = "#5A5E66"      # neutral

LABEL_COLOR = {
    "Strong Buy": BUY, "Buy": BUY,
    "Strong Sell": SELL, "Sell": SELL, "Hold": HOLD,
}

# Web-safe font stacks (no web fonts — only Apple Mail would load them).
SANS = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'Courier New',Courier,monospace"


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _chg_color(direction: int) -> str:
    return BUY if direction > 0 else (SELL if direction < 0 else INK_SOFT)


def _section(kicker: str, title: str, inner: str) -> str:
    """An editorial section: a mono uppercase kicker + bold title over a 2px
    rule, then the section body. Table-wrapped so Outlook keeps the spacing."""
    return (
        "<tr><td style='padding:26px 32px 0 32px'>"
        f"<div style='font:700 11px/1.4 {MONO};letter-spacing:1.5px;"
        f"text-transform:uppercase;color:{STAMP}'>{kicker}</div>"
        f"<div style='font:700 19px/1.3 {SANS};color:{INK};padding:2px 0 8px'>"
        f"{title}</div>"
        f"<div style='border-top:2px solid {INK};font-size:1px;line-height:1px'>"
        "&nbsp;</div>"
        "</td></tr>"
        f"<tr><td style='padding:12px 32px 0 32px'>{inner}</td></tr>"
    )


def scorecard_table(scorecard: list[dict]) -> str:
    """The featured-stocks read as a full-width, zebra-striped table.

    Each row: ``{ticker, price, chg, chg_dir, rsi, trend, label}`` (already
    formatted strings, plus ``chg_dir`` in {-1,0,1})."""
    if not scorecard:
        return (f"<p style='margin:0;font:14px/1.5 {SANS};color:{INK_SOFT}'>"
                "<i>No indicator data.</i></p>")
    heads = ("Ticker", "Price", "1d", "RSI", "Trend", "Read")
    aligns = ("left", "right", "right", "right", "left", "right")
    head_html = "".join(
        f"<th style='padding:6px 8px;text-align:{a};font:700 11px/1.3 {MONO};"
        f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT};"
        f"border-bottom:2px solid {RULE}'>{h}</th>"
        for h, a in zip(heads, aligns))
    body = []
    for i, r in enumerate(scorecard):
        bg = PAPER if i % 2 == 0 else WASH
        color = LABEL_COLOR.get(r["label"], HOLD)
        cells = (
            f"<td style='padding:7px 8px;font:700 13px/1.3 {MONO};color:{INK}'>"
            f"<b>{_esc(r['ticker'])}</b></td>"
            f"<td style='padding:7px 8px;text-align:right;font:13px/1.3 {MONO};"
            f"color:{INK}'>${_esc(r['price'])}</td>"
            f"<td style='padding:7px 8px;text-align:right;font:13px/1.3 {MONO};"
            f"color:{_chg_color(r['chg_dir'])}'>{_esc(r['chg'])}</td>"
            f"<td style='padding:7px 8px;text-align:right;font:13px/1.3 {MONO};"
            f"color:{INK}'>{_esc(r['rsi'])}</td>"
            f"<td style='padding:7px 8px;font:13px/1.3 {MONO};color:{INK_SOFT}'>"
            f"{_esc(r['trend'])}</td>"
            f"<td style='padding:7px 8px;text-align:right;font:700 12px/1.3 {SANS};"
            f"color:{color}'>{_esc(r['label'])}</td>")
        body.append(f"<tr style='background:{bg}'>{cells}</tr>")
    return (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;width:100%'><tr>{head_html}</tr>"
        + "".join(body) + "</table>"
        f"<p style='margin:8px 0 0;font:12px/1.5 {SANS};color:{INK_SOFT}'>"
        "Read = a rule-based tally of the indicators (each votes buy/hold/sell), "
        "not a recommendation.</p>")


def _list_block(items: list[str]) -> str:
    """A tight, bullet-less list styled as report lines."""
    rows = "".join(
        f"<tr><td style='padding:4px 0;font:14px/1.45 {SANS};color:{INK};"
        f"border-bottom:1px solid {RULE}'>{it}</td></tr>" for it in items)
    return ("<table role='presentation' width='100%' cellpadding='0' "
            f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")


def _empty(msg: str) -> str:
    return (f"<p style='margin:0;font:14px/1.5 {SANS};color:{INK_SOFT}'>"
            f"<i>{_esc(msg)}</i></p>")


def signals_block(signals: list[dict], flips: list[dict]) -> str:
    """New mechanical signals + rating flips, or a quiet-night line."""
    parts = []
    if signals:
        items = [f"<b style='font-family:{MONO}'>{_esc(s['ticker'])}</b> — "
                 f"{_esc(s.get('label', s.get('type', 'signal')))} "
                 f"<span style='color:{INK_SOFT}'>({_esc(s.get('asof', ''))})</span>"
                 for s in signals]
        parts.append(f"<p style='margin:0 0 4px;font:700 12px/1.4 {MONO};"
                     f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                     "New signals</p>" + _list_block(items))
    if flips:
        items = []
        for f in flips:
            color = LABEL_COLOR.get(f["label"], HOLD)
            items.append(
                f"<b style='font-family:{MONO}'>{_esc(f['ticker'])}</b>: "
                f"{_esc(f['prev'])} → <span style='color:{color};font-weight:700'>"
                f"{_esc(f['label'])}</span>")
        parts.append(f"<p style='margin:14px 0 4px;font:700 12px/1.4 {MONO};"
                     f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                     "Rating changes</p>" + _list_block(items))
    if not parts:
        return _empty("No new signals or rating changes since yesterday.")
    return "".join(parts)


def disclosures_block(disclosures: list[dict], extra: int) -> str:
    """Recent congressional disclosures as report lines (date · who · TICKER …)."""
    if not disclosures:
        return _empty("No new disclosures in this window.")
    items = []
    for d in disclosures:
        items.append(
            f"<span style='color:{INK_SOFT};font-family:{MONO};font-size:12px'>"
            f"{_esc(d['filing_date'])}</span> · {_esc(d['who'])} · "
            f"<b style='font-family:{MONO}'>{_esc(d['name'])}</b> "
            f"{_esc(d['type'])} · <span style='color:{INK_SOFT}'>"
            f"{_esc(d['amount'])}</span>")
    html = _list_block(items)
    if extra > 0:
        html += (f"<p style='margin:8px 0 0;font:12px/1.5 {SANS};color:{INK_SOFT}'>"
                 f"<i>…and {extra} more.</i></p>")
    return html


def _prettify_slug(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def traffic_block(traffic: dict, member_names: dict | None = None) -> str:
    """The Vercel traffic summary as a brand-styled inner block, from the
    ``analytics.daily_summary`` dict. Returns '' if there is nothing to show."""
    if not traffic:
        return ""
    total = traffic.get("total")
    pages = traffic.get("pages") or []
    member_pages = traffic.get("memberPages") or []
    names = member_names or {}
    total_txt = f"{total:,} page views" if total is not None else "views unavailable"
    html = (f"<p style='margin:0;font:700 20px/1.2 {MONO};color:{INK}'>"
            f"{_esc(total_txt)}</p>")
    if pages:
        rows = "".join(
            f"<tr><td style='padding:4px 0;font:13px/1.4 {MONO};color:{INK_SOFT};"
            f"border-bottom:1px solid {RULE}'>{_esc(p)}</td>"
            f"<td style='padding:4px 0;text-align:right;font:700 13px/1.4 {MONO};"
            f"color:{INK};border-bottom:1px solid {RULE}'>{v:,}</td></tr>"
            for p, v in pages)
        html += (f"<p style='margin:14px 0 4px;font:700 12px/1.4 {MONO};"
                 f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                 "Top pages</p>"
                 "<table role='presentation' width='100%' cellpadding='0' "
                 f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")
    if member_pages:
        def label(slug):
            return names.get(slug) or _prettify_slug(slug)
        rows = "".join(
            f"<tr><td style='padding:4px 0;font:13px/1.4 {SANS};color:{INK};"
            f"border-bottom:1px solid {RULE}'>{_esc(label(s))}</td>"
            f"<td style='padding:4px 0;text-align:right;font:700 13px/1.4 {MONO};"
            f"color:{INK};border-bottom:1px solid {RULE}'>{v:,}</td></tr>"
            for s, v in member_pages)
        html += (f"<p style='margin:14px 0 4px;font:700 12px/1.4 {MONO};"
                 f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                 "Member pages</p>"
                 "<table role='presentation' width='100%' cellpadding='0' "
                 f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")
    return html


def render_html(*, date_label: str, disclaimer: str, scorecard: list[dict],
                signals: list[dict], flips: list[dict],
                disclosures: list[dict], extra_disclosures: int, cutoff: str,
                traffic: dict | None, member_names: dict | None,
                tracker_url: str, preheader: str) -> str:
    """Assemble the full email document from structured data (pure)."""
    sections = [
        _section("Featured stocks", "Technical read",
                 scorecard_table(scorecard)),
        _section("Overnight", "Signals &amp; rating changes",
                 signals_block(signals, flips)),
        _section("Congress", f"New disclosures "
                 f"<span style='font-weight:400;font-size:13px;color:{INK_SOFT}'>"
                 f"(filed since {_esc(cutoff)})</span>",
                 disclosures_block(disclosures, extra_disclosures)),
    ]
    traffic_inner = traffic_block(traffic, member_names)
    if traffic_inner:
        sections.append(_section("Audience", "Site traffic", traffic_inner))

    body_rows = "".join(sections)
    disc_txt = _esc(disclaimer.replace("**", ""))

    return f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>Capitol Ledger — Morning report</title>
<style>
  /* Light-only by design: the card is a "paper" sheet. Partial dark-mode
     styling renders worse than none across email clients, so we opt out of
     auto-inversion (color-scheme:light) and keep one predictable theme. */
  @media (max-width:620px){{
    .cl-pad{{padding-left:18px!important;padding-right:18px!important}}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{WASH};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
{_esc(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{WASH};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:{PAPER};border:1px solid {RULE};border-collapse:collapse;">

  <!-- Masthead -->
  <tr><td class="cl-pad" style="padding:30px 32px 22px 32px;">
    <div style="border-top:3px double {INK};font-size:1px;line-height:1px;">&nbsp;</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td style="padding:14px 0 0;font:700 22px/1 {SANS};letter-spacing:3px;text-transform:uppercase;color:{INK};">
        Capitol&nbsp;Ledger</td>
      <td align="right" style="padding:14px 0 0;font:700 11px/1.4 {MONO};letter-spacing:1px;text-transform:uppercase;color:{STAMP};">
        Morning<br>report</td>
    </tr></table>
    <div style="margin-top:6px;font:12px/1.4 {MONO};letter-spacing:.5px;color:{INK_SOFT};">
      {_esc(date_label)}</div>
    <div style="border-top:3px double {INK};font-size:1px;line-height:1px;margin-top:12px;">&nbsp;</div>
    <p style="margin:12px 0 0;font:12px/1.5 {SANS};color:{INK_SOFT};"><i>{disc_txt}</i></p>
  </td></tr>

  {body_rows}

  <!-- Footer -->
  <tr><td class="cl-pad" style="padding:28px 32px 30px 32px;">
    <div style="border-top:1px solid {RULE};font-size:1px;line-height:1px;">&nbsp;</div>
    <p style="margin:16px 0 0;font:13px/1.5 {SANS};color:{INK};">
      <a href="{tracker_url}" style="color:{STAMP};font-weight:700;text-decoration:none;">
        Open the full tracker →</a></p>
    <p style="margin:10px 0 0;font:11px/1.6 {SANS};color:{INK_SOFT};">
      Mechanical technical readings from past daily closes and official STOCK Act
      disclosures (30–45-day legal lag; bracketed amounts). Not investment advice.<br>
      Capitol Ledger · a public-data project.<br>
      <a href="#" style="color:{INK_SOFT};text-decoration:underline;">Unsubscribe</a>
      &nbsp;·&nbsp; You are receiving this because you subscribed to trade alerts.</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
