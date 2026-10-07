// Model.js under node: the date, card, reminder and "next up" logic.
//   TZ=America/Toronto node tests/model.test.js
const fs = require("fs")
const path = require("path")
const src = fs.readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
const M = new Function(src + "; return { nextUp, dueSnoozes, reminderText, keyForDate, addDays, dueReminders, english," +
  " rangeTitle, shortDay, indexEvents, namedFormat, openCommand, capitalize, dateLabel, cardWhen, responseText, cardCalendar, linkify, answerLabel, isInvitation, boldTime, isPast, cardStart, chord, shiftKey, PANEL_KEYS, CARD_KEYS, SETTINGS_KEYS }")()
const i18nSrc = fs.readFileSync(path.join(__dirname, "..", "I18n.js"), "utf8").replace(/^\.pragma.*$/m, "")
const I = new Function(i18nSrc + "; return { translator, textLanguage, formatLocaleName, TABLES }")()

let failed = 0
function eq(got, want, name) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (!ok) failed++
  console.log((ok ? "ok   " : "FAIL ") + name + (ok ? "" : "\n     got  " + JSON.stringify(got) + "\n     want " + JSON.stringify(want)))
}

// Bar label: only the time is bold.
eq(M.boldTime("29 сент., Вт 09:44"), "29 сент., Вт <b>09:44</b>", "boldTime: date and time")
eq(M.boldTime("Mon 9:05:30 PM"), "Mon <b>9:05:30 PM</b>", "boldTime: seconds and AM/PM")
eq(M.boldTime("a<b & c"), "a&lt;b &amp; c", "boldTime: no time, markup escaped")

// Past events: over once their end has come; all-day ones the day after.
{
  const nowMs = new Date(2026, 8, 28, 9, 50).getTime(), day = M.keyForDate(new Date(nowMs))
  const t = (h, m, dd) => new Date(2026, 8, 28 + (dd || 0), h, m).toISOString()
  eq(M.isPast({ start: t(8, 0), end: t(9, 0) }, nowMs), true, "isPast: ended earlier today")
  eq(M.isPast({ start: t(9, 0), end: t(9, 50) }, nowMs), true, "isPast: ends right now")
  eq(M.isPast({ start: t(9, 30), end: t(10, 0) }, nowMs), false, "isPast: on now")
  eq(M.isPast({ start: t(22, 0, -2), end: t(12, 0) }, nowMs), false, "isPast: multi-day, still on")
  eq(M.isPast({ start: M.addDays(day, -1), end: day, allDay: true }, nowMs), true, "isPast: all-day yesterday")
  eq(M.isPast({ start: day, end: M.addDays(day, 1), allDay: true }, nowMs), false, "isPast: all-day today")
  eq(M.isPast({ start: M.addDays(day, -1), end: M.addDays(day, -1), allDay: true }, nowMs), true, "isPast: all-day, end not after start")
}

// The card Enter opens: the first timed event not over yet, else the day's first.
{
  const nowMs = new Date(2026, 8, 28, 9, 50).getTime(), day = M.keyForDate(new Date(nowMs))
  const t = (h, m) => new Date(2026, 8, 28, h, m).toISOString()
  const allDay = { start: day, end: M.addDays(day, 1), allDay: true }
  const past = { start: t(8, 0), end: t(9, 0) }, now = { start: t(9, 30), end: t(10, 0) }
  eq(M.cardStart([allDay, past, now], nowMs), 2, "cardStart: skips all-day and past")
  eq(M.cardStart([allDay, past], nowMs), 0, "cardStart: all over, the first")
  eq(M.cardStart([], nowMs), -1, "cardStart: no events")
}

