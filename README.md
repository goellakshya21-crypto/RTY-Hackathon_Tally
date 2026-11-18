# 🚀 Buildathon: Make Wednesdays Great Again

**Masters' Union · For AI Developers · Winner gets Rs. 25,000**

> **Every team must build in a fork of this repository.** Projects not built in a fork of this repo won't be judged.

| | |
|---|---|
| **Date** | Wednesday, 18 November 2026 |
| **Hacking** | **3:00 PM – 7:00 PM IST** (code freeze at 7:00 PM sharp) |
| **Venue** | CDS Audi, 8th floor |
| **Prize** | Rs. 25,000 to the winning team |
| **Register your fork** | 👉 **[https://forms.gle/ZJUYKwTYjsMsVB2b9](https://forms.gle/ZJUYKwTYjsMsVB2b9)** (**deadline 3:30 PM IST**) |
| **Final submission** | Your fork as it stands at **7:00 PM IST**. There's nothing else to submit. |

> 🤖 **Using an AI coding agent?** Point it at [`AGENTS.md`](AGENTS.md). It has the full event brief, tracks, judging and rules in a form agents can read directly. Claude Code loads it automatically through `CLAUDE.md`, and Codex reads `AGENTS.md` natively.

---

## 🎯 Pick one build track

| # | Track | Brief |
|---|---|---|
| **01** | **Build for the Physical World** | Make a real-world task easier, faster or more reliable. Show it in a realistic scenario. |
| **02** | **Build for AI Agents** | Find something an agent struggles with. Build the tool that fixes it, then demo the agent using it. |
| **03** | **Build in Your Area of Expertise** | Pick a field you know firsthand. Ship a working product that improves how people handle it today. |

## ⚖️ How you'll be judged (each criterion is ⅓ of your score)

| Criterion | The question judges ask |
|---|---|
| **Working product** | Does it do what you say it does? Show the core workflow in your demo. |
| **Problem insight** | Who faces this problem, and why does it happen? |
| **Depth of execution** | How well did you solve the hardest part of the build? |

---

## Why fork this repo?

Everyone starts from the same commit (the **genesis commit**) at the same time. Organizers can then check that:
- all code was written **during** the Buildathon and not brought in from an earlier project,
- teams commit steadily instead of pasting in one huge AI-generated dump at the end,
- every repo stays public and visible while you build.

The organizers track every fork automatically: commits, timing and activity. Read [RULES.md](RULES.md) before you write any code.

---

## ✅ Setup (about 5 minutes, do it at 3:00 PM)

**In short:** fork → register your fork in the form **by 3:30 PM** → build → push before 7:00 PM.

### 1. Fork this repo
Click **Fork** (top right). On the fork screen:
- **Owner:** one team member's personal account. Only **one fork per team**.
- **Repository name:** `buildathon-<team-name>`, for example `buildathon-byte-bandits`
- Click **Create fork**.

> ⚠️ Don't download a ZIP or copy the files into a new repo. **It has to be a real GitHub fork**, or the tracker can't see you.

### 2. Keep it public
Forks of a public repo are public. **Don't make it private, archive it, or delete it** until judging is over.

### 3. Add your teammates
In your fork: **Settings → Collaborators → Add people**. Add each teammate's GitHub account so their commits count toward the team.

### 4. Enable Actions
Open the **Actions** tab of your fork and click **"I understand my workflows, go ahead and enable them"**. This runs the automatic check on every push.

### 5. Make your registration commit (your first commit)
Fill in [`team.json`](team.json). `track` must be one of `physical-world`, `ai-agents` or `area-of-expertise`. Then:

```bash
git clone https://github.com/<your-username>/buildathon-<team-name>.git
cd buildathon-<team-name>
# edit team.json
git add team.json
git commit -m "register: <team name>"
git push
```

The **Hackathon check** in the Actions tab should go green ✅. If it's red, open the run to see what's wrong in `team.json`.

### 6. Register your fork (deadline: 3:30 PM IST)
👉 **[https://forms.gle/ZJUYKwTYjsMsVB2b9](https://forms.gle/ZJUYKwTYjsMsVB2b9)**

It's a 4-question Google Form: team name, fork link, track, team members. It connects your repo to the organizers' live tracker.

- Fill it in **once per team**, right after forking, and **no later than 3:30 PM IST**. **Teams that don't register can't be tracked.**
- Paste your **fork's** URL (`https://github.com/<you>/buildathon-<team-name>`), not this starter repo's.
- Need to change something? Use the **"Edit your response"** link on the confirmation page. Don't fill it in twice.
- **Final submission is automatic.** Whatever is pushed to your fork at 7:00 PM IST is what gets judged.

---

## 🛠 While you build (3:00 – 7:00 PM)

- Put your code anywhere in the repo (`app/`, `src/`, `frontend/`, `backend/`…). There's no required layout.
- **Commit early, commit often**, at least every 30 minutes of real work, with messages that say what changed.
- **Push regularly.** Commits you never push don't exist to the tracker.
- AI coding tools (Claude Code, Codex, Cursor, Copilot…) are **allowed and encouraged**. Keep `AGENTS.md` and `CLAUDE.md` in the repo; they keep your agent within the rules.
- Before 7:00 PM, replace the "Your project" section below with your project's README.

## 🧊 Code freeze: 7:00 PM IST

At 7:00 PM the tracker takes a snapshot of every fork. **Commits pushed after code freeze are ignored.** Judges look at your last commit before 7:00 PM.

## ❌ Things that get you flagged

- Rewriting history (`git push --force`, rebasing away the genesis commit, squashing everything into one commit)
- Commits dated before 3:00 PM
- One or two giant commits containing most of the project
- A repo that isn't a fork of this one, or that's private or deleted

See [RULES.md](RULES.md) for the full list.

---

## Your project

- **Team:** Tally MCP (Lakshya Goel, @goellakshya21-crypto)
- **Track:** Build for AI Agents (`ai-agents`)

**Problem.** Millions of Indian small businesses keep their books in TallyPrime. Tally has an API (XML over HTTP on `localhost:9000`), but what it returns is close to unreadable for people and for AI agents: deeply nested tags, dozens of empty and audit fields, control characters like `&#4;` that break normal XML parsers, undeclared `UDF:` tags, dates like `20261102`, and signed amounts where `-118000.00` silently means "₹1,18,000 Debit". When an agent is pointed at this raw output it misreads debits as credits, chokes on the XML, or runs out of context.

**What we built.** [`tally-mcp/`](tally-mcp/) is an MCP server that sits between Claude and TallyPrime. The agent calls simple tools and gets back clean Markdown tables with Indian-format ₹ amounts and Dr/Cr labels:
`list_companies`, `list_ledgers`, `ledger_statement` (with running balance), `day_book`, `trial_balance`, `profit_and_loss`, `balance_sheet`, `outstandings` (receivables/payables), `stock_summary`, and `raw_request` (cleans up the reply to any Tally XML request).

**The hardest part.** Talking to a live TallyPrime without breaking it, and making its numbers *mean* the right thing:
- **A request format that freezes Tally.** Every trial balance request froze TallyPrime solid (window "Not Responding", 100% CPU, restart needed). We wrote [`diagnose.py`](tally-mcp/diagnose.py) to send tiny requests one at a time against the live integration sandbox, and pinned it to one detail: a report period sent as plain `YYYYMMDD` (`<SVFROMDATE>20250401</SVFROMDATE>` + `<SVTODATE>`) sends Tally into an endless loop, while the same period as a typed `1-Apr-2025` date answers in 0.02 s. The server now always sends the safe form, rewrites the unsafe form if an agent writes it in `raw_request`, sends one request at a time, and the fake Tally fails the tests if the unsafe form ever comes back.
- **Stock makes group totals wrong.** Rebuilding the trial balance and P&L from group balances gave wrong figures for any company holding stock (₹41 L off on Current Assets in the sandbox company, and net profit ₹54.6 L instead of Tally's ₹13.5 L). Tally treats opening stock, closing stock and *negative* stock specially, so these three statements now come from Tally's own reports and match its screens to the paisa. The P&L and stock summary flag negative stock, a common data-entry problem.
- **Parsing Tally's XML.** Stripping illegal control-character references (`&#4;`), rewriting undeclared `UDF:` prefixes, and ignoring the all-zero `CMPINFO` block Tally adds to every reply.
- **Signs and errors.** Getting the sign convention right everywhere (negative = Dr), showing Tally's "Difference in opening balances" line instead of hiding it, and clear messages when Tally is closed, frozen, or has no company open.

**How to run it.** See [`tally-mcp/README.md`](tally-mcp/README.md). In short:
```bash
cd tally-mcp
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python test_offline.py          # every tool against a fake Tally
claude mcp add tally -- .venv\Scripts\python.exe server.py
```
`seed_demo.py "Demo Stones"` loads sample ledgers and vouchers into a real (empty) Tally company. `diagnose.py` finds which kind of request freezes a TallyPrime install.

**Demo.** Ask Claude *"Show me the trial balance"* or *"What does Sharma Builders owe us?"*. Without the MCP the agent gets raw XML; with it, it gets a balanced trial balance and a ledger statement it can explain. [`demo.py`](tally-mcp/demo.py) runs the whole comparison live (raw Tally XML, then a real Claude agent using the tools) and can screen-record it.

**What's next.** This version only *reads* Tally. The same API also accepts new entries (our [`seed_demo.py`](tally-mcp/seed_demo.py) already created vouchers in a live Tally), and Claude can read photos and PDFs. Put together, the agent can do the bookkeeping itself, with a person approving every entry:
- **Snap a bill, get the entry:** photo of a purchase bill → Claude reads supplier, GSTIN, items and tax → the MCP matches ledgers, checks the GST split and catches duplicates → you approve → the voucher is in Tally.
- **Bank statement → reconciled books**, **GSTR-2B vs purchase register** (input-credit check), **collections assistant** with reminders, **weekly books health check**, **voice entries in Hindi/Hinglish**, and **one agent across all of a CA's client companies**.

Details, how each would work, and the safety rules for writing to Tally: [`tally-mcp/ROADMAP.md`](tally-mcp/ROADMAP.md).
