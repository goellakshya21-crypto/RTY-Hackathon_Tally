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

@mcp.tool(structured_output=False)
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


@mcp.tool(structured_output=False)
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


@mcp.tool(structured_output=False)
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


@mcp.tool(structured_output=False)
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


# Trial balance, P&L and balance sheet come from Tally's own reports rather than being rebuilt from
# group balances: Tally applies stock rules (opening stock in the trial balance, closing stock in the
# P&L and balance sheet, negative stock) that a group-balance sum gets wrong.

DIFF_LABEL = "_Difference in opening balances_"


def _tb_rows(root) -> list[tuple[str, float]]:
    """Trial Balance report -> [(name, net)], Tally sign (negative = Dr)."""
    rows, name = [], None
    for el in root:
        if el.tag == "DSPACCNAME":
            name = tc.text(el, "DSPDISPNAME")
        elif el.tag == "DSPACCINFO" and name is not None:
            dr = tc.to_number(el.findtext(".//DSPCLDRAMTA"))
            cr = tc.to_number(el.findtext(".//DSPCLCRAMTA"))
            rows.append((name, dr + cr))
            name = None
    return rows


def _statement_rows(root, name_tag, amt_tag) -> list[tuple[str, float | None, float | None]]:
    """P&L / Balance Sheet report -> [(name, sub_amount, main_amount)], None where Tally left it blank."""
    rows, name = [], None
    num = lambda s: tc.to_number(s) if s and s.strip() else None
    for el in root:
        if el.tag == name_tag:
            name = el.findtext(".//DSPDISPNAME", "").strip()
        elif el.tag == amt_tag and name is not None:
            sub_tag = amt_tag[:-3] + "SUBAMT"  # PLAMT -> PLSUBAMT, BSAMT -> BSSUBAMT
            rows.append((name, num(el.findtext(".//" + sub_tag)), num(el.findtext(".//BSMAINAMT"))))
            name = None
    return rows


def _dr_cr_cells(net: float) -> list[str]:
    return [inr(-net) if net < -0.005 else "", inr(net) if net > 0.005 else ""]


@mcp.tool(structured_output=False)
@_safe
def trial_balance(from_date: str = "", to_date: str = "", company: str = "", by_ledger: bool = False) -> str:
    """Trial balance exactly as TallyPrime computes it, with Debit and Credit columns per primary group.

    by_ledger: also list the sub-groups and ledgers one level under each group.
    """
    co, f, t = company or None, from_date or None, to_date or None
    top = _tb_rows(tc.report("Trial Balance", company=co, from_date=f, to_date=t))
    top = [(n, b) for n, b in top if abs(b) >= 0.005]
    rows = []
    if by_ledger:
        primary = {n for n, _ in top}
        for n, b in _tb_rows(tc.report("Trial Balance", company=co, from_date=f, to_date=t, explode=True)):
            if abs(b) < 0.005:
                continue
            rows.append([f"**{n}**" if n in primary else f"&nbsp;&nbsp;&nbsp;↳ {n}"] + _dr_cr_cells(b))
    else:
        rows = [[n] + _dr_cr_cells(b) for n, b in top]
    dr = sum(-b for _, b in top if b < 0)
    cr = sum(b for _, b in top if b > 0)
    note = ""
    if abs(dr - cr) >= 0.5:
        diff = abs(dr - cr)
        rows.append([DIFF_LABEL] + ([inr(diff), ""] if dr < cr else ["", inr(diff)]))
        note = (f"\n\nThe books don't balance by **{inr(diff)}**. Tally shows this line too; it means "
                "opening balances entered in Tally don't add up (Dr ≠ Cr).")
        dr = cr = max(dr, cr)
    rows.append(["**Total**", f"**{inr(dr)}**", f"**{inr(cr)}**"])
    return (f"## Trial Balance · {period(f, t)}\n\n"
            + table(["Particulars", "Debit", "Credit"], rows, ["l", "r", "r"]) + note)


@mcp.tool(structured_output=False)
@_safe
def profit_and_loss(from_date: str = "", to_date: str = "", company: str = "") -> str:
    """Profit & Loss exactly as TallyPrime computes it (incl. opening/closing stock), with gross and net profit."""
    f, t = from_date or None, to_date or None
    rows = _statement_rows(tc.report("Profit and Loss", company=company or None, from_date=f, to_date=t),
                           "DSPACCNAME", "PLAMT")
    out, net, gross, main_sign, warn = [], 0.0, None, 1, ""
    for name, sub, main in rows:
        if sub is not None and "closing stock" in name.lower() and sub * main_sign < 0:
            warn = (f"\n\n⚠️ Closing stock is **negative ({inr(sub * main_sign)})**: Tally has more goods going "
                    "out than coming in. Usually sales were entered without the matching purchases or opening "
                    "stock, which inflates cost of sales and understates profit.")
        if main is not None:
            if gross is None and name.lower().startswith("indirect"):
                gross = net
                out.append(["**Gross profit**" if gross >= 0 else "**Gross loss**", "", f"**{inr(abs(gross))}**"])
            net += main
            main_sign = 1 if main >= 0 else -1
            out.append([f"**{name}**", "", ("+" if main >= 0 else "−") + inr(abs(main))])
        elif sub is not None:
            # Tally signs sub-lines as balances (negative = Dr); show them the way its screen does.
            out.append([f"&nbsp;&nbsp;&nbsp;{name}", inr(sub * main_sign), ""])
    if not out:
        return "## Profit & Loss\n\n_No income or expenses in this period._"
    if gross is None:
        gross = net
    out.append(["**Net profit**" if net >= 0 else "**Net loss**", "", f"**{inr(abs(net))}**"])
    lab = lambda x: f"{'Profit' if x >= 0 else 'Loss'} {inr(abs(x))}"
    return (f"## Profit & Loss · {period(f, t)}\n\n"
            f"| Gross | Net |\n|---:|---:|\n| **{lab(gross)}** | **{lab(net)}** |\n\n"
            + table(["Particulars", "Details", "Amount"], out, ["l", "r", "r"])
            + "\n\n`+` adds to profit, `−` reduces it." + warn)


