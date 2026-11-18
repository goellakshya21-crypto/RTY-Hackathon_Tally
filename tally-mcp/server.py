"""Tally MCP: asks TallyPrime for data and returns clean, readable answers."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict

from mcp.server.mcpserver import MCPServer

import tally_client as tc
from fmt import drcr, inr, period, qty, table

mcp = MCPServer(
    "tally",
    instructions=(
        "Tools to read accounting data from TallyPrime running on this PC. Answers are already "
        "formatted as Markdown tables; show them to the user as-is. Dates are YYYY-MM-DD. "
        "'company' is optional when only one company is open in Tally."),
)


def _safe(fn):
    """Turn Tally failures into a readable message instead of a stack trace."""
    import functools

    @functools.wraps(fn)
    def wrap(*a, **k):
        try:
            return fn(*a, **k)
        except tc.TallyError as e:
            return f"**Couldn't get this from Tally.** {e}"
    return wrap


def _date_filter(from_date, to_date) -> dict[str, str]:
    conds = []
    if from_date:
        conds.append(f'$Date >= $$Date:"{tc.tdl_date(from_date)}"')
    if to_date:
        conds.append(f'$Date <= $$Date:"{tc.tdl_date(to_date)}"')
    return {"MCPDateRange": " AND ".join(conds)} if conds else {}


def _ledger_entries(v: ET.Element) -> list[tuple[str, float]]:
    out = []
    for tag in ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"):
        for e in v.findall(tag):
            name = tc.text(e, "LEDGERNAME")
            if name:
                out.append((name, tc.to_number(tc.text(e, "AMOUNT"))))
    return out


def _voucher_amount(v: ET.Element) -> float:
    amt = abs(tc.to_number(tc.text(v, "AMOUNT")))
    if amt:
        return amt
    return sum(-a for _, a in _ledger_entries(v) if a < 0)  # total of debit side


# ---------------- tools ----------------

@mcp.tool()
@_safe
def list_companies() -> str:
    """Companies currently open in TallyPrime, with financial year start and books-from date."""
    rows = []
    for c in tc.collection("Company", ["Name", "StartingFrom", "BooksFrom", "StateName", "GSTRegistrationNumber"]):
        rows.append([c.get("NAME") or tc.text(c, "NAME"), tc.from_tally_date(tc.text(c, "STARTINGFROM")),
                     tc.from_tally_date(tc.text(c, "BOOKSFROM")), tc.text(c, "STATENAME"),
                     tc.text(c, "GSTREGISTRATIONNUMBER")])
    return "## Companies open in Tally\n\n" + table(
        ["Company", "FY starts", "Books from", "State", "GSTIN"], rows)


@mcp.tool()
@_safe
def list_ledgers(group: str = "", search: str = "", company: str = "", to_date: str = "",
                 hide_zero: bool = True) -> str:
    """All ledgers with their group and opening/closing balances.

    group: only ledgers under this group (incl. sub-groups), e.g. 'Sundry Debtors', 'Bank Accounts'.
    search: case-insensitive text to match in the ledger name.
    to_date: balances as on this date (YYYY-MM-DD); defaults to Tally's current period.
    """
    filters = {"MCPGroup": f'$$IsBelongsTo:"{group}"'} if group else None
    items = tc.collection("Ledger", ["Name", "Parent", "OpeningBalance", "ClosingBalance"],
                          company=company or None, to_date=to_date or None, filters=filters)
    rows, total = [], 0.0
    for l in items:
        name = l.get("NAME", "")
        if search and search.lower() not in name.lower():
            continue
        op, cl = tc.to_number(tc.text(l, "OPENINGBALANCE")), tc.to_number(tc.text(l, "CLOSINGBALANCE"))
        if hide_zero and abs(op) < 0.005 and abs(cl) < 0.005:
            continue
        total += cl
        rows.append((tc.text(l, "PARENT"), name, op, cl))
    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    title = f"## Ledgers{' in ' + group if group else ''} ({period(None, to_date or None)})"
    return (f"{title}\n\n{len(rows)} ledgers · net closing balance **{drcr(total)}**\n\n"
            + table(["Group", "Ledger", "Opening", "Closing"],
                    [[g, n, drcr(o), drcr(c)] for g, n, o, c in rows], ["l", "l", "r", "r"]))


@mcp.tool()
@_safe
def ledger_statement(ledger: str, from_date: str = "", to_date: str = "", company: str = "") -> str:
    """Account statement for one ledger: every voucher touching it, with running balance.

    ledger: exact ledger name as in Tally (use list_ledgers(search=...) to find it).
    """
    co = company or None
    led = [l for l in tc.collection("Ledger", ["Name", "Parent", "OpeningBalance", "ClosingBalance"],
                                    company=co, from_date=from_date or None, to_date=to_date or None)
           if l.get("NAME", "").lower() == ledger.lower()]
    if not led:
        return f"No ledger named **{ledger}**. Try list_ledgers(search=\"{ledger.split()[0]}\")."
    l = led[0]
    name = l.get("NAME")
    opening = tc.to_number(tc.text(l, "OPENINGBALANCE"))

    vouchers = tc.collection(
        "Voucher", ["Date", "VoucherTypeName", "VoucherNumber", "Narration", "PartyLedgerName",
                    "AllLedgerEntries.LedgerName", "AllLedgerEntries.Amount",
                    "LedgerEntries.LedgerName", "LedgerEntries.Amount"],
        company=co, from_date=from_date or None, to_date=to_date or None,
        filters=_date_filter(from_date, to_date))

    entries = []
    for v in vouchers:
        les = _ledger_entries(v)
        mine = sum(a for n, a in les if n.lower() == name.lower())
        if not any(n.lower() == name.lower() for n, _ in les):
            continue
        others = sorted({n for n, _ in les if n.lower() != name.lower()})
        entries.append((tc.text(v, "DATE"), tc.text(v, "VOUCHERTYPENAME"), tc.text(v, "VOUCHERNUMBER"),
                        ", ".join(others[:3]) + (" …" if len(others) > 3 else ""), mine,
                        tc.text(v, "NARRATION")))
    entries.sort(key=lambda e: e[0])

    bal, dr_tot, cr_tot, rows = opening, 0.0, 0.0, []
    for d, typ, no, against, amt, narr in entries:
        bal += amt
        dr, cr = (-amt, 0) if amt < 0 else (0, amt)
        dr_tot += dr
        cr_tot += cr
        rows.append([tc.from_tally_date(d), typ, no, against, inr(dr) if dr else "", inr(cr) if cr else "",
                     drcr(bal), narr])

    head = (f"## Ledger statement: {name}\n"
            f"Group: {tc.text(l, 'PARENT')} · Period: {period(from_date or None, to_date or None)}\n\n"
            f"| Opening | Total Debit | Total Credit | Closing |\n|---:|---:|---:|---:|\n"
            f"| {drcr(opening)} | {inr(dr_tot)} | {inr(cr_tot)} | **{drcr(bal)}** |\n\n")
    return head + table(["Date", "Type", "No.", "Against", "Debit", "Credit", "Balance", "Narration"],
                        rows, ["l", "l", "l", "l", "r", "r", "r", "l"])


@mcp.tool()
@_safe
def day_book(from_date: str, to_date: str = "", voucher_type: str = "", company: str = "",
             show_entries: bool = False) -> str:
    """Vouchers entered in a period (date, type, number, party, amount, narration), with totals per type.

    voucher_type: e.g. 'Sales', 'Purchase', 'Receipt', 'Payment', 'Journal', 'Contra'.
    show_entries: also list each voucher's ledger-wise Dr/Cr lines.
    """
    to_date = to_date or from_date
    filters = _date_filter(from_date, to_date)
    if voucher_type:
        filters["MCPType"] = f'$VoucherTypeName = "{voucher_type}"'
    vouchers = tc.collection(
        "Voucher", ["Date", "VoucherTypeName", "VoucherNumber", "PartyLedgerName", "Narration", "Amount",
                    "AllLedgerEntries.LedgerName", "AllLedgerEntries.Amount",
                    "LedgerEntries.LedgerName", "LedgerEntries.Amount"],
        company=company or None, from_date=from_date, to_date=to_date, filters=filters)
    vouchers.sort(key=lambda v: (tc.text(v, "DATE"), tc.text(v, "VOUCHERNUMBER")))

    by_type = defaultdict(lambda: [0, 0.0])
    rows, detail = [], []
    for v in vouchers:
        typ, amt = tc.text(v, "VOUCHERTYPENAME"), _voucher_amount(v)
        by_type[typ][0] += 1
        by_type[typ][1] += amt
        les = _ledger_entries(v)
        party = tc.text(v, "PARTYLEDGERNAME") or (les[0][0] if les else "")
        rows.append([tc.from_tally_date(tc.text(v, "DATE")), typ, tc.text(v, "VOUCHERNUMBER"), party,
                     inr(amt), tc.text(v, "NARRATION")])
        if show_entries:
            detail.append(f"**{typ} #{tc.text(v, 'VOUCHERNUMBER')}** ({tc.from_tally_date(tc.text(v, 'DATE'))})\n"
                          + "\n".join(f"- {n}: {drcr(a)}" for n, a in les))

    out = (f"## Day Book · {period(from_date, to_date)}{' · ' + voucher_type if voucher_type else ''}\n\n"
           f"**{len(vouchers)} vouchers**\n\n"
           + table(["Voucher type", "Count", "Total"],
                   [[t, c, inr(a)] for t, (c, a) in sorted(by_type.items())], ["l", "r", "r"])
           + "\n\n### Vouchers\n\n"
           + table(["Date", "Type", "No.", "Party / Ledger", "Amount", "Narration"], rows,
                   ["l", "l", "l", "l", "r", "l"]))
    if detail:
        out += "\n\n### Ledger entries\n\n" + "\n\n".join(detail)
    return out


def _groups(company, from_date, to_date):
    gs = tc.collection("Group", ["Name", "Parent", "ClosingBalance", "IsRevenue", "AffectsGrossProfit",
                                 "IsDeemedPositive"],
                       company=company or None, from_date=from_date or None, to_date=to_date or None)
    out = []
    for g in gs:
        parent = tc.text(g, "PARENT").strip()
        out.append({"name": g.get("NAME", ""), "parent": parent,
                    "primary": parent in ("", "Primary"),
                    "bal": tc.to_number(tc.text(g, "CLOSINGBALANCE")),
                    "revenue": tc.yes(tc.text(g, "ISREVENUE")),
                    "gross": tc.yes(tc.text(g, "AFFECTSGROSSPROFIT"))})
    return out


@mcp.tool()
@_safe
def trial_balance(from_date: str = "", to_date: str = "", company: str = "", by_ledger: bool = False) -> str:
    """Trial balance with Debit and Credit columns, by primary group (or by ledger)."""
    if by_ledger:
        items = [(l.get("NAME", ""), tc.text(l, "PARENT"), tc.to_number(tc.text(l, "CLOSINGBALANCE")))
                 for l in tc.collection("Ledger", ["Name", "Parent", "ClosingBalance"],
                                        company=company or None, from_date=from_date or None,
                                        to_date=to_date or None)]
        items = sorted((i for i in items if abs(i[2]) >= 0.005), key=lambda i: (i[1], i[0]))
        rows = [[n, g, inr(-b) if b < 0 else "", inr(b) if b > 0 else ""] for n, g, b in items]
        headers, align = ["Ledger", "Group", "Debit", "Credit"], ["l", "l", "r", "r"]
        bals = [i[2] for i in items]
    else:
        prim = [g for g in _groups(company, from_date, to_date) if g["primary"] and abs(g["bal"]) >= 0.005]
        rows = [[g["name"], inr(-g["bal"]) if g["bal"] < 0 else "", inr(g["bal"]) if g["bal"] > 0 else ""]
                for g in prim]
        headers, align = ["Group", "Debit", "Credit"], ["l", "r", "r"]
        bals = [g["bal"] for g in prim]
    dr = sum(-b for b in bals if b < 0)
    cr = sum(b for b in bals if b > 0)
    rows.append(["**Total**"] + ([""] if by_ledger else []) + [f"**{inr(dr)}**", f"**{inr(cr)}**"])
    note = "" if abs(dr - cr) < 1 else f"\n\n⚠️ Difference of {inr(abs(dr - cr))} (often the opening-balance difference in Tally)."
    return (f"## Trial Balance · {period(from_date or None, to_date or None)}\n\n"
            + table(headers, rows, align) + note)


@mcp.tool()
@_safe
def profit_and_loss(from_date: str = "", to_date: str = "", company: str = "") -> str:
    """Profit & Loss summary: trading items, gross profit, indirect items, net profit."""
    rev = [g for g in _groups(company, from_date, to_date) if g["primary"] and g["revenue"]]
    def side(gs, credit):
        return [(g["name"], abs(g["bal"])) for g in gs if (g["bal"] > 0) == credit and abs(g["bal"]) >= 0.005]
    trading, indirect = [g for g in rev if g["gross"]], [g for g in rev if not g["gross"]]
    gp = sum(g["bal"] for g in trading)
    np_ = sum(g["bal"] for g in rev)

    def block(title, gs):
        parts = [f"### {title}"]
        for label, items in (("Income", side(gs, True)), ("Expense", side(gs, False))):
            if items:
                parts.append(table([label, "Amount"], [[n, inr(a)] for n, a in items], ["l", "r"]))
        return "\n\n".join(parts if len(parts) > 1 else parts + ["_No entries._"])

    lab = lambda x: f"{'Profit' if x >= 0 else 'Loss'} {inr(abs(x))}"
    return (f"## Profit & Loss · {period(from_date or None, to_date or None)}\n\n"
            f"| Gross | Net |\n|---:|---:|\n| **{lab(gp)}** | **{lab(np_)}** |\n\n"
            + block("Trading (direct)", trading) + "\n\n" + block("Indirect", indirect))


@mcp.tool()
@_safe
def balance_sheet(to_date: str = "", company: str = "") -> str:
    """Balance sheet as on a date: liabilities and assets by primary group, with profit/loss carried."""
    gs = _groups(company, None, to_date)
    bs = [g for g in gs if g["primary"] and not g["revenue"] and abs(g["bal"]) >= 0.005]
    pl = sum(g["bal"] for g in gs if g["primary"] and g["revenue"])
    liab = [(g["name"], g["bal"]) for g in bs if g["bal"] > 0]
    assets = [(g["name"], -g["bal"]) for g in bs if g["bal"] < 0]
    if abs(pl) >= 0.005:
        (liab if pl > 0 else assets).append(("Profit & Loss A/c" + (" (loss)" if pl < 0 else ""), abs(pl)))
    lt, at = sum(a for _, a in liab), sum(a for _, a in assets)
    return (f"## Balance Sheet · {period(None, to_date or None)}\n\n### Liabilities\n\n"
            + table(["Group", "Amount"], [[n, inr(a)] for n, a in liab] + [["**Total**", f"**{inr(lt)}**"]], ["l", "r"])
            + "\n\n### Assets\n\n"
            + table(["Group", "Amount"], [[n, inr(a)] for n, a in assets] + [["**Total**", f"**{inr(at)}**"]], ["l", "r"])
            + ("" if abs(lt - at) < 1 else f"\n\n⚠️ Sides differ by {inr(abs(lt - at))} (check opening balances in Tally)."))


@mcp.tool()
@_safe
def outstandings(kind: str = "receivable", to_date: str = "", company: str = "", top: int = 0) -> str:
    """Who owes you (receivable: Sundry Debtors) or whom you owe (payable: Sundry Creditors), largest first."""
    receivable = kind.lower().startswith("r")
    group = "Sundry Debtors" if receivable else "Sundry Creditors"
    items = tc.collection("Ledger", ["Name", "Parent", "ClosingBalance"], company=company or None,
                          to_date=to_date or None, filters={"MCPGroup": f'$$IsBelongsTo:"{group}"'})
    rows = []
    for l in items:
        b = tc.to_number(tc.text(l, "CLOSINGBALANCE"))
        due = -b if receivable else b  # receivables are Dr (negative), payables Cr (positive)
        if abs(due) >= 0.005:
            rows.append((l.get("NAME", ""), tc.text(l, "PARENT"), due))
    rows.sort(key=lambda r: -r[2])
    total = sum(r[2] for r in rows)
    shown = rows[:top] if top else rows
    title = "Receivables (owed to you)" if receivable else "Payables (you owe)"
    return (f"## {title} · {period(None, to_date or None)}\n\n**{len(rows)} part{'y' if len(rows) == 1 else 'ies'} · total {inr(total)}**"
            + ("\n\nNegative amounts are advances." if any(r[2] < 0 for r in rows) else "") + "\n\n"
            + table(["Party", "Group", "Amount"], [[n, g, inr(a)] for n, g, a in shown], ["l", "l", "r"]))


@mcp.tool()
@_safe
def stock_summary(group: str = "", search: str = "", to_date: str = "", company: str = "") -> str:
    """Stock items with closing quantity, rate and value."""
    filters = {"MCPGroup": f'$$IsBelongsTo:"{group}"'} if group else None
    items = tc.collection("StockItem", ["Name", "Parent", "BaseUnits", "ClosingBalance", "ClosingRate",
                                       "ClosingValue"], company=company or None, to_date=to_date or None,
                          filters=filters)
    rows, total = [], 0.0
    for s in items:
        name = s.get("NAME", "")
        if search and search.lower() not in name.lower():
            continue
        q_raw = tc.text(s, "CLOSINGBALANCE")
        q = tc.to_number(q_raw)
        unit = tc.unit_of(q_raw) or tc.text(s, "BASEUNITS")
        val = abs(tc.to_number(tc.text(s, "CLOSINGVALUE")))
        total += val
        rows.append([tc.text(s, "PARENT"), name, qty(q, unit), inr(abs(tc.to_number(tc.text(s, "CLOSINGRATE")))),
                     inr(val)])
    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    return (f"## Stock summary · {period(None, to_date or None)}\n\n**{len(rows)} items · value {inr(total)}**\n\n"
            + table(["Group", "Item", "Quantity", "Rate", "Value"], rows, ["l", "l", "r", "r", "r"]))


def _tidy(el: ET.Element, depth=0, max_depth=8) -> list[str]:
    """Generic cleaner: drops empty tags and noise lists, shows nesting as indented bullets."""
    noise = ("OLDAUDITENTRYIDS.LIST", "UDF_", "EXCLUDEDTAXATIONS.LIST", "ACCOUNTAUDITENTRIES.LIST",
             "AUDITENTRIES.LIST")
    lines = []
    for ch in el:
        tag = ch.tag
        if any(tag.startswith(n) for n in noise) or depth > max_depth:
            continue
        val = (ch.text or "").strip()
        sub = _tidy(ch, depth + 1, max_depth)
        if not val and not sub and not ch.get("NAME"):
            continue
        label = tag.replace(".LIST", "").title()
        if ch.get("NAME"):
            label += f" “{ch.get('NAME')}”"
        if val:
            t = ch.get("TYPE", "")
            if t == "Amount" or (tag in ("AMOUNT", "CLOSINGBALANCE", "OPENINGBALANCE") and tc._NUM.fullmatch(val)):
                val = drcr(tc.to_number(val))
            elif t == "Date" or (len(val) == 8 and val.isdigit()):
                val = tc.from_tally_date(val)
            lines.append(f"{'  ' * depth}- **{label}:** {val}")
        else:
            lines.append(f"{'  ' * depth}- **{label}**")
        lines += sub
    return lines


@mcp.tool()
@_safe
def raw_request(xml: str) -> str:
    """Send any TallyPrime XML request and get the reply cleaned up (empty/audit tags removed,
    amounts as ₹ Dr/Cr, dates readable). Use when no dedicated tool covers the question."""
    root = tc.raw(xml)
    body = next((b for b in (root.find(".//DATA"), root.find(".//BODY")) if b is not None), root)
    lines = _tidy(body)
    if len(lines) > 1500:
        lines = lines[:1500] + [f"\n_…truncated ({len(lines)} lines total)._"]
    return "## Tally response\n\n" + ("\n".join(lines) or "_Empty response._")


def main():
    import os
    if os.environ.get("TALLY_MOCK") == "1":
        import mock_tally
        tc.transport = mock_tally.transport
    mcp.run()


if __name__ == "__main__":
    main()
