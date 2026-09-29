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
  readonly property bool invitation: !!event && !event.organizer && event.response !== "none"

  implicitHeight: body.implicitHeight

  onEventChanged: {
    answer.open = false
    if (event) Qt.callLater(function() { body.forceActiveFocus() })
  }

  // A line of the card: plain text, with its https links clickable.
  component Line: Text {
    property string plain: ""
    width: parent.width
    wrapMode: Text.WordWrap
    textFormat: Text.StyledText
    text: Model.linkify(plain)
    linkColor: Color.accent
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
    Keys.onPressed: function(event) {
      if (event.key === Qt.Key_Escape || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        card.close()
        event.accepted = true
      }
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
      font.pixelSize: Style.font.title
      font.bold: true
    }

    Line { plain: card.event ? Model.cardWhen(card.event, card.use24h, card.tr, card.labelLocale) : "" }

    Line {
      plain: card.event ? Model.cardCalendar(card.event, card.tr) : ""
      color: Qt.darker(card.foreground, 1.4)
    }

    Line {
      visible: plain !== ""
      plain: card.event ? String(card.event.location || "") : ""
    }

    Line {
      visible: plain !== ""
      plain: card.event ? [card.invitation ? "" : Model.responseText(card.event, card.tr), card.tr(card.event.busy ? "Busy" : "Free")]
                           .filter(function(s) { return s }).join("  ·  ") : ""
      color: Qt.darker(card.foreground, 1.4)
    }

    Item {
      width: parent.width
      height: Math.max(links.height, closeButton.height)

      Row {
        id: links
        anchors.left: parent.left
        spacing: Style.space(6)

        // An invitation: one button with the answer made (or Choose); the
        // answers open above it, where the card has room. A recurring one is
        // answered for the whole series, as in the day's list.
        Item {
          id: answer
          visible: card.invitation
          width: answerButton.width
          height: answerButton.height
          property bool open: false

          Button {
            id: answerButton
            bordered: true
            enabled: !card.busy
            iconText: "󰅀"
            text: card.event ? Model.answerLabel(card.event, card.tr) : ""
            foreground: card.event && card.event.response !== "needsAction" ? Color.accent : card.foreground
            fontFamily: card.fontFamily
            onClicked: answer.open = !answer.open
          }

          Rectangle {
            visible: answer.open
            anchors.bottom: parent.top
            anchors.bottomMargin: Style.space(4)
            width: choices.implicitWidth + Style.space(8)
            height: choices.implicitHeight + Style.space(8)
            radius: Style.cornerRadius
            color: Color.popups.background
            border.width: Style.spacing.hairline
            border.color: Color.popups.border

            Column {
              id: choices
              anchors.centerIn: parent
              spacing: Style.space(2)

              Repeater {
                model: [
                  { answer: "accept", response: "accepted", label: card.tr("Accept"), icon: "󰄬" },
                  { answer: "tentative", response: "tentative", label: card.tr("Maybe"), icon: "󰋗" },
                  { answer: "decline", response: "declined", label: card.tr("Decline"), icon: "󰅖" }
                ]
                Button {
                  required property var modelData
                  readonly property bool current: !!card.event && card.event.response === modelData.response
                  iconText: current ? "󰄵" : modelData.icon
                  text: modelData.label
                  tooltipText: current ? card.tr("Your answer now")
                                       : (card.event && card.event.recurring ? card.tr("Every occurrence: ") : "")
                                         + card.tr("%1 and let the organiser know", modelData.label)
                  foreground: current ? Color.accent : card.foreground
                  fontFamily: card.fontFamily
                  onClicked: {
                    answer.open = false
                    card.respond(modelData.answer)
                  }
                }
              }
            }
          }
        }

        Button {
          visible: card.hasJoin
          bordered: true
          iconText: "󰕧"
          text: card.tr("Join")
          foreground: card.foreground
          fontFamily: card.fontFamily
          onClicked: card.openLink(card.event.join.url)
        }

        Button {
          visible: card.hasWeb
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
        text: card.tr("Close")
        foreground: card.foreground
        fontFamily: card.fontFamily
        onClicked: card.close()
      }
    }
  }
}
