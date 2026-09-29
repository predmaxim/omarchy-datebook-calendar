# Datebook (read-only) — Yandex and Google calendars in Omarchy's clock

A read-only fork of [Datebook](https://github.com/jonspinks/omarchy-calendar).
Click the clock and your week is there, with a Join button when a meeting is
about to start. Events are never created, edited or deleted from here; the
one thing it sends back is your answer to an invitation (Accept, Maybe,
Decline). For anything else, **Open in Web** takes you to the event in the
calendar's own web app.

![Datebook: your week, what's next, and a reminder you can join from](preview.png)

## What you get

- **Day, week, working week, month and year**, switched with the buttons or
  keys 1 to 5. Overlapping meetings sit side by side.
- **An event card**: click an event for its time, calendar (and where else the
  same event is), place and clickable links, with **Join**, **Open in Web** and,
  for invitations, one button with your answer (or Choose) that opens Accept /
  Maybe / Decline; a recurring invitation is answered for the whole series.
- **Compact view**: each of the day's events on one line, with its time and an
  icon-only Join; expand, sync and calendars as icons down the right.
- **Reminders you can join from**, and snooze.
- **Language.** Text follows the system language (`LC_MESSAGES`; English and
  Russian so far), dates follow its formats (`LC_TIME`): with
  `LANG=en_US.UTF-8` and `LC_TIME=ru_RU.UTF-8` the buttons read "Today" and
  "Join" and the dates "29 сентября".
- **Private.** It talks straight to Yandex or Google from your machine; sign-ins
  live in the system keyring. See [PRIVACY.md](PRIVACY.md).

## Install

```bash
git clone -b readonly https://github.com/predmaxim/omarchy-calendar.git \
  ~/.config/omarchy/plugins/predmaxim.datebook
omarchy plugin enable predmaxim.datebook --before omarchy.clock
omarchy plugin disable omarchy.clock
```

## Sign in

```bash
C=~/.config/omarchy/plugins/predmaxim.datebook/scripts/calendar-ctl
$C add-yandex Yandex you@example.ru      # paste an app password (id.yandex.ru → Security → App passwords → Calendar)
$C add-caldav Home https://dav.example.org/ you [email]   # any other CalDAV server
$C add-google Personal ~/Downloads/client_secret_*.json   # a Desktop OAuth client of your own
$C sync
```

For Google, make a project in the Google Cloud Console, enable the **Google
Calendar API**, set up the OAuth consent screen with the scope
`https://www.googleapis.com/auth/calendar` (answers to invitations are a
write), publish it **In production**, and create an OAuth client ID of type
**Desktop app**.

Yandex doesn't expand recurring events for CalDAV clients, so the plugin does
(daily and weekly rules; other rules show only their moved or edited
occurrences). Yandex doesn't send its reminders over CalDAV.

## Using it

- **Calendars:** click one in the list on the left to show or hide it, or
  `calendar-ctl choose` for a checklist. A hidden calendar isn't downloaded.
- **Keys:** `1`–`5` views, `[` `]` or the arrows to step, `t` today, `w` the
  first day of the week; Esc or Enter closes an event card.
- **Sync** runs every three minutes and when you open the calendar;
  `calendar-ctl sync` runs one by hand.
- **Settings** (the widget's entry in `shell.json`, all optional):
  `"layout": "classic"`, `"reminders": false`, `"view"`, and `"format"` (the
  clock's format; its 12- or 24-hour choice carries into the calendar).
- **IPC:** `qs ipc -p /usr/share/omarchy/shell call predmaxim.datebook view week`
  (also `toggle`, `compact`, `expand`, `showEvent <uid>`).

## Remove

```bash
C=~/.config/omarchy/plugins/predmaxim.datebook/scripts/calendar-ctl
$C list && $C remove Yandex             # each account: deletes its keyring entry
omarchy plugin remove predmaxim.datebook
omarchy plugin enable omarchy.clock --section center
```

Left afterwards: `~/.config/predmaxim.datebook/` (account list, no secrets)
and `~/.cache/predmaxim.datebook/` (the event copy); both are safe to delete.

## How it works

`scripts/omcal/` does the talking: CalDAV (`caldav.py`, with recurring series
expanded in `ical.py`) and Google (`google.py`). A copy of the next four months
and the last five weeks lives in `~/.cache/predmaxim.datebook/`, and the widget
reads one file from it. `tests/run.sh` runs the tests (node and Python).

## License

MIT — see [LICENSE](LICENSE). Parts of the panel are derived from Omarchy's
own clock (MIT).
