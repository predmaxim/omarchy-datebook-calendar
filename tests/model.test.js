// Model.js under node: the date, draft, reminder and "next up" logic.
//   TZ=America/Toronto node tests/model.test.js
const fs = require("fs")
const path = require("path")
const src = fs.readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
const M = new Function(src + "; return { parseClock, parseDateText, eventDraft, newDraft, draftArgs," +
  " nextUp, dueSnoozes, reminderText, keyForDate, addDays, dueReminders, english, rangeTitle, shortDay, indexEvents, namedFormat, openCommand }")()
const i18nSrc = fs.readFileSync(path.join(__dirname, "..", "I18n.js"), "utf8").replace(/^\.pragma.*$/m, "")
const I = new Function(i18nSrc + "; return { translator, language, localeName, TABLES }")()

let failed = 0
function eq(got, want, name) {
  const ok = JSON.stringify(got) === JSON.stringify(want)
  if (!ok) failed++
  console.log((ok ? "ok   " : "FAIL ") + name + (ok ? "" : "\n     got  " + JSON.stringify(got) + "\n     want " + JSON.stringify(want)))
}

// Times and dates as typed.
eq(["9", "9:30", "0930", "14:30", "2pm", "2:30 pm", "12am", "12pm", "24:00", "13pm", "9:75"].map(M.parseClock),
   [540, 570, 570, 870, 840, 870, 0, 720, -1, -1, -1], "parseClock")
eq(["2026-10-02", "2026-10-2", "2026-2-30", "x"].map(M.parseDateText), ["2026-10-02", "2026-10-02", "", ""], "parseDateText")

// New events: options can't be smuggled in through a title.
let d = M.newDraft("2026-10-02", new Date(2026, 8, 27, 21, 10), "Google/c")
d.title = "--all-day"
eq(M.draftArgs(d).args, ["create", "Google/c", "--title", "--all-day", "--start", "2026-10-02 09:00",
                         "--end", "2026-10-02 10:00", "--busy"], "create: title stays a value")
d.from = "23:00"; d.to = "1am"
eq(M.draftArgs(d).args.slice(5, 8), ["2026-10-02 23:00", "--end", "2026-10-03 01:00"], "create: past midnight")
d.allDay = true; d.endDate = "2026-10-03"; d.busy = false
eq(M.draftArgs(d).args.slice(5, 10), ["2026-10-02", "--end", "2026-10-04", "--all-day", "--free"], "create: all-day ends the day after")
d.invite = "a@b.co, bad"
eq(M.draftArgs(d).error, "bad isn't an email address.", "create: bad guest")

// Editing sends only what changed.
const ev = { uid: "P/c/1", account: "P", calendar: "c", title: "T", location: "", busy: true, recurring: true,
             start: "2026-09-29T02:45:00Z", end: "2026-09-29T03:15:00Z" }
let e = M.eventDraft(ev)
eq([e.date, e.from, e.to], ["2026-09-28", "22:45", "23:15"], "edit: shown in local time")
eq(M.draftArgs(e).args, [], "edit: nothing changed")
e.title = "New"
eq(M.draftArgs(e).args, ["update", "P/c/1", "--title", "New"], "edit: title only")
e.series = true
eq(M.draftArgs(e).args, ["update", "P/c/1", "--title", "New", "--series"], "edit: series title")
e.from = "22:00"
eq(!!M.draftArgs(e).error, true, "edit: a series isn't moved")
e.series = false; e.busy = false
eq(M.draftArgs(e).args.slice(2), ["--title", "New", "--free", "--start", "2026-09-28 22:00",
                                  "--end", "2026-09-28 23:15", "--timed"], "edit: move one, and free")
const ad = M.eventDraft(Object.assign({}, ev, { start: "2026-10-05", end: "2026-10-07" }))
eq([ad.allDay, ad.date, ad.endDate], [true, "2026-10-05", "2026-10-06"], "edit: all-day shows its last day")

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

