"""Resolve an OGE 278-T asset description to an equity ticker — or refuse.

The President's newer 278-Ts (June 2026 onward) disclose stocks and ETFs, not
only bonds, but the form has **no ticker column** and its OCR text layer
mangles names ("QUALM INC", "BOEING PANY"). Guessing a ticker from a garbled
name would put a false row on a real stock page, so this module's contract is
strict: **resolve exactly, or return None and say so**. The pipeline reports
every miss; a human adds it to the override map.

Two sources of truth, in order:

1. ``OVERRIDES`` — a curated map for names the OCR garbles or the index
   cannot know. Hand-maintained, like ``oge_filings.json``.
2. An index built from the trades we already publish: House and Senate rows
   carry both the asset name and its ticker, so ~13,000 rows vote on what
   each normalized name means. A name that maps to two different tickers is
   dropped as ambiguous rather than resolved by majority.

Pure stdlib; no I/O outside :func:`load_index`.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Bond / debt detection — these rows keep ticker=None on purpose
# ---------------------------------------------------------------------------
# A coupon percentage is the strongest tell (munis and corporates both carry
# one); the keywords catch the rest. Checked BEFORE any ticker resolution.
_COUPON = re.compile(r"\d(?:\.\d+)?\s*%")
_DEBT_WORDS = re.compile(
    r"\b(BOND|BONDS|NOTE|NOTES|DUE|PERP|MUNI|TREAS|TSY|T-?BILL|DEBENTURE|"
    r"REV|BD|OBLIG|CTF|B/E|B/Q|GO REF)\b",
    re.IGNORECASE,
)


_ETF = re.compile(
    r"\bETFS?\b|\bFUND\b|\bISHARES\b|\bSPDR\b|\bVANGUARD\b|"
    r"\bBULLETSHARES\b|\bPREFERRED\b|\bPFD\b", re.IGNORECASE)


def is_debt(asset: str) -> bool:
    """True for a bond/note/muni row. An ETF is never debt — a bond ETF
    trades as shares under a ticker, and the President's June 2026 filing
    holds several (iShares Treasury Bond ETF among them)."""
    if _ETF.search(asset):
        return False
    return bool(_COUPON.search(asset) or _DEBT_WORDS.search(asset))


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------
# OCR garbles seen in the real filings. Applied as whole-word fixes before
# suffix stripping, and only ones unambiguous enough to be safe.
_OCR_FIXES = {
    "PANY": "COMPANY",
    "PANIES": "COMPANIES",
    "QUALM": "QUALCOMM",
    "INCORPORA": "INCORPORATED",
    # Abbreviations the form uses where the congressional record spells out.
    "INTL": "INTERNATIONAL",
    "NATL": "NATIONAL",
    "FINL": "FINANCIAL",
    "SVCS": "SERVICES",
    "LABS": "LABORATORIES",
    "MFG": "MANUFACTURING",
    "RESH": "RESEARCH",
    "ENTMT": "ENTERTAINMENT",
    "SYS": "SYSTEMS",
    "SVC": "SERVICE",
    "PPTYS": "PROPERTIES",
    "PRODS": "PRODUCTS",
    "PROOUC": "PRODUCTS",
    "INSTRS": "INSTRUMENTS",
    "INTERNTNL": "INTERNATIONAL",
    "JPMORGAN": "JP MORGAN",
    "GROUO": "GROUP",
    "UNSOLICITEO": "UNSOLICITED",
}
# Corporate furniture that varies between filings of the same company.
_SUFFIXES = re.compile(
    r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|COMPANIES|PLC|LTD|LLC|"
    r"GROUP|HOLDINGS|HLDGS|THE|NEW)\b\.?",
)
_CLASS_TAIL = re.compile(
    r"\b(CLASS\s+[A-C]\b|CL\s+[A-C]\b|CLASS|SERIES\s+[A-C]\b|SERIES|"
    r"COMMON|ORDINARY|SHARES|SHS|STOCK|ADR|ADS|COM|"
    r"UNSOLICITED|SOLICITED|EQUITY|REIT|DEL|MASS|ORDER|"
    r"SPONSORED|AMERICAN\s+DEPOSITARY(?:\s+SHARES?)?|USD?\s*[\d.]+(?:\s+\d+)*)\b\.?",
)
_NON_ALNUM = re.compile(r"[^A-Z0-9 ]+")


_GLUED_SUFFIX = re.compile(r"(?<=[A-Z]{3})(INC|CORP|INTL)\b")


def normalize_name(asset: str) -> str:
    """A canonical key for an asset name: OCR-fixed, de-suffixed, squashed."""
    # Apostrophes vanish rather than becoming spaces: the filing writes
    # MCDONALDS where the record writes McDonald's, and the two must key
    # the same. Glued suffixes (RESMEDINC, AUTOZONEINC) split off; the
    # lookbehind wants three letters first, so ZINC stays a metal.
    up = asset.upper().replace("'", "").replace("\u2019", "")
    # Character-level OCR damage: "!" for I ("!SHARES"), "CU\\SS" for CLASS.
    up = up.replace("!", "I").replace("CU\\SS", "CLASS")
    up = _GLUED_SUFFIX.sub(r" \1", up)
    words = [_OCR_FIXES.get(w, w) for w in up.split()]
    up = " ".join(words)
    up = _NON_ALNUM.sub(" ", up)
    up = _CLASS_TAIL.sub(" ", up)
    up = _SUFFIXES.sub(" ", up)
    up = re.sub(r"\s+", " ", up).strip()
    return re.sub(r"(?:\s+[A-Z])+$", "", up)


# ---------------------------------------------------------------------------
# The curated override map — garbled or index-invisible names
# ---------------------------------------------------------------------------
# Keys are normalize_name() outputs. Add a line per reported miss; never let
# code guess. ETFs the congressional record rarely trades are listed here too.
OVERRIDES: dict[str, str] = {
    "QUALCOMM": "QCOM",
    "REPUBLIC SVCS": "RSG",
    "MOODYS": "MCO",
    "LENNOX INTL": "LII",
    "FACTSET RESH SYS": "FDS",
    "ROYAL CARIBBEAN": "RCL",
    "AXON ENTERPRISE": "AXON",
    "INTUIT": "INTU",
    "WALT DISNEY": "DIS",
    "MOTOROLA SOLUTIONS": "MSI",
    "BERKSHIRE HATHAWAY": "BRK.B",
    "T MOBILE US": "TMUS",
    "BROADRIDGE FINANCIAL SOLUTIONS": "BR",
    # June-2026 filing residue — names the congressional record never traded,
    # or OCR damage beyond mechanical repair. Each entry verified by hand.
    "FISERV": "FI",
    "MSA SAFETY": "MSA",
    "BANCFIRST": "BANF",
    "TRI POINTE HOMES": "TPH",
    "TRJ POINTE HOMES": "TPH",
    "BATH BODY WK": "BBWI",
    "BATH BODY WORKS": "BBWI",
    "COMCAST": "CMCSA",
    "CRH PUBLIC LIMITED": "CRH",
    "DUOLINGO": "DUOL",
    "OUOLINGO": "DUOL",
    "FLUTTER ENTERTAINMENT": "FLUT",
    "GRAPHIC PACKAGING HLDG": "PKG",
    "INGREDION": "INGR",
    "INGREOION": "INGR",
    "NETFLIX": "NFLX",
    "NEIFLIX": "NFLX",
    "NETFUX": "NFLX",
    "PILGRIMS PRIDE": "PPC",
    "PLANET FITNESS": "PLNT",
    "SHIFT4 PMTS": "FOUR",
    "SHIFT4 PAYMENTS": "FOUR",
    "TEMPUS AI": "TEM",
    "TWO HARBORS INVESTME": "TWO",
    "LWO HARBORS INVESTME": "TWO",
    "CSG SYS INTERNATIONAL": "CSGS",
    "ILLINOIS TOOL WKS": "ITW",
    "ALEXANDRIA REAL ESTATE": "ARE",
    "AMERICAN WTR WKS": "AWK",
    "AON": "AON",
    "AST SPACEMOBILE": "ASTS",
    "AT&T": "T",
    "BRIGHT HORIZONS FAMILY": "BFAM",
    "CARLISLE COS": "CSL",
    "CBRE": "CBRE",
    "CENCORA": "COR",
    "FIDELIIY NATI INFORMATIO": "FIS",
    "GENUINE PARTS": "GPC",
    "GRAINGER WW": "GWW",
    "INTERNTNL PAPER": "IP",
    "PG&E": "PCG",
    "PINTEREST": "PINS",
    "PUBLIC SVC ENTERPRISE GR": "PEG",
    "HCA HEALTHCARE": "HCA",
    "MERIT MEO SYS": "MMSI",
    "MERIT MED SYS": "MMSI",
    "MGE ENERGY": "MGEE",
    "MILLERKNOLL": "MLKN",
    "MISTER CAR WASH": "MCW",
    "MOHAWK INDS": "MHK",
    "MONRO": "MNRO",
    "MUELLER WATER PROOUC": "MWA",
    "MUELLER WATER PRODUC": "MWA",
    "NMI HLDGS": "NMIH",
    "NORTHERN OIL GAS": "NOG",
    "0 1 GLASS": "OI",
    "O 1 GLASS": "OI",
    "ONESPAWORLO HLDGS LTO": "OSW",
    "ONESPAWORLD HLDGS": "OSW",
    "OTTER TAIL": "OTTR",
    "OUTFRONT MEDIA": "OUT",
    "PALOMAR HLDGS": "PLMR",
    "PAR PAC HLDGS": "PARR",
    "GODADDY": "GDDY",
    "EQUIFAX": "EFX",
    "EXPEDIA": "EXPE",
    "GENERAL MILLS": "GIS",
    "DANAHER": "DHR",
    "DOCUSIGN": "DOCU",
    "ELF BEAUTY": "ELF",
    "E L F BEAUTY": "ELF",
    "AVANTOR": "AVTR",
    "AUTOZONE": "AZO",
    "RESMED": "RMD",
    "INSULET": "PODD",
    "ATLASSIAN": "TEAM",
    "ALBERTSONS": "ACI",
    "SMURFIT WESTROCK": "SW",
    "ABBOTT LABORATORIES": "ABT",
    "MCDONALDS": "MCD",
    "FAIR ISAAC": "FICO",
    "PHILIP MORRIS INTERNATIONAL": "PM",
    "HONEYWELL INTERNATIONAL": "HON",
    "VERIZON COMMUNICATIONS": "VZ",
    "INTERCONTINENTAL EXCHANG": "ICE",
    "INTUITIVE SURGICAL": "ISRG",
    "LENNAR": "LEN",
    "HUBSPOT": "HUBS",
    "NELFLIX": "NFLX",
    "FIDELLLY NATI INFORMATIO": "FIS",
    "TEMPUS AL": "TEM",
    "GODADDYLNC": "GDDY",
    "LIFE360": "LIF",
    # An old filing used the pre-2016 ticker BRCM, so the index drops
    # "BROADCOM" as ambiguous. The override settles it on the current one.
    "BROADCOM": "AVGO",
    "DISNEY WALT": "DIS",
    "FAIR ISMC": "FICO",
    "AMERISAFE": "AMSF",
    "TTM TECHNOLOGIES": "TTMI",
    "ALARM HLDGS": "ALRM",
    "OOORDASH": "DASH",
    "DOORDASH": "DASH",
    "CREDIT ACCEP MICH": "CACC",
    "CREDIT ACCEP": "CACC",
    "OLD DOMINION FGHT LINE": "ODFL",
    "CINNA GRAUE": "CI",
    "CIGNA": "CI",
    "AT TINC": "T",
    "ISHARES U S TREASURY BOND ETF": "GOVT",
    "PC CONNECTION": "CNXN",
    "PERDOCEO ED": "PRDO",
    "PERRIGO": "PRGO",
    "PHIBRO ANIMAL HEALTH COR": "PAHC",
    "PIPER SANDLER COS": "PIPR",
    "PLEXUS": "PLXS",
    "POWELL INDS": "POWL",
    "PRESTIGE CONSUMER HEALTH": "PBH",
    "PROTAGONIST THERAPEUTICS": "PTGX",
    "QUINSTREET": "QNST",
    "RADNET": "RDNT",
    "RED ROCK RESORTS": "RRR",
    "SKYWEST": "SKYW",
    "SOLAREDGE TECHNOLOGIES": "SEDG",
    "SOLAREOGE TECHNOLOGIES": "SEDG",
    "STEWART INFORMATION SERVICES": "STC",
    "SYLVAMO": "SLVM",
    "TELEPHONE DATA SYS": "TDS",
    "TG THERAPEUTICS": "TGTX",
    "TRIPADVISOR": "TRIP",
    "TRJPAOVISDR": "TRIP",
    "US PHYSICAL THERAPY": "USPH",
    "ULTRA CLEAN HLDGS": "UCTT",
    "UNIFIRST": "UNF",
    "VEECO INSTRUMENTS": "VECO",
    "BANCORP": "TBBK",
    "BANK HAWAII": "BOH",
    "BRADY": "BRC",
    "BRIGHTSPRING HEALTH": "BTSG",
    "CABLE ONE": "CABO",
    "CALIFORNIA RES": "CRC",
    "CARGURUS": "CARG",
    "CERTARA": "CERT",
    "COGENT COMMUNICATIONS": "CCOI",
    "COMSTOCK RES": "CRK",
    "CONOCOPHIUIPS": "COP",
    "CORE NAT RES": "CNR",
    "DORMAN PRODUCTS": "DORM",
    "EDISON INTERNATIONAL": "EIX",
    "EMBECTA": "EMBC",
    "ENVLRI": "NVRI",
    "ESSENTIAL PROPERTIES RLTY TR": "EPRT",
    "FRESH DEL MONTE PRODUCTS": "FDP",
    "G 111 APPAREL": "GIII",
    "GRIFFON": "GFF",
    "HUB": "HUBG",
    "J J SNACK FOODS": "JJSF",
    "KAYNE ANDERSON BOC": "KBDC",
    "KAYNE ANDERSON BDC": "KBDC",
    "KINETIK HLDGS": "KNTK",
    "KORN FERRY": "KFY",
    "KRYSTAL BIOTECH": "KRYS",
    "LYFT": "LYFT",
    "MASTERBRAND": "MBC",
    "MATERION": "MTRN",
    "MATTHEWS INTERNATIONAL": "MATW",
    "MEDICAL PROPERTIES TR": "MPW",
    "SAMSARA": "IOT",
    "GRID DYNAMICS HLDGS": "GDYN",
    "CACTUS": "WHD",
    "SEZZI": "SEZL",
    "SEZZLE": "SEZL",
    "NTNL BK HLDGS": "NBHC",
    "CLEANSPARK": "CLSK",
    "MACERICH": "MAC",
    "URBAN OUTFITTERS": "URBN",
    "APELLIS PHARMACEUTICALS": "APLS",
    "CORCEPT THERAPEUTICS": "CORT",
    "VIRTUS INVT PARTNERS": "VRTS",
    "TALEN ENERGY": "TLN",
    "DAVE BUSTERS ENTERTAINMENT": "PLAY",
    "PRMA HEALTH": "PRVA",
    "PRIVIA HEALTH": "PRVA",
    "TERAOYNE": "TER",
    "TERADYNE": "TER",
    "TRANSOIGM": "TDG",
    "TRANSDIGM": "TDG",
    "ZOETLS": "ZTS",
    "CH ROBINSON WORLDWIDE": "CHRW",
    "CHEVRON": "CVX",
    "HOWMET AEROSOACE": "HWM",
    "HOWMET AEROSPACE": "HWM",
    "COGNIZANT TECHNOLOGY SOLUTIONS": "CTSH",
    "WELLS FARGO": "WFC",
    "VANGUARD INTERMEDIATE TERM CORPORATE BOND INDEX FUND": "VCIT",
    "INNOVATIVE INOL PROPERTIES IN": "IIPR",
    "INNOVATIVE INDL PROPERTIES": "IIPR",
    "LXP INDUSTRIAL TRUST": "LXP",
    "XP INDUSTRIAL TRUST REI": "LXP",
    "ITRON": "ITRI",
}


# Keys are written naturally and normalized here, so an entry like
# "NMI HLDGS" works even though normalize_name strips HLDGS. Without this,
# an override whose key contains a stripped word can never match anything.
OVERRIDES = {normalize_name(k) or k: v for k, v in OVERRIDES.items()}


def build_index(trades: list[dict]) -> dict[str, str]:
    """name → ticker from rows that carry both. Ambiguous names are dropped."""
    votes: dict[str, set[str]] = defaultdict(set)
    for t in trades:
        tk = (t.get("ticker") or "").strip().upper()
        asset = t.get("asset") or ""
        if not tk or not asset or is_debt(asset):
            continue
        key = normalize_name(asset)
        if key:
            votes[key].add(tk)
    return {k: next(iter(v)) for k, v in votes.items() if len(v) == 1}


def load_index(path: str | Path) -> dict[str, str]:
    """The index from a published congress-trades.json; {} when unreadable."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return build_index(doc.get("trades") or [])


