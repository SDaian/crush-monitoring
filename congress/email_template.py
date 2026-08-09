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
# The multi-word family names MUST be quoted in CSS, but a literal ' would
# close our single-quoted style='…' attributes and silently drop every
# property after font-family (that is what made titles render plain). Use the
# &#39; entity: the HTML parser decodes it back to ' before the CSS parser sees
# it, so the attribute stays intact in both single- and double-quoted contexts.
SANS = "-apple-system,&#39;Segoe UI&#39;,Roboto,Helvetica,Arial,sans-serif"
MONO = "&#39;Courier New&#39;,Courier,monospace"


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _chg_color(direction: int) -> str:
    return BUY if direction > 0 else (SELL if direction < 0 else INK_SOFT)


def _f(size: str, lh: str, fam: str, weight: int | None = None) -> str:
    """Long-form font CSS. The ``font`` *shorthand* is unreliable in email —
    Gmail's sanitizer can drop the whole declaration (and any sibling ``color``
    with it), which is why colours vanish — so always emit the properties
    separately."""
    w = f"font-weight:{weight};" if weight else ""
    return f"font-family:{fam};font-size:{size};line-height:{lh};{w}"


# Horizontal padding inside the card. The standalone document can shrink this
# with a media query; an embed cannot (no <head>), so it ships tighter to begin
# with — 6 scorecard columns simply do not fit 390px at 32px padding.
PAD = 32
PAD_EMBED = 16


def _section(kicker: str, title: str, inner: str, pad: int = PAD) -> str:
    """An editorial section: a mono uppercase kicker + bold title over a 2px
    rule, then the section body. Table-wrapped so Outlook keeps the spacing."""
    return (
        f"<tr><td style='padding:26px {pad}px 0 {pad}px'>"
        f"<div style='{_f('11px', '1.4', MONO, 700)}letter-spacing:1.5px;"
        f"text-transform:uppercase;color:{STAMP}'>{kicker}</div>"
        f"<div style='{_f('19px', '1.3', SANS, 700)}color:{INK};padding:2px 0 8px'>"
        f"{title}</div>"
        f"<div style='border-top:2px solid {INK};font-size:1px;line-height:1px'>"
        "&nbsp;</div>"
        "</td></tr>"
        f"<tr><td style='padding:12px {pad}px 0 {pad}px'>{inner}</td></tr>"
    )


BAND_COLOR = {"calm": BUY, "normal": HOLD, "elevated": SELL,
              "stressed": STAMP}


def market_line(reading: dict | None) -> str:
    """The market-wide volatility strip above the scorecard.

    One line: the label, the level, the day's move and the band. It is
    context for the readings below, never a signal — the note says which
    number it is, and the band is stated as our own convention."""
    if not reading:
        return ""
    color = BAND_COLOR.get(reading.get("band", ""), HOLD)
    move = ""
    if reading.get("chg_1d") is not None:
        chg = reading["chg_1d"]
        move = (f"<font color='{_chg_color(1 if chg > 0 else (-1 if chg < 0 else 0))}'>"
                f"{'+' if chg > 0 else ''}{_esc(chg)} pts</font>")
    return (
        f"<table role='presentation' width='100%' cellpadding='0' "
        f"cellspacing='0' style='border-collapse:collapse;background:{WASH};"
        f"border:1px solid {RULE};margin:0 0 14px'>"
        f"<tr><td style='padding:9px 10px'>"
        f"<span style='{_f('11px', '1.3', MONO, 700)}letter-spacing:.5px;"
        f"text-transform:uppercase;color:{INK_SOFT}'>Market</span>"
        f"<span style='{_f('13px', '1.4', MONO, 700)}color:{INK}'>"
        f"&nbsp;&nbsp;{_esc(reading['label'])} {_esc(reading['level'])}</span>"
        + (f"<span style='{_f('12px', '1.4', MONO)}'>&nbsp;{move}</span>"
           if move else "")
        + f"<span style='{_f('12px', '1.4', MONO, 700)}color:{color}'>"
          f"&nbsp;·&nbsp;{_esc(reading['bandLabel'])}</span>"
        f"<div style='margin:4px 0 0;{_f('11px', '1.45', SANS)}color:{INK_SOFT}'>"
        f"{_esc(reading['note'])} {_esc(reading['bandNote'])}</div>"
        f"</td></tr></table>"
    )


