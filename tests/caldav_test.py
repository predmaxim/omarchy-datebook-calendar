"""The CalDAV provider against recorded replies and a fake server; nothing goes on the network.

    python3 -B -m unittest discover -s tests -p '*_test.py'
"""
import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from omcal import auth, caldav, sync  # noqa: E402
from caldav_fixtures import (ALLDAY, CAL, EXPANDED, HOME, HOME_SET, OUTLOOK_ZONE, PRINCIPAL,  # noqa: E402
                             SERIES, SINGLE, TOK, FakeServer, report)


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

    def test_unexpanded_series_shows_only_its_exceptions(self):
        # Yandex ignores <C:expand>: the rule's own occurrences aren't shown yet
        # (a known gap), but a moved or edited occurrence is a VEVENT of its own.
        fake = reported(("/c/s.ics", '"e5"', SERIES))
        with mock.patch.object(caldav, "request", fake):
            events = caldav.fetch("Y", TOK, CAL, WINDOW)[0]
        self.assertEqual([e["title"] for e in events], ["Standup (moved)"])
        ev = events[0]
        self.assertEqual((ev["recurring"], ev["seriesId"], ev["start"], ev["response"]),
                         (True, "s.ics", "2026-10-07T09:00:00Z", "accepted"))
        self.assertTrue(ev["uid"].endswith("/s.ics#20261007T070000Z"))


class Sync(unittest.TestCase):
    """A moved ctag makes the sync read the calendar whole and drop what's gone."""

    def test_moved_ctag_replaces_the_calendars_events(self):
        from caldav_fixtures import ALLDAY
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(sync, "CACHE", d), \
                mock.patch.object(auth, "caldav_access", return_value=TOK), \
                mock.patch.object(auth, "hidden_calendars", return_value={}), \
                mock.patch.object(caldav, "calendars", return_value=[CAL]), \
                mock.patch.object(caldav, "request", reported(("/c/a.ics", '"e3"', ALLDAY))):
            stale = "Y/%s/gone.ics" % CAL["id"]
            sync.write_private(os.path.join(d, "state-Y.json"), {
                "windowDay": sync.window_now()[0],
                "calendars": {CAL["id"]: dict(CAL, cursor="ctag-1", fullAt=time.time())},
                "events": {stale: {"uid": stale, "calendar": CAL["id"], "status": "confirmed"}}})
            st = sync.sync_account({"name": "Y", "provider": "caldav"}, False, lambda *_: None)
        self.assertEqual(st["status"], "ok", st.get("error"))
        self.assertEqual([e["title"] for e in st["events"].values()], ["Отпуск"])
        self.assertEqual(st["calendars"][CAL["id"]]["cursor"], "ctag-2")


HREF = "/calendars/me%40astral.ru/events-default/series.ics"
ONE = "/calendars/me%40astral.ru/events-default/single.ics"


