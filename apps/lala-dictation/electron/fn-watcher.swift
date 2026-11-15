import Foundation
import CoreGraphics

/// Polls the macOS Function (fn / Globe) key and prints down/up lines.
/// Provides the hold-to-dictate hotkey for Lala Dictation.
let fnKey: CGKeyCode = 63 // kVK_Function
var wasDown = false

setbuf(stdout, nil)

while true {
  let down = CGEventSource.keyState(.combinedSessionState, key: fnKey)
  if down != wasDown {
    fputs(down ? "down\n" : "up\n", stdout)
    wasDown = down
  }
  usleep(12_000)
}
