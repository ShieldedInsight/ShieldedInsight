const $ = (id) => document.getElementById(id);

async function refresh() {
  const r = await chrome.runtime.sendMessage({ type: "tvo-state" }).catch(() => null);
  $("state").textContent = "Status: " + (r ? r.state : "background not running") +
    (r && r.lastCapture ? " · last screenshot: " + r.lastCapture : "") +
    (r && r.lastCaptureError ? " · screenshot error: " + r.lastCaptureError : "");
}

(async () => {
  const s = await chrome.storage.local.get({ port: 8765, token: "", journalOn: true });
  $("journalOn").checked = s.journalOn;
  $("port").value = s.port;
  $("token").value = s.token;
  refresh();
  setInterval(refresh, 1500);
})();

$("save").addEventListener("click", async () => {
  await chrome.storage.local.set({ port: Number($("port").value) || 8765, token: $("token").value.trim(), journalOn: $("journalOn").checked });
  $("state").textContent = "Status: saved, connecting…";
});
