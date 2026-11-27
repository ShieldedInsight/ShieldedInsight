# TruePath TV Optimizer

Lets Claude Code on your Mac run strategy optimizations in TradingView: it sets
your strategy's inputs, exports the Strategy Tester report, and scores every run
(in-sample vs out-of-sample, overnight holds, fragility, Tradeify pass / payout
simulation). Personal use only. Nothing here places trades.

```
Claude Code (Mac) ──stdio──▶ MCP server (server/, Node)  ──ws://127.0.0.1:8765 + token──▶  Chrome extension (extension/)
   tv-optimize skill            scores exports from ~/Downloads                             works the TradingView chart tab
```

**Before you use it:** TradingView's terms of use may restrict automated use of
the site. Read them and decide; the extension only does what you could do by
hand (open settings, change inputs, press Export), at a person's pace.

## 1. Install Node.js (once)

```bash
brew install node            # Homebrew; or download the LTS installer from nodejs.org
node -v                      # v20 or newer
```

## 2. Install the server

```bash
cd ShieldedInsight/tools/tv-optimizer/server
npm install
```

## 3. Add it to Claude Code

```bash
claude mcp add tv-optimizer --scope user -- node "$PWD/index.js"
claude mcp list              # tv-optimizer should be listed
```

Start Claude Code once (`claude`) so the server runs and creates its token:

```bash
cat ~/.tv-optimizer/token
```

Options (add `-e NAME=value` to the `claude mcp add` command):
`TVO_PORT` (default 8765), `TVO_DOWNLOADS` (default `~/Downloads`, where Chrome
saves the export).

## 4. Install the Chrome extension

**Test it first by loading it unpacked:**

1. Chrome → `chrome://extensions` → turn on **Developer mode** (top right).
2. **Load unpacked** → choose `tools/tv-optimizer/extension`.
3. Click the extension's icon → paste the token → **Save and connect**. The
   status reads `connected` while Claude Code is running.
4. Reload your TradingView chart tab once.

**Then publish your private copy on the Chrome Web Store:**

1. Register at the Chrome Web Store Developer Dashboard (one-time fee, $5 at the time of writing).
2. Zip the folder: `cd tools/tv-optimizer && zip -r tv-optimizer-extension.zip extension`.
3. Dashboard → **New item** → upload the zip.
4. **Distribution → Visibility:** choose **Unlisted** (only people with the
   link can find it). If your account offers **Private** with trusted testers,
   add only your own email instead.
5. **Privacy practices:** single purpose: "Lets the user's own local tool set
   TradingView strategy inputs and export Strategy Tester reports." Permission
   justifications: *tabs* (find the TradingView chart tab), *storage* (port,
   token, selector overrides), *alarms* (reconnect to the local server),
   *host permission tradingview.com* (the content script that works the chart).
   Data: none collected or sent anywhere except to `127.0.0.1` on your Mac.
6. Submit for review (usually a few days), then install from your listing link
   and remove the unpacked copy.

## 5. Use it

Open a TradingView chart with your strategy and the Strategy Tester panel, turn
on **Deep Backtesting** with a range from 2019 (or as far as the data goes),
then in Claude Code (in this repo):

```
/tv-optimize TP Bot — vary risk 300–600 and the profit exit
```

The `tv-optimize` skill (`.claude/skills/tv-optimize`) runs the loop: baseline,
candidates, choose on in-sample data, then judge on out-of-sample. Every export
is kept in `~/.tv-optimizer/runs/` and logged in `~/.tv-optimizer/runs.jsonl`.

## Tools Claude gets

| Tool | What it does |
| --- | --- |
| `tv_status` | Connection, chart tab, strategies in the legend |
| `tv_get_inputs` | Reads every input on the strategy's Inputs tab |
| `tv_set_inputs` | Sets inputs by label, presses OK, waits for the tester |
| `tv_export_and_score` | Clicks Export, picks up the file, scores and logs it |
| `tv_score_file` | Scores an export already on disk |
| `tv_runs` | The run log, with what changed per run |
| `tv_inspect`, `tv_click`, `tv_set_selector` | Repair tools for when TradingView changes its page |

## When something breaks

- **"extension is not connected":** Claude Code must be running (it starts the
  server); check the token in the extension; reload the chart tab.
- **"No new .xlsx/.csv appeared":** Chrome may ask where to save, or save
  elsewhere. Turn off "Ask where to save each file" or set `TVO_DOWNLOADS`.
- **"not found" (legend, dialog, export button):** TradingView changed its
  page. Ask Claude to repair it: it uses `tv_inspect` and `tv_set_selector`.
  Tell me (or edit `SEL` in `extension/content.js`) to make the fix permanent.
- **An input is in `failed`:** use the exact label from `tv_get_inputs`. A
  second field on the same row is labelled `<label> #2`.

## Security

- The WebSocket listens on `127.0.0.1` only, accepts only `chrome-extension://`
  origins, and needs the 48-character token from `~/.tv-optimizer/token`
  (file mode 600). Delete the file to rotate it.
- The extension runs only on `tradingview.com/chart` pages. It reads and changes
  the strategy settings dialog and clicks Export; it does not read your account,
  alerts or broker panel.
