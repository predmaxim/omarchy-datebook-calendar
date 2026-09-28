"""Replies recorded in the shape Yandex's CalDAV server gives them, and a fake server for writes."""

from omcal import auth

TOK = {"base": "https://caldav.yandex.ru", "user": "me@astral.ru", "password": "x",
       "home": "/calendars/me%40astral.ru/", "email": "me@astral.ru", "web": "https://calendar.yandex.ru/"}
CAL = {"id": "/calendars/me%40astral.ru/events-default/", "name": "Мои события", "color": "",
       "primary": True, "editable": True, "defaultRemind": []}

PRINCIPAL = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:"><d:response><d:href>/</d:href><d:propstat><d:prop>
<d:current-user-principal><d:href>/principals/users/me%40astral.ru/</d:href></d:current-user-principal>
</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"""

HOME_SET = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response>
<d:href>/principals/users/me%40astral.ru/</d:href><d:propstat><d:prop>
<c:calendar-home-set><d:href>/calendars/me%40astral.ru/</d:href></c:calendar-home-set>
</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>"""

HOME = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"
  xmlns:cs="http://calendarserver.org/ns/" xmlns:ical="http://apple.com/ns/ical/">
 <d:response><d:href>/calendars/me%40astral.ru/</d:href><d:propstat><d:prop>
  <d:resourcetype><d:collection/></d:resourcetype></d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
 <d:response><d:href>/calendars/me%40astral.ru/events-123/</d:href><d:propstat><d:prop>
  <d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Работа</d:displayname>
  <ical:calendar-color>#3F51B5FF</ical:calendar-color><cs:getctag>ctag-work</cs:getctag>
  <c:supported-calendar-component-set><c:comp name="VEVENT"/></c:supported-calendar-component-set>
  <d:current-user-privilege-set><d:privilege><d:read/></d:privilege></d:current-user-privilege-set>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
 <d:response><d:href>/calendars/me%40astral.ru/events-default/</d:href><d:propstat><d:prop>
  <d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Мои события</d:displayname>
  <cs:getctag>ctag-1</cs:getctag>
  <c:supported-calendar-component-set><c:comp name="VEVENT"/></c:supported-calendar-component-set>
  <d:current-user-privilege-set><d:privilege><d:read/></d:privilege><d:privilege><d:write/></d:privilege></d:current-user-privilege-set>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>
  <d:propstat><d:prop><ical:calendar-color/></d:prop><d:status>HTTP/1.1 404 Not Found</d:status></d:propstat></d:response>
 <d:response><d:href>/calendars/me%40astral.ru/todos-9/</d:href><d:propstat><d:prop>
  <d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>Дела</d:displayname>
  <c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set>
  </d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>
</d:multistatus>"""

SINGLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Yandex LLC//Yandex Calendar//EN
BEGIN:VEVENT
UID:single-1
DTSTART;TZID=Europe/Moscow:20260929T100000
DTEND;TZID=Europe/Moscow:20260929T110000
SUMMARY:Планёрка
LOCATION:Переговорная 5
TRANSP:TRANSPARENT
URL:https://calendar.yandex.ru/event?event_id=42
X-TELEMOST-CONFERENCE:https://telemost.yandex.ru/j/12345678901234
ORGANIZER:mailto:boss@astral.ru
ATTENDEE;PARTSTAT=ACCEPTED:mailto:boss@astral.ru
ATTENDEE;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:me@astral.ru
SEQUENCE:0
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT15M
END:VALARM
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT1H
END:VALARM
END:VEVENT
END:VCALENDAR
"""

