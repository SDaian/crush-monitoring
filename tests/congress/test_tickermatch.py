"""The 278-T name→ticker resolver: exact or refused, never guessed.

The fixture rows are transcribed from page 8 of the real 22-August-2026
filing (1,000+ June trades), OCR garbles included — "BOEING PANY",
"QUALM INC". That page is the contract: every equity on it must resolve,
every bond must classify as debt, and an unknown name must return None.
"""

import unittest

from congress import tickermatch as tm

# name → expected ticker, straight from the filing page.
PAGE_8 = {
    "CINTAS CORP": "CTAS",
    "VISA INC-CLASS A SHARES": "V",
    "MASTERCARD INCORPORATED": "MA",
    "REPUBLIC SVCS INC": "RSG",
    "MOODYS CORP": "MCO",
    "T-MOBILE US INC USD0.001": "TMUS",
    "HOME DEPOT INC": "HD",
    "BOEING PANY": "BA",
    "TYLER TECHNOLOGIES INC": "TYL",
    "PAYCHEX INC": "PAYX",
    "STRYKER CORP": "SYK",
    "PROCTER & GAMBLE PANY": "PG",
    "LENNOX INTL INC": "LII",
    "INTUIT": "INTU",
    "FACTSET RESH SYS INC": "FDS",
    "FORTINET INC": "FTNT",
    "CROWDSTRIKE HLDGS INC": "CRWD",
    "PALO ALTO NETWORKS INC": "PANW",
    "SERVICENOW INC": "NOW",
    "CLOROX PANY": "CLX",
    "ROYAL CARIBBEAN GROUP": "RCL",
    "QUALM INC": "QCOM",
    "ECOLAB INC": "ECL",
    "AXON ENTERPRISE INC": "AXON",
    "APPLOVIN CORP": "APP",
    "Salesforce Inc.": "CRM",
    "WALT DISNEY PANY": "DIS",
    "CHIPOTLE MEXICAN GRILL INC": "CMG",
    "Blackstone Inc.": "BX",
    "BROADRIDGE FINL SOLUTIONS INC": "BR",
    "BERKSHIRE HATHAWAY INC CLASS B": "BRK.B",
}
BONDS = [
    "SCHWAB CHARLES CORP PERP SUB 4.0000%",
    "M & T BK CORP PERP SUB GLBL 3.5000%",
    "GENERAL MTRS FINL CO INC PER 6.5000%",
]
# A believable index, as build_index would produce it from published rows.
INDEX = tm.build_index([
    {"ticker": v, "asset": k} for k, v in {
        "Cintas Corporation - Common Stock": "CTAS",
        "Visa Inc.": "V",
        "Mastercard Inc": "MA",
        "Republic Services, Inc. Common Stock": "RSG",
        "T-Mobile US, Inc. Common Stock": "TMUS",
        "Home Depot, Inc. (The) Common Stock": "HD",
        "Boeing Company (The) Common Stock": "BA",
        "Tyler Technologies, Inc. Common Stock": "TYL",
        "Paychex, Inc. - Common Stock": "PAYX",
        "Stryker Corporation Common Stock": "SYK",
        "Procter & Gamble Company (The) Common Stock": "PG",
        "Intuit Inc. - Common Stock": "INTU",
        "Fortinet, Inc. - Common Stock": "FTNT",
        "CrowdStrike Holdings, Inc. - Class A Common Stock": "CRWD",
        "Palo Alto Networks, Inc.": "PANW",
        "ServiceNow, Inc. Common Stock": "NOW",
        "The Clorox Company Common Stock": "CLX",
        "Ecolab Inc. Common Stock": "ECL",
        "Applovin Corporation - Class A Common Stock": "APP",
        "Salesforce, Inc. Common Stock": "CRM",
        "Chipotle Mexican Grill, Inc. Common Stock": "CMG",
        "Blackstone Inc. Common Stock": "BX",
        "Berkshire Hathaway Inc. New Common Stock": "BRK.B",
        "Walt Disney Company (The) Common Stock": "DIS",
        "Lennox International, Inc. Common Stock": "LII",
        "FactSet Research Systems Inc. Common Stock": "FDS",
        "Royal Caribbean Group Common Stock": "RCL",
        "Moody's Corporation Common Stock": "MCO",
        "Axon Enterprise, Inc. Common Stock": "AXON",
        "Broadridge Financial Solutions, Inc. Common Stock": "BR",
    }.items()
])


class TestPage8(unittest.TestCase):
    def test_every_equity_on_the_page_resolves(self):
        for asset, want in PAGE_8.items():
            self.assertFalse(tm.is_debt(asset), asset)
            self.assertEqual(tm.resolve(asset, INDEX), want, asset)

    def test_every_bond_on_the_page_classifies_as_debt(self):
        for asset in BONDS:
            self.assertTrue(tm.is_debt(asset), asset)

    def test_an_unknown_name_is_refused_not_guessed(self):
        self.assertIsNone(tm.resolve("SOME NEW LISTING NOBODY TRADED", INDEX))


class TestIndex(unittest.TestCase):
    def test_ambiguous_names_are_dropped(self):
        idx = tm.build_index([
            {"ticker": "GOOG", "asset": "Alphabet Inc."},
            {"ticker": "GOOGL", "asset": "Alphabet Inc."},
        ])
        self.assertNotIn(tm.normalize_name("Alphabet Inc."), idx)

    def test_debt_rows_never_enter_the_index(self):
        idx = tm.build_index([
            {"ticker": "XX", "asset": "Something Corp Notes 4.5% due 2031"},
        ])
        self.assertEqual(idx, {})

    def test_missing_fields_are_skipped(self):
        self.assertEqual(tm.build_index([{"asset": "A"}, {"ticker": "B"}]), {})


class TestNormalize(unittest.TestCase):
    def test_digit_bearing_names_survive(self):
        # The par-value stripper must not eat a real "3M".
        self.assertEqual(tm.normalize_name("3M Company Common Stock"), "3M")

    def test_par_value_tail_is_stripped(self):
        self.assertEqual(tm.normalize_name("T-MOBILE US INC USD0.001"),
                         "T MOBILE US")


if __name__ == "__main__":
    unittest.main()
