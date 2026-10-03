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

  signal respond(string answer)

  visible: Model.isInvitation(event)
  width: visible ? answerButton.width : 0
  height: answerButton.height

  onEventChanged: open = false

  Button {
    id: answerButton
    bordered: true
    enabled: !picker.busy
    iconText: "󰅀"
    text: picker.event ? Model.answerLabel(picker.event, picker.tr) : ""
    foreground: picker.event && picker.event.response !== "needsAction" ? Color.accent : picker.foreground
    fontFamily: picker.fontFamily
    onClicked: picker.open = !picker.open
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
      x = Math.min(0, picker.Window.width - p.x - width)
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

    contentItem: Column {
      id: choices
      spacing: Style.space(2)

      Repeater {
        model: [
          { answer: "accept", response: "accepted", label: picker.tr("Accept"), icon: "󰄬" },
          { answer: "tentative", response: "tentative", label: picker.tr("Maybe"), icon: "󰋗" },
          { answer: "decline", response: "declined", label: picker.tr("Decline"), icon: "󰅖" }
        ]
        Button {
          required property var modelData
          readonly property bool current: !!picker.event && picker.event.response === modelData.response
          enabled: !picker.busy
          iconText: current ? "󰄵" : modelData.icon
          text: modelData.label
          tooltipText: current ? picker.tr("Your answer now")
                               : (picker.event && picker.event.recurring ? picker.tr("Every occurrence: ") : "")
                                 + picker.tr("%1 and let the organiser know", modelData.label)
          foreground: current ? Color.accent : picker.foreground
          fontFamily: picker.fontFamily
          onClicked: {
            picker.open = false
            picker.respond(modelData.answer)
          }
        }
      }
    }
  }
}
