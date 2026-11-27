// Parse a TradingView Strategy Tester export (.xlsx or .csv) and score it the
// TruePath way: per-position stats, in-sample / out-of-sample split, overnight
// holds, fragility, and a Tradeify evaluation + payout simulation.
import fs from "node:fs";
import path from "node:path";
import ExcelJS from "exceljs";

// Tradeify plans as reported by third-party summaries (Nov 2026) - verify with Tradeify.
export const PLANS = {
  select50: { name: "Tradeify Select 50K", target: 3000, dd: 2000, cons: 0.4, winDay: 150, winNeed: 5, share: 0.5, cap: 2500, minPayout: 250 },
  select100: { name: "Tradeify Select 100K", target: 6000, dd: 3000, cons: 0.4, winDay: 250, winNeed: 5, share: 0.5, cap: 3000, minPayout: 250 },
  growth50: { name: "Tradeify Growth 50K", target: 3000, dd: 2000, cons: 0, winDay: 150, winNeed: 5, share: 0.5, cap: 2500, minPayout: 250 },
  growth100: { name: "Tradeify Growth 100K", target: 6000, dd: 3500, cons: 0, winDay: 250, winNeed: 5, share: 0.5, cap: 3000, minPayout: 250 },
};

const norm = (s) => String(s ?? "").trim().toLowerCase();

function cellValue(v) {
  if (v && typeof v === "object") {
    if (v instanceof Date) return v;
    if ("result" in v) return v.result;
    if ("text" in v) return v.text;
    if ("richText" in v) return v.richText.map((r) => r.text).join("");
  }
  return v;
}