// Languages.
const ru = I.translator("ru"), en = I.translator("en")
eq([I.language("ru", "en_US"), I.language("", "ru_RU"), I.language("de", "de_DE"), I.language("", "")],
   ["ru", "ru", "en", "en"], "language: setting, then locale, else English")
eq([I.localeName("ru"), I.localeName("en")], ["ru_RU", "en_US"], "localeName")
eq([ru("Today"), ru("In %1 min", 5), ru("No such string"), en("In %1 min", 5)],
   ["Сегодня", "Через 5 мин", "No such string", "In 5 min"], "tr: table, args, fallback")
eq(Object.keys(I.TABLES.ru).filter(k => (k.match(/%\d/g) || []).sort().join() !== (I.TABLES.ru[k].match(/%\d/g) || []).sort().join()),
   [], "tr: every translation keeps its placeholders")

// Russian through tr; English unchanged without it.
by[k] = [{ title: "soon", start: at(10, 0), end: at(10, 30) }]; delete by[M.addDays(k, 1)]
eq(M.nextUp(by, now, true, ru).when, "Через 10 мин", "nextUp: ru")
eq(M.rangeTitle("week", "2026-10-07", 1, ru), "Неделя 41 · 5 окт – 11 окт", "rangeTitle: ru week")
eq(M.rangeTitle("week", "2026-10-07", 1), "Week 41 · 5 Oct – 11 Oct", "rangeTitle: English as before")
eq(M.rangeTitle("day", "2026-10-07", 1, ru), "среда 7 окт 2026", "rangeTitle: ru day")
eq(M.reminderText(back[0], "Работа", true, ru).body.indexOf("отложено · "), 0, "reminderText: ru")
eq(M.draftArgs({ date: "x" }, ru).error, "Дата начала — в виде 2026-10-02.", "draftArgs: ru error")
const allDayIdx = M.indexEvents({ calendars: [{ account: "a", id: "c", shown: true }],
  events: [{ uid: "a/c/1", account: "a", calendar: "c", title: "T", allDay: true, start: "2026-10-05", end: "2026-10-06", status: "confirmed" }] }, true, ru)
eq([allDayIdx.byDay["2026-10-05"][0].label, allDayIdx.byDay["2026-10-05"][0].allDay], ["Весь день", true], "indexEvents: ru all-day stays all-day")
eq(M.english("+%1 more", 3), "+3 more", "english: fills args")

// Bar label names: capitalised days, month abbreviations without their dot.
eq(M.namedFormat("d MMM, ddd HH:mm", "понедельник", "пн", "сент."), "d 'сент', 'Пн' HH:mm", "namedFormat: ru short")
eq(M.namedFormat("dddd HH:mm", "понедельник", "пн", "сент."), "'Понедельник' HH:mm", "namedFormat: ru long day")
eq(M.namedFormat("d MMMM 'W'ww yyyy", "Monday", "Mon", "Sep"), "d MMMM 'W'ww yyyy", "namedFormat: long month left to the locale")
eq(M.namedFormat("ddd d MMM", "Monday", "Mon", "Sep"), "'Mon' d 'Sep'", "namedFormat: English unchanged in effect")
// Telemost meetings open in the Telemost web app; everything else in the browser.
eq(M.openCommand("https://telemost.yandex.ru/j/12345678901234"),
   ["omarchy-launch-webapp", "https://telemost.yandex.ru/j/12345678901234"], "openCommand: Telemost")
eq(M.openCommand("https://telemost.360.yandex.ru/j/5566"), ["omarchy-launch-webapp", "https://telemost.360.yandex.ru/j/5566"], "openCommand: Telemost 360")
eq(M.openCommand("https://calendar.yandex.ru/event?event_id=1"), ["xdg-open", "https://calendar.yandex.ru/event?event_id=1"], "openCommand: other links")
eq(M.openCommand("https://telemost.yandex.ru.evil.example/j/1")[0], "xdg-open", "openCommand: lookalike host")

if (failed) { console.log(failed + " failed"); process.exit(1) }
console.log("all passed")