def scorecard_table(scorecard: list[dict]) -> str:
    """The featured-stocks read as a full-width, zebra-striped table.

    Each row: ``{ticker, price, chg, chg_dir, rsi, trend, label}`` (already
    formatted strings, plus ``chg_dir`` in {-1,0,1})."""
    if not scorecard:
        return (f"<p style='margin:0;{_f('14px', '1.5', SANS)}color:{INK_SOFT}'>"
                "<i>No indicator data.</i></p>")
    heads = ("Ticker", "Price", "1d", "RSI", "Trend", "Read")
    aligns = ("left", "right", "right", "right", "left", "right")
    head_html = "".join(
        f"<th style='padding:6px 4px;text-align:{a};{_f('11px', '1.3', MONO, 700)}"
        f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT};"
        f"border-bottom:2px solid {RULE}'>{h}</th>"
        for h, a in zip(heads, aligns))
    body = []
    for i, r in enumerate(scorecard):
        bg = PAPER if i % 2 == 0 else WASH
        color = LABEL_COLOR.get(r["label"], HOLD)
        # Colour rides on an inline <span>/<font> around the text — not the <td> —
        # so it survives even a client that strips a cell's style attribute.
        chg = (f"<font color='{_chg_color(r['chg_dir'])}'>{_esc(r['chg'])}</font>")
        read = (f"<font color='{color}'><b>{_esc(r['label'])}</b></font>")
        # Tickers with a public page become links back into the site (UTM-tagged
        # so Vercel analytics can attribute the email as a traffic source).
        sym = f"<b>{_esc(r['ticker'])}</b>"
        if r.get("url"):
            sym = (f"<a href='{r['url']}' style='color:{INK};"
                   f"text-decoration:none;border-bottom:1px solid {RULE}'>"
                   f"{sym}</a>")
        cells = (
            f"<td style='padding:7px 4px;{_f('13px', '1.3', MONO, 700)}color:{INK}'>"
            f"{sym}</td>"
            f"<td style='padding:7px 4px;text-align:right;{_f('13px', '1.3', MONO)}"
            f"color:{INK}'>${_esc(r['price'])}</td>"
            f"<td style='padding:7px 4px;text-align:right;{_f('13px', '1.3', MONO)}'>"
            f"{chg}</td>"
            f"<td style='padding:7px 4px;text-align:right;{_f('13px', '1.3', MONO)}"
            f"color:{INK}'>{_esc(r['rsi'])}</td>"
            f"<td style='padding:7px 4px;{_f('13px', '1.3', MONO)}color:{INK_SOFT}'>"
            f"{_esc(r['trend'])}</td>"
            f"<td style='padding:7px 4px;text-align:right;{_f('12px', '1.3', SANS, 700)}'>"
            f"{read}</td>")
        body.append(f"<tr style='background:{bg}'>{cells}</tr>")
    return (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse;width:100%'><tr>{head_html}</tr>"
        + "".join(body) + "</table>"
        f"<p style='margin:8px 0 0;{_f('12px', '1.5', SANS)}color:{INK_SOFT}'>"
        "Read = a rule-based tally of the indicators (each votes buy/hold/sell), "
        "not a recommendation.</p>")


