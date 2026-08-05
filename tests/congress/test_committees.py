"""Offline tests for congress.committees (join + classification are pure)."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from congress import committees

# Two real committees plus a subcommittee each, in the source's shape.
COMMITTEES = [
    {"type": "house", "thomas_id": "HSSY",
     "name": "House Committee on Science, Space, and Technology",
     "url": "https://science.house.gov/",
     "subcommittees": [{"thomas_id": "15", "name": "Research and Technology"}]},
    {"type": "house", "thomas_id": "HSAG",
     "name": "House Committee on Agriculture",
     "url": "https://agriculture.house.gov/",
     "subcommittees": [{"thomas_id": "14", "name": "Conservation"}]},
    {"type": "house", "thomas_id": "HSBA",
     "name": "House Committee on Financial Services",
     "url": "https://financialservices.house.gov/", "subcommittees": []},
]

# April McClain Delaney (D000836) and Lisa C. McClain (M000317) — the pair
# that a name-substring join would cross.
MEMBERSHIP = {
    "HSSY": [{"name": "April McClain Delaney", "bioguide": "D000836"}],
    "HSSY15": [{"name": "April McClain Delaney", "bioguide": "D000836"}],
    "HSAG": [{"name": "April McClain Delaney", "bioguide": "D000836"}],
    "HSAG14": [{"name": "April McClain Delaney", "bioguide": "D000836"}],
    "HSBA": [{"name": "Lisa C. McClain", "bioguide": "M000317",
              "title": "Chair"}],
}

ROSTER = [
    {"name": "April McClain Delaney", "chamber": "house", "bioguide": "D000836"},
    {"name": "Lisa C. McClain", "chamber": "house", "bioguide": "M000317"},
    {"name": "Nancy Pelosi", "chamber": "house", "bioguide": "P000197"},
    {"name": "Marjorie Taylor Greene", "chamber": "house",
     "sitting": False},
    {"name": "Donald J. Trump", "chamber": "executive", "bioguide": None},
    {"name": "No Bioguide Person", "chamber": "house"},
]
# Greene has left Congress, so she is absent here; Pelosi sits but holds
# no committee seats.
SITTING = {"D000836", "M000317", "P000197"}


def payload():
    return committees.build(ROSTER, MEMBERSHIP, COMMITTEES, SITTING)


class TestShortName(unittest.TestCase):
    def test_strips_the_boilerplate(self):
        self.assertEqual(
            committees.short_name(
                "House Committee on Science, Space, and Technology"),
            "House Science, Space & Technology")

    def test_select_and_special_variants(self):
        self.assertEqual(
            committees.short_name(
                "House Permanent Select Committee on Intelligence"),
            "House Intelligence")
        self.assertEqual(
            committees.short_name("Senate Special Committee on Aging"),
            "Senate Aging")

    def test_leaves_unrecognised_names_alone(self):
        self.assertEqual(committees.short_name("Joint Economic Committee"),
                         "Joint Economic Committee")


class TestSeats(unittest.TestCase):
    def test_joins_by_bioguide_not_name(self):
        full, subs = committees.index_committees(COMMITTEES)
        delaney = committees.seats_for("D000836", MEMBERSHIP, full, subs)
        mcclain = committees.seats_for("M000317", MEMBERSHIP, full, subs)
        self.assertEqual([c["id"] for c in delaney], ["HSAG", "HSSY"])
        self.assertEqual([c["id"] for c in mcclain], ["HSBA"])
        # The near-name-collision must not leak across members.
        self.assertNotIn("HSBA", [c["id"] for c in delaney])

    def test_subcommittees_nest_under_their_parent(self):
        full, subs = committees.index_committees(COMMITTEES)
        seats = committees.seats_for("D000836", MEMBERSHIP, full, subs)
        science = next(c for c in seats if c["id"] == "HSSY")
        self.assertEqual([s["name"] for s in science["subcommittees"]],
                         ["Research and Technology"])
        self.assertEqual(science["shortName"],
                         "House Science, Space & Technology")

    def test_title_is_carried(self):
        full, subs = committees.index_committees(COMMITTEES)
        seats = committees.seats_for("M000317", MEMBERSHIP, full, subs)
        self.assertEqual(seats[0]["title"], "Chair")

    def test_subcommittee_without_parent_surfaces_the_parent(self):
        full, subs = committees.index_committees(COMMITTEES)
        seats = committees.seats_for(
            "X000001", {"HSSY15": [{"bioguide": "X000001"}]}, full, subs)
        self.assertEqual([c["id"] for c in seats], ["HSSY"])
        self.assertEqual([s["name"] for s in seats[0]["subcommittees"]],
                         ["Research and Technology"])

    def test_no_bioguide_means_no_seats(self):
        full, subs = committees.index_committees(COMMITTEES)
        self.assertEqual(committees.seats_for(None, MEMBERSHIP, full, subs), [])


class TestClassify(unittest.TestCase):
    """The four zeroes are four different facts and must not collapse."""

    def test_assigned(self):
        self.assertEqual(
            committees.classify(chamber="house", bioguide="D000836",
                                sitting=True, seats=2),
            committees.REASON_ASSIGNED)

    def test_sitting_member_with_no_seats_is_a_true_zero(self):
        self.assertEqual(
            committees.classify(chamber="house", bioguide="P000197",
                                sitting=True, seats=0),
            committees.REASON_NONE_CURRENT)

    def test_former_member_even_without_a_bioguide(self):
        # The roster only gets ids from the sitting-members file, so a
        # member who has left Congress has none. That is not our gap.
        self.assertEqual(
            committees.classify(chamber="house", bioguide=None,
                                sitting=False, seats=0),
            committees.REASON_FORMER_MEMBER)

    def test_executive_filer(self):
        self.assertEqual(
            committees.classify(chamber="executive", bioguide=None,
                                sitting=False, seats=0),
            committees.REASON_NOT_IN_CONGRESS)

    def test_missing_bioguide_on_a_sitting_member_is_our_gap(self):
        reason = committees.classify(chamber="house", bioguide=None,
                                     sitting=True, seats=0)
        self.assertEqual(reason, committees.REASON_UNMATCHED)
        self.assertIn(reason, committees.NEEDS_REVIEW)

    def test_true_zeroes_are_not_review_gaps(self):
        for reason in (committees.REASON_NONE_CURRENT,
                       committees.REASON_FORMER_MEMBER,
                       committees.REASON_NOT_IN_CONGRESS):
            self.assertNotIn(reason, committees.NEEDS_REVIEW)


class TestBuild(unittest.TestCase):
    def test_every_member_gets_a_reason(self):
        members = payload()["members"]
        self.assertEqual(members["April McClain Delaney"]["reason"],
                         committees.REASON_ASSIGNED)
        self.assertEqual(members["Nancy Pelosi"]["reason"],
                         committees.REASON_NONE_CURRENT)
        self.assertEqual(members["Marjorie Taylor Greene"]["reason"],
                         committees.REASON_FORMER_MEMBER)
        self.assertEqual(members["Donald J. Trump"]["reason"],
                         committees.REASON_NOT_IN_CONGRESS)
        self.assertEqual(members["No Bioguide Person"]["reason"],
                         committees.REASON_UNMATCHED)

    def test_only_assigned_members_carry_seats(self):
        members = payload()["members"]
        self.assertEqual(len(members["April McClain Delaney"]["committees"]), 2)
        for name in ("Nancy Pelosi", "Marjorie Taylor Greene",
                     "Donald J. Trump", "No Bioguide Person"):
            self.assertEqual(members[name]["committees"], [])

    def test_round_trip_and_lookup(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "committees.json"
            committees.save(payload(), path)
            data = committees.load(path)
            rec = committees.for_member("April McClain Delaney", data)
            self.assertEqual(rec["reason"], committees.REASON_ASSIGNED)
            names = [c["shortName"] for c in rec["committees"]]
            self.assertIn("House Science, Space & Technology", names)

    def test_unknown_member_reads_as_unmatched(self):
        rec = committees.for_member("Nobody At All", payload())
        self.assertEqual(rec["reason"], committees.REASON_UNMATCHED)
        self.assertEqual(rec["committees"], [])

    def test_missing_file_does_not_raise(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(
                committees.load(Path(tmp) / "absent.json")["members"], {})