// Dates in the export are the chart's wall-clock time; keep them as "YYYY-MM-DD HH:MM" strings.
function toStamp(v) {
  if (v instanceof Date) return v.toISOString().slice(0, 16).replace("T", " ");
  const s = String(v ?? "").trim();
  const m = s.match(/(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}` : s;
}

async function readSheets(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === ".csv") {
    const rows = parseCsv(fs.readFileSync(file, "utf8"));
    return { Trades: rows };
  }
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(file);
  const out = {};
  wb.eachSheet((ws) => {
    const rows = [];
    ws.eachRow({ includeEmpty: false }, (row) => {
      const vals = [];
      for (let c = 1; c <= row.cellCount; c++) vals.push(cellValue(row.getCell(c).value));
      rows.push(vals);
    });
    out[ws.name] = rows;
  });
  return out;
}

function parseCsv(text) {
  const rows = [];
  let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') q = false;
      else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cur); cur = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cur); cur = "";
      if (row.some((x) => x !== "")) rows.push(row);
      row = [];
    } else cur += ch;
  }
  if (cur !== "" || row.length) { row.push(cur); rows.push(row); }
  return rows.map((r) => r.map((x) => (x !== "" && !isNaN(Number(x)) ? Number(x) : x)));
}

function col(header, ...names) {
  const h = header.map(norm);
  for (const n of names) {
    const i = h.findIndex((x) => x === norm(n) || x.startsWith(norm(n)));
    if (i >= 0) return i;
  }
  return -1;
}

// One position per (entry time, entry signal): TradingView writes each partial exit as its own trade.
function positions(tradeRows) {
  const [header, ...rows] = tradeRows;
  const iNum = col(header, "Trade number", "Trade #");
  const iType = col(header, "Type");
  const iTime = col(header, "Date and time", "Date/Time", "Date");
  const iSig = col(header, "Signal");
  const iPx = col(header, "Price USD", "Price");
  const iQty = col(header, "Size (qty)", "Contracts", "Quantity");
  const iPnl = col(header, "Net PnL USD", "Net P&L USD", "Profit USD", "Net PnL", "Profit");
  const iMae = col(header, "Adverse excursion USD", "Drawdown USD", "Adverse excursion");
  if ([iNum, iType, iTime, iPnl].includes(-1)) throw new Error(`Trades sheet: unexpected columns ${JSON.stringify(header)}`);
  const legs = new Map();
  for (const r of rows) {
    const n = r[iNum];
    if (n == null || n === "") continue;
    const leg = legs.get(n) || {};
    const t = norm(r[iType]);
    if (t.startsWith("entry")) {
      Object.assign(leg, { side: t.includes("short") ? "short" : "long", entry: toStamp(r[iTime]), signal: String(r[iSig] ?? ""),
        qty: Number(r[iQty]) || 0, pnl: Number(r[iPnl]) || 0, mae: iMae >= 0 ? Number(r[iMae]) || 0 : 0, entryPx: Number(r[iPx]) || 0 });
    } else if (t.startsWith("exit")) {
      Object.assign(leg, { exit: toStamp(r[iTime]), exitSignal: String(r[iSig] ?? ""), exitPx: Number(r[iPx]) || 0 });
    }
    legs.set(n, leg);
  }
  const pos = new Map();
  for (const leg of [...legs.values()].filter((l) => l.entry)) {
    const k = `${leg.entry}|${leg.signal}|${leg.side}`;
    const p = pos.get(k) || { entry: leg.entry, side: leg.side, signal: leg.signal, qty: 0, pnl: 0, mae: 0, exit: leg.exit, exits: [] };
    p.qty += leg.qty; p.pnl += leg.pnl; p.mae += Math.min(leg.mae, 0);
    if (leg.exit && (!p.exit || leg.exit > p.exit)) p.exit = leg.exit;
    p.exits.push(leg.exitSignal);
    pos.set(k, p);
  }
  return [...pos.values()].sort((a, b) => (a.entry < b.entry ? -1 : 1));
}

function stats(ps) {
  const n = ps.length;
  if (!n) return { trades: 0 };
  const x = ps.map((p) => p.pnl);
  const sum = x.reduce((a, b) => a + b, 0);
  const mean = sum / n;
  const sd = n > 1 ? Math.sqrt(x.reduce((a, v) => a + (v - mean) ** 2, 0) / (n - 1)) : 0;
  const gw = x.filter((v) => v > 0).reduce((a, b) => a + b, 0);
  const gl = -x.filter((v) => v < 0).reduce((a, b) => a + b, 0);
  let eq = 0, peak = 0, dd = 0;
  for (const v of x) { eq += v; peak = Math.max(peak, eq); dd = Math.min(dd, eq - peak); }
  const r2 = (v) => Math.round(v * 100) / 100;
  return { trades: n, net: r2(sum), perTrade: r2(mean), winRate: r2(x.filter((v) => v > 0).length / n),
    profitFactor: gl > 0 ? r2(gw / gl) : null, tStat: sd > 0 ? r2(mean / (sd / Math.sqrt(n))) : null, maxDrawdown: r2(-dd) };
}

function dailySeries(ps) {
  const days = new Map();
  for (const p of ps) {
    const d = (p.exit || p.entry).slice(0, 10);
    const e = days.get(d) || { pnl: 0, worst: 0 };
    e.pnl += p.pnl;
    e.worst += Math.min(p.mae, 0) || Math.min(p.pnl, 0);
    days.set(d, e);
  }
  return [...days.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).map(([date, v]) => ({ date, ...v }));
}

// Start an evaluation on every trading day; run it through evaluation and Select Flex-style payouts.
export function propSim(daily, planKey = "select50", runway = 20) {
  const p = PLANS[planKey];
  const n = daily.length;
  let passed = 0, failed = 0, open = 0, payout = 0, paid = 0;
  const daysToPass = [];
  for (let s = 0; s < Math.max(0, n - runway); s++) {
    let bal = 0, peak = 0, floor = -p.dd, best = 0, i = s, res = null;
    while (i < n) {
      const { pnl, worst } = daily[i];
      if (bal + Math.min(worst, 0) <= floor) { res = "fail"; break; }
      bal += pnl; best = Math.max(best, pnl);
      if (bal > peak) { peak = bal; floor = Math.min(peak - p.dd, 0); }
      i++;
      if (bal >= p.target && (!p.cons || best <= p.cons * bal)) { res = "pass"; break; }
    }
    if (res === null) { open++; continue; }
    if (res === "fail") { failed++; continue; }
    passed++; daysToPass.push(i - s);
    bal = 0; peak = 0; floor = -p.dd; let wins = 0, got = 0;
    while (i < n) {
      const { pnl, worst } = daily[i];
      if (bal + Math.min(worst, 0) <= floor) break;
      bal += pnl; if (pnl >= p.winDay) wins++;
      if (bal > peak) { peak = bal; floor = Math.min(peak - p.dd, 0); }
      const amt = Math.min(p.share * bal, p.cap);
      if (wins >= p.winNeed && bal > 0 && amt >= p.minPayout) { got += amt; bal -= amt; wins = 0; peak = Math.max(peak - amt, bal); }
      i++;
    }
    paid += got; if (got > 0) payout++;
  }
  const tot = passed + failed + open;
  const pct = (v) => (tot ? Math.round((100 * v) / tot) : null);
  daysToPass.sort((a, b) => a - b);
  return { plan: p.name, evaluations: tot, passPct: pct(passed), failPct: pct(failed), unfinishedPct: pct(open),
    medianTradingDaysToPass: daysToPass.length ? daysToPass[Math.floor(daysToPass.length / 2)] : null,
    reachedPayoutPct: pct(payout), avgWithdrawn: tot ? Math.round(paid / tot) : null };
}

function properties(sheets) {
  const rows = sheets.Properties || [];
  const out = {};
  for (const [k, v] of rows.slice(1)) if (k != null && k !== "") out[String(k).trim()] = v;
  return out;
}

export async function scoreExport(file, { split = "2026-01-01", plan = "select50" } = {}) {
  const sheets = await readSheets(file);
  const tradeSheet = sheets.Trades || sheets["List of Trades"] || Object.values(sheets).find((r) => r[0] && col(r[0], "Trade number", "Trade #") >= 0);
  if (!tradeSheet) throw new Error("No trades sheet found in the export");
  const ps = positions(tradeSheet);
  const props = properties(sheets);
  const isP = ps.filter((p) => p.entry < split);
  const oosP = ps.filter((p) => p.entry >= split);
  const overnight = ps.filter((p) => p.exit && p.exit.slice(0, 10) !== p.entry.slice(0, 10));
  const sorted = ps.map((p) => p.pnl).sort((a, b) => b - a);
  const net = sorted.reduce((a, b) => a + b, 0);
  const top10 = sorted.slice(0, 10).reduce((a, b) => a + b, 0);
  const byMonth = {};
  for (const p of ps) { const m = p.entry.slice(0, 7); byMonth[m] = Math.round(((byMonth[m] || 0) + p.pnl) * 100) / 100; }
  const daily = dailySeries(ps);
  const warnings = [];
  if (!isP.length) warnings.push(`No trades before ${split}: every trade is out-of-sample, nothing was validated. Extend the backtest (Deep Backtesting) or move the split.`);
  if (overnight.length) warnings.push(`${overnight.length} position(s) held past the trade date (check EOD flatten / contract data).`);
  if (ps.length < 100) warnings.push(`Only ${ps.length} positions: too few to trust a difference between settings.`);
  if (net > 0 && top10 > net) warnings.push(`The 10 best trades made more than the whole net (${Math.round(top10)} vs ${Math.round(net)}): fragile.`);
  return {
    file: path.basename(file),
    symbol: props.Symbol || null, timeframe: props.Timeframe || null, range: props["Trading range"] || null,
    split, all: stats(ps), inSample: stats(isP), outOfSample: stats(oosP),
    longs: stats(ps.filter((p) => p.side === "long")), shorts: stats(ps.filter((p) => p.side === "short")),
    overnightHolds: overnight.length, top10ShareOfNet: net > 0 ? Math.round((100 * top10) / net) : null,
    profitableMonths: `${Object.values(byMonth).filter((v) => v > 0).length}/${Object.keys(byMonth).length}`,
    byMonth, prop: propSim(daily, plan),
    propInSample: propSim(daily.filter((d) => d.date < split), plan),
    propOutOfSample: propSim(daily.filter((d) => d.date >= split), plan),
    inputs: props, warnings,
  };
}
