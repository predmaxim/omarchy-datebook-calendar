.pragma library
// Interface text in other languages, keyed by the English text itself, so a
// string missing from a table simply shows in English. tr("In %1 min", 5)
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
    "Expand: week, month and year views, and your calendars": "Развернуть: неделя, месяц, год и ваши календари",
    "Compact: Omarchy's month and the day's appointments": "Свернуть: месяц Omarchy и события дня",
    "Start weeks on %1": "Начинать неделю с: %1", "year": "год", "Week %1 · ": "Неделя %1 · ",
    // Days and events
    "Nothing on.": "Событий нет.", "Nothing in the next week": "На ближайшей неделе ничего",
    "All day": "Весь день", "from %1": "с %1", "until %1": "до %1", "+%1 more": "ещё %1",
    "%1 1": "1 %1", "repeats": "повторяется",
    "New": "Новое", "New event on this day (n)": "Новое событие в этот день (n)",
    "New event on the selected day (n)": "Новое событие в выбранный день (n)",
    "Choose calendars": "Выбрать календари", "Pick which calendars to show": "Какие календари показывать",
    "Sync": "Синхронизировать", "Sync now": "Синхронизировать сейчас", "Syncing…": "Синхронизация…",
    "sign-in needed": "нужен вход", "offline": "нет сети", "couldn't sync": "не удалось синхронизировать",
    "sign-in needed (calendar-ctl add-%1 %2 …)": "нужен вход (calendar-ctl add-%1 %2 …)",
    "offline, showing the last copy": "нет сети, показана последняя копия",
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
    // Editor
    "NEW EVENT": "НОВОЕ СОБЫТИЕ", "EDIT EVENT": "ИЗМЕНИТЬ СОБЫТИЕ", "INVITATION": "ПРИГЛАШЕНИЕ",
    "Title": "Название", "Busy": "Занят", "Free": "Свободен",
    "Others see you as busy": "Другие видят, что вы заняты",
    "Others see you as available": "Другие видят, что вы свободны",
    "Location": "Место", "Invite: email addresses, separated by commas": "Пригласить: адреса через запятую",
    "Every occurrence": "Все повторы",
    "Title, place and delete apply to the whole series; times move one at a time":
      "Название, место и удаление — для всей серии; время переносится по одному повтору",
    "Answer for the whole series": "Ответить за всю серию",
    "Delete the series?": "Удалить серию?", "Really delete?": "Точно удалить?", "Delete": "Удалить",
    "Take it off your calendar (decline to tell the organiser)":
      "Убрать из календаря (чтобы сообщить организатору, отклоните)",
    "Delete it; guests get a cancellation": "Удалить; гости получат отмену",
    "Open in %1": "Открыть в %1", "Google Calendar": "Google Календаре",
    "Yandex Calendar": "Яндекс Календаре", "Outlook": "Outlook",
    "Cancel": "Отмена", "Close": "Закрыть", "Saving…": "Сохранение…", "Create": "Создать", "Save": "Сохранить",
    // Checks on what was typed
    "The start date should look like 2026-10-02.": "Дата начала — в виде 2026-10-02.",
    "The end date should look like 2026-10-02.": "Дата окончания — в виде 2026-10-02.",
    "The last day can't be before the first.": "Последний день не может быть раньше первого.",
    "The start time should look like 14:30 or 2:30pm.": "Время начала — в виде 14:30.",
    "The end time should look like 15:30 or 3:30pm.": "Время окончания — в виде 15:30.",
    "The end can't be before the start.": "Окончание не может быть раньше начала.",
    "Pick a calendar.": "Выберите календарь.", "%1 isn't an email address.": "%1 — не адрес почты.",
    "A whole series can't be moved from here: untick it to move this one.":
      "Всю серию отсюда не перенести: снимите галочку, чтобы перенести этот повтор.",
    // Names Model.js spells out
    "Sunday": "воскресенье", "Monday": "понедельник", "Tuesday": "вторник", "Wednesday": "среда",
    "Thursday": "четверг", "Friday": "пятница", "Saturday": "суббота",
    "Sun": "вс", "Mon": "пн", "Tue": "вт", "Wed": "ср", "Thu": "чт", "Fri": "пт", "Sat": "сб",
    "Jan": "янв", "Feb": "фев", "Mar": "мар", "Apr": "апр", "May": "мая", "Jun": "июн",
    "Jul": "июл", "Aug": "авг", "Sep": "сен", "Oct": "окт", "Nov": "ноя", "Dec": "дек"
  }
}

function language(setting, localeName) {
  var wanted = [setting, localeName]
  for (var i = 0; i < wanted.length; i++) {
    var l = String(wanted[i] || "").slice(0, 2).toLowerCase()
    if (TABLES[l]) return l
  }
  return "en"
}

function localeName(lang) {
  return ({ ru: "ru_RU" })[lang] || "en_US"
}

function translator(lang) {
  var table = TABLES[lang] || {}
  return function (text) {
    var out = Object.prototype.hasOwnProperty.call(table, text) ? table[text] : text
    for (var i = 1; i < arguments.length; i++) out = out.split("%" + i).join(String(arguments[i]))
    return out
  }
}
