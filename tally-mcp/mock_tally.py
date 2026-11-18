"""Fake TallyPrime replies in Tally's real (messy) XML shape, for offline testing/demo.
Run with TALLY_MOCK=1 to make the server use it instead of a live Tally."""
import re

# Real TallyPrime puts this all-zero CMPINFO block in every reply, whether or not a company is open.
CMPINFO = "<CMPINFO>" + "".join(f"<{t}>0</{t}>" for t in ("COMPANY", "GROUP", "LEDGER", "STOCKITEM", "VOUCHER")) + "</CMPINFO>"
HEAD = ('<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DESC>' + CMPINFO
        + '</DESC><DATA><COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="4">')
TAIL = '</COLLECTION></DATA></BODY></ENVELOPE>'

COMPANIES = '''<COMPANY NAME="Goel Stones Pvt Ltd" RESERVEDNAME=""><NAME TYPE="String">Goel Stones Pvt Ltd</NAME>
<STARTINGFROM TYPE="Date">20260401</STARTINGFROM><BOOKSFROM TYPE="Date">20260401</BOOKSFROM>
<STATENAME TYPE="String">Rajasthan</STATENAME><GSTREGISTRATIONNUMBER TYPE="String">08AABCG1234F1Z5</GSTREGISTRATIONNUMBER>
<OLDAUDITENTRYIDS.LIST TYPE="Number"><OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS></OLDAUDITENTRYIDS.LIST></COMPANY>'''

def L(name, parent, op, cl):
    return (f'<LEDGER NAME="{name}" RESERVEDNAME=""><PARENT TYPE="String">{parent}</PARENT>'
            f'<OPENINGBALANCE TYPE="Amount">{op}</OPENINGBALANCE><CLOSINGBALANCE TYPE="Amount">{cl}</CLOSINGBALANCE>'
            '<LANGUAGENAME.LIST><NAME.LIST TYPE="String"><NAME>' + name + '</NAME></NAME.LIST>'
            '<LANGUAGEID TYPE="Number"> 1033</LANGUAGEID></LANGUAGENAME.LIST></LEDGER>')

LEDGERS = [
    L("Capital Account - Lakshya", "Capital Account", "518300.00", "518300.00"),
    L("HDFC Bank", "Bank Accounts", "-300000.00", "-412500.00"),
    L("Cash", "Cash-in-Hand", "-25000.00", "-18200.00"),
    L("Sharma Builders", "Sundry Debtors", "", "-118000.00"),
    L("Mehta Interiors", "Sundry Debtors", "-40000.00", "-12500.00"),
    L("Rajasthan Marble Suppliers", "Sundry Creditors", "", "94400.00"),
    L("Sales - Marble", "Sales Accounts", "", "350000.00"),
    L("Purchase - Marble", "Purchase Accounts", "", "-240000.00"),
    L("Freight Inward", "Direct Expenses", "", "-12000.00"),
    L("Shop Rent", "Indirect Expenses", "", "-30000.00"),
    L("Electricity", "Indirect Expenses", "", "-4300.00"),
    L("Output IGST", "Duties &amp; Taxes", "", "63000.00"),
    L("Input IGST", "Duties &amp; Taxes", "", "-43200.00"),
    L("Furniture", "Fixed Assets", "-135000.00", "-135000.00"),
    L("Unused Ledger", "Indirect Expenses", "", ""),
]

def G(name, bal, rev, gross, parent="&#4; Primary"):
    return (f'<GROUP NAME="{name}" RESERVEDNAME="{name}"><PARENT TYPE="String">{parent}</PARENT>'
            f'<CLOSINGBALANCE TYPE="Amount">{bal}</CLOSINGBALANCE><ISREVENUE TYPE="Logical">{rev}</ISREVENUE>'
            f'<AFFECTSGROSSPROFIT TYPE="Logical">{gross}</AFFECTSGROSSPROFIT></GROUP>')

GROUPS = [
    G("Capital Account", "518300.00", "No", "No"),
    G("Current Assets", "-604400.00", "No", "No"),
    G("Bank Accounts", "-412500.00", "No", "No", "Current Assets"),
    G("Current Liabilities", "157400.00", "No", "No"),
    G("Fixed Assets", "-135000.00", "No", "No"),
    G("Sales Accounts", "350000.00", "Yes", "Yes"),
    G("Purchase Accounts", "-240000.00", "Yes", "Yes"),
    G("Direct Expenses", "-12000.00", "Yes", "Yes"),
    G("Indirect Expenses", "-34300.00", "Yes", "No"),
]

