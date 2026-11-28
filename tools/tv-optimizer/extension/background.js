// Connects to the local MCP server (ws://127.0.0.1:<port>) with the shared token and
// relays its commands to the TradingView chart tab's content script.
let ws = null;
let state = "disconnected";

async function settings() {
  return chrome.storage.local.get({ port: 8765, token: "" });
}

async function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const { port, token } = await settings();
  if (!token) { state = "no token: open the extension options"; return; }
  try {
    ws = new WebSocket(`ws://127.0.0.1:${port}`);
  } catch (e) {
    state = "cannot open socket"; return;
  }
  state = "connecting";
  ws.onopen = () => ws.send(JSON.stringify({ type: "hello", token }));
  ws.onclose = (e) => { state = e.reason ? `closed: ${e.reason}` : "server not running"; ws = null; };
  ws.onerror = () => { state = "server not running"; };
  ws.onmessage = async (e) => {
    let msg;
    try { msg = JSON.parse(e.data); } catch { return; }
    if (msg.type === "welcome") { state = "connected"; return; }
    if (msg.type !== "cmd") return;
    const reply = (ok, payload) => ws && ws.readyState === WebSocket.OPEN &&
      ws.send(JSON.stringify(ok ? { id: msg.id, ok: true, result: payload } : { id: msg.id, ok: false, error: payload }));
    try {
      reply(true, await handle(msg.cmd, msg.args || {}));
    } catch (err) {
      reply(false, String(err && err.message || err));
    }
  };
}

async function chartTab() {
  const tabs = await chrome.tabs.query({ url: ["https://*.tradingview.com/chart*"] });
  if (!tabs.length) throw new Error("No TradingView chart tab is open in Chrome.");
  return tabs.find((t) => t.active) || tabs[0];
}

async function handle(cmd, args) {
  if (cmd === "setSelector") {
    const { selectors = {} } = await chrome.storage.local.get("selectors");
    if (args.selector) selectors[args.name] = args.selector; else delete selectors[args.name];
    await chrome.storage.local.set({ selectors });
    return { selectors };
  }
  const tab = await chartTab();
  const res = await chrome.tabs.sendMessage(tab.id, { cmd, args });
  if (!res) throw new Error("The chart tab did not answer: reload the TradingView tab once after installing the extension.");
  if (!res.ok) throw new Error(res.error);
  if (cmd === "status") return { tabTitle: tab.title, url: tab.url, ...res.result };
  return res.result;
}

// Keep the connection alive: a ping every 20 s keeps the service worker awake while
// connected; an alarm every minute reconnects after Chrome stops the worker.
setInterval(() => { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" })); }, 20000);
chrome.alarms.create("tvo-reconnect", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "tvo-reconnect") connect(); });
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.storage.onChanged.addListener((c) => { if (c.port || c.token) { if (ws) ws.close(); setTimeout(connect, 300); } });
// ── Trade journal: screenshot the chart tab, save PNG + JSON to Downloads ──────
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const nyTime = (d) => d.toLocaleTimeString("en-GB", { timeZone: "America/New_York", hour12: false }).replace(/:/g, "");

async function captureTrade(ev, tab) {
  const win = await chrome.windows.get(tab.windowId);
  if (win.state === "minimized") throw new Error("The TradingView window is minimized: Chrome cannot screenshot it.");
  let back = null;
  if (!tab.active) {                                     // bring the chart forward, then put the other tab back
    const [cur] = await chrome.tabs.query({ active: true, windowId: tab.windowId });
    back = cur ? cur.id : null;
    await chrome.tabs.update(tab.id, { active: true });
    await sleep(900);
  }
  let png;
  try {
    png = await chrome.tabs.captureVisibleTab(tab.windowId, { format: "png" });
  } finally {
    if (back) chrome.tabs.update(back, { active: true }).catch(() => {});
  }
  const now = new Date();
  const m = /(\d{4})(\d{2})(\d{2})$/.exec(String(ev.id)) || [];
  const day = m[1] ? `${m[1]}-${m[2]}-${m[3]}` : now.toISOString().slice(0, 10);
  const base = `TruePath-Journal/${day}/${String(ev.sym || "chart").replace(/\W/g, "")}_${ev.ev}_${nyTime(now)}`;
  await chrome.downloads.download({ url: png, filename: `${base}.png`, conflictAction: "uniquify", saveAs: false });
  const rec = { ...ev, capturedAt: now.toISOString(), image: `${base.split("/").pop()}.png`, chart: tab.url };
  const json = "data:application/json;base64," + btoa(unescape(encodeURIComponent(JSON.stringify(rec, null, 2))));
  await chrome.downloads.download({ url: json, filename: `${base}.json`, conflictAction: "uniquify", saveAs: false });
  await chrome.storage.local.set({ lastCapture: `${ev.ev} ${ev.sym || ""} ${now.toLocaleString()}` });
  return rec;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "tvo-state") {
    connect();
    chrome.storage.local.get({ lastCapture: "", lastCaptureError: "" }).then((j) => sendResponse({ state, ...j }));
    return true;
  }
  if (msg && msg.type === "tvo-wake") connect();
  if (msg && msg.type === "tpj-capture" && sender.tab) {
    captureTrade(msg.ev, sender.tab)
      .then((rec) => { chrome.storage.local.set({ lastCaptureError: "" }); sendResponse({ ok: true, rec }); })
      .catch((e) => { const err = String(e && e.message || e); chrome.storage.local.set({ lastCaptureError: err }); sendResponse({ ok: false, error: err }); });
    return true;
  }
});
connect();
