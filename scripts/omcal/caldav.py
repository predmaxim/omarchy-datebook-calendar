"""CalDAV calendars (RFC 4791): Yandex Calendar, and any server that speaks it.

Standard library only. Signs in with a user name and an app password over
https (HTTP Basic); the password is kept in the keyring like the other
providers' tokens, and the account entry keeps the server, the user and the
calendar home found at sign-in, so a sync makes no discovery requests.

The password is only ever sent to the account's own server over https: a
reply naming any other place (an href on another host) is refused, not
followed.

Reading asks the server to expand recurring events into occurrences for the
sync window (calendar-query with <C:expand>), so no RRULE is evaluated here.
Yandex ignores that and sends each series as its rule plus its exceptions:
until RRULE expansion lands here, such a series shows only its moved or edited
occurrences. The cursor is a fingerprint of the calendar's objects and their
ETags (Yandex's getctag doesn't move on edits): unchanged, the calendar isn't
read again (Yandex rate-limits hard); changed, it is read whole, as CalDAV has
no cheap delta like Graph's.

Writing edits the event's own iCalendar object and puts it back guarded by
its ETag, so a change made elsewhere since the last sync is never
overwritten. Yandex sometimes answers a write with 504 after making it, so a
504 is followed by a read before anything is sent again.
"""

import copy
import hashlib
import json
import posixpath
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from base64 import b64encode
from datetime import datetime, timedelta, timezone

from . import auth, files, ical
from .model import find_join, join_kind, utc_iso

YANDEX = "https://caldav.yandex.ru"
YANDEX_WEB = "https://calendar.yandex.ru/"
NS = {"d": "DAV:", "c": "urn:ietf:params:xml:ns:caldav",
      "cs": "http://calendarserver.org/ns/", "ical": "http://apple.com/ns/ical/"}
