#!/usr/bin/env node
// TruePath TV Optimizer - MCP server for Claude Code.
// Claude Code starts this over stdio. It also opens a WebSocket on 127.0.0.1 that the
// Chrome extension connects to (with a shared token), and watches ~/Downloads for the
// Strategy Tester exports the extension triggers. Nothing here places trades.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { WebSocketServer } from "ws";
import { scoreExport, PLANS } from "./report.js";

const HOME = path.join(os.homedir(), ".tv-optimizer");
const RUNS = path.join(HOME, "runs");
const PORT = Number(process.env.TVO_PORT || 8765);
const DOWNLOADS = process.env.TVO_DOWNLOADS || path.join(os.homedir(), "Downloads");
fs.mkdirSync(RUNS, { recursive: true });

// stdout belongs to MCP; everything we print goes to stderr.
const log = (...a) => console.error("[tv-optimizer]", ...a);

// ── shared token ─────────────────────────────────────────────────────────────
const TOKEN_FILE = path.join(HOME, "token");
if (!fs.existsSync(TOKEN_FILE)) fs.writeFileSync(TOKEN_FILE, crypto.randomBytes(24).toString("hex"), { mode: 0o600 });
const TOKEN = fs.readFileSync(TOKEN_FILE, "utf8").trim();

// ── bridge to the extension ──────────────────────────────────────────────────
let ext = null;            // the authenticated extension socket
const pending = new Map(); // id -> {resolve, reject, timer}

const wss = new WebSocketServer({ host: "127.0.0.1", port: PORT });
wss.on("listening", () => log(`waiting for the Chrome extension on ws://127.0.0.1:${PORT}`));
wss.on("error", (e) => log("websocket error:", e.message));
wss.on("connection", (ws, req) => {
  const origin = req.headers.origin || "";
  if (!origin.startsWith("chrome-extension://")) { ws.close(1008, "origin"); return; }
  let authed = false;
  ws.on("message", (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }
    if (!authed) {
      if (msg.type === "hello" && typeof msg.token === "string" && msg.token.length === TOKEN.length &&
          crypto.timingSafeEqual(Buffer.from(msg.token), Buffer.from(TOKEN))) {
        authed = true;
        if (ext && ext !== ws) ext.close(1000, "replaced");
        ext = ws;
        ws.send(JSON.stringify({ type: "welcome" }));
        log("extension connected", origin);
      } else ws.close(1008, "token");
      return;
    }
    if (msg.type === "ping") { ws.send(JSON.stringify({ type: "pong" })); return; }
    const p = pending.get(msg.id);
    if (p) {
      clearTimeout(p.timer);
      pending.delete(msg.id);
      msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error || "extension error"));
    }
  });
  ws.on("close", () => { if (ext === ws) { ext = null; log("extension disconnected"); } });
});

function call(cmd, args = {}, timeoutMs = 60000) {
  if (!ext) return Promise.reject(new Error(
    "The Chrome extension is not connected. Open a TradingView chart in Chrome, and check the extension's options page (port and token)."));
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${cmd} timed out after ${timeoutMs / 1000}s`)); }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
    ext.send(JSON.stringify({ type: "cmd", id, cmd, args }));
  });
}

// ── downloads ────────────────────────────────────────────────────────────────
const isExport = (f) => /\.(xlsx|csv)$/i.test(f) && !/\.crdownload$/i.test(f);

async function waitForNewExport(since, timeoutMs) {
  const end = Date.now() + timeoutMs;
  while (Date.now() < end) {
    const files = fs.readdirSync(DOWNLOADS).filter(isExport).map((f) => {
      const full = path.join(DOWNLOADS, f);
      return { full, mtime: fs.statSync(full).mtimeMs };
    }).filter((f) => f.mtime >= since).sort((a, b) => b.mtime - a.mtime);
    if (files.length) {
      const f = files[0];
      await new Promise((r) => setTimeout(r, 700));                 // let the write finish
      if (fs.statSync(f.full).mtimeMs === f.mtime) return f.full;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`No new .xlsx/.csv appeared in ${DOWNLOADS} within ${timeoutMs / 1000}s. Check Chrome's download folder or set TVO_DOWNLOADS.`);
}