// Keys as chords: modifiers by name, letters by scan code in any layout.
{
  const Left = 0x01000012, Return = 0x01000004, Enter = 0x01000005, Backtab = 0x01000002
  const Shift = 0x02000000, Ctrl = 0x04000000, Alt = 0x08000000, Keypad = 0x20000000
  eq([M.chord(Left, 113, 0), M.chord(Left, 113, Shift), M.chord(Left, 113, Shift | Keypad)],
     ["Left", "Shift+Left", "Shift+Left"], "chord: arrows, Shift, keypad flag ignored")
  eq([M.chord(Return, 36, Ctrl), M.chord(Enter, 104, Alt), M.chord(Backtab, 23, Shift)],
     ["Ctrl+Enter", "Alt+Enter", "Shift+Tab"], "chord: Enter both keys, Shift+Tab")
  eq([M.chord(0x52, 27, Ctrl), M.chord(0x41a, 27, Ctrl), M.chord(0x411, 59, Ctrl), M.chord(0x31, 10, 0)],
     ["Ctrl+R", "Ctrl+R", "Ctrl+,", "1"], "chord: Latin, the Russian layout by scan code, digits")
  eq(M.chord(0x416, 47, 0), "", "chord: an unmapped Cyrillic key")
  const tables = [M.PANEL_KEYS, M.CARD_KEYS, M.SETTINGS_KEYS]
  eq(tables.map(t => Object.keys(t).filter(k => !/^((Ctrl|Alt|Shift)\+)*(Left|Right|Up|Down|Home|Enter|Esc|Tab|[0-9]|[A-Z]|,)$/.test(k))),
     [[], [], []], "key tables: only chords chord() can give")
}

// The selected day moved by a day, week, month or year.
eq([M.shiftKey("2026-12-31", "day", 1), M.shiftKey("2026-10-08", "week", -1), M.shiftKey("2026-01-31", "month", 1),
    M.shiftKey("2026-03-31", "month", -1), M.shiftKey("2024-02-29", "year", 1)],
   ["2027-01-01", "2026-10-01", "2026-02-28", "2026-02-28", "2025-02-28"], "shiftKey: across the year, month ends clamped")

// Next up.
const now = new Date(2026, 8, 28, 9, 50), k = M.keyForDate(now)
const at = (h, m, dd) => new Date(2026, 8, 28 + (dd || 0), h, m).toISOString()
const by = {}
by[k] = [{ title: "past", start: at(8, 0), end: at(9, 0) },
         { title: "allday", start: k, end: M.addDays(k, 1), allDay: true },
         { title: "declined", start: at(10, 0), end: at(11, 0), declined: true },
         { title: "live", start: at(9, 30), end: at(10, 15) },
         { title: "soon", start: at(10, 0), end: at(10, 30) }]
let n = M.nextUp(by, now, false)
eq([n.event.title, n.when, n.live], ["live", "Now · 25 min left", true], "nextUp: on now")
by[k].splice(3, 1); n = M.nextUp(by, now, false)
eq([n.event.title, n.when, n.soon], ["soon", "In 10 min", true], "nextUp: soon")
by[k] = []; by[M.addDays(k, 1)] = [{ title: "t", start: at(14, 30, 1), end: at(15, 0, 1) }]
eq(M.nextUp(by, now, false).when, "Tomorrow · 2:30pm", "nextUp: tomorrow")
eq(M.nextUp({}, now, false), null, "nextUp: nothing")

// Snoozes come back while the event runs, and say so.
const t = Date.now(), iso = ms => new Date(ms).toISOString().replace(/\.\d+Z/, "Z")
const se = { uid: "a/c/1", account: "a", calendar: "c", title: "T", allDay: false, start: iso(t - 60000),
             end: iso(t + 1800000), status: "confirmed", join: { url: "https://x" }, remind: [5], response: "organizer" }
eq(M.dueSnoozes({ events: [se] }, { "snooze:a/c/1": t + 1000 }, t).length, 0, "snooze: not yet")
const back = M.dueSnoozes({ events: [se] }, { "snooze:a/c/1": t - 1 }, t)
eq(back.length, 1, "snooze: due")
eq(M.reminderText(back[0], "Work", false).body.indexOf("snoozed · "), 0, "snooze: labelled")
eq(M.dueSnoozes({ events: [Object.assign({}, se, { end: iso(t - 1) })] }, { "snooze:a/c/1": t - 1 }, t).length, 0, "snooze: not after the end")

