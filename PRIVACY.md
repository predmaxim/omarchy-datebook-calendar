# Privacy policy: Datebook

*Last updated: 27 September 2026*

Datebook (Omarchy Calendar) is a desktop calendar for the Omarchy Linux desktop. It shows
your Yandex (CalDAV) and Google Calendar events in the desktop's calendar,
sends meeting reminders, and lets you answer invitations. It never creates,
edits or deletes events.
It is open source: everything it does is in this repository.

## What it accesses

When you sign in, you grant access to your calendars through Google's own
sign-in page, or with a Yandex app password:

- **Google:** the Google Calendar scope (`https://www.googleapis.com/auth/calendar`),
  plus your email address, to show which account is signed in.
- **Yandex / CalDAV:** an app password for the calendar only.

It uses that access only to show your events, remind you about them, and send
the answers to invitations you choose. It doesn't read email, contacts, files or
anything else.

## Where your data goes

Nowhere but your own computer. Datebook has no server, and no one
operates a service behind it: it runs entirely on your machine and talks
directly to Google's and your CalDAV server's calendar APIs.

- **Sign-in tokens** are stored in your system keyring (the GNOME keyring,
  through `secret-tool`), never in a plain file.
- **Account settings** that aren't secret (account names, and the server and
  login you signed in with) are kept in
  `~/.config/predmaxim.datebook/`, readable only by you.
- **A copy of your events** is kept in your user cache, readable only by you,
  so the calendar can show them instantly and work offline.

Your calendar data is never sent to the developer, never shared with or sold
to anyone, and never used for advertising, analytics or training.

## Removing your data

- `calendar-ctl remove <account>` deletes that account's settings and its
  keyring entry. Do this for each account **before** removing the plugin:
  removing the plugin alone leaves the keyring entries in place.
- Removing the plugin doesn't delete its files outside the plugin folder.
  The account list in `~/.config/predmaxim.datebook/` and the copy of your
  events in `~/.cache/predmaxim.datebook/` stay until you delete them; both
  are safe to delete.
- You can revoke its access at any time: for Google at
  <https://myaccount.google.com/permissions>; for Yandex, delete the app
  password at id.yandex.ru → Security.

## Use of Google user data

Datebook's use and transfer of information received from Google APIs
adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Contact

Questions or concerns: open an issue at
<https://github.com/jonspinks/omarchy-calendar/issues>.
