"""Finds which kind of request makes TallyPrime freeze.

Sends small requests one at a time, from safest to riskiest, and stops at the first one
Tally doesn't answer within a few seconds. Run it right after (re)starting TallyPrime:

    python diagnose.py                    # all steps except the known freezer
    python diagnose.py 5                  # start from step 5
    python diagnose.py --include-freeze   # also send step 4, which FREEZES TallyPrime

Finding (18 Nov 2026, TallyPrime integration sandbox): step 4 - SVFROMDATE + SVTODATE sent as
plain YYYYMMDD - puts Tally in an endless loop (100% CPU, window Not Responding, restart needed).
The same dates as <SVFROMDATE TYPE="Date">1-Apr-2025</SVFROMDATE> answer in 0.02s.
"""
import socket
import sys
import time
import urllib.request

URL = "http://localhost:9000"
WAIT = 15  # seconds; a tiny company answers these in well under a second


def collection(obj, fetch, sv=""):
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
            "<TYPE>Collection</TYPE><ID>DiagColl</ID></HEADER><BODY><DESC><STATICVARIABLES>"
            f"<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{sv}</STATICVARIABLES>"
            f'<TDL><TDLMESSAGE><COLLECTION NAME="DiagColl" ISMODIFY="No"><TYPE>{obj}</TYPE>'
            f"<FETCH>{fetch}</FETCH></COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>")


def report(name, sv=""):
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
            f"<TYPE>Data</TYPE><ID>{name}</ID></HEADER><BODY><DESC><STATICVARIABLES>"
            f"<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>{sv}</STATICVARIABLES></DESC></BODY></ENVELOPE>")


def send(xml):
    req = urllib.request.Request(URL, data=xml.encode(), headers={"Content-Type": "text/xml"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=WAIT) as r:
        body = r.read().decode("utf-8", "replace")
    return time.time() - t, body


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    include_freeze = "--include-freeze" in sys.argv
    start = int(args[0]) if args else 1
    try:
        _, body = send(collection("Company", "Name,StartingFrom"))
    except OSError as e:
        sys.exit(f"Tally isn't answering on {URL} at all ({e}). Restart TallyPrime and run this again.")
    import re
    names = re.findall(r'<COMPANY NAME="([^"]+)"', body)
    starts = re.findall(r"<STARTINGFROM[^>]*>(\d{8})<", body)
    if not names:
        sys.exit("Tally answered but no company is open. Open a company and run this again.")
    co, fy = names[0], (starts[0] if starts else "20250401")
    y = int(fy[:4])
    ymd_from, ymd_to = f"{y}0401", f"{y + 1}0331"
    dmy_from, dmy_to = f"1-Apr-{y}", f"31-Mar-{y + 1}"
    print(f"Companies open: {names}. Testing with: {co} (FY from {fy})\n")

    C = f"<SVCURRENTCOMPANY>{co}</SVCURRENTCOMPANY>"
    steps = [
        ("Ledger list, no company, no dates", collection("Ledger", "Name,Parent,ClosingBalance")),
        ("Ledger list, company name only", collection("Ledger", "Name,Parent,ClosingBalance", C)),
        ("Ledger list, to-date only (YYYYMMDD)", collection("Ledger", "Name,ClosingBalance",
                                                           f"<SVTODATE>{ymd_to}</SVTODATE>")),
        ("Ledger list, from+to dates (YYYYMMDD)", collection("Ledger", "Name,ClosingBalance",
                                                            f"<SVFROMDATE>{ymd_from}</SVFROMDATE><SVTODATE>{ymd_to}</SVTODATE>")),
        ("Ledger list, from+to dates (1-Apr-YYYY, TYPE=Date)", collection(
            "Ledger", "Name,ClosingBalance",
            f'<SVFROMDATE TYPE="Date">{dmy_from}</SVFROMDATE><SVTODATE TYPE="Date">{dmy_to}</SVTODATE>')),
        ("Ledger list, company + dates", collection(
            "Ledger", "Name,ClosingBalance",
            C + f'<SVFROMDATE TYPE="Date">{dmy_from}</SVFROMDATE><SVTODATE TYPE="Date">{dmy_to}</SVTODATE>')),
        ("Group list, no company, no dates", collection("Group", "Name,Parent,ClosingBalance,IsRevenue,AffectsGrossProfit")),
        ("Voucher list, no company, no dates", collection("Voucher", "Date,VoucherTypeName,VoucherNumber,Amount")),
        ("Built-in Trial Balance report, no dates", report("Trial Balance")),
    ]
    for i, (label, xml) in enumerate(steps, 1):
        if i < start:
            continue
        if i == 4 and not include_freeze:
            print(f"Step {i}: {label} ... skipped (known to freeze Tally; --include-freeze to send it)")
            continue
        print(f"Step {i}: {label} ... ", end="", flush=True)
        try:
            secs, body = send(xml)
        except (socket.timeout, TimeoutError, OSError) as e:
            print(f"NO ANSWER after {WAIT}s ({type(e).__name__})")
            print(f"\n>>> Step {i} froze Tally: {label}")
            print(">>> Restart TallyPrime. To continue past it later: python diagnose.py", i + 1)
            return 1
        n = body.count("<LEDGER ") + body.count("<GROUP ") + body.count("<VOUCHER ")
        err = re.search(r"<LINEERROR>(.*?)</LINEERROR>", body)
        print(f"OK in {secs:.2f}s, {n} objects" + (f", Tally error: {err.group(1)}" if err else ""))
    print("\nEvery step answered. None of these requests froze Tally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
