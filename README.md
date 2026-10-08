# Datebook Calendar for Omarchy

Based on [Datebook](https://github.com/jonspinks/omarchy-calendar).

A calendar in Omarchy's top bar for looking, not editing. Click the date and
you see today's meetings with a Join button for each. Expand it for a week,
month or year of Yandex, Google and any CalDAV calendars.

![Compact view: the month and today's meetings](screenshots/compact.png)

It never creates, changes or deletes events. The only thing it writes back
is your answer to an invitation.

## Install

```bash
git clone https://github.com/predmaxim/omarchy-datebook-calendar.git \
  ~/.config/omarchy/plugins/predmaxim.datebook
omarchy plugin enable predmaxim.datebook --before omarchy.clock
omarchy plugin disable omarchy.clock
```

## Connect a calendar

```bash
C=~/.config/omarchy/plugins/predmaxim.datebook/scripts/calendar-ctl

$C add-yandex Work you@example.ru                        # asks for an app password
$C add-caldav Home https://dav.example.org/ you [email]  # any CalDAV server
$C add-google Personal ~/Downloads/client_secret_*.json  # your own OAuth client
$C sync
```

- **Yandex:** make an app password at id.yandex.ru → Security → App passwords
  → Calendar.
- **Google:** in the Google Cloud Console create a project, turn on the
  Google Calendar API, set up the consent screen with the scope
  `https://www.googleapis.com/auth/calendar` (answering an invitation is a
  write), publish it *In production*, then create an OAuth client of type
  *Desktop app* and download its JSON.

## What's inside

**Week, month, year.** The expand button opens the big view: day, week, work
week, month and year, with calendars to tick on the left and the next meeting
at the top.

![Week view](screenshots/week.png)

**Event card.** Click an event to see its time, calendar, place and links.
From the card you can join, open the event on the web, or answer an
invitation (for a recurring one, the answer covers the whole series).

![Event card of an invitation](screenshots/card.png)

**Reminders** pop up before a meeting; click one to join, or snooze it.

**Language.** Buttons follow the system language (`LC_MESSAGES`, English or
Russian), dates follow `LC_TIME`. The screenshots use English text with
Russian dates.

![Month view](screenshots/month.png)

## Controls

Arrows move the selected day, Shift moves it further; Ctrl acts, Alt does the
other thing. Letters go by the key, not the layout.

| | |
|---|---|
| ←/→, ↑/↓ | a day, a week back / on |
| Shift+←/→, Shift+↑/↓ | a month, a year back / on |
| Home | today |
| `1`–`5` | day, week, work week, month, year |
| `0` | compact: Omarchy's month and the day's appointments |
| Enter | the selected day's events: the only one opens its card; with more, ↑/↓ pick one (on today it starts on the meeting on now or next), Enter opens it, Esc goes back to the days, other keys work as usual. In the year view Enter opens the day |
| Ctrl+Enter | join the meeting: the one picked, else the one Enter would start on |
| Alt+Enter | open that event on the web |
| Ctrl+R | sync now |
| Ctrl+, | Settings (also the gear in the header): ↑/↓ rows, Enter opens/runs/toggles, Esc back. The rows: clock format, time zone, first day of week, then a switch per calendar |
| Tab, Shift+Tab | the next / previous panel on the bar |
| Esc | close |

In the event card:

| | |
|---|---|
| ↑/↓ | the links in the description, then the row of buttons |
| ←/→ | along the buttons: answer, Join, Open in Web, Close |
| Enter | what the cursor is on; on the answer it opens the choices (↑/↓, Enter, Esc) |
| Ctrl+Enter | join the meeting |
| Alt+Enter | open the event on the web |
| Ctrl+1 / Ctrl+2 / Ctrl+3 | accept / maybe / decline an invitation |
| Esc | close the card (back to the day's events if you came from them) |

Sync runs every 3 minutes and when you open the calendar; `calendar-ctl sync`
runs it by hand. Calendars are switched on and off in Settings (or `calendar-ctl choose` in a terminal);
hidden calendars aren't downloaded.

Optional settings in the widget's entry in `shell.json`: `"format"` (the date
on the bar; 12/24-hour carries into the calendar), `"view"`,
`"layout": "classic"`, `"reminders": false`.

From scripts: `qs ipc -p /usr/share/omarchy/shell call predmaxim.datebook <cmd>`,
where `<cmd>` is `toggle`, `compact`, `expand`, `view week` or `showEvent <uid>`.

## Your data

Everything stays on your computer; there's no server behind this plugin.
Passwords and tokens are kept in the system keyring. The account list lives in
`~/.config/predmaxim.datebook/`, a copy of your events in
`~/.cache/predmaxim.datebook/`, and both are readable only by you. Google access
can be revoked at myaccount.google.com/permissions; for Yandex, delete the app
password.

## Remove

```bash
C=~/.config/omarchy/plugins/predmaxim.datebook/scripts/calendar-ctl
$C list && $C remove Work            # for each account: drops its keyring entry
omarchy plugin remove predmaxim.datebook
omarchy plugin enable omarchy.clock --section center
rm -rf ~/.config/predmaxim.datebook ~/.cache/predmaxim.datebook
```

## Notes

- Yandex sends recurring meetings as rules and doesn't expand them itself, so
  the plugin expands daily and weekly series on its own. Other rules show only
  their moved or edited occurrences. Yandex doesn't send its reminders over
  CalDAV.
- Code: `scripts/omcal/` syncs (`caldav.py`, `ical.py`, `google.py`) into
  `~/.cache/predmaxim.datebook/events.json`, which the QML widget reads.
  Tests: `tests/run.sh`.

## License

MIT, see [LICENSE](LICENSE). Parts of the panel come from Omarchy's own clock.
