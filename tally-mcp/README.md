# Tally MCP

An MCP server that reads data from **TallyPrime** and returns it as clean, readable answers: Markdown tables, ₹ amounts in Indian format (₹1,23,456.00), Dr/Cr instead of negative signs, readable dates, and none of Tally's empty or audit tags.

## Tools

| Tool | What you get |
|---|---|
| `list_companies` | Companies open in Tally, FY start, GSTIN |
| `list_ledgers` | Ledgers with group and opening/closing balance (filter by group or name) |
| `ledger_statement` | One ledger's entries for a period, with running balance and totals |
| `day_book` | Vouchers in a period, totals per voucher type, optional Dr/Cr lines |
| `trial_balance` | Tally's own trial balance, by primary group or one level deeper, incl. the opening-balance difference line |
| `profit_and_loss` | Tally's own P&L incl. opening/closing stock, gross and net profit, negative-stock warning |
| `balance_sheet` | Tally's own balance sheet with P&L A/c and stock |
| `outstandings` | Receivables or payables by party, largest first |
| `stock_summary` | Items with quantity, rate and value; flags items below zero stock |
| `raw_request` | Send any Tally XML and get the reply cleaned up |

## 1. Turn on Tally's API (once)

In TallyPrime: **F1 Help → Settings → Connectivity → Client/Server configuration**
- *TallyPrime acts as*: **Both** (or Server)
- *Port*: **9000** (or your own; then set `TALLY_URL`)

Keep TallyPrime open with the company loaded while you use it.

## 2. Install

```bash
cd D:\tally-mcp
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## 3. Connect to Claude

**Claude Code:**
```bash
claude mcp add tally --scope user -- D:\tally-mcp\.venv\Scripts\python.exe D:\tally-mcp\server.py
```

**Claude Desktop:** add this to `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "tally": {
      "command": "D:\\tally-mcp\\.venv\\Scripts\\python.exe",
      "args": ["D:\\tally-mcp\\server.py"],
      "env": { "TALLY_URL": "http://localhost:9000" }
    }
  }
}
```

Then ask things like *"Show Sharma Builders' statement for November"* or *"Who owes us the most money?"*

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `TALLY_URL` | `http://localhost:9000` | Where TallyPrime listens (use the PC's IP if Tally runs on another machine) |
| `TALLY_TIMEOUT` | `30` | Seconds to wait for an answer before reporting that Tally isn't responding |
| `TALLY_MOCK` | off | `1` = use built-in sample data instead of a real Tally (demo/testing) |

## Testing without Tally

```bash
.venv\Scripts\python test_offline.py
```
This runs every tool against `mock_tally.py`, which replies in Tally's real messy XML format (control characters like `&#4;`, undeclared `UDF:` tags, the all-zero `CMPINFO` block, signed amounts, empty lists) and checks the report figures. The fake Tally also refuses the date format that freezes real Tally, so that bug can't come back unnoticed.

## If TallyPrime freezes

Tally answers XML requests on its UI thread, so a bad request freezes the whole window ("Not Responding", 100% CPU) until it is restarted.

`diagnose.py` sends small requests one at a time and stops at the first one Tally doesn't answer:
```bash
python diagnose.py
```

**What it found:** sending a report period as `<SVFROMDATE>20250401</SVFROMDATE><SVTODATE>20260331</SVTODATE>` (plain `YYYYMMDD`) puts TallyPrime into an endless loop. The same period as `<SVFROMDATE TYPE="Date">1-Apr-2025</SVFROMDATE>` answers in 0.02 s. The server always sends the safe form, and rewrites the unsafe form if an agent writes it in `raw_request`. Requests are also sent one at a time, never in parallel.

## What's next

Read-only today. Next: write tools with approval, starting with **photo of a bill → purchase voucher in Tally**. Then bank reconciliation, GSTR-2B matching, collections reminders, weekly health checks and voice entries. See [ROADMAP.md](ROADMAP.md).

## Notes / limits
- Sign convention follows Tally: negative = Debit, positive = Credit. The output always says Dr or Cr.
- Trial balance, P&L and balance sheet are Tally's own reports, not recalculated, because Tally's stock rules (opening stock in the trial balance, closing stock in P&L/balance sheet, negative stock) are easy to get wrong from group balances.
- `outstandings` shows party balances, not bill-wise ageing.
