"""The CalDAV provider against recorded replies and a fake server; nothing goes on the network.

    python3 -B -m unittest discover -s tests -p '*_test.py'
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from omcal import auth, caldav  # noqa: E402
from caldav_fixtures import (ALLDAY, CAL, EXPANDED, HOME, HOME_SET, OUTLOOK_ZONE, PRINCIPAL,  # noqa: E402
                             SINGLE, TOK, report)


def replies(*bodies):
    """A fake caldav.request answering with these bodies in order, recording the calls."""
    calls = []

    def fake(tok, method, path, body=None, headers=None):
        calls.append((method, path, dict(headers or {})))
        return 207, {}, bodies[len(calls) - 1].encode()
    fake.calls = calls
    return fake


class Requests(unittest.TestCase):
    def test_request_refuses_other_host(self):
        with mock.patch.object(caldav.urllib.request, "urlopen") as net:
            with self.assertRaises(auth.HttpError):
                caldav.request(TOK, "GET", "https://evil.example/calendars/x.ics")
            with self.assertRaises(auth.HttpError):
                caldav.request(dict(TOK, base="http://caldav.yandex.ru"), "GET", "/x")
            net.assert_not_called()

    def test_discover_follows_principal_to_home(self):
        fake = replies(PRINCIPAL, HOME_SET)
        with mock.patch.object(caldav, "request", fake):
            self.assertEqual(caldav.discover(TOK), "/calendars/me%40astral.ru/")
        self.assertEqual([(m, p, h["Depth"]) for m, p, h in fake.calls],
                         [("PROPFIND", "/", "0"), ("PROPFIND", "/principals/users/me%40astral.ru/", "0")])


class Calendars(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(caldav, "request", replies(HOME)):
            self.cals = caldav.calendars(TOK)

    def test_only_event_calendars(self):
        self.assertEqual([c["id"] for c in self.cals],
                         ["/calendars/me%40astral.ru/events-123/", "/calendars/me%40astral.ru/events-default/"])

    def test_fields(self):
        work, mine = self.cals
        self.assertEqual((work["name"], work["color"], work["editable"], work["primary"], work["ctag"]),
                         ("Работа", "#3F51B5", False, False, "ctag-work"))
        self.assertEqual((mine["name"], mine["color"], mine["editable"], mine["primary"], mine["ctag"]),
                         ("Мои события", "", True, True, "ctag-1"))
        self.assertEqual(mine["defaultRemind"], [])


WINDOW = ("2026-08-24T00:00:00Z", "2027-01-26T00:00:00Z")


def reported(*objects):
    body = report(*objects)

    def fake(tok, method, path, data=None, headers=None):
        fake.calls.append((method, path, data))
        return 207, {}, body
    fake.calls = []
    return fake


class Fetch(unittest.TestCase):
    def read(self, *objects):
        fake = reported(*objects)
        with mock.patch.object(caldav, "request", fake):
            events, removed, cursor = caldav.fetch("Y", TOK, CAL, WINDOW)
        return {e["title"]: e for e in events}, removed, cursor, fake.calls

    def test_unchanged_ctag_reads_nothing(self):
        fake = reported()
        with mock.patch.object(caldav, "request", fake):
            self.assertEqual(caldav.fetch("Y", TOK, CAL, WINDOW, "ctag-2"), ([], [], "ctag-2"))
        self.assertEqual(fake.calls, [])

    def test_moved_ctag_asks_for_a_whole_read(self):
        with self.assertRaises(caldav.Changed):
            caldav.fetch("Y", TOK, CAL, WINDOW, "ctag-1")

    def test_query_asks_for_expansion_of_the_window(self):
        _, _, cursor, calls = self.read()
        method, path, body = calls[0]
        self.assertEqual((method, path, cursor), ("REPORT", CAL["id"], "ctag-2"))
        self.assertIn('<c:expand start="20260824T000000Z" end="20270126T000000Z"/>', body)

    def test_invitation(self):
        ev = self.read(("/c/single.ics", '"e1"', SINGLE))[0]["Планёрка"]
        self.assertEqual((ev["start"], ev["end"], ev["allDay"]), ("2026-09-29T07:00:00Z", "2026-09-29T08:00:00Z", False))
        self.assertEqual((ev["response"], ev["organizer"], ev["editable"]), ("needsAction", False, False))
        self.assertEqual(ev["join"], {"url": "https://telemost.yandex.ru/j/12345678901234", "kind": "telemost"})
        self.assertEqual(ev["webLink"], "https://calendar.yandex.ru/event?event_id=42")
        self.assertEqual((ev["busy"], ev["remind"], ev["location"]), (False, [15, 60], "Переговорная 5"))
        self.assertEqual((ev["recurring"], ev["seriesId"], ev["etag"]), (False, None, '"e1"'))
        self.assertEqual(ev["uid"][len("Y/%s/" % CAL["id"]):], "single.ics")

    def test_occurrences_of_own_series(self):
        fake = reported(("/c/own.ics", '"e2"', EXPANDED))
        with mock.patch.object(caldav, "request", fake):
            occ = caldav.fetch("Y", TOK, CAL, WINDOW)[0]
        self.assertEqual([e["uid"].split("/")[-1] for e in occ],
                         ["own.ics#20261005T070000Z", "own.ics#20261006T070000Z"])
        self.assertTrue(all(e["recurring"] and e["seriesId"] == "own.ics" for e in occ))
        self.assertTrue(all(e["organizer"] and e["editable"] and e["response"] == "organizer" for e in occ))
        self.assertEqual(occ[0]["webLink"], "https://calendar.yandex.ru/")

    def test_all_day(self):
        ev = self.read(("/c/a.ics", '"e3"', ALLDAY))[0]["Отпуск"]
        self.assertEqual((ev["allDay"], ev["start"], ev["end"]), (True, "2026-10-10", "2026-10-12"))

    def test_unknown_tzid_event_still_listed(self):
        self.assertIn("From Outlook", self.read(("/c/o.ics", '"e4"', OUTLOOK_ZONE))[0])

    def test_unexpanded_series_is_reported(self):
        from caldav_fixtures import SERIES
        with self.assertRaises(auth.HttpError) as cm:
            self.read(("/c/s.ics", '"e5"', SERIES))
        self.assertEqual(cm.exception.code, 501)


if __name__ == "__main__":
    unittest.main()