function logRun(entry) {
  fs.appendFileSync(path.join(HOME, "runs.jsonl"), JSON.stringify(entry) + "\n");
}

function readRuns() {
  const f = path.join(HOME, "runs.jsonl");
  if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
}

const text = (obj) => ({ content: [{ type: "text", text: typeof obj === "string" ? obj : JSON.stringify(obj, null, 2) }] });
const fail = (e) => ({ isError: true, content: [{ type: "text", text: String(e?.message || e) }] });
const planKeys = Object.keys(PLANS);

// ── MCP tools ────────────────────────────────────────────────────────────────
const server = new McpServer({ name: "tv-optimizer", version: "1.0.0" });

server.registerTool("tv_status", {
  title: "TradingView connection status",
  description: "Whether the Chrome extension is connected, and the active TradingView chart tab (title, symbol, URL). Call this first.",
  inputSchema: {},
}, async () => {
  try {
    if (!ext) return text({ connected: false, port: PORT, tokenFile: TOKEN_FILE, downloads: DOWNLOADS });
    return text({ connected: true, downloads: DOWNLOADS, chart: await call("status", {}, 15000) });
  } catch (e) { return fail(e); }
});

server.registerTool("tv_get_inputs", {
  title: "Read strategy inputs",
  description: "Opens the strategy's settings dialog on the chart, reads every input on the Inputs tab (label, type, value, dropdown options) and closes it without changes.",
  inputSchema: { strategy: z.string().describe("Text of the strategy's name or short title as shown in the chart legend, e.g. 'TP Bot'") },
}, async ({ strategy }) => {
  try { return text(await call("getInputs", { strategy })); } catch (e) { return fail(e); }
});

server.registerTool("tv_set_inputs", {
  title: "Set strategy inputs",
  description: "Sets inputs on the strategy's Inputs tab by their label and presses OK, then waits for the Strategy Tester to recalculate. Values: numbers, strings (dropdown option text or text/session fields) or booleans (checkboxes). Returns which inputs were set and which were not found.",
  inputSchema: {
    strategy: z.string(),
    inputs: z.record(z.string(), z.union([z.number(), z.string(), z.boolean()])).describe("label -> value, e.g. {\"Risk per Trade ($, 0 = auto: MNQ $500 · MES $300)\": 400, \"Profit Exit\": \"2R\"}"),
    waitMs: z.number().int().min(1000).max(600000).optional().describe("Max wait for the recalculation (default 120000; Deep Backtesting can be slow)"),
  },
}, async ({ strategy, inputs, waitMs = 120000 }) => {
  try { return text(await call("setInputs", { strategy, inputs, waitMs }, waitMs + 30000)); } catch (e) { return fail(e); }
});

server.registerTool("tv_export_and_score", {
  title: "Export the Strategy Tester report and score it",
  description: "Clicks the Strategy Tester's export, waits for the file in Downloads, saves a copy under ~/.tv-optimizer/runs, and scores it: per-position stats, in-sample vs out-of-sample split, longs/shorts, overnight holds, top-10 fragility, monthly P&L and a Tradeify evaluation + payout simulation. Logs the run with its inputs.",
  inputSchema: {
    split: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe("Out-of-sample start date (default 2026-01-01)"),
    plan: z.enum(planKeys).optional().describe("Tradeify plan for the simulation (default select50)"),
    label: z.string().optional().describe("A short name for this run, e.g. 'risk400-2R'"),
    timeoutMs: z.number().int().min(5000).max(300000).optional(),
  },
}, async ({ split = "2026-01-01", plan = "select50", label = "", timeoutMs = 90000 }) => {
  try {
    const since = Date.now() - 1000;
    await call("exportReport", {}, 30000);
    const file = await waitForNewExport(since, timeoutMs);
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const saved = path.join(RUNS, `${stamp}${label ? "-" + label.replace(/[^\w.-]+/g, "_") : ""}${path.extname(file)}`);
    fs.copyFileSync(file, saved);
    const score = await scoreExport(saved, { split, plan });
    logRun({ at: new Date().toISOString(), label, file: saved, split, plan, inputs: score.inputs,
      all: score.all, inSample: score.inSample, outOfSample: score.outOfSample, prop: score.prop,
      propInSample: score.propInSample, propOutOfSample: score.propOutOfSample, warnings: score.warnings });
    const { inputs, ...rest } = score;
    return text({ saved, ...rest });
  } catch (e) { return fail(e); }
});

