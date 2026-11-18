"""Live demo of Tally MCP, made to be screen-recorded.

Everything on screen is live: the raw XML comes from the running TallyPrime, and the answers come
from a real Claude Code agent calling this MCP server. Nothing is pre-recorded.

    python demo.py                              # run in this terminal
    python demo.py --record demo.mp4            # own big-font window, recorded with ffmpeg
    python demo.py --company "Demo Stones" --fy 2026
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW_TITLE = "Tally MCP demo"
TALLY_URL = os.environ.get("TALLY_URL", "http://localhost:9000")
REPO_URL = "github.com/goellakshya21-crypto/RTY-Hackathon_Tally"
AGENT_RULES = ("You are answering a business owner's question about their TallyPrime books using the tally "
               "tools. Be brief: at most one table and three short bullet points. Use Indian ₹ formatting.")

console = Console(highlight=False)


# ---------- window + recording ----------

def big_window(font_px: int) -> None:
    """Give this console a title, a large font and a maximised window (Windows conhost only)."""
    if os.name != "nt":
        return
    k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
    k32.SetConsoleTitleW(WINDOW_TITLE)

    class COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class FONT(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("nFont", ctypes.c_ulong), ("dwFontSize", COORD),
                    ("FontFamily", ctypes.c_uint), ("FontWeight", ctypes.c_uint), ("FaceName", ctypes.c_wchar * 32)]

    f = FONT()
    f.cbSize = ctypes.sizeof(FONT)
    f.dwFontSize = COORD(0, font_px)
    f.FontFamily, f.FontWeight, f.FaceName = 54, 400, "Consolas"
    k32.SetCurrentConsoleFontEx(k32.GetStdHandle(-11), False, ctypes.byref(f))
    hwnd = k32.GetConsoleWindow()
    u32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE
    u32.SetForegroundWindow(hwnd)
    time.sleep(1.5)


def start_recording(path: str) -> subprocess.Popen:
    ffmpeg = shutil.which("ffmpeg") or sys.exit("ffmpeg not found on PATH")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0",
           "-i", f"title={WINDOW_TITLE}", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", path]
    rec = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                           stderr=open(path + ".log", "w"))
    time.sleep(1.5)
    return rec


def stop_recording(rec: subprocess.Popen) -> None:
    try:
        rec.communicate(b"q", timeout=30)
    except subprocess.TimeoutExpired:
        rec.kill()


# ---------- small helpers ----------

def pause(s: float) -> None:
    time.sleep(s)


def type_out(text: str, style: str = "", delay: float = 0.025) -> None:
    for ch in text:
        console.print(ch, style=style, end="")
        time.sleep(delay)
    console.print()


def scene(title: str) -> None:
    console.clear()
    console.print(Rule(Text(title, style="bold cyan"), style="cyan"))
    console.print()


def tally_post(xml: str) -> str:
    req = urllib.request.Request(TALLY_URL, data=xml.encode("utf-8"),
                                 headers={"Content-Type": "text/xml; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ---------- scenes ----------

def centre_vertically(panel_rows: int) -> None:
    console.print("\n" * max(1, (console.height - panel_rows) // 2 - 1), end="")


def title_card() -> None:
    console.clear()
    centre_vertically(9)
    console.print(Panel(Group(
        Text("Tally MCP", style="bold white", justify="center"),
        Text(""),
        Text("Lets AI agents read TallyPrime books, correctly", style="cyan", justify="center"),
        Text(""),
        Text("Buildathon · Build for AI Agents", style="dim", justify="center"),
    ), border_style="cyan", padding=(1, 4)))
    pause(4)


def the_problem(company: str, fy: int) -> None:
    scene("The problem")
    console.print("Millions of Indian businesses keep their books in [bold]TallyPrime[/].", )
    console.print("Tally has an API, but it answers in raw XML.\n")
    pause(2.5)
    console.print(f"[bold]Without the MCP[/]: ask Tally for {company}'s trial balance, FY {fy}-{str(fy + 1)[2:]}\n")
    pause(1)
    req = ("<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST><TYPE>Data</TYPE>"
           "<ID>Trial Balance</ID></HEADER><BODY><DESC><STATICVARIABLES>"
           "<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
           f"<SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY>"
           f'<SVFROMDATE TYPE="Date">1-Apr-{fy}</SVFROMDATE><SVTODATE TYPE="Date">31-Mar-{fy + 1}</SVTODATE>'
           "</STATICVARIABLES></DESC></BODY></ENVELOPE>")
    type_out(f"POST {TALLY_URL}  (live TallyPrime)", "yellow", 0.02)
    reply = tally_post(req)
    pause(0.8)
    lines = reply.splitlines()
    for line in lines:
        console.print(Text(line, style="green"))
        time.sleep(0.045)
    pause(1.5)
    console.print()
    console.print(Panel(
        "[bold]What an agent gets back[/]\n"
        f"• {len(reply):,} characters of tags for {reply.count('<DSPDISPNAME>')} lines of numbers\n"
        "• [yellow]-8121925.00[/] means ₹81,21,925 [bold]Debit[/]. Nothing says so\n"
        "• Names and amounts sit in separate tags, linked only by order\n"
        "• No net figures, no totals, no warning that the books don't balance\n"
        "• And the obvious date format ([yellow]20250401[/]) [bold red]freezes Tally completely[/]",
        border_style="red", title="Without the MCP", title_align="left"))
    pause(7)


def ask_claude(question: str, model: str, cfg_path: str, workdir: str) -> None:
    console.print(Panel(Text(question, style="bold white"), title="You ask Claude", title_align="left",
                        border_style="magenta"))
    claude = shutil.which("claude") or sys.exit("Claude Code CLI ('claude') not found on PATH")
    cmd = [claude, "-p", question, "--output-format", "stream-json", "--verbose",
           "--strict-mcp-config", "--mcp-config", cfg_path, "--allowedTools", "mcp__tally",
           "--append-system-prompt", AGENT_RULES]
    if model:
        cmd += ["--model", model]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8", errors="replace", cwd=workdir)
    pending_text, final = [], None
    with console.status("[magenta]Claude is working…[/]", spinner="dots"):
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = ev.get("type")
            if kind == "assistant":
                for c in ev["message"].get("content", []):
                    if c.get("type") == "text" and c.get("text", "").strip():
                        pending_text.append(c["text"].strip())
                    elif c.get("type") == "tool_use":
                        for t in pending_text:
                            console.print(Text("Claude: " + t, style="italic dim"))
                        pending_text = []
                        name = c["name"].replace("mcp__tally__", "")
                        args = ", ".join(f"{k}={v!r}" for k, v in c.get("input", {}).items())
                        console.print(Text.assemble(("🔧 Claude calls ", "bold yellow"),
                                                    (f"tally.{name}", "bold white on dark_orange3"),
                                                    (f"({args})", "yellow")))
            elif kind == "user":
                for c in ev["message"].get("content", []):
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        body = c.get("content")
                        if isinstance(body, list):
                            body = "\n".join(x.get("text", "") for x in body if isinstance(x, dict))
                        body = str(body or "")
                        shown = body.splitlines()
                        more = len(shown) - 12
                        md = "\n".join(shown[:12]) + (f"\n\n*… {more} more lines*" if more > 0 else "")
                        console.print(Panel(Markdown(md), title="tally MCP returned (clean Markdown)",
                                            title_align="left", border_style="red" if c.get("is_error") else "green"))
            elif kind == "result":
                final = ev.get("result")
                if ev.get("is_error"):
                    console.print(Panel(str(final), title="Claude failed", border_style="red"))
                    final = None
    proc.wait()
    if final:
        console.print(Panel(Markdown(final), title="Claude's answer", title_align="left", border_style="cyan"))
    else:
        err = proc.stderr.read()[-500:]
        console.print(Panel(err or "No answer from Claude.", title="Claude failed", border_style="red"))


def with_mcp(company: str, fy: int, model: str) -> None:
    cfg = {"mcpServers": {"tally": {"command": sys.executable, "args": [os.path.join(HERE, "server.py")]}}}
    workdir = tempfile.mkdtemp(prefix="tally-demo-")
    cfg_path = os.path.join(workdir, "mcp.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    fy_label = f"FY {fy}-{str(fy + 1)[2:]}"

    scene("With the Tally MCP: a real Claude agent, live TallyPrime")
    ask_claude(f"Show me the trial balance of {company} for {fy_label}.", model, cfg_path, workdir)
    pause(8)

    scene("The agent can now reason about the books")
    ask_claude(f"Does anything look wrong in {company}'s books for {fy_label}?", model, cfg_path, workdir)
    pause(10)


def outro() -> None:
    console.clear()
    centre_vertically(13)
    console.print(Panel(Group(
        Text("Tally MCP", style="bold white", justify="center"),
        Text(""),
        Text("10 tools: ledgers · statements · day book · trial balance · P&L", style="cyan", justify="center"),
        Text("balance sheet · receivables/payables · stock · cleaned raw XML", style="cyan", justify="center"),
        Text(""),
        Text("Figures match Tally's own reports · never freezes Tally · flags bad data", style="white",
             justify="center"),
        Text(""),
        Text(REPO_URL, style="bold yellow", justify="center"),
    ), border_style="cyan", padding=(1, 4)))
    pause(5)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--company", default="Bhrama Enterprises")
    ap.add_argument("--fy", type=int, default=2025, help="financial year start, e.g. 2025 for FY 2025-26")
    ap.add_argument("--model", default="sonnet", help="Claude model for the agent ('' = your default)")
    ap.add_argument("--record", metavar="OUT.mp4", help="open a big-font window and record it with ffmpeg")
    ap.add_argument("--font", type=int, default=26, help="console font height in pixels when recording")
    ap.add_argument("--only", choices=["problem", "mcp"], help="run one part only (for rehearsing)")
    a = ap.parse_args()

    rec = None
    if a.record:
        big_window(a.font)
        rec = start_recording(os.path.abspath(a.record))
    try:
        if a.only != "mcp":
            title_card()
            the_problem(a.company, a.fy)
        if a.only != "problem":
            with_mcp(a.company, a.fy, a.model)
            outro()
    finally:
        if rec:
            stop_recording(rec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