// Languages: text from LC_MESSAGES, formats from LC_TIME, as the system splits them.
const envOf = vars => name => vars[name]
const mine = envOf({ LANG: "en_US.UTF-8", LC_TIME: "ru_RU.UTF-8" })
eq([I.textLanguage(mine), I.formatLocaleName(mine)], ["en", "ru_RU"], "locale: English text, Russian formats")
eq([I.textLanguage(envOf({ LANG: "ru_RU.UTF-8" })), I.formatLocaleName(envOf({ LANG: "ru_RU.UTF-8" }))], ["ru", "ru_RU"], "locale: LANG alone")
eq([I.textLanguage(envOf({ LC_ALL: "ru_RU.UTF-8", LC_MESSAGES: "en_US.UTF-8", LC_TIME: "de_DE.UTF-8" })),
    I.formatLocaleName(envOf({ LC_ALL: "ru_RU.UTF-8", LC_TIME: "de_DE.UTF-8" }))], ["ru", "ru_RU"], "locale: LC_ALL wins")
eq([I.textLanguage(envOf({ LANG: "C.UTF-8" })), I.formatLocaleName(envOf({})), I.textLanguage(envOf({ LC_MESSAGES: "de_DE@euro" }))],
   ["en", "en_US", "en"], "locale: C, nothing, no table")
const ru = I.translator("ru"), en = I.translator("en")
eq([ru("Today"), ru("In %1 min", 5), ru("No such string"), en("In %1 min", 5)],
   ["Сегодня", "Через 5 мин", "No such string", "In 5 min"], "tr: table, args, fallback")
eq(Object.keys(I.TABLES.ru).filter(k => (k.match(/%\d/g) || []).sort().join() !== (I.TABLES.ru[k].match(/%\d/g) || []).sort().join()),
   [], "tr: every translation keeps its placeholders")

// Every tr("…") literal has a Russian line, and no Russian line is left over.
const sources = fs.readdirSync(path.join(__dirname, "..")).filter(f => /\.(qml|js)$/.test(f) && f !== "I18n.js")
  .map(f => fs.readFileSync(path.join(__dirname, "..", f), "utf8")).join("\n")
