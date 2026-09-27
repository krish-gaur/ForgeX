"use client";

// Monaco editor wired for offline use: bundled monaco-editor package (no CDN),
// ForgeX dark theme, plus a custom FQL (intent language) monarch tokenizer.
import Editor, { loader, type Monaco } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import { useEffect, useRef } from "react";

loader.config({ monaco });

let registered = false;

const FQL_TOKENIZER: monaco.languages.IMonarchLanguage = {
  defaultToken: "",
  ignoreCase: true,
  keywords: [
    "investigate", "where", "and", "or", "not", "limit", "from", "correlate", "timeline",
    "between", "contains", "in", "count", "group", "by", "order", "asc", "desc", "as",
  ],
  collectors: ["processes", "files", "network", "events", "users", "registry", "memory", "browser", "hashes", "logs"],
  operators: ["=", "!=", ">", "<", ">=", "<=", "~", "!~"],
  symbols: /[=><!~?&|+\-*/^%]+/,
  tokenizer: {
    root: [
      [/[a-zA-Z_]\w*/, {
        cases: {
          "@keywords": { token: "keyword.fql" },
          "@collectors": { token: "type.fql" },
          "@default": "identifier",
        },
      }],
      { include: "@whitespace" },
      [/'[^']*'/, "string"],
      [/"[^"]*"/, "string"],
      [/\d+(\.\d+)?/, "number"],
      [/@symbols/, { cases: { "@operators": "operator", "@default": "" } }],
      [/[()[\]{}]/, "delimiter"],
    ],
    whitespace: [
      [/[ \t\r\n]+/, ""],
      [/#.*$/, "comment"],
      [/--.*$/, "comment"],
    ],
  },
};

function registerForgex(m: Monaco) {
  if (registered) return;
  registered = true;
  m.languages.register({ id: "fql" });
  m.languages.setMonarchTokensProvider("fql", FQL_TOKENIZER);
  m.editor.defineTheme("forgex-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "keyword.fql", foreground: "3dff9e", fontStyle: "bold" },
      { token: "type.fql", foreground: "35d6ff" },
      { token: "comment", foreground: "4a5b6e", fontStyle: "italic" },
      { token: "string", foreground: "ffb547" },
      { token: "number", foreground: "b28dff" },
      { token: "operator", foreground: "3dff9e" },
    ],
    colors: {
      "editor.background": "#05080d",
      "editor.foreground": "#c8d6e5",
      "editorLineNumber.foreground": "#27405a",
      "editorLineNumber.activeForeground": "#3dff9e",
      "editor.selectionBackground": "#1d2b3a",
      "editor.lineHighlightBackground": "#0a0f16",
      "editorCursor.foreground": "#3dff9e",
      "editorIndentGuide.background1": "#16212e",
      "editorGutter.background": "#05080d",
      "editorWidget.background": "#0d141d",
      "editorWidget.border": "#1d2b3a",
    },
  });
  // Python semantic niceties for forensic functions come from monaco's built-in
  // python language; keep the same palette via theme (shared above).
}

export interface MonacoProps {
  value: string;
  onChange?: (v: string) => void;
  language?: "python" | "fql" | "yaml" | "json" | "plaintext";
  height?: number | string;
  readOnly?: boolean;
  line?: number | null;
  onMount?: () => void;
}

export default function Monaco({ value, onChange, language = "python", height = 420, readOnly, line, onMount }: MonacoProps) {
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    if (line && editorRef.current) {
      editorRef.current.revealLineInCenter(line);
      editorRef.current.setPosition({ lineNumber: line, column: 1 });
      editorRef.current.focus();
    }
  }, [line]);

  return (
    <div className="monaco-shell border border-edge">
      <Editor
        height={height}
        language={language}
        value={value}
        theme="forgex-dark"
        onChange={(v) => onChange?.(v ?? "")}
        beforeMount={registerForgex}
        onMount={(editor) => {
          editorRef.current = editor;
          onMount?.();
        }}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 12.5,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          fontLigatures: false,
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          renderLineHighlight: "all",
          tabSize: 4,
          automaticLayout: true,
          padding: { top: 10, bottom: 10 },
          overviewRulerLanes: 0,
          scrollbar: { verticalScrollbarSize: 9, horizontalScrollbarSize: 9 },
          bracketPairColorization: { enabled: true },
          quickSuggestions: true,
          wordWrap: "on",
        }}
      />
    </div>
  );
}
