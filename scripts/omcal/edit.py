"""The one change made from Omarchy: this account's answer to an invitation.

The event is named by its uid (as in events.json) and checked against the
local copy first: an unknown uid, or an event of your own, stops before
anything is sent. An answer that lands is applied to the local copy at once,
so the widget shows it without waiting, and a sync then brings back the
provider's own version. It carries the provider's version stamp (Google's etag
as If-Match, CalDAV's object ETag), so a change made elsewhere since the event
was read is never overwritten: the write fails with Conflict instead.
"""

import os
import urllib.parse

from . import auth, caldav, sync

GOOGLE = "https://www.googleapis.com/calendar/v3"
GRAPH = "https://graph.microsoft.com/v1.0"

ANSWERS = {"accept": "accepted", "tentative": "tentative", "decline": "declined"}
GRAPH_ACTIONS = {"accept": "accept", "tentative": "tentativelyAccept", "decline": "decline"}


class EditError(RuntimeError):
    """A change that can't be made, said in plain words."""


def q(part):
    return urllib.parse.quote(part, safe="")


def locate(uid):
    """(account entry, state path, state, event, provider event id) for a uid."""
    name = uid.split("/", 1)[0]
    a = next((x for x in auth.load_accounts() if x["name"] == name), None)
    if not a:
        raise EditError("no account called %r" % name)
    path = os.path.join(sync.CACHE, "state-%s.json" % name)
    st = sync.read_json(path, {"events": {}})
    e = st.get("events", {}).get(uid)
    if not e:
        raise EditError("that event isn't in the local copy any more; sync and try again")
    prefix = "%s/%s/" % (name, e["calendar"])
    return a, path, st, e, uid[len(prefix):]


def token(a):
    if a["provider"] == "google":
        return auth.google_access(a)
    if a["provider"] == "caldav":
        return auth.caldav_access(a)
    return auth.ms_access(a)


def _object(e, eid):
    """(object href, occurrence key or None) of a CalDAV event: eid is "<object>[#<key>]"."""
    obj, _, rid = eid.partition("#")
    return e["calendar"].rstrip("/") + "/" + obj, rid or None


def _restamp(a, e, href, etag):
    """A CalDAV write gives the whole object a new ETag: every local event from
    it (all occurrences of a series) takes it, or the next edit would conflict."""
    if etag:
        _apply(a["name"], lambda x: x["calendar"] == e["calendar"] and _object(x, x["uid"].rsplit("/", 1)[1])[0] == href,
               {"etag": etag})


def respond(uid, answer, series=False):
    """Accept, tentatively accept or decline an invitation, and tell the organiser.

    series answers for every occurrence of a recurring event; otherwise only
    this one.
    """
    if answer not in ANSWERS:
        raise EditError("the answer is accept, tentative or decline")
    a, path, st, e, eid = locate(uid)
    if e.get("organizer"):
        raise EditError("this is your own event: there is no invitation to answer")
    if series and not e.get("seriesId"):
        series = False
    target = e["seriesId"] if series else eid
    tok = token(a)
    if a["provider"] == "google":
        _google_respond(tok, e["calendar"], target, ANSWERS[answer])
    elif a["provider"] == "caldav":
        href, rid = _object(e, eid)
        _restamp(a, e, href, caldav.respond(tok, href, e.get("etag"), rid, answer, series))
    else:
        auth.send_json("POST", GRAPH + "/me/calendars/%s/events/%s/%s" % (q(e["calendar"]), q(target), GRAPH_ACTIONS[answer]),
                       tok, {"sendResponse": True})
    _apply(a["name"], lambda x: x["uid"] == uid or series and x.get("seriesId") == e["seriesId"],
           {"response": ANSWERS[answer]})


def _google_respond(tok, cal, eid, status):
    # Google has no "respond" call: the answer is this account's entry in the
    # guest list, and the list is written back whole. The etag of the copy
    # just read guards it, so a guest added meanwhile is never dropped; on a
    # conflict it is read and tried once more.
    url = GOOGLE + "/calendars/%s/events/%s" % (q(cal), q(eid))
    for attempt in (1, 2):
        ev = auth.get_json(url, tok)
        guests = ev.get("attendees") or []
        me = next((g for g in guests if g.get("self")), None)
        if not me:
            raise EditError("you aren't on this event's guest list (a group invitation?): answer it in Google Calendar")
        me["responseStatus"] = status
        try:
            auth.send_json("PATCH", url + "?sendUpdates=all", tok, {"attendees": guests},
                           {"If-Match": ev["etag"]})
            return
        except auth.Conflict:
            if attempt == 2:
                raise


def _apply(account, match, fields):
    """Patch the local copy (under the sync lock) and republish events.json."""
    with sync.locked():
        path = os.path.join(sync.CACHE, "state-%s.json" % account)
        st = sync.read_json(path, {"events": {}})
        for x in st.get("events", {}).values():
            if match(x):
                x.update(fields)
        sync.write_private(path, st)
        sync.republish()
