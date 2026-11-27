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
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "tvo-state") { connect(); sendResponse({ state }); }
  if (msg && msg.type === "tvo-wake") connect();
});
connect();