# A series as stored (GET): daily at 10:00 Moscow, with the 7 October moved to noon.
SERIES = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Yandex LLC//Yandex Calendar//EN
BEGIN:VEVENT
UID:series-1
DTSTART;TZID=Europe/Moscow:20261005T100000
DTEND;TZID=Europe/Moscow:20261005T103000
RRULE:FREQ=DAILY;COUNT=10
SUMMARY:Standup
ORGANIZER:mailto:boss@astral.ru
ATTENDEE;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:me@astral.ru
SEQUENCE:2
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT10M
END:VALARM
END:VEVENT
BEGIN:VEVENT
UID:series-1
RECURRENCE-ID;TZID=Europe/Moscow:20261007T100000
DTSTART;TZID=Europe/Moscow:20261007T120000
DTEND;TZID=Europe/Moscow:20261007T123000
SUMMARY:Standup (moved)
ORGANIZER:mailto:boss@astral.ru
ATTENDEE;PARTSTAT=ACCEPTED:mailto:me@astral.ru
END:VEVENT
END:VCALENDAR
"""

# The same series as the server expands it for a REPORT: occurrences in UTC.
EXPANDED = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:own-series
RECURRENCE-ID:20261005T070000Z
DTSTART:20261005T070000Z
DTEND:20261005T073000Z
SUMMARY:Зарядка
END:VEVENT
BEGIN:VEVENT
UID:own-series
RECURRENCE-ID:20261006T070000Z
DTSTART:20261006T070000Z
DTEND:20261006T073000Z
SUMMARY:Зарядка
END:VEVENT
END:VCALENDAR
"""

ALLDAY = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:allday-1
DTSTART;VALUE=DATE:20261010
DTEND;VALUE=DATE:20261012
SUMMARY:Отпуск
END:VEVENT
END:VCALENDAR
"""

OUTLOOK_ZONE = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:outlook-1
DTSTART;TZID=Russian Standard Time:20261001T150000
DTEND;TZID=Russian Standard Time:20261001T160000
SUMMARY:From Outlook
END:VEVENT
END:VCALENDAR
"""


def report(*objects):
    """A calendar-query reply holding (href, etag, ics) objects."""
    rows = "".join(
        "<d:response><d:href>%s</d:href><d:propstat><d:prop><d:getetag>%s</d:getetag>"
        "<c:calendar-data>%s</c:calendar-data></d:prop><d:status>HTTP/1.1 200 OK</d:status>"
        "</d:propstat></d:response>" % (href, etag, ics) for href, etag, ics in objects)
    return ('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:" '
            'xmlns:c="urn:ietf:params:xml:ns:caldav">%s</d:multistatus>' % rows).encode()


def etags(*pairs):
    """A PROPFIND Depth 1 reply listing (href, etag) objects, after the collection itself."""
    rows = "".join(
        "<d:response><d:href>%s</d:href><d:propstat><d:prop><d:getetag>%s</d:getetag></d:prop>"
        "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>" % (h, e) for h, e in pairs)
    return ('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:"><d:response>'
            '<d:href>%s</d:href><d:propstat><d:prop><d:getetag/></d:prop><d:status>HTTP/1.1 404 Not Found'
            '</d:status></d:propstat></d:response>%s</d:multistatus>' % (CAL["id"], rows)).encode()


class FakeServer:
    """Stands in for caldav.request: objects are {path: (ics text, etag)}.

    fail[(method, path)] = code raises that HTTP error before acting;
    after[(method, path)] = code acts, then raises (a write that landed).
    """

    def __init__(self, objects=None, etag_on_put=True):
        self.objects = dict(objects or {})
        self.calls, self.fail, self.after = [], {}, {}
        self.etag_on_put = etag_on_put   # Yandex answers a PUT without an ETag

    def __call__(self, tok, method, path, body=None, headers=None):
        headers = headers or {}
        self.calls.append((method, path, dict(headers), body))
        code = self.fail.pop((method, path), None)
        if code:
            raise auth.HttpError("fake", code)
        out = self._act(method, path, body, headers)
        code = self.after.pop((method, path), None)
        if code:
            raise auth.HttpError("fake", code)
        return out

    def _act(self, method, path, body, headers):
        have = self.objects.get(path)
        if method == "GET":
            if not have:
                raise auth.HttpError("fake", 404)
            return 200, {"ETag": have[1]}, have[0].encode()
        if method == "PUT":
            if headers.get("If-None-Match") == "*" and have:
                raise auth.Conflict("exists")
            if "If-Match" in headers and (not have or have[1] != headers["If-Match"]):
                raise auth.Conflict("changed")
            etag = '"v%d"' % len(self.calls)
            self.objects[path] = (body, etag)
            return 201, {"ETag": etag} if self.etag_on_put else {}, b""
        if method == "DELETE":
            if not have:
                raise auth.HttpError("fake", 404)
            if "If-Match" in headers and have[1] != headers["If-Match"]:
                raise auth.Conflict("changed")
            del self.objects[path]
            return 204, {}, b""
        raise AssertionError("unexpected %s" % method)

    def puts(self):
        return [c for c in self.calls if c[0] == "PUT"]
