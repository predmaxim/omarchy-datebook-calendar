"""The CalDAV provider against recorded replies and a fake server; nothing goes on the network.

    python3 -B -m unittest discover -s tests -p '*_test.py'
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from omcal import auth, caldav  # noqa: E402
from caldav_fixtures import HOME, HOME_SET, PRINCIPAL, TOK  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
