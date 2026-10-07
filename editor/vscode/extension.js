// Appends one JSON line per editor event to ~/.duckwalk/editor.jsonl (or $DUCKWALK_HOME/editor.jsonl).
// Logged: timestamp, event type, file path. Never file contents.
const vscode = require("vscode");
const fs = require("fs");
const os = require("os");
const path = require("path");

const home = process.env.DUCKWALK_HOME || path.join(os.homedir(), ".duckwalk");
const logPath = path.join(home, "editor.jsonl");

function log(type, uri) {
  if (!uri || uri.scheme !== "file") return;
  const line = JSON.stringify({ ts: Date.now() / 1000, type, file: uri.fsPath }) + "\n";
  fs.appendFile(logPath, line, () => {});
}

function activate(context) {
  fs.mkdirSync(home, { recursive: true });
  const { Undo, Redo } = vscode.TextDocumentChangeReason;
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.contentChanges.length === 0) return;
      const type = e.reason === Undo ? "undo" : e.reason === Redo ? "redo" : "edit";
      log(type, e.document.uri);
    }),
    vscode.workspace.onDidSaveTextDocument((doc) => log("save", doc.uri)),
    vscode.window.onDidChangeActiveTextEditor((ed) => ed && log("focus", ed.document.uri))
  );
}

module.exports = { activate, deactivate() {} };