server.registerTool("tv_score_file", {
  title: "Score an export file",
  description: "Scores a TradingView export already on disk (e.g. one you downloaded by hand) the same way as tv_export_and_score, without touching the browser.",
  inputSchema: {
    file: z.string().describe("Path to the .xlsx or .csv export"),
    split: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
    plan: z.enum(planKeys).optional(),
  },
}, async ({ file, split = "2026-01-01", plan = "select50" }) => {
  try {
    const full = file.startsWith("~") ? path.join(os.homedir(), file.slice(1)) : file;
    return text(await scoreExport(full, { split, plan }));
  } catch (e) { return fail(e); }
});

server.registerTool("tv_runs", {
  title: "List logged runs",
  description: "The optimization log: every scored run with its label, inputs changed from the first run, in-sample and out-of-sample stats and the prop simulation. Use it to compare settings; judge candidates on out-of-sample only after choosing them on in-sample.",
  inputSchema: { last: z.number().int().min(1).max(500).optional().describe("Only the last N runs (default 50)") },
}, async ({ last = 50 }) => {
  try {
    const runs = readRuns().slice(-last);
    const base = runs[0]?.inputs || {};
    return text(runs.map((r) => ({
      at: r.at, label: r.label,
      changed: Object.fromEntries(Object.entries(r.inputs || {}).filter(([k, v]) => base[k] !== v)),
      inSample: r.inSample, propInSample: r.propInSample, outOfSample: r.outOfSample, propOutOfSample: r.propOutOfSample, warnings: r.warnings,
    })));
  } catch (e) { return fail(e); }
});

server.registerTool("tv_inspect", {
  title: "Inspect the TradingView page (repair tool)",
  description: "Lists visible elements matching a CSS selector and/or containing text (tag, role, aria-label, data-name, class, short text, a CSS path). Use it when another tool fails because TradingView changed its page, to find the right element.",
  inputSchema: {
    selector: z.string().optional(),
    text: z.string().optional(),
    within: z.enum(["page", "dialog", "tester", "legend"]).optional(),
    max: z.number().int().min(1).max(200).optional(),
  },
}, async (args) => {
  try { return text(await call("inspect", args, 20000)); } catch (e) { return fail(e); }
});

server.registerTool("tv_click", {
  title: "Click an element (repair tool)",
  description: "Clicks the first visible element matching a CSS selector, or whose text / aria-label / title contains the given text. For manual steps the other tools cannot do yet (e.g. closing a pop-up).",
  inputSchema: { selector: z.string().optional(), text: z.string().optional(), within: z.enum(["page", "dialog", "tester", "legend"]).optional() },
}, async (args) => {
  try { return text(await call("click", args, 20000)); } catch (e) { return fail(e); }
});

server.registerTool("tv_set_selector", {
  title: "Override a selector (repair tool)",
  description: "Stores a CSS selector override in the extension for one of its named targets: legendItem, legendSettings, dialog, dialogOk, dialogCancel, inputsTab, tester, exportButton, exportMenuXlsx, busy. Use after tv_inspect shows TradingView changed its page.",
  inputSchema: { name: z.string(), selector: z.string().describe("CSS selector; empty string removes the override") },
}, async (args) => {
  try { return text(await call("setSelector", args, 10000)); } catch (e) { return fail(e); }
});

await server.connect(new StdioServerTransport());
log(`MCP server ready · token in ${TOKEN_FILE} · runs in ${RUNS}`);
