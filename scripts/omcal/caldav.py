"""CalDAV calendars (RFC 4791): Yandex Calendar, and any server that speaks it.

Standard library only. Signs in with a user name and an app password over
https (HTTP Basic); the password is kept in the keyring like the other
providers' tokens, and the account entry keeps the server, the user and the
calendar home found at sign-in, so a sync makes no discovery requests.

The password is only ever sent to the account's own server over https: a
reply naming any other place (an href on another host) is refused, not
followed.

Reading asks the server to expand recurring events into occurrences for the
sync window (calendar-query with <C:expand>), so no RRULE is evaluated here;
a server that ignores that is reported, not worked around. A calendar's
getctag is its cursor: unchanged, the calendar isn't read at all (Yandex
rate-limits hard); changed, it is read whole, as CalDAV has no cheap delta
like Graph's.

Writing edits the event's own iCalendar object and puts it back guarded by
its ETag, so a change made elsewhere since the last sync is never
overwritten. Yandex sometimes answers a write with 504 after making it, so a
504 is followed by a read before anything is sent again.
"""

import copy
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
CALENDAR_PROPS = ["d:resourcetype", "d:displayname", "ical:calendar-color", "cs:getctag",
                  "c:supported-calendar-component-set", "d:current-user-privilege-set"]


class Changed(Exception):
    """The calendar's ctag moved since the last read: read it whole."""


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
        with urllib.request.urlopen(req, timeout=30) as r:
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
    principal = _href(propfind(tok, "/", ["d:current-user-principal"], 0), tag("d", "current-user-principal"))
    home = principal and _href(propfind(tok, principal, ["c:calendar-home-set"], 0), tag("c", "calendar-home-set"))
    if not home:
        raise auth.HttpError(host(tok), 404, "no CalDAV calendar home for %s" % tok["user"])
    return home


def _color(c):
    """#RRGGBB from Apple's #RRGGBBAA."""
    return c[:7] if len(c) == 9 and c.startswith("#") else c


def calendars(tok):
    """Every event calendar in the home, with the fields google/graph give, plus its ctag."""
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
                    "primary": False, "editable": editable, "defaultRemind": [],
                    "ctag": _text(p.get(tag("cs", "getctag")))})
    if out:
        main = next((c for c in out if c["id"].rstrip("/").endswith("/events-default")), out[0])
        main["primary"] = True
    return out
