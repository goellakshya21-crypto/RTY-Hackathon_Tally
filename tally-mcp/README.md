# Tally MCP

An MCP server that reads data from **TallyPrime** and returns it as clean, readable answers: Markdown tables, ₹ amounts in Indian format (₹1,23,456.00), Dr/Cr instead of negative signs, readable dates, and none of Tally's empty or audit tags.

## Tools

| Tool | What you get |
|---|---|
| `list_companies` | Companies open in Tally, FY start, GSTIN |
| `list_ledgers` | Ledgers with group and opening/closing balance (filter by group or name) |
| `ledger_statement` | One ledger's entries for a period, with running balance and totals |
| `day_book` | Vouchers in a period, totals per voucher type, optional Dr/Cr lines |
| `trial_balance` | By primary group or by ledger, with a check that totals match |
| `profit_and_loss` | Gross and net profit, direct and indirect income/expenses |
| `balance_sheet` | Liabilities and assets with P&L carried over |
| `outstandings` | Receivables or payables by party, largest first |
| `stock_summary` | Items with quantity, rate and value |
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
| `TALLY_TIMEOUT` | `60` | Seconds to wait for big reports |
| `TALLY_MOCK` | off | `1` = use built-in sample data instead of a real Tally (demo/testing) |

## Testing without Tally

```bash
.venv\Scripts\python test_offline.py
```
This runs every tool against `mock_tally.py`, which replies in Tally's real messy XML format (control characters like `&#4;`, undeclared `UDF:` tags, signed amounts, empty lists).

## Notes / limits
- Sign convention follows Tally: negative = Debit, positive = Credit. The output always says Dr or Cr.
- `outstandings` shows party balances, not bill-wise ageing.
- P&L and Balance Sheet come from primary-group totals, so they match Tally's condensed view; expand using `list_ledgers(group=...)`.
