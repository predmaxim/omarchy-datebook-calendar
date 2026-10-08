import QtQuick
import qs.Commons
import qs.Ui
import "Model.js" as Model

// One event, read only: what, when, where, your part in it, and the ways out:
// answer an invitation, join the meeting, or open the event on the web.
Item {
  id: card

  property var event: null                       // a row from Model.indexEvents
  property bool use24h: true
  property bool busy: false                      // an answer is being sent
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property var tr: Model.english                 // I18n.translator from the panel
  property var labelLocale: Qt.locale("en_US")   // the format locale

  signal close()
  signal openLink(string url)
  signal respond(string answer)

  readonly property bool hasWeb: !!event && /^https:\/\//.test(String(event.webLink || ""))
  readonly property bool hasJoin: !!event && !!event.join && /^https:\/\//.test(String(event.join.url || ""))
  // The description as the web app shows it; LOCATION may hold a stale link.
  readonly property string description: event ? String(event.description || event.location || "") : ""

  // The keyboard cursor (Model.cardMove): the description's links, then the
  // buttons in their order; -1 until an arrow is pressed.
  readonly property var urls: Model.linksIn(description)
  readonly property var buttons: [Model.isInvitation(event) ? "answer" : "", hasJoin ? "join" : "", hasWeb ? "web" : "", "close"]
                                 .filter(function(b) { return b })
  property int cursor: -1
  readonly property string cursorAt: cursor < 0 ? "" : cursor < urls.length ? "link" : buttons[cursor - urls.length] || ""

  implicitHeight: body.implicitHeight

  onEventChanged: {
    cursor = -1
    if (event) Qt.callLater(function() { body.forceActiveFocus() })
  }

  // Enter: what the cursor is on, as a click would.
  function press() {
    if (cursorAt === "link") openLink(urls[cursor])
    else if (cursorAt === "answer") { if (!busy) answer.openWithKeys() }
    else if (cursorAt === "join") openLink(event.join.url)
    else if (cursorAt === "web") openLink(event.webLink)
    else if (cursorAt === "close") close()
  }

  // A line of the card: plain text, with its https links clickable. RichText,
  // as StyledText can't fill the link under the cursor; it takes link colours inline.
  component Line: Text {
    property string plain: ""
    property int current: -1                     // the link under the keyboard cursor
    width: parent.width
    wrapMode: Text.WordWrap
    textFormat: Text.RichText
    text: Model.linkify(plain, { color: String(Color.accent), current: current,
                                 fill: String(Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.3)) })
    color: card.foreground
    font.family: card.fontFamily
    font.pixelSize: Style.font.body
    onLinkActivated: function(link) { card.openLink(link) }

    HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
  }

  Column {
    id: body
    width: parent.width
    spacing: Style.space(8)
    focus: true
    // The card's key map (Model.CARD_KEYS); a key with nothing to do here
    // (no link, not an invitation) is still kept from the panel.
    Keys.onPressed: function(event) {
      var a = Model.CARD_KEYS[Model.chord(event.key, event.nativeScanCode, event.modifiers)]
      if (!a) return
      event.accepted = true
      if (a[0] === "close") card.close()
      else if (a[0] === "move") card.cursor = Model.cardMove(card.urls.length, card.urls.length + card.buttons.length, card.cursor, a[1])
      else if (a[0] === "press") card.press()
      else if (a[0] === "join") { if (card.hasJoin) card.openLink(card.event.join.url) }
      else if (a[0] === "web") { if (card.hasWeb) card.openLink(card.event.webLink) }
      else if (a[0] === "answer") { if (Model.isInvitation(card.event) && !card.busy) card.respond(a[1]) }
    }

    Text {
      textFormat: Text.PlainText
      text: card.tr("EVENT")
      color: Qt.darker(card.foreground, 1.4)
      font.family: card.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: true
      font.letterSpacing: 1.2
    }

    Line {
      plain: card.event ? card.event.title : ""
      font.pixelSize: Style.font.display
      font.bold: true
    }

    Line { plain: card.event ? Model.cardWhen(card.event, card.use24h, card.tr, card.labelLocale) : "" }

    Line {
      plain: card.event ? Model.cardCalendar(card.event, card.tr) : ""
      color: Qt.darker(card.foreground, 1.4)
    }

    Line {
      visible: plain !== ""
      plain: card.description
      current: card.cursorAt === "link" ? card.cursor : -1
    }

    Line {
      visible: plain !== ""
      plain: card.event ? [Model.isInvitation(card.event) ? "" : Model.responseText(card.event, card.tr), card.tr(card.event.busy ? "Busy" : "Free")]
                           .filter(function(s) { return s }).join("  ·  ") : ""
      color: Qt.darker(card.foreground, 1.4)
    }

    Item {
      width: parent.width
      height: Math.max(buttonRow.height, closeButton.height)

      Row {
        id: buttonRow
        anchors.left: parent.left
        spacing: Style.space(6)

        AnswerPicker {
          id: answer
          event: card.event
          busy: card.busy
          foreground: card.foreground
          fontFamily: card.fontFamily
          tr: card.tr
          hasCursor: card.cursorAt === "answer"
          onRespond: function(a) { card.respond(a) }
          onOpenChanged: if (!open) Qt.callLater(function() { body.forceActiveFocus() })   // the answers had the keys
        }

        Button {
          visible: card.hasJoin
          hasCursor: card.cursorAt === "join"
          bordered: true
          iconText: "󰕧"
          text: card.tr("Join")
          foreground: card.foreground
          fontFamily: card.fontFamily
          onClicked: card.openLink(card.event.join.url)
        }

        Button {
          visible: card.hasWeb
          hasCursor: card.cursorAt === "web"
          bordered: true
          iconText: "󰏌"
          text: card.tr("Open in Web")
          foreground: card.foreground
          fontFamily: card.fontFamily
          onClicked: card.openLink(card.event.webLink)
        }
      }

      Button {
        id: closeButton
        anchors.right: parent.right
        hasCursor: card.cursorAt === "close"
        text: card.tr("Close")
        foreground: card.foreground
        fontFamily: card.fontFamily
        onClicked: card.close()
      }
    }
  }
}
