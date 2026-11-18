"""Runs every tool against the fake Tally and prints the output."""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
import tally_client as tc, mock_tally, server
tc.transport = mock_tally.transport

calls = [("list_companies", {}), ("list_ledgers", {}), ("list_ledgers", {"group": "Sundry Debtors"}),
         ("ledger_statement", {"ledger": "sharma builders", "from_date": "2026-11-01", "to_date": "2026-11-30"}),
         ("day_book", {"from_date": "2026-11-01", "to_date": "2026-11-30", "show_entries": True}),
         ("day_book", {"from_date": "2026-11-01", "to_date": "2026-11-30", "voucher_type": "Sales"}),
         ("trial_balance", {}), ("trial_balance", {"by_ledger": True}), ("profit_and_loss", {}),
         ("balance_sheet", {}), ("outstandings", {}), ("outstandings", {"kind": "payable"}),
         ("stock_summary", {}), ("raw_request", {"xml": "<ENVELOPE/>"})]

async def main():
    tools = await server.mcp.list_tools()
    print("TOOLS:", [t.name for t in tools])
    for name, args in calls:
        res = await server.mcp.call_tool(name, args)
        out = res[0][0].text if isinstance(res, tuple) else (res[0].text if isinstance(res, list) else res.content[0].text)
        print(f"\n===== {name} {args} =====\n{out}")
asyncio.run(main())
