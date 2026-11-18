# Roadmap: from reading Tally to working in it

Today Tally MCP is **read-only**: an agent can read ledgers, statements and reports, get figures that match Tally's own screens, and spot problems in the books. The same API that we read from also accepts new entries, so the next step is letting the agent **do the bookkeeping work**, always with a person approving what gets written.

## What makes this possible

| Piece | Status |
|---|---|
| Reading Tally reliably (clean output, no freezes, figures match Tally's reports) | ✅ Built |
| Writing to Tally: TallyPrime's XML **Import** accepts ledgers and vouchers | ✅ Proven: [`seed_demo.py`](seed_demo.py) created 13 ledgers and 10 vouchers in a live Tally with 0 errors |
| Reading documents: Claude reads photos, scans and PDFs of invoices, bills and bank statements | ✅ Available in Claude today |
| Safe write tools: preview, validation, duplicate checks, approval, audit log | 🔜 Next |

**Design rule for every write feature:** Claude reads the document and fills in structured fields. The MCP server never sees the image; it only checks those fields against Tally and turns them into a voucher. Nothing is written to Tally until a person has seen a preview and said yes.

---

## 1. Snap a bill, get the entry ⭐ (next to build)

Take a photo of a purchase bill on your phone and send it to Claude. A few seconds later the purchase voucher is in Tally.

**How it works**
1. **Claude reads the photo**: supplier, GSTIN, invoice number and date, line items, HSN codes, taxable value, CGST/SGST/IGST, total.
2. **`draft_voucher`** (new MCP tool) checks those fields against Tally:
   - finds the supplier ledger by name *or* GSTIN, with fuzzy matching ("Rajasthan Marble Supp." → "Rajasthan Marble Suppliers")
   - validates the GSTIN's check digit, and that IGST vs CGST+SGST matches the supplier's state
   - checks that the totals add up (taxable + tax = invoice total)
   - **catches duplicates**: same supplier and invoice number already in Tally
   - returns a preview in plain words: *"Purchase from Rajasthan Marble Suppliers, ₹80,000 + IGST ₹14,400 = ₹94,400, dated 8 Nov. New ledger needed: none."*
3. **You approve** ("yes, post it"), and **`post_voucher`** imports it and returns the voucher number Tally gave it.

**Why it matters:** typing bills into Tally is the most time-consuming job in a small business's books, and where most errors (wrong GST split, duplicate bills, wrong party) come from.

## 2. Bank statement → reconciled books

Upload the month's bank statement (PDF or CSV). The agent matches every line to a voucher in Tally by amount, date and narration.
- Matched lines get their bank date set in Tally (bank reconciliation done).
- Unmatched lines are proposed as new receipts or payments ("₹27,500 NEFT from Mehta Interiors → receipt against their account?").
- Leftover items get flagged: cheques issued but not cleared, charges and interest not yet booked.

## 3. GST input-credit check (GSTR-2B vs purchase register)

Load the GSTR-2B JSON downloaded from the GST portal. The agent compares it with the purchases in Tally:
- bills in Tally that the supplier **hasn't filed** (credit at risk: follow up before claiming it)
- bills on the portal **missing from Tally** (credit you're leaving unclaimed)
- mismatched amounts, GSTINs or invoice numbers

This is a monthly job that accountants do by hand in spreadsheets today.

## 4. Collections assistant

- Bill-wise ageing of receivables (0–30, 31–60, 61–90, 90+ days) from Tally's bill records.
- Drafts a polite reminder for each overdue customer with their ledger statement attached, ready to send on WhatsApp or email **after you approve it**.
- Flags concentration risk, like the sandbox company where one customer holds ₹54 L of ₹61 L receivables.

## 5. Books health check, every week

The demo already shows Claude finding real problems by reading the reports. Next step: a dedicated `health_check` tool and a weekly scheduled run that reports:
- opening-balance differences, negative stock, suspense balances
- duplicate bills, round-figure cash entries, cash payments over ₹10,000 (Income Tax s.40A(3)) and cash receipts of ₹2 lakh or more (s.269ST)
- ledgers in the wrong group, unused or duplicate ledgers (e.g. four separate sales ledgers)
- GST master gaps (no GSTIN on the company or on registered parties)

## 6. Speak your entries, in your language

*"Sharma ko ₹5,000 cash diye, rent ke liye"* → a draft payment voucher: Rent Dr ₹5,000 / Cash Cr ₹5,000, shown for approval. Voice notes in Hindi, Hinglish or other Indian languages, for owners who will never open Tally's voucher screen.

## 7. For CAs: one agent across all client companies

A CA firm keeps dozens of client companies in Tally. One question covers them all: *"Which clients have GST input-credit mismatches this month?"*, *"Whose books have opening differences?"*, *"Who hasn't entered November's bank statement?"*. This needs a company switcher and multi-company summaries.

## 8. Plain-language finance for the owner

- *"Can I afford a ₹10 L machine next month?"*: cash and bank position, receivables due, payables due.
- Month-on-month and year-on-year comparisons with reasons ("profit fell because freight doubled").
- A one-page monthly summary in simple language, on WhatsApp.

---

## Safety for anything that writes to Tally

Writing to someone's books needs stronger guarantees than reading them:

- **Read-only by default.** Write tools are switched on separately (`TALLY_ALLOW_WRITES=1`).
- **Preview, then approve.** Every write shows exactly what will be created, and needs a yes from a person. An instruction found inside a document (e.g. text printed on an invoice) never counts as approval.
- **Checks before writing:** ledgers exist, totals add up, GST split is right, no duplicate invoice number, date inside the books' period.
- **Audit log:** every voucher created through the MCP is recorded with the source document, the extracted fields and who approved it.
- **Easy undo:** the log keeps Tally's voucher ID so an entry can be found and reversed.
- **Never freeze Tally:** all writes go through the same safe request layer (typed dates, one request at a time) that fixed the freeze.
