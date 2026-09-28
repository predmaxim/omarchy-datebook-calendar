"""iCalendar (RFC 5545) text: just enough to read CalDAV events and edit them in place.

parse() keeps every property it doesn't interpret, so serialize(parse(x)) gives
back what the server sent, give or take line folding: an edit changes only the
properties it names, and whatever the server or another client stored in the
event (X- properties, alarms, attendees' parameters) survives the round trip.

Values are kept as written (escaped); text() and escape() convert TEXT values,
instant() and stamp() convert date and date-time values.
"""

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_VALUE = r'(?:"[^"]*"|[^";:,]*)'
_PARAM = re.compile(r';([A-Za-z0-9-]+)=(%s(?:,%s)*)' % (_VALUE, _VALUE))
_LINE = re.compile(r'^([A-Za-z0-9-]+)((?:;[A-Za-z0-9-]+=%s(?:,%s)*)*):(.*)$' % (_VALUE, _VALUE), re.S)
_DURATION = re.compile(r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


class Prop:
    """One content line, NAME;PARAM=x:value. The value is kept as written (escaped)."""
    __slots__ = ("name", "value", "params")

    def __init__(self, name, value="", params=None):
        self.name = name.upper()
        self.value = value
        self.params = {k.upper(): v for k, v in (params or {}).items()}


class Component:
    """BEGIN:NAME … END:NAME: its properties in order, and its sub-components."""

    def __init__(self, name, props=None, children=None):
        self.name = name.upper()
        self.props = list(props or [])
        self.children = list(children or [])

    def get(self, name):
        name = name.upper()
        return next((p for p in self.props if p.name == name), None)

    def all(self, name):
        name = name.upper()
        return [p for p in self.props if p.name == name]

    def find(self, name):
        name = name.upper()
        return [c for c in self.children if c.name == name]

    def add(self, name, value, params=None):
        p = Prop(name, value, params)
        self.props.append(p)
        return p

    def set(self, name, value, params=None):
        """Every `name` replaced by one property, standing where the first one stood."""
        name = name.upper()
        at = next((i for i, p in enumerate(self.props) if p.name == name), len(self.props))
        self.props = [p for p in self.props if p.name != name]
        p = Prop(name, value, params)
        self.props.insert(min(at, len(self.props)), p)
        return p

    def remove(self, name):
        name = name.upper()
        self.props = [p for p in self.props if p.name != name]


# ------------------------------------------------------------------ text

def _unquote(v):
    return v[1:-1] if re.fullmatch(r'"[^"]*"', v) else v


def _quote(v):
    if re.fullmatch(r'"[^"]*"(?:,"[^"]*")*', v) or not re.search(r'[:;,]', v):
        return v
    return '"%s"' % v


def parse(text):
    """The VCALENDAR in text, as a Component tree. Malformed lines are dropped."""
    root = Component("ROOT")
    stack = [root]
    for line in re.split(r"\r?\n", re.sub(r"\r?\n[ \t]", "", text)):
        m = _LINE.match(line)
        if not m:
            continue
        p = Prop(m.group(1), m.group(3), {k: _unquote(v) for k, v in _PARAM.findall(m.group(2))})
        if p.name == "BEGIN":
            c = Component(p.value.strip())
            stack[-1].children.append(c)
            stack.append(c)
        elif p.name == "END":
            if len(stack) > 1:
                stack.pop()
        else:
            stack[-1].props.append(p)
    cals = root.find("VCALENDAR")
    if not cals:
        raise ValueError("no VCALENDAR in the calendar data")
    return cals[0]


def _fold(line):
    """A content line split into parts of at most 75 octets, never inside a character."""
    parts, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (74 if parts else 75):
            parts.append(cur.decode())
            cur = b""
        cur += b
    parts.append(cur.decode())
    return "\r\n ".join(parts)


def _lines(comp, out):
    out.append("BEGIN:" + comp.name)
    for p in comp.props:
        out.append(p.name + "".join(";%s=%s" % (k, _quote(v)) for k, v in p.params.items()) + ":" + p.value)
    for c in comp.children:
        _lines(c, out)
    out.append("END:" + comp.name)


def serialize(comp):
    out = []
    _lines(comp, out)
    return "".join(_fold(line) + "\r\n" for line in out)


def text(p):
    """A TEXT value unescaped; "" when the property is missing."""
    if p is None:
        return ""
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), p.value)


def escape(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r\n", "\n").replace("\n", "\\n"))


# ----------------------------------------------------------------- times

def zone(tzid):
    """The zone a TZID names, or None for one tzdata doesn't know (Outlook's
    "Russian Standard Time"): such times are read as local time rather than
    dropped. ponytail: VTIMEZONE definitions are not read."""
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def instant(p):
    """A DTSTART-like property as a date (all-day) or an aware datetime."""
    v = p.value.strip()
    if p.params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", v):
        return date(int(v[:4]), int(v[4:6]), int(v[6:8]))
    dt = datetime.strptime(v.rstrip("Z"), "%Y%m%dT%H%M%S")
    if v.endswith("Z"):
        return dt.replace(tzinfo=timezone.utc)
    z = zone(p.params["TZID"]) if p.params.get("TZID") else None
    return dt.replace(tzinfo=z) if z else dt.astimezone()


def duration(v):
    m = _DURATION.match(v.strip())
    if not m or not any(m.groups()[1:]) and "0" not in v:
        raise ValueError("not a duration: %r" % v)
    w, d, h, mi, s = (int(x or 0) for x in m.groups()[1:])
    span = timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)
    return -span if m.group(1) == "-" else span


def stamp(when, like=None):
    """(value, params) for a date or aware datetime, in the form of `like`.

    RECURRENCE-ID and EXDATE must match their DTSTART's form: a date stays a
    date, a time is written in like's TZID when tzdata knows it, else in UTC.
    Without `like` a time is UTC, which also makes stamp(x)[0] a canonical key
    for an occurrence.
    """
    if not isinstance(when, datetime):
        return when.strftime("%Y%m%d"), {"VALUE": "DATE"}
    tzid = like.params.get("TZID") if like is not None else None
    z = zone(tzid) if tzid else None
    if z is not None:
        return when.astimezone(z).strftime("%Y%m%dT%H%M%S"), {"TZID": tzid}
    return when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ"), {}


def from_key(key):
    """The date or UTC time an occurrence key names ("20261006" or "20261006T070000Z")."""
    if len(key) == 8:
        return date(int(key[:4]), int(key[4:6]), int(key[6:]))
    return datetime.strptime(key, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def master(vcal):
    """The VEVENT that isn't an exception: a single event, or a series' rule."""
    return next((v for v in vcal.find("VEVENT") if v.get("RECURRENCE-ID") is None), None)