const used = new Set([...sources.matchAll(/\btr\("((?:[^"\\]|\\.)*)"\s*[,)]/g)].map(m => JSON.parse('"' + m[1] + '"')))
eq([...used].filter(k => !(k in I.TABLES.ru)), [], "tr: every string translated")
eq(Object.keys(I.TABLES.ru).filter(k => !sources.includes(JSON.stringify(k))), [], "tr: no unused translations")

// A Russian format locale, as Qt's Locale gives its names (0 long, 1 short; months in the genitive).
const RU = {
  name: "ru_RU",
  dayName: (i, f) => (f === 1 ? ["вс", "пн", "вт", "ср", "чт", "пт", "сб"]
                              : ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"])[i],
  monthName: (i, f) => (f === 1 ? ["янв.", "февр.", "мар.", "апр.", "мая", "июн.", "июл.", "авг.", "сент.", "окт.", "нояб.", "дек."]
                                : ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"])[i]
}

// Text through tr, names through the format locale.
by[k] = [{ title: "soon", start: at(10, 0), end: at(10, 30) }]; delete by[M.addDays(k, 1)]
eq(M.nextUp(by, now, true, ru, RU).when, "Через 10 мин", "nextUp: ru")
eq(M.rangeTitle("week", "2026-10-07", 1, ru, RU), "5 окт – 11 окт", "rangeTitle: week, no week number")
eq(M.rangeTitle("workweek", "2026-10-07", 1, en, RU), "5 окт – 9 окт", "rangeTitle: working week, Russian months")
eq(M.rangeTitle("week", "2026-10-07", 1), "5 Oct – 11 Oct", "rangeTitle: English months without a locale")
eq(M.rangeTitle("day", "2026-10-07", 1, en, RU), "среда 7 окт 2026", "rangeTitle: day in the format locale")
by[k] = []; by[M.addDays(k, 3)] = [{ title: "t", start: at(14, 30, 3), end: at(15, 0, 3) }]
eq(M.nextUp(by, now, true, en, RU).when, "чт · 14:30", "nextUp: weekday from the format locale")
eq(M.reminderText(back[0], "Работа", true, ru).body.indexOf("отложено · "), 0, "reminderText: ru")
const allDayIdx = M.indexEvents({ calendars: [{ account: "a", id: "c", shown: true }],
  events: [{ uid: "a/c/1", account: "a", calendar: "c", title: "T", allDay: true, start: "2026-10-05", end: "2026-10-06", status: "confirmed", description: "D" }] }, true, ru)
eq([allDayIdx.byDay["2026-10-05"][0].label, allDayIdx.byDay["2026-10-05"][0].allDay], ["Весь день", true], "indexEvents: ru all-day stays all-day")
eq(allDayIdx.byDay["2026-10-05"][0].description, "D", "indexEvents: description reaches the card")
eq(M.english("+%1 more", 3), "+3 more", "english: fills args")

// The event card.
eq(M.dateLabel(new Date(2026, 8, 29), RU), "Вторник, 29 сентября", "dateLabel: ru")
eq(M.dateLabel(new Date(2026, 8, 29)), "Tuesday, September 29", "dateLabel: en_US")
const timed = { start: new Date(2026, 8, 29, 10, 0).toISOString(), end: new Date(2026, 8, 29, 10, 15).toISOString() }
eq(M.cardWhen(timed, true, en, RU), "Вторник, 29 сентября · 10:00 – 10:15", "cardWhen: timed")
eq(M.cardWhen({ start: new Date(2026, 8, 29, 23, 0).toISOString(), end: new Date(2026, 8, 30, 1, 0).toISOString() }, true, en, RU),
   "Вторник, 29 сентября 23:00 – Среда, 30 сентября 01:00", "cardWhen: past midnight")
eq(M.cardWhen({ start: "2026-10-05", end: "2026-10-06" }, true, en, RU), "Понедельник, 5 октября · All day", "cardWhen: all day")
eq(M.cardWhen({ start: "2026-10-05", end: "2026-10-08" }, true, ru, RU),
   "Понедельник, 5 октября – Среда, 7 октября · Весь день", "cardWhen: several days, last day inclusive")
const copies = M.indexEvents({ calendars: [{ account: "a", id: "c", name: "Мои события", shown: true }],
  events: [{ uid: "a/c/1", account: "a", calendar: "c", title: "T", allDay: true, start: "2026-10-05", end: "2026-10-06",
             status: "confirmed", recurring: true, alsoIn: ["Google: Work"] }] }, true, en).byDay["2026-10-05"][0]
eq(M.cardCalendar(copies, en), "Мои события  ·  repeats  ·  also in Google: Work", "cardCalendar: repeats and copies")
eq(M.cardCalendar({ calendarName: "Мои события", recurring: false }, ru), "Мои события", "cardCalendar: just the calendar")
eq(M.linkify("Zoom: https://zoom.us/j/1?pwd=a&b=2, room <5>"),
   'Zoom: <a href="https://zoom.us/j/1?pwd=a&amp;b=2">https://zoom.us/j/1?pwd=a&amp;b=2</a>, room &lt;5&gt;', "linkify: https link, text escaped, trailing comma left out")
eq(M.linkify("http://x.ru and javascript:alert(1) and \"https://a.ru/x\"."),
   'http://x.ru and javascript:alert(1) and &quot;<a href="https://a.ru/x">https://a.ru/x</a>&quot;.', "linkify: only https, quotes and dot outside")
eq(M.linkify("a\nb"), "a<br>b", "linkify: line breaks kept")
eq(M.linkify(""), "", "linkify: empty")
eq(["accepted", "tentative", "declined", "needsAction"].map(r => M.answerLabel({ response: r }, en)),
   ["Accepted", "Maybe", "Declined", "Choose"], "answerLabel: the answer made, else Choose")
eq(M.answerLabel({ response: "declined" }, ru), "Отклонено", "answerLabel: ru")
eq([{ organizer: false, response: "needsAction" }, { organizer: false, response: "declined" }, { organizer: true, response: "organizer" },
    { organizer: false, response: "none" }, { organizer: false }, null].map(r => M.isInvitation(r)),
   [true, true, false, false, false, false], "isInvitation: on the guest list, not the organiser")
eq(["organizer", "accepted", "tentative", "declined", "needsAction", "none"].map(r => M.responseText({ response: r, organizer: r === "organizer" }, en)),
   ["You organise it", "You accepted", "You said maybe", "You declined", "Not answered yet", ""], "responseText")

// Bar label names: capitalised days, month abbreviations without their dot.
eq(M.namedFormat("d MMM, ddd HH:mm", "понедельник", "пн", "сент."), "d 'Сент', 'Пн' HH:mm", "namedFormat: ru short")
eq(M.namedFormat("dddd HH:mm", "понедельник", "пн", "сент."), "'Понедельник' HH:mm", "namedFormat: ru long day")
eq(M.namedFormat("d MMMM 'W'ww yyyy", "Monday", "Mon", "Sep"), "d MMMM 'W'ww yyyy", "namedFormat: long month left to the locale")
eq(M.namedFormat("ddd d MMM", "Monday", "Mon", "Sep"), "'Mon' d 'Sep'", "namedFormat: English unchanged in effect")
// Telemost meetings open in the Telemost web app; everything else in the browser.
eq(M.openCommand("https://telemost.yandex.ru/j/12345678901234"),
   ["omarchy-launch-webapp", "https://telemost.yandex.ru/j/12345678901234?skip_app=1"], "openCommand: Telemost, without the desktop app prompt")
eq(M.openCommand("https://telemost.360.yandex.ru/j/5566"), ["omarchy-launch-webapp", "https://telemost.360.yandex.ru/j/5566?skip_app=1"], "openCommand: Telemost 360")
eq(M.openCommand("https://telemost.yandex.ru/j/5566?x=1"), ["omarchy-launch-webapp", "https://telemost.yandex.ru/j/5566?x=1&skip_app=1"], "openCommand: Telemost link with a query")
eq(M.openCommand("https://calendar.yandex.ru/event?event_id=1"), ["xdg-open", "https://calendar.yandex.ru/event?event_id=1"], "openCommand: other links")
eq(M.openCommand("https://telemost.yandex.ru.evil.example/j/1")[0], "xdg-open", "openCommand: lookalike host")

// Headings: every caption has a Russian form; month names start upper-case.
eq(["CALENDARS", "EVENT", "BORN", "LIVE TO", "LIFE"].filter(k => !(k in I.TABLES.ru)),
   [], "tr: captions translated")
eq([M.capitalize("сентябрь 2026"), M.capitalize("September"), M.capitalize("")], ["Сентябрь 2026", "September", ""], "capitalize")

// Every Model.X the QML uses exists in Model.js (a removed helper otherwise
// fails only at run time, as a TypeError in the shell's log).
const qml = fs.readdirSync(path.join(__dirname, "..")).filter(f => f.endsWith(".qml"))
  .map(f => fs.readFileSync(path.join(__dirname, "..", f), "utf8")).join("\n")
const defined = new Set([...src.matchAll(/^(?:function|var)\s+(\w+)/gm)].map(m => m[1]))
eq([...new Set([...qml.matchAll(/(?<!")\bModel\.(\w+)/g)].map(m => m[1]))].filter(n => !defined.has(n)), [], "qml: every Model.X is defined")

if (failed) { console.log(failed + " failed"); process.exit(1) }
console.log("all passed")