def V(date, typ, no, party, narr, entries):
    les = "".join(
        f'<ALLLEDGERENTRIES.LIST><OLDAUDITENTRYIDS.LIST TYPE="Number"><OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>'
        f'</OLDAUDITENTRYIDS.LIST><LEDGERNAME>{n}</LEDGERNAME><GSTCLASS>&#4; Not Applicable</GSTCLASS>'
        f'<ISDEEMEDPOSITIVE>{"Yes" if a < 0 else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{a:.2f}</AMOUNT>'
        f'<BANKALLOCATIONS.LIST>       </BANKALLOCATIONS.LIST><BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>'
        f'</ALLLEDGERENTRIES.LIST>' for n, a in entries)
    return (f'<VOUCHER REMOTEID="abc-{no}" VCHTYPE="{typ}" ACTION="Create"><DATE TYPE="Date">{date}</DATE>'
            f'<VOUCHERTYPENAME>{typ}</VOUCHERTYPENAME><VOUCHERNUMBER>{no}</VOUCHERNUMBER>'
            f'<PARTYLEDGERNAME>{party}</PARTYLEDGERNAME><NARRATION>{narr}</NARRATION>'
            f'<UDF:HSNCODE.LIST DESC="`HSNCode`" ISLIST="YES" TYPE="String"><UDF:HSNCODE DESC="`HSNCode`">6802</UDF:HSNCODE></UDF:HSNCODE.LIST>'
            f'{les}</VOUCHER>')

VOUCHERS = [
    V("20261102", "Sales", "S-101", "Sharma Builders", "Italian marble 1200 sqft",
      [("Sharma Builders", -118000), ("Sales - Marble", 100000), ("Output IGST", 18000)]),
    V("20261105", "Receipt", "R-44", "Mehta Interiors", "Part payment by NEFT",
      [("HDFC Bank", -27500), ("Mehta Interiors", 27500)]),
    V("20261108", "Purchase", "P-17", "Rajasthan Marble Suppliers", "Makrana white lot",
      [("Purchase - Marble", -80000), ("Input IGST", -14400), ("Rajasthan Marble Suppliers", 94400)]),
    V("20261110", "Payment", "PY-9", "Cash", "November shop rent",
      [("Shop Rent", -10000), ("Cash", 10000)]),
]

STOCK = '''<STOCKITEM NAME="Makrana White 18mm"><PARENT TYPE="String">Marble</PARENT><BASEUNITS>sqft</BASEUNITS>
<CLOSINGBALANCE TYPE="Quantity"> 1,250.00 sqft</CLOSINGBALANCE><CLOSINGRATE TYPE="Rate">85.00/sqft</CLOSINGRATE>
<CLOSINGVALUE TYPE="Amount">-106250.00</CLOSINGVALUE></STOCKITEM>
<STOCKITEM NAME="Black Galaxy Granite"><PARENT TYPE="String">Granite</PARENT><BASEUNITS>sqft</BASEUNITS>
<CLOSINGBALANCE TYPE="Quantity"> 430.50 sqft</CLOSINGBALANCE><CLOSINGRATE TYPE="Rate">140.00/sqft</CLOSINGRATE>
<CLOSINGVALUE TYPE="Amount">-60270.00</CLOSINGVALUE></STOCKITEM>'''

BELONGS = {"Sundry Debtors": ["Sundry Debtors"], "Sundry Creditors": ["Sundry Creditors"],
           "Bank Accounts": ["Bank Accounts"], "Indirect Expenses": ["Indirect Expenses"]}


def _tb(rows):
    return "<ENVELOPE>" + "".join(
        f"<DSPACCNAME><DSPDISPNAME>{n}</DSPDISPNAME></DSPACCNAME><DSPACCINFO><DSPCLDRAMT><DSPCLDRAMTA>"
        f"{f'{b:.2f}' if b < 0 else ''}</DSPCLDRAMTA></DSPCLDRAMT><DSPCLCRAMT><DSPCLCRAMTA>"
        f"{f'{b:.2f}' if b > 0 else ''}</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO>" for n, b in rows) + "</ENVELOPE>"


