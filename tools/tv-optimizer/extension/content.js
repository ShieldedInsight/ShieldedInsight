// Runs on TradingView chart pages. Opens the strategy's settings, reads / sets inputs,
// waits for the Strategy Tester, clicks its export, and offers inspect / click helpers
// for repairs. TradingView has no public API for this, so it works the page the way a
// person would; selectors live in SEL and can be overridden from Claude (tv_set_selector).
(() => {
  const SEL = {
    legendItem: '[data-name="legend-source-item"]',
    legendTitle: '[data-name="legend-source-title"]',
    legendSettings: '[data-name="legend-settings-action"]',
    dialog: '[data-name="indicator-properties-dialog"], [role="dialog"]',
    dialogOk: '[data-name="submit-button"]',
    dialogCancel: '[data-name="cancel-button"], [data-name="close"]',
    inputsTab: '#inputs, [data-value="inputs"], [data-id="inputs"]',
    tester: '[data-name="backtesting"], [id*="bottom-area"], [class*="backtesting"]',
    exportButton: '[data-name*="export" i], [aria-label*="export" i], [data-tooltip*="export" i], [aria-label*="download" i], [data-tooltip*="download" i]',
    exportMenuXlsx: '',
    busy: '[class*="spinner"], [class*="loader"], [aria-busy="true"]',
  };
  const CONTROL = 'input:not([type="hidden"]), [role="combobox"], [role="button"][aria-haspopup], button[aria-haspopup]';

  let overrides = {};
  const loadOverrides = async () => { overrides = (await chrome.storage.local.get("selectors")).selectors || {}; };
  const sel = (name) => overrides[name] || SEL[name];

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const visible = (el) => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden";
  const txt = (el) => (el && (el.innerText || el.textContent) || "").replace(/\s+/g, " ").trim();
  const qa = (s, root = document) => (s ? [...root.querySelectorAll(s)].filter(visible) : []);

  async function waitFor(fn, timeout = 8000, step = 100) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      const v = fn();
      if (v) return v;
      await sleep(step);
    }
    return null;
  }

  function byText(root, needle, selector = "*") {
    const n = needle.toLowerCase();
    const hits = qa(selector, root).filter((el) => {
      const t = [txt(el), el.getAttribute("aria-label"), el.getAttribute("title"), el.getAttribute("data-tooltip")].join(" ").toLowerCase();
      return t.includes(n);
    });
    return hits.sort((a, b) => txt(a).length - txt(b).length)[0] || null;
  }

  function fire(el, type, init = {}) {
    const Ev = type.startsWith("key") ? KeyboardEvent : type.startsWith("mouse") || type === "click" || type === "dblclick" ? MouseEvent : Event;
    el.dispatchEvent(new Ev(type, { bubbles: true, cancelable: true, view: window, ...init }));
  }
  function realClick(el) {
    el.scrollIntoView({ block: "center" });
    for (const t of ["pointerdown", "mousedown", "pointerup", "mouseup"]) el.dispatchEvent(new (t.startsWith("pointer") ? PointerEvent : MouseEvent)(t, { bubbles: true, cancelable: true, view: window }));
    el.click();
  }

  const dialog = () => qa(sel("dialog")).pop() || null;
  const tester = () => qa(sel("tester"))[0] || null;
  const rootOf = (within) => (within === "dialog" ? dialog() : within === "tester" ? tester() : within === "legend" ? document.querySelector('[data-name="legend"]') : document.body) || document.body;

  // ── the strategy's settings dialog ─────────────────────────────────────────
  async function openSettings(strategy) {
    if (dialog()) await closeDialog(false);
    const items = qa(sel("legendItem")).filter((el) => txt(el).toLowerCase().includes(strategy.toLowerCase()));
    if (!items.length) throw new Error(`No chart legend item contains "${strategy}". Legend: ${qa(sel("legendItem")).map(txt).map((t) => t.slice(0, 40)).join(" | ")}`);
    const item = items[0];
    fire(item, "mouseover"); fire(item, "mouseenter"); fire(item, "mousemove");
    await sleep(250);
    const gear = qa(sel("legendSettings"), item)[0];
    if (gear) realClick(gear);
    else {
      const title = qa(sel("legendTitle"), item)[0] || item;
      fire(title, "dblclick");
    }
    const dlg = await waitFor(dialog, 8000);
    if (!dlg) throw new Error("The settings dialog did not open (try tv_inspect within=legend and tv_set_selector legendSettings).");
    const tab = qa(sel("inputsTab"), dlg)[0] || byText(dlg, "Inputs", '[role="tab"], button');
    if (tab) { realClick(tab); await sleep(300); }
    return dlg;
  }

  async function closeDialog(ok) {
    const dlg = dialog();
    if (!dlg) return;
    const btn = ok ? (qa(sel("dialogOk"), dlg)[0] || byText(dlg, "Ok", "button"))
                   : (qa(sel("dialogCancel"), dlg)[0] || byText(dlg, "Cancel", "button"));
    if (btn) realClick(btn); else fire(document.activeElement || document.body, "keydown", { key: "Escape", code: "Escape", keyCode: 27 });
    await waitFor(() => !dialog(), 5000);
  }

  // A control's label: the text of its smallest ancestor row that has text besides controls.
  function labelOf(ctrl, dlg) {
    if (ctrl.type === "checkbox") {
      const l = ctrl.closest("label");
      if (l && txt(l)) return txt(l);
    }
    let p = ctrl.parentElement;
    for (let depth = 0; p && p !== dlg && depth < 6; depth++, p = p.parentElement) {
      const clone = p.cloneNode(true);
      clone.querySelectorAll(CONTROL + ", [role='listbox']").forEach((c) => c.remove());
      const t = txt(clone);
      if (t && p.querySelectorAll(CONTROL).length <= 3) return t;
    }
    return "";
  }

  function controlType(c) {
    if (c.matches('input[type="checkbox"]')) return "checkbox";
    if (c.matches("input")) return c.inputMode === "numeric" || c.type === "number" ? "number" : "text";
    return "dropdown";
  }
  const controlValue = (c) => (c.type === "checkbox" ? c.checked : c.matches("input") ? c.value : txt(c));

  function rows(dlg) {
    const seen = new Map();
    return qa(CONTROL, dlg).filter((c) => !c.closest('[role="tablist"]')).map((c) => {
      let label = labelOf(c, dlg);
      const k = label.toLowerCase();
      const n = (seen.get(k) || 0) + 1;
      seen.set(k, n);
      if (n > 1) label = `${label} #${n}`;
      return { label, type: controlType(c), value: controlValue(c), el: c };
    });
  }

  const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;

  async function setControl(row, v) {
    const c = row.el;
    if (row.type === "checkbox") {
      if (c.checked !== Boolean(v)) realClick(c);
      return c.checked === Boolean(v);
    }
    if (row.type !== "dropdown") {
      c.focus();
      nativeSetter.call(c, String(v));
      fire(c, "input"); fire(c, "change");
      fire(c, "keydown", { key: "Enter", code: "Enter", keyCode: 13 });
      c.blur(); fire(c, "blur");
      await sleep(80);
      return String(c.value).replace(/,/g, "") === String(v) || Number(String(c.value).replace(/,/g, "")) === Number(v);
    }
    realClick(c);
    const want = String(v).toLowerCase();
    const option = await waitFor(() => {
      const opts = qa('[role="option"], [data-role="menuitem"], [class*="menuItem"], [class*="item-"]').filter((o) => !o.closest(sel("dialog")) || o.closest('[role="listbox"]'));
      return opts.find((o) => txt(o).toLowerCase() === want) || null;
    }, 3000);
    if (!option) {
      const seenOpts = qa('[role="option"], [data-role="menuitem"]').map(txt).filter(Boolean).slice(0, 30);
      fire(document.activeElement || document.body, "keydown", { key: "Escape", code: "Escape", keyCode: 27 });
      throw new Error(`option "${v}" not found${seenOpts.length ? "; options: " + seenOpts.join(" | ") : ""}`);
    }
    realClick(option);
    await sleep(200);
    return txt(c).toLowerCase() === want;
  }

  // ── the Strategy Tester ────────────────────────────────────────────────────
  async function waitRecalc(waitMs) {
    const t0 = Date.now();
    await sleep(1200);
    let last = "", stableSince = Date.now();
    while (Date.now() - t0 < waitMs) {
      const t = tester();
      const busy = t ? qa(sel("busy"), t).length > 0 : false;
      const snap = t ? txt(t).slice(0, 4000) : "";
      if (snap !== last) { last = snap; stableSince = Date.now(); }
      if (!busy && Date.now() - stableSince > 2000) return { waitedMs: Date.now() - t0 };
      await sleep(300);
    }
    throw new Error(`The Strategy Tester was still busy after ${waitMs / 1000}s`);
  }

  async function exportReport() {
    const t = tester();
    if (!t) throw new Error("Strategy Tester panel not found: open it under the chart (tv_set_selector tester to repair).");
    const btn = qa(sel("exportButton"), t)[0] || byText(t, "export", "button, [role='button']") || byText(t, "download", "button, [role='button']");
    if (!btn) throw new Error("Export button not found in the Strategy Tester (use tv_inspect within=tester, then tv_set_selector exportButton).");
    realClick(btn);
    await sleep(600);
    const x = (sel("exportMenuXlsx") && qa(sel("exportMenuXlsx"))[0]) || byText(document.body, "xlsx", '[role="menuitem"], [role="option"], button, [data-role="menuitem"]');
    if (x) { realClick(x); await sleep(300); }
    return { clicked: txt(btn) || btn.getAttribute("aria-label") || "export", format: x ? "xlsx" : "default" };
  }

  // ── commands ───────────────────────────────────────────────────────────────
  function cssPath(el) {
    const parts = [];
    for (let e = el, i = 0; e && e.nodeType === 1 && i < 5; e = e.parentElement, i++) {
      let s = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(`${s}#${e.id}`); break; }
      const dn = e.getAttribute("data-name");
      if (dn) s += `[data-name="${dn}"]`;
      parts.unshift(s);
    }
    return parts.join(" > ");
  }

  const commands = {
    async status() {
      const legend = qa(sel("legendItem")).map((el) => txt(el).slice(0, 60));
      return { title: document.title, legend, testerOpen: !!tester(), dialogOpen: !!dialog() };
    },

    async getInputs({ strategy }) {
      const dlg = await openSettings(strategy);
      const out = rows(dlg).map(({ label, type, value }) => ({ label, type, value }));
      await closeDialog(false);
      return { strategy, inputs: out };
    },

    async setInputs({ strategy, inputs, waitMs = 120000 }) {
      const dlg = await openSettings(strategy);
      const all = rows(dlg);
      const set = [], failed = [];
      for (const [label, v] of Object.entries(inputs)) {
        const l = label.toLowerCase();
        const row = all.find((r) => r.label.toLowerCase() === l) || all.find((r) => r.label.toLowerCase().startsWith(l));
        if (!row) { failed.push({ label, reason: "no input with this label" }); continue; }
        try {
          const ok = await setControl(row, v);
          (ok ? set : failed).push(ok ? { label: row.label, value: v } : { label: row.label, reason: `value now ${JSON.stringify(controlValue(row.el))}` });
        } catch (e) { failed.push({ label: row.label, reason: e.message }); }
      }
      await closeDialog(true);
      const wait = await waitRecalc(waitMs);
      return { set, failed, ...wait };
    },

    async exportReport() { return exportReport(); },

    async inspect({ selector, text, within = "page", max = 40 }) {
      const root = rootOf(within);
      let els = qa(selector || "*", root);
      if (text) { const n = text.toLowerCase(); els = els.filter((e) => [txt(e), e.getAttribute("aria-label"), e.getAttribute("title"), e.getAttribute("data-tooltip")].join(" ").toLowerCase().includes(n)); }
      if (!selector) els = els.filter((e) => !els.some((o) => o !== e && e.contains(o)));   // innermost matches only
      return els.slice(0, max).map((e) => ({
        tag: e.tagName.toLowerCase(), role: e.getAttribute("role"), aria: e.getAttribute("aria-label"),
        dataName: e.getAttribute("data-name"), cls: String(e.className || "").slice(0, 80), text: txt(e).slice(0, 80), path: cssPath(e),
      }));
    },

    async click({ selector, text, within = "page" }) {
      const root = rootOf(within);
      const el = selector ? qa(selector, root)[0] : text ? byText(root, text) : null;
      if (!el) throw new Error("nothing matched");
      realClick(el);
      return { clicked: cssPath(el), text: txt(el).slice(0, 80) };
    },
  };

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (!msg || !msg.cmd || !commands[msg.cmd]) return false;
    loadOverrides()
      .then(() => commands[msg.cmd](msg.args || {}))
      .then((result) => sendResponse({ ok: true, result }))
      .catch((e) => sendResponse({ ok: false, error: String(e && e.message || e) }));
    return true;
  });

  chrome.runtime.sendMessage({ type: "tvo-wake" }).catch(() => {});
})();