XML = "application/xml; charset=utf-8"
CALENDAR_PROPS = ["d:resourcetype", "d:displayname", "ical:calendar-color",
                  "c:supported-calendar-component-set", "d:current-user-privilege-set"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """urllib would follow a GET's redirect carrying every header, the password
    included, to wherever it points (another host, or plain http): a 3xx is an
    error here instead."""

    def redirect_request(self, *args):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class Changed(Exception):
    """The calendar changed since the last read: read it whole."""


def tag(ns, name):
    return "{%s}%s" % (NS[ns], name)


def host(tok):
    return urllib.parse.urlsplit(tok["base"]).netloc


def request(tok, method, path, body=None, headers=None):
    """(status, headers, body bytes) for one request to the account's server.

    401 is a sign-in problem (AuthError), 412 a conflict (Conflict), any other
    error status an HttpError; network failures pass through, for the sync to
    call the account offline.
    """
    url = urllib.parse.urljoin(tok["base"] + "/", path)
    if not url.startswith("https://") or urllib.parse.urlsplit(url).netloc != host(tok):
        raise auth.HttpError(host(tok), 0, "refusing to send the password to %s" % url)
    creds = b64encode(("%s:%s" % (tok["user"], tok["password"])).encode()).decode()
    h = {"Authorization": "Basic " + creds}
    h.update(headers or {})
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with _OPENER.open(req, timeout=30) as r:
            return r.status, r.headers, files.read_reply(r)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise auth.AuthError("%s refused the saved password (was the app password revoked?)" % host(tok))
        if e.code == 412:
            raise auth.Conflict("the event was changed elsewhere; sync and try again")
        raise auth.HttpError(host(tok), e.code, auth.error_text(e))


def multistatus(raw):
    """[(href, {tag: element})] from a 207 reply: only properties the server found (200)."""
    out = []
    for resp in ET.fromstring(raw).findall("d:response", NS):
        href = (resp.findtext("d:href", "", NS) or "").strip()
        props = {}
        for ps in resp.findall("d:propstat", NS):
            if " 200 " not in " %s " % ps.findtext("d:status", "", NS):
                continue
            prop = ps.find("d:prop", NS)
            for el in (prop if prop is not None else []):
                props[el.tag] = el
        out.append((href, props))
    return out


def propfind(tok, path, props, depth):
    body = ('<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:" xmlns:c="%s" xmlns:cs="%s" '
            'xmlns:ical="%s"><d:prop>%s</d:prop></d:propfind>'
            % (NS["c"], NS["cs"], NS["ical"], "".join("<%s/>" % p for p in props)))
    return multistatus(request(tok, "PROPFIND", path, body, {"Depth": str(depth), "Content-Type": XML})[2])


def _href(results, t):
    for _, props in results:
        el = props.get(t)
        h = (el.findtext("d:href", "", NS) or "").strip() if el is not None else ""
        if h:
            return h
    return ""


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def discover(tok):
    """The signed-in user's calendar home, as an href."""
    # From the server address itself: a Nextcloud-style base has a path to keep.
    principal = _href(propfind(tok, "", ["d:current-user-principal"], 0), tag("d", "current-user-principal"))
    home = principal and _href(propfind(tok, principal, ["c:calendar-home-set"], 0), tag("c", "calendar-home-set"))
    if not home:
        raise auth.HttpError(host(tok), 404, "no CalDAV calendar home for %s" % tok["user"])
    return home


def _color(c):
    """#RRGGBB from Apple's #RRGGBBAA."""
    return c[:7] if len(c) == 9 and c.startswith("#") else c


def calendars(tok):
    """Every event calendar in the home, with the fields google/graph give."""
    out = []
    for href, p in propfind(tok, tok["home"], CALENDAR_PROPS, 1):
        rt = p.get(tag("d", "resourcetype"))
        if rt is None or rt.find("c:calendar", NS) is None:
            continue
        comps = p.get(tag("c", "supported-calendar-component-set"))
        if comps is not None and "VEVENT" not in [c.get("name") for c in comps.findall("c:comp", NS)]:
            continue   # a task list (Yandex's todos-*)
        privs = p.get(tag("d", "current-user-privilege-set"))
        editable = privs is None or any(privs.find("d:privilege/d:" + x, NS) is not None
                                        for x in ("all", "write", "write-content"))
        out.append({"id": href,
                    "name": _text(p.get(tag("d", "displayname"))) or posixpath.basename(href.rstrip("/")),
                    "color": _color(_text(p.get(tag("ical", "calendar-color")))),
                    "primary": False, "editable": editable, "defaultRemind": []})
    if out:
        main = next((c for c in out if c["id"].rstrip("/").endswith("/events-default")), out[0])
        main["primary"] = True
    return out


# ------------------------------------------------------------------ read

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
<d:prop><d:getetag/><c:calendar-data><c:expand start="%(start)s" end="%(end)s"/></c:calendar-data></d:prop>
<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT">
<c:time-range start="%(start)s" end="%(end)s"/></c:comp-filter></c:comp-filter></c:filter>
</c:calendar-query>"""

PARTSTAT = {"ACCEPTED": "accepted", "TENTATIVE": "tentative", "DECLINED": "declined",
            "NEEDS-ACTION": "needsAction"}


ETAGS = ('<?xml version="1.0" encoding="utf-8"?><d:propfind xmlns:d="DAV:">'
         '<d:prop><d:getetag/></d:prop></d:propfind>')


def version(tok, cal):
    """A fingerprint of every event object in the calendar and its ETag.

    Yandex's getctag and sync-token move when an event is added or removed but
    not when one is edited, so they can't tell a sync that anything changed;
    the objects' ETags can, for one small PROPFIND.
    """
    raw = request(tok, "PROPFIND", cal["id"], ETAGS, {"Depth": "1", "Content-Type": XML})[2]
    pairs = sorted((href, _text(p.get(tag("d", "getetag")))) for href, p in multistatus(raw)
                   if href.rstrip("/") != cal["id"].rstrip("/"))
    return hashlib.sha1(json.dumps(pairs).encode()).hexdigest()


def fetch(account, tok, cal, window, cursor=None):
    """(events, removed, cursor) for one calendar; the cursor is its version().

    With a cursor there is nothing to do if the version hasn't changed, and
    Changed if it has (the sync then reads the calendar whole: removed is
    always empty, since a whole read replaces the calendar's events). Without
    one, every event in the window.
    """
    now = version(tok, cal)
    if cursor is not None:
        if cursor == now:
            return [], [], cursor
        raise Changed()
    start, end = (w.replace("-", "").replace(":", "") for w in window)
    raw = request(tok, "REPORT", cal["id"], REPORT % {"start": start, "end": end},
                  {"Depth": "1", "Content-Type": XML})[2]
    events = []
    for href, p in multistatus(raw):
        data = _text(p.get(tag("c", "calendar-data")))
        if not data:
            continue
        try:
            vevents = ical.parse(data).find("VEVENT")
        except ValueError:
            continue
        for ve in vevents:
            if ve.get("RRULE") is not None or ve.get("RDATE") is not None:
                # ponytail: a series the server didn't expand (Yandex ignores
                # <C:expand>) shows only its moved or edited occurrences, which
                # arrive as VEVENTs of their own. Expanding RRULE here (weekly
                # BYDAY/INTERVAL, EXDATE, zoneinfo) is the upgrade path.
                continue
            try:
                events.append(normalise(account, cal, tok, href, _text(p.get(tag("d", "getetag"))), ve))
            except (ValueError, TypeError, AttributeError):
                continue   # an event this reader can't place is skipped; the rest still show
    return events, [], now


def _addr(p):
    v = (p.value if p is not None else "").strip().lower()
    return v[7:] if v.startswith("mailto:") else v


def _end(ve, s):
    """The end, of the same kind (date or time) as the start."""
    if ve.get("DTEND") is not None:
        e = ical.instant(ve.get("DTEND"))
    elif ve.get("DURATION") is not None:
        e = s + ical.duration(ve.get("DURATION").value)
    else:
        e = s
    if isinstance(e, datetime) != isinstance(s, datetime):
        e = s
    return e


def _join(ve):
    """Yandex keeps a meeting's Telemost link in its own property; else look in the text."""
    tm = ical.text(ve.get("X-TELEMOST-CONFERENCE")).strip()
    if join_kind(tm) == "telemost":
        return {"url": tm, "kind": "telemost"}
    return find_join(ical.text(ve.get("URL")), ical.text(ve.get("LOCATION")), ical.text(ve.get("DESCRIPTION")))


def _web_link(ve, web):
    """The event's own page when the server put one on the web app's host in URL, else the web app."""
    url = ical.text(ve.get("URL")).strip()
    if web and url.startswith("https://") and \
            urllib.parse.urlsplit(url).netloc == urllib.parse.urlsplit(web).netloc:
        return url
    return web


def _remind(ve):
    """Minutes before the start of each alarm set relative to the start."""
    out = set()
    for alarm in ve.find("VALARM"):
        t = alarm.get("TRIGGER")
        if t is None or t.params.get("VALUE", "DURATION").upper() != "DURATION" \
                or t.params.get("RELATED", "START").upper() != "START":
            continue
        try:
            before = -ical.duration(t.value)
        except ValueError:
            continue
        if before >= timedelta(0):
            out.add(int(before.total_seconds() // 60))
    return sorted(out)


def normalise(account, cal, tok, href, etag, ve):
    """One VEVENT (a single event or one expanded occurrence) in the shape model.py describes."""
    s = ical.instant(ve.get("DTSTART"))
    all_day = not isinstance(s, datetime)
    e = _end(ve, s)
    if all_day:
        start, end = s.isoformat(), max(e, s + timedelta(days=1)).isoformat()
    else:
        start, end = utc_iso(s), utc_iso(max(e, s))
    me = tok.get("email", "").lower()
    org, guests = ve.get("ORGANIZER"), ve.all("ATTENDEE")
    organizer = _addr(org) == me if org is not None else not guests
    mine = next((g for g in guests if _addr(g) == me), None)
    if organizer:
        response = "organizer"
    elif mine is not None:
        response = PARTSTAT.get(mine.params.get("PARTSTAT", "NEEDS-ACTION").upper(), "needsAction")
    else:
        response = "none"
    rid = ve.get("RECURRENCE-ID")
    obj = posixpath.basename(href.rstrip("/"))
    eid = obj + ("#" + ical.stamp(ical.instant(rid))[0] if rid is not None else "")
    status = ical.text(ve.get("STATUS")).strip().lower()
    return {
        "uid": "%s/%s/%s" % (account, cal["id"], eid),
        "account": account, "calendar": cal["id"],
        "title": ical.text(ve.get("SUMMARY")).strip() or "(no title)",
        "allDay": all_day, "start": start, "end": end,
        "location": ical.text(ve.get("LOCATION")),
        "join": _join(ve),
        "response": response,
        "organizer": organizer,
        "status": status if status in ("confirmed", "tentative", "cancelled") else "confirmed",
        "busy": ical.text(ve.get("TRANSP")).strip().upper() != "TRANSPARENT",
        "recurring": rid is not None,
        "seriesId": obj if rid is not None else None,
        "editable": bool(cal.get("editable")) and organizer,
        "webLink": _web_link(ve, tok.get("web", "")),
        "etag": etag,
        "remind": _remind(ve),
    }


# ----------------------------------------------------------------- write

ANSWERS = {"accept": "ACCEPTED", "tentative": "TENTATIVE", "decline": "DECLINED"}


class NotInvited(RuntimeError):
    """This account isn't among the event's attendees (a group invitation?)."""


def _get(tok, href):
    """(VCALENDAR, etag) of an event object."""
    _, h, raw = request(tok, "GET", href)
    return ical.parse(raw.decode("utf-8", "replace")), (h.get("ETag") or "").strip()


def _exists(tok, href):
    """_get, or None when the object isn't there."""
    try:
        return _get(tok, href)
    except auth.HttpError as e:
        if e.code == 404:
            return None
        raise


def _put(tok, href, vcal, guard):
    """Write the object; returns its new ETag.

    Yandex answers a PUT without an ETag, so it is read back: without it the
    next edit of this event would look like a change made elsewhere.
    """
    headers = dict(guard)
    headers["Content-Type"] = "text/calendar; charset=utf-8"
    _, h, _ = request(tok, "PUT", href, ical.serialize(vcal), headers)
    etag = (h.get("ETag") or "").strip()
    if not etag:
        again = _exists(tok, href)
        etag = again[1] if again else ""
    return etag


def _now():
    return datetime.now(timezone.utc)


def _modify(tok, href, etag, change):
    """Read the object, check it's the version the local copy came from, change it, put it back.

    After a 504 the object is read again: an ETag other than the one written
    from means the write landed; the same one means it didn't, and it is sent
    once more.
    """
    vcal, current = _get(tok, href)
    if etag and current and current != etag:
        raise auth.Conflict("the event was changed elsewhere; sync and try again")
    change(vcal)
    for attempt in (1, 2):
        try:
            return _put(tok, href, vcal, {"If-Match": current} if current else {})
        except auth.HttpError as e:
            if e.code != 504 or attempt == 2:
                raise
            again = _exists(tok, href)
            if again is None:
                raise auth.Conflict("the event was deleted elsewhere")
            if again[1] != current:
                return again[1]


def create(tok, cal, title, start, end, all_day, location="", invite=(), busy=True):
    """A new event in cal, inviting whoever is in invite. Returns (href, etag, VEVENT).

    Guests are written as ATTENDEEs with this account as ORGANIZER; the
    server sends the invitations. all_day is carried by start/end being dates.
    """
    uid = str(uuid.uuid4())
    href = cal["id"].rstrip("/") + "/" + uid + ".ics"
    ve = ical.Component("VEVENT")
    ve.add("UID", uid)
    ve.add("DTSTAMP", *ical.stamp(_now()))
    ve.add("SUMMARY", ical.escape(title))
    ve.add("DTSTART", *ical.stamp(start))
    ve.add("DTEND", *ical.stamp(end))
    ve.add("TRANSP", "OPAQUE" if busy else "TRANSPARENT")
    if location:
        ve.add("LOCATION", ical.escape(location))
    if invite:
        ve.add("ORGANIZER", "mailto:" + tok["email"])
        ve.add("ATTENDEE", "mailto:" + tok["email"], {"PARTSTAT": "ACCEPTED", "ROLE": "CHAIR"})
        for m in invite:
            ve.add("ATTENDEE", "mailto:" + m, {"PARTSTAT": "NEEDS-ACTION", "RSVP": "TRUE", "ROLE": "REQ-PARTICIPANT"})
    vcal = ical.Component("VCALENDAR", [ical.Prop("VERSION", "2.0"),
                                        ical.Prop("PRODID", "-//blacksheep//Datebook//EN")], [ve])
    for attempt in (1, 2):
        try:
            return href, _put(tok, href, vcal, {"If-None-Match": "*"}), ve
        except auth.HttpError as e:
            if e.code != 504 or attempt == 2:
                raise
            again = _exists(tok, href)
            if again is not None:
                return href, again[1], ve


def _occurrence(vcal, rid):
    """The VEVENT for occurrence rid (a stamp key), made from the series if it has no exception yet.

    A new exception copies the series (alarms and attendees included) without
    its rule, at this occurrence's own time; RECURRENCE-ID is written in the
    series' DTSTART form, or the server wouldn't match it to the occurrence.
    """
    for ve in vcal.find("VEVENT"):
        r = ve.get("RECURRENCE-ID")
        if r is not None and ical.stamp(ical.instant(r))[0] == rid:
            return ve
    series = ical.master(vcal)
    if series is None:
        raise auth.HttpError("caldav", 404, "the series of this occurrence is gone")
    when = ical.from_key(rid)
    start = series.get("DTSTART")
    ve = ical.Component("VEVENT",
                        [ical.Prop(p.name, p.value, p.params) for p in series.props
                         if p.name not in ("RRULE", "RDATE", "EXRULE", "EXDATE", "RECURRENCE-ID", "DTSTART", "DTEND")],
                        [copy.deepcopy(c) for c in series.find("VALARM")])
    ve.add("RECURRENCE-ID", *ical.stamp(when, start))
    ve.add("DTSTART", *ical.stamp(when, start))
    if series.get("DTEND") is not None:
        length = ical.instant(series.get("DTEND")) - ical.instant(start)
        ve.add("DTEND", *ical.stamp(when + length, series.get("DTEND")))
    vcal.children.append(ve)
    return ve


def _set(ve, fields):
    if "title" in fields:
        ve.set("SUMMARY", ical.escape(fields["title"]))
    if "location" in fields:
        if fields["location"]:
            ve.set("LOCATION", ical.escape(fields["location"]))
        else:
            ve.remove("LOCATION")
    if "busy" in fields:
        ve.set("TRANSP", "OPAQUE" if fields["busy"] else "TRANSPARENT")
    if "start" in fields:
        ve.set("DTSTART", *ical.stamp(fields["start"]))
        ve.set("DTEND", *ical.stamp(fields["end"]))
        ve.remove("DURATION")
    seq = ve.get("SEQUENCE")
    ve.set("SEQUENCE", str(int(seq.value) + 1 if seq is not None and seq.value.strip().isdigit() else 1))
    ve.set("DTSTAMP", *ical.stamp(_now()))


def update(tok, href, etag, rid, fields, series=False):
    """Change title, location, busy or start/end. Returns the new ETag.

    rid None: the single event, or with series every VEVENT in the object (the
    series and its exceptions). rid set: that occurrence only, as an exception.
    """
    def change(vcal):
        if rid:
            targets = [_occurrence(vcal, rid)]
        elif series:
            targets = vcal.find("VEVENT")
        else:
            targets = [ical.master(vcal) or vcal.find("VEVENT")[0]]
        for ve in targets:
            _set(ve, fields)
    return _modify(tok, href, etag, change)


def delete(tok, href, etag, rid=None):
    """The whole object (an event, or a series with its exceptions), or with rid one
    occurrence (then the object's new ETag is returned)."""
    if rid:
        def change(vcal):
            series = ical.master(vcal)
            if series is None:
                raise auth.HttpError("caldav", 404, "the series of this occurrence is gone")
            series.add("EXDATE", *ical.stamp(ical.from_key(rid), series.get("DTSTART")))
            vcal.children = [c for c in vcal.children if not (
                c.name == "VEVENT" and c.get("RECURRENCE-ID") is not None
                and ical.stamp(ical.instant(c.get("RECURRENCE-ID")))[0] == rid)]
        return _modify(tok, href, etag, change)
    for attempt in (1, 2):
        try:
            request(tok, "DELETE", href, None, {"If-Match": etag} if etag else {})
            return
        except auth.HttpError as e:
            if e.code == 404:
                return   # already gone
            if e.code != 504 or attempt == 2:
                raise
            if _exists(tok, href) is None:
                return


def respond(tok, href, etag, rid, answer, series=False):
    """This account's answer to an invitation, as its ATTENDEE's PARTSTAT. Returns the new ETag.

    For one occurrence of a series the answer goes on that occurrence's
    exception; with series, on the series and every exception. The server
    sends the reply to the organiser.
    """
    me = tok["email"].lower()

    def change(vcal):
        targets = vcal.find("VEVENT") if series or not rid else [_occurrence(vcal, rid)]
        found = False
        for ve in targets:
            for g in ve.all("ATTENDEE"):
                if _addr(g) == me:
                    g.params["PARTSTAT"] = ANSWERS[answer]
                    g.params.pop("RSVP", None)
                    found = True
        if not found:
            raise NotInvited("you aren't on this event's guest list (a group invitation?): "
                             "answer it in the calendar's web app")
    return _modify(tok, href, etag, change)