class Writes(unittest.TestCase):
    def setUp(self):
        self.srv = FakeServer({HREF: (SERIES, '"s1"'), ONE: (SINGLE, '"e1"')})
        patcher = mock.patch.object(caldav, "request", self.srv)
        patcher.start()
        self.addCleanup(patcher.stop)

    def vevents(self, path):
        from omcal import ical
        return ical.parse(self.srv.objects[path][0]).find("VEVENT")

    def test_update_single_event(self):
        caldav.update(TOK, ONE, '"e1"', None, {"title": "Новое, название", "busy": True})
        (ev,) = self.vevents(ONE)
        from omcal import ical
        self.assertEqual(ical.text(ev.get("SUMMARY")), "Новое, название")
        self.assertEqual((ev.get("TRANSP").value, ev.get("SEQUENCE").value), ("OPAQUE", "1"))
        self.assertEqual(ev.get("X-TELEMOST-CONFERENCE").value, "https://telemost.yandex.ru/j/12345678901234")
        self.assertEqual(self.srv.puts()[0][2]["If-Match"], '"e1"')

    def test_stale_local_copy_is_a_conflict(self):
        with self.assertRaises(auth.Conflict):
            caldav.update(TOK, ONE, '"old"', None, {"title": "x"})
        self.assertEqual(self.srv.puts(), [])

    def test_edit_one_occurrence_makes_an_exception(self):
        caldav.update(TOK, HREF, '"s1"', "20261006T070000Z", {"title": "Only this"})
        evs = self.vevents(HREF)
        self.assertEqual(len(evs), 3)
        new = evs[-1]
        self.assertEqual((new.get("RECURRENCE-ID").value, new.get("RECURRENCE-ID").params),
                         ("20261006T100000", {"TZID": "Europe/Moscow"}))
        self.assertEqual((new.get("DTSTART").value, new.get("DTEND").value), ("20261006T100000", "20261006T103000"))
        self.assertIsNone(new.get("RRULE"))
        self.assertEqual(len(new.find("VALARM")), 1)
        self.assertEqual(new.get("SUMMARY").value, "Only this")
        self.assertEqual(evs[0].get("SUMMARY").value, "Standup")

    def test_edit_an_existing_exception(self):
        caldav.update(TOK, HREF, '"s1"', "20261007T070000Z", {"location": "Zoom"})
        evs = self.vevents(HREF)
        self.assertEqual(len(evs), 2)
        self.assertEqual(evs[1].get("LOCATION").value, "Zoom")

    def test_move_one_occurrence(self):
        s = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
        caldav.update(TOK, HREF, '"s1"', "20261006T070000Z", {"start": s, "end": s.replace(hour=10)})
        new = self.vevents(HREF)[-1]
        self.assertEqual((new.get("DTSTART").value, new.get("DTEND").value), ("20261006T090000Z", "20261006T100000Z"))
        self.assertEqual(new.get("RECURRENCE-ID").value, "20261006T100000")

    def test_series_title_changes_every_vevent(self):
        caldav.update(TOK, HREF, '"s1"', None, {"title": "Team sync"}, series=True)
        self.assertEqual([e.get("SUMMARY").value for e in self.vevents(HREF)], ["Team sync", "Team sync"])

    def test_delete_one_occurrence(self):
        caldav.delete(TOK, HREF, '"s1"', "20261007T070000Z")
        evs = self.vevents(HREF)
        self.assertEqual(len(evs), 1)
        ex = evs[0].get("EXDATE")
        self.assertEqual((ex.value, ex.params), ("20261007T100000", {"TZID": "Europe/Moscow"}))

    def test_delete_whole_object(self):
        caldav.delete(TOK, HREF, '"s1"')
        self.assertNotIn(HREF, self.srv.objects)
        self.assertEqual(self.srv.calls[-1][2], {"If-Match": '"s1"'})

    def test_respond_for_one_occurrence(self):
        caldav.respond(TOK, HREF, '"s1"', "20261006T070000Z", "accept")
        evs = self.vevents(HREF)
        mine = [g for g in evs[-1].all("ATTENDEE") if g.value == "mailto:me@astral.ru"][0]
        self.assertEqual(mine.params, {"PARTSTAT": "ACCEPTED"})
        self.assertEqual(evs[0].all("ATTENDEE")[0].params["PARTSTAT"], "NEEDS-ACTION")

    def test_respond_for_the_series(self):
        caldav.respond(TOK, HREF, '"s1"', "20261006T070000Z", "decline", series=True)
        self.assertEqual([e.all("ATTENDEE")[0].params["PARTSTAT"] for e in self.vevents(HREF)],
                         ["DECLINED", "DECLINED"])

    def test_respond_when_not_on_the_guest_list(self):
        with self.assertRaises(caldav.NotInvited):
            caldav.respond(dict(TOK, email="someone@else.ru"), ONE, '"e1"', None, "accept")
        self.assertEqual(self.srv.puts(), [])

    def test_create_with_guests(self):
        cal = {"id": "/calendars/me%40astral.ru/events-default/"}
        s = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        with mock.patch.object(caldav.uuid, "uuid4", return_value="fixed"):
            href, etag, ve = caldav.create(TOK, cal, "Обед", s, s.replace(hour=10), False, "Кафе, 2 этаж", ["a@b.ru"], True)
        self.assertEqual(href, cal["id"] + "fixed.ics")
        self.assertEqual(self.srv.puts()[0][2]["If-None-Match"], "*")
        text = self.srv.objects[href][0]
        for line in ("ORGANIZER:mailto:me@astral.ru", "LOCATION:Кафе\\, 2 этаж", "DTSTART:20261001T090000Z",
                     "ATTENDEE;PARTSTAT=NEEDS-ACTION;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:a@b.ru"):
            self.assertIn(line, text)
        self.assertEqual(etag, self.srv.objects[href][1])

    def test_create_all_day(self):
        cal = {"id": "/c/"}
        with mock.patch.object(caldav.uuid, "uuid4", return_value="d"):
            caldav.create(TOK, cal, "Day off", date(2026, 10, 2), date(2026, 10, 3), True)
        self.assertIn("DTSTART;VALUE=DATE:20261002", self.srv.objects["/c/d.ics"][0])

    def test_create_504_that_landed_is_not_resent(self):
        cal = {"id": "/c/"}
        self.srv.after[("PUT", "/c/x.ics")] = 504
        s = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
        with mock.patch.object(caldav.uuid, "uuid4", return_value="x"):
            href, etag, _ = caldav.create(TOK, cal, "T", s, s, False)
        self.assertEqual(len(self.srv.puts()), 1)
        self.assertEqual(etag, self.srv.objects[href][1])

    def test_update_504_that_landed_is_not_resent(self):
        self.srv.after[("PUT", ONE)] = 504
        etag = caldav.update(TOK, ONE, '"e1"', None, {"title": "x"})
        self.assertEqual(len(self.srv.puts()), 1)
        self.assertEqual(etag, self.srv.objects[ONE][1])

    def test_update_504_that_did_not_land_is_sent_once_more(self):
        self.srv.fail[("PUT", ONE)] = 504
        caldav.update(TOK, ONE, '"e1"', None, {"title": "x"})
        self.assertEqual(len(self.srv.puts()), 2)
        from omcal import ical
        self.assertEqual(self.vevents(ONE)[0].get("SUMMARY").value, "x")