# Names where the share class picks the ticker. normalize_name strips class
# tails, so these match on the raw uppercase text before normalization.
CLASS_SENSITIVE = (
    ("ALPHABET", "CLASS A", "GOOGL"),
    ("ALPHABET", "CLASS C", "GOOG"),
)


def resolve(asset: str, index: dict[str, str]) -> str | None:
    """The ticker for an asset name, or None. Never a guess.

    After an exact miss, one deterministic fallback: the form truncates
    long names mid-word ("FIDELITY NATL INFORMATIO"), so a key that starts
    with the query (or vice versa) resolves — but only when the match is
    at least 10 characters and exactly ONE candidate exists across the
    overrides and the index together. Two candidates is ambiguity, and
    ambiguity is a refusal.
    """
    raw = asset.upper()
    for name, cls, tk in CLASS_SENSITIVE:
        if name in raw and cls in raw.replace("CU\\SS", "CLASS"):
            return tk

    def lookup(key: str) -> str | None:
        if key in OVERRIDES:
            return OVERRIDES[key]
        if key in index:
            return index[key]
        if len(key) < 10:
            return None
        hits = {tk for pool in (OVERRIDES, index) for k, tk in pool.items()
                if len(k) >= 10 and (k.startswith(key) or key.startswith(k))}
        return hits.pop() if len(hits) == 1 else None

    key = normalize_name(asset)
    if not key:
        return None
    got = lookup(key)
    if got:
        return got
    # A leading OCR-garbled row number ("n3 GENUINE PARTS CO"): drop the
    # first token and retry, but only after a full miss — a real leading
    # token like the 3M in "3M COMPANY" resolves on the first pass and
    # never reaches this retry.
    head, _, rest = key.partition(" ")
    if rest and len(head) <= 5:
        return lookup(rest)
    return None
