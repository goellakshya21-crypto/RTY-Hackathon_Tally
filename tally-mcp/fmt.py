"""Readable output: Indian-style rupee amounts, Dr/Cr, Markdown tables."""
from __future__ import annotations


def inr(x: float, symbol: bool = True) -> str:
    neg = x < 0
    x = abs(round(x, 2))
    whole, frac = f"{x:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    s = f"{'₹' if symbol else ''}{whole}.{frac}"
    return f"-{s}" if neg else s


def drcr(tally_amount: float) -> str:
    """Tally convention: negative = Debit, positive = Credit."""
    if abs(tally_amount) < 0.005:
        return "—"
    return f"{inr(abs(tally_amount))} {'Dr' if tally_amount < 0 else 'Cr'}"


def qty(x: float, unit: str = "") -> str:
    s = f"{x:,.3f}".rstrip("0").rstrip(".")
    return f"{s} {unit}".strip()


def table(headers: list[str], rows: list[list], align: list[str] | None = None) -> str:
    if not rows:
        return "_No entries._"
    align = align or ["l"] * len(headers)
    cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---:" if a == "r" else "---" for a in align) + " |"]
    out += ["| " + " | ".join(cell(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def period(from_date, to_date) -> str:
    if from_date and to_date:
        return f"{from_date} to {to_date}"
    if to_date:
        return f"as on {to_date}"
    return "current period in Tally"