def _list_block(items: list[str]) -> str:
    """A tight, bullet-less list styled as report lines."""
    rows = "".join(
        f"<tr><td style='padding:4px 0;{_f('14px', '1.45', SANS)}color:{INK};"
        f"border-bottom:1px solid {RULE}'>{it}</td></tr>" for it in items)
    return ("<table role='presentation' width='100%' cellpadding='0' "
            f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")


def _empty(msg: str) -> str:
    return (f"<p style='margin:0;{_f('14px', '1.5', SANS)}color:{INK_SOFT}'>"
            f"<i>{_esc(msg)}</i></p>")


def signals_block(signals: list[dict], flips: list[dict]) -> str:
    """New mechanical signals + rating flips, or a quiet-night line."""
    parts = []
    if signals:
        items = [f"<b style='font-family:{MONO}'>{_esc(s['ticker'])}</b> — "
                 f"{_esc(s.get('label', s.get('type', 'signal')))} "
                 f"<span style='color:{INK_SOFT}'>({_esc(s.get('asof', ''))})</span>"
                 for s in signals]
        parts.append(f"<p style='margin:0 0 4px;{_f('12px', '1.4', MONO, 700)}"
                     f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                     "New signals</p>" + _list_block(items))
    if flips:
        items = []
        for f in flips:
            color = LABEL_COLOR.get(f["label"], HOLD)
            items.append(
                f"<b style='font-family:{MONO}'>{_esc(f['ticker'])}</b>: "
                f"{_esc(f['prev'])} → <font color='{color}'><b>"
                f"{_esc(f['label'])}</b></font>")
        parts.append(f"<p style='margin:14px 0 4px;{_f('12px', '1.4', MONO, 700)}"
                     f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                     "Rating changes</p>" + _list_block(items))
    if not parts:
        return _empty("No new signals or rating changes since yesterday.")
    return "".join(parts)


def disclosures_block(disclosures: list[dict], extra: int,
                      report_url: str = "", bond_count: int = 0) -> str:
    """Recent stock/option disclosures as report lines (date · who ·
    TICKER …). Bond/muni filings are deliberately a COUNT, not rows —
    they drowned the signal (one senator's muni ladder is a dozen lines).
    The /report page shows the whole undivided picture, so that is where
    the count links."""
    if not disclosures:
        return (_empty("No new stock/option disclosures in this window.")
                + _bond_note(bond_count, report_url))
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
        # The email caps the list (clients clip long messages); the web edition
        # carries every one, so send the reader there rather than dead-ending.
        more = (f"<a href='{report_url}' style='color:{STAMP};font-weight:700;"
                f"text-decoration:none'>see all {extra + len(disclosures)} "
                "on the site →</a>") if report_url else f"…and {extra} more."
        html += (f"<p style='margin:8px 0 0;{_f('12px', '1.5', SANS)}color:{INK_SOFT}'>"
                 f"<i>…and {extra} more · </i>{more}</p>")
    return html + _bond_note(bond_count, report_url)


def _bond_note(bond_count: int, report_url: str) -> str:
    if not bond_count:
        return ""
    s = "s" if bond_count != 1 else ""
    link = (f"<a href='{report_url}' style='color:{INK_SOFT};"
            "text-decoration:underline'>see the full report</a>"
            if report_url else "see the full report")
    return (f"<p style='margin:8px 0 0;{_f('12px', '1.5', SANS)}"
            f"color:{INK_SOFT}'>…plus {bond_count} bond &amp; muni "
            f"filing{s} — {link}.</p>")


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
    html = (f"<p style='margin:0;{_f('20px', '1.2', MONO, 700)}color:{INK}'>"
            f"{_esc(total_txt)}</p>")
    if pages:
        rows = "".join(
            f"<tr><td style='padding:4px 0;{_f('13px', '1.4', MONO)}color:{INK_SOFT};"
            f"border-bottom:1px solid {RULE}'>{_esc(p)}</td>"
            f"<td style='padding:4px 0;text-align:right;{_f('13px', '1.4', MONO, 700)}"
            f"color:{INK};border-bottom:1px solid {RULE}'>{v:,}</td></tr>"
            for p, v in pages)
        html += (f"<p style='margin:14px 0 4px;{_f('12px', '1.4', MONO, 700)}"
                 f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                 "Top pages</p>"
                 "<table role='presentation' width='100%' cellpadding='0' "
                 f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")
    if member_pages:
        def label(slug):
            return names.get(slug) or _prettify_slug(slug)
        rows = "".join(
            f"<tr><td style='padding:4px 0;{_f('13px', '1.4', SANS)}color:{INK};"
            f"border-bottom:1px solid {RULE}'>{_esc(label(s))}</td>"
            f"<td style='padding:4px 0;text-align:right;{_f('13px', '1.4', MONO, 700)}"
            f"color:{INK};border-bottom:1px solid {RULE}'>{v:,}</td></tr>"
            for s, v in member_pages)
        html += (f"<p style='margin:14px 0 4px;{_f('12px', '1.4', MONO, 700)}"
                 f"letter-spacing:.5px;text-transform:uppercase;color:{INK_SOFT}'>"
                 "Member pages</p>"
                 "<table role='presentation' width='100%' cellpadding='0' "
                 f"cellspacing='0' style='border-collapse:collapse'>{rows}</table>")
    return html


def _footer(tracker_url: str, subscribe_note: str,
            unsubscribe: bool = True, pad: int = PAD) -> str:
    """Shared footer: tracker link, provenance/disclaimer, unsubscribe line.

    ``unsubscribe=False`` drops our line for broadcasts through a provider that
    injects a real one (Buttondown). Ours is a placeholder ``href='#'`` — fine
    in the owner's own copy, but a dead unsubscribe link in a mailing-list
    send is both a CAN-SPAM violation and a duplicate of the provider's."""
    return (
        f"<tr><td class='cl-pad' style='padding:28px {pad}px 30px {pad}px;'>"
        f"<div style='border-top:1px solid {RULE};font-size:1px;line-height:1px;'>"
        "&nbsp;</div>"
        f"<p style='margin:16px 0 0;{_f('13px', '1.5', SANS)}color:{INK};'>"
        f"<a href='{tracker_url}' style='color:{STAMP};font-weight:700;"
        "text-decoration:none;'>Open the full tracker →</a></p>"
        f"<p style='margin:10px 0 0;{_f('11px', '1.6', SANS)}color:{INK_SOFT};'>"
        "Mechanical technical readings from past daily closes and official STOCK "
        "Act disclosures (30–45-day legal lag; bracketed amounts). Not investment "
        "advice.<br>Capitol Ledger · a public-data project.<br>"
        + (f"<a href='#' style='color:{INK_SOFT};text-decoration:underline;'>"
           "Unsubscribe</a>&nbsp;·&nbsp; " if unsubscribe else "")
        + f"{_esc(subscribe_note)}</p></td></tr>")


def _card_rows(*, right_label: str, date_label: str, intro_html: str,
               body_rows: str, tracker_url: str, subscribe_note: str,
               unsubscribe: bool, pad: int = PAD) -> str:
    """The card's table rows: masthead, sections, footer. No outer chrome.

    An empty ``right_label`` renders the wordmark across the full row instead
    of beside a label. Newsletter providers print their own subject above the
    content, so repeating "MORNING REPORT" there is redundant — and that cell
    is what squeezed "CAPITOL LEDGER" onto two lines on a phone, since an
    embed has no <head> for the mobile media query to live in."""
    label_cell = (
        f'<td align="right" style="padding:14px 0 0;{_f("11px", "1.4", MONO, 700)}'
        f'letter-spacing:1px;text-transform:uppercase;color:{STAMP};'
        f'white-space:nowrap;">{right_label}</td>' if right_label else "")
    return f"""\
  <!-- Masthead -->
  <tr><td class="cl-pad" style="padding:30px {pad}px 22px {pad}px;">
    <div style="border-top:3px double {INK};font-size:1px;line-height:1px;">&nbsp;</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td class="cl-mark" style="padding:14px 0 0;{_f('21px', '1.15', SANS, 700)}letter-spacing:2px;text-transform:uppercase;color:{INK};">
        Capitol&nbsp;Ledger</td>
      {label_cell}
    </tr></table>
    <div style="margin-top:6px;{_f('12px', '1.4', MONO)}letter-spacing:.5px;color:{INK_SOFT};">
      {_esc(date_label)}</div>
    <div style="border-top:3px double {INK};font-size:1px;line-height:1px;margin-top:12px;">&nbsp;</div>
    {intro_html}
  </td></tr>

  {body_rows}

  {_footer(tracker_url, subscribe_note, unsubscribe, pad)}
"""


def _document(*, right_label: str, date_label: str, intro_html: str,
              body_rows: str, tracker_url: str, subscribe_note: str,
              title: str, preheader: str, standalone: bool = True) -> str:
    """The email, either as a complete document or as a bare embeddable card.

    ``standalone=True`` (SMTP, where we are the sender) returns a full
    document: page background, a centred fixed-width "paper" card with a
    border, the preheader, and the light-only ``<style>``.

    ``standalone=False`` returns ONLY the card's table, at width 100% with no
    page background, no border and no preheader. A newsletter provider already
    supplies the document, its own centred ~600px container and its own
    preview text — so repeating ours nests a bordered box inside their box,
    doubles the padding and squeezes the content. Fill their container instead
    of building a second one inside it."""
    rows = _card_rows(right_label=right_label if standalone else "",
                      date_label=date_label,
                      intro_html=intro_html, body_rows=body_rows,
                      tracker_url=tracker_url, subscribe_note=subscribe_note,
                      unsubscribe=standalone,
                      pad=PAD if standalone else PAD_EMBED)
    if not standalone:
        return (
            "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" "
            "cellspacing=\"0\" style=\"width:100%;border-collapse:collapse;"
            f"background:{PAPER};\">\n{rows}</table>")
    return f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{_esc(title)}</title>
<style>
  /* Light-only by design: the card is a "paper" sheet. Partial dark-mode
     styling renders worse than none across email clients, so we opt out of
     auto-inversion (color-scheme:light) and keep one predictable theme. */
  @media (max-width:620px){{
    .cl-pad{{padding-left:18px!important;padding-right:18px!important}}
    /* 22px + 3px tracking wraps "CAPITOL LEDGER" on a phone. */
    .cl-mark{{font-size:17px!important;letter-spacing:1.5px!important}}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:{WASH};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">
{_esc(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{WASH};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:{PAPER};border:1px solid {RULE};border-collapse:collapse;">
{rows}
</table>
</td></tr>
</table>
</body>
</html>"""


def render_html(*, date_label: str, disclaimer: str, scorecard: list[dict],
                signals: list[dict], flips: list[dict],
                disclosures: list[dict], extra_disclosures: int, cutoff: str,
                tracker_url: str, preheader: str, report_url: str = "",
                bond_count: int = 0, market: dict | None = None,
                coverage: list[str] | None = None,
                standalone: bool = True) -> str:
    """The daily trade/scorecard digest email (traffic is a separate email)."""
    pad = PAD if standalone else PAD_EMBED
    # Disclosures lead — they are the product; the scorecard supports.
    body_rows = "".join([
        _section("Congress", f"New disclosures "
                 f"<span style='font-weight:400;font-size:13px;color:{INK_SOFT}'>"
                 f"(filed since {_esc(cutoff)})</span>",
                 disclosures_block(disclosures, extra_disclosures,
                                   report_url, bond_count), pad),
        # The market strip leads the readings it gives context to.
        _section("Featured stocks", "Technical read",
                 market_line(market) + scorecard_table(scorecard), pad),
        _section("Overnight", "Signals &amp; rating changes",
                 signals_block(signals, flips), pad),
        # Owner's ops note: featured annual reports we could not parse.
        # Rendered only when gapped, so a clean day stays clean.
        (_section("Coverage", "Holdings we could not parse",
                  "".join(
                      f"<p style='margin:0 0 6px;{_f('13px', '1.5', MONO)}"
                      f"color:{INK}'>{_esc(g)}</p>" for g in coverage), pad)
         if coverage else ""),
    ])
    disc_txt = _esc(disclaimer.replace("**", ""))
    browser = (f"<p style='margin:10px 0 0;{_f('11px', '1.5', MONO)}'>"
               f"<a href='{report_url}' style='color:{INK_SOFT};"
               "text-decoration:underline'>View this report in your browser"
               "</a></p>") if report_url else ""
    intro = (f"<p style='margin:12px 0 0;{_f('12px', '1.5', SANS)}color:{INK_SOFT};'>"
             f"<i>{disc_txt}</i></p>" + browser)
    return _document(
        right_label="Morning report", date_label=date_label,
        intro_html=intro, body_rows=body_rows, tracker_url=tracker_url,
        subscribe_note="You are receiving this because you subscribed to trade alerts.",
        title="Capitol Ledger — Morning report", preheader=preheader,
        standalone=standalone)


def render_traffic_html(*, date_label: str, traffic: dict,
                        member_names: dict | None, tracker_url: str,
                        preheader: str) -> str:
    """The standalone site-traffic email (Vercel Web Analytics), same chrome."""
    days = traffic.get("windowDays", 7)
    intro = (f"<p style='margin:12px 0 0;{_f('12px', '1.5', SANS)}color:{INK_SOFT};'>"
             f"<i>Aggregated, cookieless page views over the last {days} days "
             "(Vercel Web Analytics).</i></p>")
    body_rows = _section("Audience", f"Site traffic "
                         f"<span style='font-weight:400;font-size:13px;color:{INK_SOFT}'>"
                         f"(last {days} days)</span>",
                         traffic_block(traffic, member_names))
    return _document(
        right_label="Traffic report", date_label=date_label,
        intro_html=intro, body_rows=body_rows, tracker_url=tracker_url,
        subscribe_note="Internal audience metrics for the Capitol Ledger project.",
        title="Capitol Ledger — Traffic report", preheader=preheader)
