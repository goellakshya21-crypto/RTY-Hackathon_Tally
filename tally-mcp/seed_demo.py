"""Loads sample ledgers and vouchers into a TallyPrime company (for demos).
Usage: python seed_demo.py "Demo Stones"
Dates are the 1st/2nd of the month so it also works in TallyPrime Educational mode."""
import re
import sys
from xml.sax.saxutils import escape

import tally_client as tc

COMPANY = sys.argv[1] if len(sys.argv) > 1 else "Demo Stones"

# name, group, opening (Tally sign: negative = Dr)
LEDGERS = [
    ("Capital Account - Owner", "Capital Account", 475000),
    ("HDFC Bank", "Bank Accounts", -300000),
    ("Furniture", "Fixed Assets", -135000),
    ("Sharma Builders", "Sundry Debtors", 0),
    ("Mehta Interiors", "Sundry Debtors", -40000),
    ("Rajasthan Marble Suppliers", "Sundry Creditors", 0),
    ("Sales - Marble", "Sales Accounts", 0),
    ("Purchase - Marble", "Purchase Accounts", 0),
    ("Freight Inward", "Direct Expenses", 0),
    ("Shop Rent", "Indirect Expenses", 0),
    ("Electricity", "Indirect Expenses", 0),
    ("Output IGST", "Duties & Taxes", 0),
    ("Input IGST", "Duties & Taxes", 0),
]

# date, type, number, narration, [(ledger, amount)]  negative = Dr
VOUCHERS = [
    ("20261101", "Sales", "S-101", "Italian marble 1200 sqft",
     [("Sharma Builders", -118000), ("Sales - Marble", 100000), ("Output IGST", 18000)]),
    ("20261101", "Sales", "S-102", "Makrana white for lobby",
     [("Mehta Interiors", -59000), ("Sales - Marble", 50000), ("Output IGST", 9000)]),
    ("20261101", "Purchase", "P-17", "Makrana white lot",
     [("Purchase - Marble", -80000), ("Input IGST", -14400), ("Rajasthan Marble Suppliers", 94400)]),
    ("20261102", "Receipt", "R-44", "Part payment by NEFT",
     [("HDFC Bank", -27500), ("Mehta Interiors", 27500)]),
    ("20261102", "Receipt", "R-45", "Advance against S-101",
     [("HDFC Bank", -60000), ("Sharma Builders", 60000)]),
    ("20261102", "Payment", "PY-9", "November shop rent",
     [("Shop Rent", -10000), ("Cash", 10000)]),
    ("20261102", "Payment", "PY-10", "Electricity bill Oct",
     [("Electricity", -4300), ("HDFC Bank", 4300)]),
    ("20261102", "Payment", "PY-11", "Truck freight Kishangarh",
     [("Freight Inward", -12000), ("HDFC Bank", 12000)]),
    ("20261102", "Payment", "PY-12", "Part payment to supplier",
     [("Rajasthan Marble Suppliers", -50000), ("HDFC Bank", 50000)]),
    ("20261102", "Contra", "C-1", "Cash withdrawn",
     [("Cash", -25000), ("HDFC Bank", 25000)]),
]


def envelope(report, body):
    return (f"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>"
            f"<REQUESTDESC><REPORTNAME>{report}</REPORTNAME><STATICVARIABLES>"
            f"<SVCURRENTCOMPANY>{escape(COMPANY)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>"
            f'<REQUESTDATA><TALLYMESSAGE xmlns:UDF="TallyUDF">{body}</TALLYMESSAGE></REQUESTDATA>'
            f"</IMPORTDATA></BODY></ENVELOPE>")


def send(report, body):
    reply = tc.transport(envelope(report, body))
    counts = {k: re.search(fr"<{k}>(\d+)</{k}>", reply) for k in ("CREATED", "ALTERED", "ERRORS")}
    counts = {k: int(m.group(1)) if m else 0 for k, m in counts.items()}
    errs = re.findall(r"<LINEERROR>(.*?)</LINEERROR>", reply)
    print(report, counts, *errs, sep="\n  ")
    return counts


ledgers = "".join(
    f'<LEDGER NAME="{escape(n)}" ACTION="Create"><NAME>{escape(n)}</NAME><PARENT>{escape(g)}</PARENT>'
    f"<OPENINGBALANCE>{o:.2f}</OPENINGBALANCE><ISBILLWISEON>No</ISBILLWISEON></LEDGER>"
    for n, g, o in LEDGERS)

vouchers = "".join(
    f'<VOUCHER VCHTYPE="{t}" ACTION="Create" OBJVIEW="Accounting Voucher View"><DATE>{d}</DATE>'
    f"<VOUCHERTYPENAME>{t}</VOUCHERTYPENAME><VOUCHERNUMBER>{no}</VOUCHERNUMBER>"
    f"<PARTYLEDGERNAME>{escape(es[0][0])}</PARTYLEDGERNAME><NARRATION>{escape(narr)}</NARRATION>"
    f"<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>"
    + "".join(f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(l)}</LEDGERNAME>"
              f"<ISDEEMEDPOSITIVE>{'Yes' if a < 0 else 'No'}</ISDEEMEDPOSITIVE>"
              f"<AMOUNT>{a:.2f}</AMOUNT></ALLLEDGERENTRIES.LIST>" for l, a in es)
    + "</VOUCHER>" for d, t, no, narr, es in VOUCHERS)

if __name__ == "__main__":
    send("All Masters", ledgers)
    send("Vouchers", vouchers)
