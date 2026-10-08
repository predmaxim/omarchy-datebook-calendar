import QtQuick
import QtQuick.Window
import QtQuick.Controls as QC
import qs.Commons
import qs.Ui
import "Model.js" as Model

// The answer to an invitation: one button with the answer made (or Choose);
// the answers open above it, where there is room in the panel. A recurring
// invitation is answered for the whole series. Hidden for anything else.
Item {
  id: picker

  property var event: null                       // a row from Model.indexEvents
  property bool busy: false                      // an answer is being sent
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property var tr: Model.english
  property bool open: false
  property bool hasCursor: false                 // the card's keyboard cursor is on the button
  property int choice: -1                        // the answer under the keys while open

  readonly property var answers: [
    { answer: "accept", response: "accepted", label: picker.tr("Accept"), icon: "󰄬" },
    { answer: "tentative", response: "tentative", label: picker.tr("Maybe"), icon: "󰋗" },
    { answer: "decline", response: "declined", label: picker.tr("Decline"), icon: "󰅖" }
  ]

  signal respond(string answer)

  // Enter on the button: the answers open with the cursor on the one made.
  function openWithKeys() {
    choice = Math.max(0, answers.findIndex(function(a) { return !!event && a.response === event.response }))
    open = true
  }

  function pick(answer) {
    open = false
    respond(answer)
  }

  visible: Model.isInvitation(event)
  width: visible ? answerButton.width : 0
  height: answerButton.height

  onEventChanged: open = false

  Button {
    id: answerButton
    bordered: true
    enabled: !picker.busy
    hasCursor: picker.hasCursor
    iconText: "󰅀"
    text: picker.event ? Model.answerLabel(picker.event, picker.tr) : ""
    foreground: picker.event && picker.event.response !== "needsAction" ? Color.accent : picker.foreground
    fontFamily: picker.fontFamily
    onClicked: {
      picker.choice = -1
      picker.open = !picker.open
    }
  }

  onOpenChanged: if (open !== popup.visible) { open ? popup.open() : popup.close() }

  // A Popup lives in the window overlay and gets input first; a plain
  // Rectangle with z would lose clicks to items declared later elsewhere.
  QC.Popup {
    id: popup
    padding: Style.space(4)
    // Above the button; below it when the panel has no room above; kept inside the window's right edge.
    onAboutToShow: {
      const p = picker.mapToItem(null, 0, 0)
      y = p.y < height + Style.space(4) ? picker.height + Style.space(4) : -height - Style.space(4)
      const w = picker.Window.width
      x = w > 0 ? Math.min(0, w - p.x - width) : 0
    }
    focus: true
    closePolicy: QC.Popup.CloseOnEscape | QC.Popup.CloseOnPressOutsideParent   // the button toggles itself
    onClosed: picker.open = false

    background: Rectangle {
      radius: Style.cornerRadius
      color: Color.popups.background
      border.width: Style.spacing.hairline
      border.color: Color.popups.border
    }

    // ↑/↓ and Enter; Esc closes (closePolicy).
    contentItem: Column {
      id: choices
      spacing: Style.space(2)
      focus: true
      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Up || event.key === Qt.Key_Down)
          picker.choice = Math.max(0, Math.min(picker.answers.length - 1, picker.choice + (event.key === Qt.Key_Down ? 1 : -1)))
        else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && picker.choice >= 0 && !picker.busy)
          picker.pick(picker.answers[picker.choice].answer)
        else return
        event.accepted = true
      }

      Repeater {
        model: picker.answers
        Button {
          required property var modelData
          required property int index
          readonly property bool current: !!picker.event && picker.event.response === modelData.response
          enabled: !picker.busy
          hasCursor: picker.choice === index
          iconText: current ? "󰄵" : modelData.icon
          text: modelData.label
          tooltipText: current ? picker.tr("Your answer now")
                               : (picker.event && picker.event.recurring ? picker.tr("Every occurrence: ") : "")
                                 + picker.tr("%1 and let the organiser know", modelData.label)
          foreground: current ? Color.accent : picker.foreground
          fontFamily: picker.fontFamily
          onClicked: picker.pick(modelData.answer)
        }
      }
    }
  }
}