def _stmt(name_tag, amt_tag, rows):
    sub = amt_tag[:-3] + "SUBAMT"
    wrap = (lambda n: f"<BSNAME><DSPACCNAME><DSPDISPNAME>{n}</DSPDISPNAME></DSPACCNAME></BSNAME>") \
        if name_tag == "BSNAME" else (lambda n: f"<DSPACCNAME><DSPDISPNAME>{n}</DSPDISPNAME></DSPACCNAME>")
    f = lambda v: "" if v is None else f"{v:.2f}"
    return "<ENVELOPE>" + "".join(
        f"{wrap(n)}<{amt_tag}><{sub}>{f(s)}</{sub}><BSMAINAMT>{f(m)}</BSMAINAMT></{amt_tag}>" for n, s, m in rows
    ) + "</ENVELOPE>"


# Built-in reports, consistent with the ledgers above (closing stock = stock summary value 1,66,520).
TB_TOP = [("Capital Account", 518300), ("Current Liabilities", 157400), ("Fixed Assets", -135000),
          ("Current Assets", -604400), ("Sales Accounts", 350000), ("Purchase Accounts", -240000),
          ("Direct Expenses", -12000), ("Indirect Expenses", -34300)]
TB_DETAIL = [("Capital Account", 518300), ("Capital Account - Lakshya", 518300),
             ("Current Liabilities", 157400), ("Duties &amp; Taxes", 63000), ("Sundry Creditors", 94400),
             ("Fixed Assets", -135000), ("Furniture", -135000),
             ("Current Assets", -604400), ("Bank Accounts", -412500), ("Cash-in-Hand", -18200),
             ("Sundry Debtors", -130500), ("Input IGST", -43200),
             ("Sales Accounts", 350000), ("Sales - Marble", 350000),
             ("Purchase Accounts", -240000), ("Purchase - Marble", -240000),
             ("Direct Expenses", -12000), ("Freight Inward", -12000),
             ("Indirect Expenses", -34300), ("Shop Rent", -30000), ("Electricity", -4300)]
PL = [("Sales Accounts", None, 350000), ("Cost of Sales :", None, -85480), ("Opening Stock", None, None),
      ("Add: Purchase Accounts", -240000, None), ("Less: Closing Stock", -166520, None),
      ("Direct Expenses", -12000, None), ("Indirect Expenses", None, -34300)]
BS = [("Capital Account", None, 518300), ("Loans (Liability)", None, None), ("Current Liabilities", None, 157400),
      ("Profit &amp; Loss A/c", None, 230220), ("Fixed Assets", None, -135000), ("Current Assets", None, -770920)]


def _report(xml):
    rid = re.search(r"<TYPE>Data</TYPE><ID>([^<]+)</ID>", xml).group(1)
    if rid == "Trial Balance":
        return _tb(TB_DETAIL if "<EXPLODEFLAG>Yes" in xml else TB_TOP)
    if rid == "Profit and Loss":
        return _stmt("DSPACCNAME", "PLAMT", PL)
    if rid == "Balance Sheet":
        return _stmt("BSNAME", "BSAMT", BS)
    return "<ENVELOPE></ENVELOPE>"


def transport(xml: str) -> str:
    # Real TallyPrime freezes (100% CPU, window Not Responding) when it gets SVFROMDATE and
    # SVTODATE as plain YYYYMMDD. Fail loudly here so the offline test catches that regression.
    if re.search(r"<SVFROMDATE>\s*\d{8}\s*</SVFROMDATE>", xml) and re.search(r"<SVTODATE>\s*\d{8}\s*</SVTODATE>", xml):
        raise TimeoutError("fake Tally: plain YYYYMMDD from/to dates would freeze real TallyPrime")
    if "<TYPE>Data</TYPE>" in xml:
        return _report(xml)
    obj = re.search(r"<COLLECTION[^>]*><TYPE>(\w+)</TYPE>", xml)
    obj = obj.group(1) if obj else ""
    if obj == "Company":
        body = COMPANIES
    elif obj == "Ledger":
        g = re.search(r'IsBelongsTo:&quot;([^&]+)&quot;|IsBelongsTo:"([^"]+)"', xml)
        grp = (g.group(1) or g.group(2)) if g else None
        body = "".join(l for l in LEDGERS if not grp or any(f">{p}<" in l for p in BELONGS.get(grp, [grp])))
    elif obj == "Group":
        body = "".join(GROUPS)
    elif obj == "Voucher":
        t = re.search(r'VoucherTypeName = (?:&quot;|")(\w+)', xml)
        body = "".join(v for v in VOUCHERS if not t or f"<VOUCHERTYPENAME>{t.group(1)}<" in v)
    elif obj == "StockItem":
        body = STOCK
    else:
        return HEAD + "".join(VOUCHERS[:1]) + TAIL
    return HEAD + body + TAIL