@mcp.tool(structured_output=False)
@_safe
def balance_sheet(to_date: str = "", company: str = "") -> str:
    """Balance sheet as on a date, exactly as TallyPrime computes it (incl. stock and Profit & Loss A/c)."""
    t = to_date or None
    rows = _statement_rows(tc.report("Balance Sheet", company=company or None, to_date=t), "BSNAME", "BSAMT")
    liab, assets, side = [], [], None
    for name, sub, main in rows:
        if main is not None and abs(main) >= 0.005:
            side = liab if main > 0 else assets  # Tally sign: positive = Cr (liability side)
            side.append([name, abs(main)])
        elif sub is not None and side is not None:
            side.append([f"&nbsp;&nbsp;&nbsp;{name}", sub if side is liab else -sub, True])
    lt = sum(r[1] for r in liab if len(r) == 2)
    at = sum(r[1] for r in assets if len(r) == 2)
    note = ""
    if abs(lt - at) >= 0.5:
        diff = abs(lt - at)
        (liab if lt < at else assets).append([DIFF_LABEL, diff])
        note = (f"\n\nThe two sides differ by **{inr(diff)}**: the opening balances entered in Tally don't add up. "
                "Tally's own Balance Sheet shows the same difference.")
        lt = at = max(lt, at)

    def tbl(items, total):
        body = [[n, "", inr(a)] if len(r) == 2 else [n, inr(a), ""] for r in items for n, a in [r[:2]]]
        return table(["Particulars", "Details", "Amount"], body + [["**Total**", "", f"**{inr(total)}**"]],
                     ["l", "r", "r"])

    return (f"## Balance Sheet · {period(None, t)}\n\n### Liabilities\n\n{tbl(liab, lt)}"
            f"\n\n### Assets\n\n{tbl(assets, at)}{note}")


@mcp.tool(structured_output=False)
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


@mcp.tool(structured_output=False)
@_safe
def stock_summary(group: str = "", search: str = "", to_date: str = "", company: str = "") -> str:
    """Stock items with closing quantity, rate and value."""
    filters = {"MCPGroup": f'$$IsBelongsTo:"{group}"'} if group else None
    items = tc.collection("StockItem", ["Name", "Parent", "BaseUnits", "ClosingBalance", "ClosingRate",
                                       "ClosingValue"], company=company or None, to_date=to_date or None,
                          filters=filters)
    rows, total, negative = [], 0.0, []
    for s in items:
        name = s.get("NAME", "")
        if search and search.lower() not in name.lower():
            continue
        q_raw = tc.text(s, "CLOSINGBALANCE")
        q = tc.to_number(q_raw)
        if not q_raw and not tc.text(s, "CLOSINGVALUE"):
            continue  # item with no stock movement at all
        unit = tc.unit_of(q_raw) or tc.text(s, "BASEUNITS")
        # Tally sign: stock held is a debit (negative); a positive value means negative stock.
        val = -tc.to_number(tc.text(s, "CLOSINGVALUE"))
        total += val
        if q < 0 or val < -0.005:
            negative.append(name)
        rows.append([tc.text(s, "PARENT"), name + (" ⚠️" if q < 0 or val < -0.005 else ""), qty(q, unit),
                     inr(abs(tc.to_number(tc.text(s, "CLOSINGRATE")))), inr(val)])
    rows.sort(key=lambda r: (r[0].lower(), r[1].lower()))
    warn = ""
    if negative:
        warn = (f"\n\n⚠️ **{len(negative)} item{'s' if len(negative) != 1 else ''} below zero stock**: more was sold "
                "or issued than Tally has received. Usually purchases or opening stock haven't been entered. "
                "These make the total stock value lower than it really is.")
    return (f"## Stock summary · {period(None, to_date or None)}\n\n**{len(rows)} items · value {inr(total)}**\n\n"
            + table(["Group", "Item", "Quantity", "Rate", "Value"], rows, ["l", "l", "r", "r", "r"]) + warn)


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


@mcp.tool(structured_output=False)
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
