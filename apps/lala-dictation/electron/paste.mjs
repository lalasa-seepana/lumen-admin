import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { clipboard } from "electron";

const execFileAsync = promisify(execFile);

/**
 * Paste polished text into the previously focused app.
 * Uses clipboard + Cmd+V via System Events. Needs Accessibility permission.
 */
export async function pasteText(text) {
  if (!text) return;
  const previous = clipboard.readText();
  clipboard.writeText(text);

  const script = `
    tell application "System Events"
      keystroke "v" using command down
    end tell
  `;

  try {
    await execFileAsync("osascript", ["-e", script]);
  } finally {
    // Restore clipboard after a short delay so paste can complete.
    setTimeout(() => {
      try {
        clipboard.writeText(previous);
      } catch {
        /* ignore */
      }
    }, 400);
  }
}
