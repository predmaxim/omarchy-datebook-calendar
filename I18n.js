.pragma library
// Interface text in other languages, keyed by the English text itself, so a
// string missing from a table simply shows in English. Day and month names
// aren't here: they come from the format locale (see Model.js). tr("In %1 min", 5)
// fills in %1, %2… after the lookup. Qt's qsTr isn't used: Quickshell plugins
// get no .qm catalogues. Kept Qt-free so it runs under node (tests/model.test.js).
var TABLES = {
  ru: {
    // Views and navigation
    "Day": "День", "Week": "Неделя", "Work week": "Рабочая неделя", "Month": "Месяц", "Year": "Год",
    "One day (1)": "Один день (1)", "Seven days (2)": "Семь дней (2)",
    "Monday to Friday (3)": "С понедельника по пятницу (3)", "The month grid (4)": "Сетка месяца (4)",
    "Twelve months (5)": "Двенадцать месяцев (5)",
    "Previous day": "Предыдущий день", "Previous week": "Предыдущая неделя",
    "Previous month": "Предыдущий месяц", "Previous year": "Предыдущий год",
    "Next day": "Следующий день", "Next week": "Следующая неделя", "Next month": "Следующий месяц",
    "Next year": "Следующий год", "Previous ([)": "Назад ([)", "Next (])": "Вперёд (])",
    "Today": "Сегодня", "Tomorrow": "Завтра", "Yesterday": "Вчера",
    "Back to today": "К сегодняшнему дню", "Back to today (t)": "К сегодняшнему дню (t)",
    "Compact: Omarchy's month and the day's appointments": "Свернуть: месяц Omarchy и события дня",
    "Start weeks on %1": "Начинать неделю с: %1", "year": "год",
    // Days and events
    "Nothing on.": "Событий нет.", "Nothing in the next week": "На ближайшей неделе ничего",
    "All day": "Весь день", "from %1": "с %1", "until %1": "до %1", "+%1 more": "ещё %1",
    "repeats": "повторяется",
    "Choose calendars": "Выбрать календари",
    "Expand": "Развернуть", "Calendars": "Календари", "More": "Ещё", "Clock format": "Формат часов", "Time zone": "Часовой пояс",
    "Sync now": "Синхронизировать сейчас", "Syncing…": "Синхронизация…",
    "sign-in needed": "нужен вход", "offline": "нет сети", "couldn't sync": "не удалось синхронизировать",
    "sign-in needed (calendar-ctl add-%1 %2 …)": "нужен вход (calendar-ctl add-%1 %2 …)",
    "offline, showing the last copy": "нет сети, показана последняя копия",
    "No accounts yet: add one with calendar-ctl.": "Аккаунтов пока нет: добавьте через calendar-ctl.",
    // Next up, joining, reminders
    "Now · %1 min left": "Сейчас · осталось %1 мин", "Now · until %1": "Сейчас · до %1",
    "In %1 min": "Через %1 мин", "In %1 h %2 min · %3": "Через %1 ч %2 мин · %3",
    "Today · %1": "Сегодня · %1", "Tomorrow · %1": "Завтра · %1",
    "Join": "Подключиться", "Open": "Открыть", "Snooze": "Отложить", "Snooze %1 min": "Отложить на %1 мин",
    "Remind me again in %1 minutes": "Напомнить снова через %1 мин",
    "Join the %1 meeting": "Подключиться к встрече: %1", "online": "онлайн",
    "today": "сегодня", "in %1 min": "через %1 мин", "starting now": "начинается",
    "started %1 min ago": "началось %1 мин назад", "snoozed · %1": "отложено · %1",
    " · click to join %1": " · нажмите, чтобы подключиться: %1", "the meeting": "встреча",
    " · click to open": " · нажмите, чтобы открыть", "Calendar: not saved": "Календарь: не сохранено",
    // Invitations
    "Accept": "Принять", "Maybe": "Возможно", "Decline": "Отклонить", "Your answer now": "Ваш текущий ответ",
    "%1 and let the organiser know": "%1 и сообщить организатору", "Every occurrence: ": "Все повторы: ",
    // Labels
    "Busy": "Занят", "Free": "Свободен",
    "CALENDARS": "КАЛЕНДАРИ", "BORN": "РОЖДЕНИЕ", "LIVE TO": "ПРОЖИТЬ ДО", "LIFE": "ЖИЗНЬ",
    "Close": "Закрыть",
    // The event card
    "EVENT": "СОБЫТИЕ", "You organise it": "Вы организатор", "You accepted": "Вы приняли",
    "You said maybe": "Вы ответили «может быть»", "You declined": "Вы отклонили",
    "Not answered yet": "Вы ещё не ответили", "Open in Web": "Открыть в браузере", "also in %1": "также в %1",
    "Accepted": "Принято", "Declined": "Отклонено", "Choose": "Выбрать"
  }
}

// The text language and the format locale, split as the system splits them:
// text follows LC_MESSAGES, dates LC_TIME, both overridden by LC_ALL and
// defaulting to LANG. env is name -> value (Quickshell.env in QML).
function localeVar(env, category) {
  var names = ["LC_ALL", category, "LANG"]
  for (var i = 0; i < names.length; i++) {
    var v = String(env(names[i]) || "").split(".")[0].split("@")[0]
    if (v && v !== "C" && v !== "POSIX") return v
  }
  return "en_US"
}
// A language with a table in TABLES, else English.
function textLanguage(env) {
  var l = localeVar(env, "LC_MESSAGES").slice(0, 2).toLowerCase()
  return TABLES[l] ? l : "en"
}
function formatLocaleName(env) {
  return localeVar(env, "LC_TIME")
}
function translator(lang) {
  var table = TABLES[lang] || {}
  return function (text) {
    var out = Object.prototype.hasOwnProperty.call(table, text) ? table[text] : text
    for (var i = 1; i < arguments.length; i++) out = out.split("%" + i).join(String(arguments[i]))
    return out
  }
}
