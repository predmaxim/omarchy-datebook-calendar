"""iCalendar text: reading, round-tripping and writing values.

    python3 -B -m unittest discover -s tests -p '*_test.py'
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from omcal import ical  # noqa: E402

RAW = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:abc\r\n"
       "SUMMARY:Planning\\, Q4\\; room 5\\nsecond line\r\n"
       "DTSTART;TZID=Europe/Moscow:20260929T100000\r\n"
       "DTEND;TZID=Europe/Moscow:20260929T110000\r\n"
       "ATTENDEE;CN=\"Ivanov, Ivan\";PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:ivan@astral.ru\r\n"
       "DESCRIPTION:a very long line that goes on and on and on and on and on and o\r\n n and wraps\r\n"
       "X-CUSTOM;X-PARAM=1:keep me\r\n"
       "BEGIN:VALARM\r\nACTION:DISPLAY\r\nTRIGGER:-PT15M\r\nEND:VALARM\r\n"
       "END:VEVENT\r\nEND:VCALENDAR\r\n")
UTC = timezone.utc


class Parse(unittest.TestCase):
    def setUp(self):
        self.cal = ical.parse(RAW)
        self.ev = self.cal.find("VEVENT")[0]

    def test_text_is_unescaped(self):
        self.assertEqual(ical.text(self.ev.get("SUMMARY")), "Planning, Q4; room 5\nsecond line")

    def test_folded_line_is_joined(self):
        self.assertEqual(ical.text(self.ev.get("DESCRIPTION")),
                         "a very long line that goes on and on and on and on and on and on and wraps")

    def test_quoted_parameter(self):
        a = self.ev.get("ATTENDEE")
        self.assertEqual((a.params["CN"], a.params["PARTSTAT"], a.value),
                         ("Ivanov, Ivan", "NEEDS-ACTION", "mailto:ivan@astral.ru"))

    def test_zoned_time(self):
        self.assertEqual(ical.instant(self.ev.get("DTSTART")), datetime(2026, 9, 29, 7, 0, tzinfo=UTC))

    def test_alarm_is_a_child(self):
        self.assertEqual(self.ev.find("VALARM")[0].get("TRIGGER").value, "-PT15M")

    def test_round_trip_keeps_what_it_does_not_know(self):
        again = ical.parse(ical.serialize(self.cal)).find("VEVENT")[0]
        self.assertEqual(again.get("X-CUSTOM").value, "keep me")
        self.assertEqual(again.get("X-CUSTOM").params, {"X-PARAM": "1"})
        self.assertEqual(again.get("ATTENDEE").params["CN"], "Ivanov, Ivan")
        self.assertEqual(ical.text(again.get("DESCRIPTION")), ical.text(self.ev.get("DESCRIPTION")))

    def test_long_lines_fold_at_75_octets(self):
        self.ev.set("SUMMARY", ical.escape("Ж" * 100))
        out = ical.serialize(self.cal)
        self.assertTrue(all(len(line.encode()) <= 75 for line in out.split("\r\n")))
        self.assertEqual(ical.text(ical.parse(out).find("VEVENT")[0].get("SUMMARY")), "Ж" * 100)

    def test_no_calendar_is_an_error(self):
        with self.assertRaises(ValueError):
            ical.parse("BEGIN:VEVENT\r\nEND:VEVENT\r\n")

    def test_escape_round_trips(self):
        s = "a,b;c\\d\ne"
        self.assertEqual(ical.text(ical.Prop("SUMMARY", ical.escape(s))), s)


class Values(unittest.TestCase):
    def test_date(self):
        self.assertEqual(ical.instant(ical.Prop("DTSTART", "20261002", {"VALUE": "DATE"})), date(2026, 10, 2))

    def test_utc(self):
        self.assertEqual(ical.instant(ical.Prop("DTSTART", "20261002T090000Z")),
                         datetime(2026, 10, 2, 9, 0, tzinfo=UTC))

    def test_unknown_zone_is_local_time(self):
        p = ical.Prop("DTSTART", "20261002T090000", {"TZID": "Russian Standard Time"})
        self.assertEqual(ical.instant(p), datetime(2026, 10, 2, 9, 0).astimezone())

    def test_floating_is_local_time(self):
        self.assertEqual(ical.instant(ical.Prop("DTSTART", "20261002T090000")),
                         datetime(2026, 10, 2, 9, 0).astimezone())

    def test_durations(self):
        self.assertEqual([ical.duration(v) for v in ("-PT15M", "P1D", "PT1H30M", "-P1W", "PT0S")],
                         [timedelta(minutes=-15), timedelta(days=1), timedelta(hours=1, minutes=30),
                          timedelta(weeks=-1), timedelta(0)])
        with self.assertRaises(ValueError):
            ical.duration("15 minutes")

    def test_stamp_in_the_zone_of_its_dtstart(self):
        like = ical.Prop("DTSTART", "20260929T100000", {"TZID": "Europe/Moscow"})
        self.assertEqual(ical.stamp(datetime(2026, 10, 6, 7, 0, tzinfo=UTC), like),
                         ("20261006T100000", {"TZID": "Europe/Moscow"}))

    def test_stamp_utc_and_date(self):
        self.assertEqual(ical.stamp(datetime(2026, 10, 6, 10, 0, tzinfo=timezone(timedelta(hours=3)))),
                         ("20261006T070000Z", {}))
        self.assertEqual(ical.stamp(date(2026, 10, 6)), ("20261006", {"VALUE": "DATE"}))

    def test_key_round_trip(self):
        for when in (date(2026, 10, 6), datetime(2026, 10, 6, 7, 0, tzinfo=UTC)):
            self.assertEqual(ical.from_key(ical.stamp(when)[0]), when)

    def test_set_replaces_in_place(self):
        ev = ical.Component("VEVENT", [ical.Prop("UID", "1"), ical.Prop("SUMMARY", "a"),
                                       ical.Prop("SUMMARY", "b"), ical.Prop("X-Y", "z")])
        ev.set("SUMMARY", "c")
        self.assertEqual([(p.name, p.value) for p in ev.props], [("UID", "1"), ("SUMMARY", "c"), ("X-Y", "z")])
        ev.set("LOCATION", "d")
        self.assertEqual(ev.props[-1].name, "LOCATION")

    def test_master_is_the_one_without_recurrence_id(self):
        cal = ical.Component("VCALENDAR", [], [
            ical.Component("VEVENT", [ical.Prop("RECURRENCE-ID", "20261006T070000Z")]),
            ical.Component("VEVENT", [ical.Prop("RRULE", "FREQ=DAILY")])])
        self.assertIsNotNone(ical.master(cal).get("RRULE"))


if __name__ == "__main__":
    unittest.main()
