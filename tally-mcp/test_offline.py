"""Runs every tool against the fake Tally and prints the output. Exits non-zero if any tool fails."""
import asyncio, sys
sys.stdout.reconfigure(encoding="utf-8")
import tally_client as tc, mock_tally, server
tc.transport = mock_tally.transport

PLAIN_DATES = ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Collection</TYPE>"
               "<ID>X</ID></HEADER><BODY><DESC><STATICVARIABLES><SVFROMDATE>20250401</SVFROMDATE>"
               "<SVTODATE>20260331</SVTODATE></STATICVARIABLES></DESC></BODY></ENVELOPE>")

calls = [("list_companies", {}), ("list_ledgers", {}), ("list_ledgers", {"group": "Sundry Debtors"}),
         ("ledger_statement", {"ledger": "sharma builders", "from_date": "2026-11-01", "to_date": "2026-11-30"}),
         ("day_book", {"from_date": "2026-11-01", "to_date": "2026-11-30", "show_entries": True}),
         ("day_book", {"from_date": "2026-11-01", "to_date": "2026-11-30", "voucher_type": "Sales"}),
         ("trial_balance", {}), ("trial_balance", {"by_ledger": True}),
         ("trial_balance", {"from_date": "2025-04-01", "to_date": "2026-03-31", "company": "Goel Stones Pvt Ltd"}),
         ("profit_and_loss", {"from_date": "2026-04-01", "to_date": "2027-03-31"}),
         ("balance_sheet", {"to_date": "2027-03-31"}), ("outstandings", {}), ("outstandings", {"kind": "payable"}),
         ("stock_summary", {}), ("raw_request", {"xml": "<ENVELOPE/>"}),
         # An agent writing its own XML with the date form that freezes real Tally must be made safe.
         ("raw_request", {"xml": PLAIN_DATES})]


def checks():
    assert tc.tdl_date("2025-04-01") == "1-Apr-2025", tc.tdl_date("2025-04-01")
    assert tc.tdl_date("20260331") == "31-Mar-2026"
    safe = tc.make_dates_safe(PLAIN_DATES)
    assert '<SVFROMDATE TYPE="Date">1-Apr-2025</SVFROMDATE>' in safe, safe
    assert '<SVTODATE TYPE="Date">31-Mar-2026</SVTODATE>' in safe, safe
    s = tc._static_vars("X", "2025-04-01", "2026-03-31")
    assert "20250401" not in s and 'TYPE="Date">1-Apr-2025<' in s, s
    print("date-format checks passed")


async def main():
    checks()
    tools = await server.mcp.list_tools()
    print("TOOLS:", [t.name for t in tools])
    failed = 0
    for name, args in calls:
        res = await server.mcp.call_tool(name, args)
        out = res[0][0].text if isinstance(res, tuple) else (res[0].text if isinstance(res, list) else res.content[0].text)
        shown = {k: (v[:40] + "…" if isinstance(v, str) and len(v) > 40 else v) for k, v in args.items()}
        print(f"\n===== {name} {shown} =====\n{out}")
        if "Couldn't get this from Tally" in out:
            failed += 1
    print(f"\n{len(calls) - failed}/{len(calls)} tool calls succeeded")

    # Figures must match the fake Tally's own reports (which are internally consistent).
    tb, pl, bs = server.trial_balance(), server.profit_and_loss(), server.balance_sheet()
    assert "**₹10,25,700.00** | **₹10,25,700.00**" in tb and "Difference" not in tb, tb
    assert "Current Assets | ₹6,04,400.00" in tb, tb
    assert "Profit ₹2,64,520.00" in pl and "Profit ₹2,30,220.00" in pl, pl  # gross, net
    assert "Less: Closing Stock | ₹1,66,520.00" in pl and "negative" not in pl, pl
    assert bs.count("**₹9,05,920.00**") == 2 and "Difference" not in bs, bs
    assert "↳ Sundry Debtors | ₹1,30,500.00" in server.trial_balance(by_ledger=True)
    st = server.stock_summary()
    assert "value ₹1,66,520.00" in st and "below zero" not in st, st  # same as P&L closing stock
    print("report figure checks passed")
    return 1 if failed else 0

sys.exit(asyncio.run(main()))