class Edits(unittest.TestCase):
    """edit.py finds the object and occurrence from the uid, calls the provider, patches the local copy."""

    def setUp(self):
        from omcal import edit
        self.edit = edit
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        acc = {"name": "Y", "provider": "caldav", "email": TOK["email"]}
        self.uid = "Y/%s/series.ics#20261006T070000Z" % CAL["id"]
        self.other = "Y/%s/series.ics#20261007T070000Z" % CAL["id"]
        ev = lambda uid: {"uid": uid, "account": "Y", "calendar": CAL["id"], "title": "Standup", "allDay": False,
                          "start": "2026-10-06T07:00:00Z", "end": "2026-10-06T07:30:00Z", "status": "confirmed",
                          "organizer": False, "response": "needsAction", "recurring": True,
                          "seriesId": "series.ics", "editable": True, "etag": '"s1"', "location": "", "busy": True}
        for p in (mock.patch.object(sync, "CACHE", self.dir.name),
                  mock.patch.object(auth, "load_accounts", return_value=[acc]),
                  mock.patch.object(auth, "caldav_access", return_value=TOK)):
            p.start()
            self.addCleanup(p.stop)
        sync.write_private(os.path.join(self.dir.name, "state-Y.json"), {
            "calendars": {CAL["id"]: CAL}, "events": {self.uid: ev(self.uid), self.other: ev(self.other)}})

    def state(self):
        return sync.read_json(os.path.join(self.dir.name, "state-Y.json"), {})["events"]

    def test_delete_one_occurrence(self):
        with mock.patch.object(caldav, "delete") as d:
            self.edit.delete(self.uid)
        d.assert_called_once_with(TOK, CAL["id"] + "series.ics", '"s1"', "20261006T070000Z")
        self.assertEqual(list(self.state()), [self.other])

    def test_delete_series(self):
        with mock.patch.object(caldav, "delete") as d:
            self.edit.delete(self.uid, series=True)
        d.assert_called_once_with(TOK, CAL["id"] + "series.ics", '"s1"', None)
        self.assertEqual(self.state(), {})

    def test_update_series_title(self):
        with mock.patch.object(caldav, "update") as u:
            self.edit.update(self.uid, title="Team sync", series=True)
        u.assert_called_once_with(TOK, CAL["id"] + "series.ics", '"s1"', None, {"title": "Team sync"}, True)
        self.assertEqual({e["title"] for e in self.state().values()}, {"Team sync"})

    def test_move_one_occurrence(self):
        with mock.patch.object(caldav, "update") as u:
            self.edit.update(self.uid, start="2026-10-06 12:00+03:00")
        args = u.call_args[0]
        self.assertEqual((args[3], sorted(args[4])), ("20261006T070000Z", ["end", "start"]))
        self.assertEqual(self.state()[self.uid]["start"], "2026-10-06T09:00:00Z")
        self.assertEqual(self.state()[self.uid]["end"], "2026-10-06T09:30:00Z")

    def test_respond(self):
        with mock.patch.object(caldav, "respond") as r:
            self.edit.respond(self.uid, "decline")
        r.assert_called_once_with(TOK, CAL["id"] + "series.ics", '"s1"', "20261006T070000Z", "decline", False)
        self.assertEqual(self.state()[self.uid]["response"], "declined")
        self.assertEqual(self.state()[self.other]["response"], "needsAction")


if __name__ == "__main__":
    unittest.main()
