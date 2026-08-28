"""FastAPI last-decision board. Not a chat box."""

from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from strikewatch.config import Settings
from strikewatch.cycle import run_cycle
from strikewatch.dataio import load_last_decision, load_market

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>StrikeWatch — desk</title>
  <style>
    :root {
      --bg: #0e1116;
      --card: #171c24;
      --ink: #e8edf5;
      --muted: #8b97a8;
      --line: #2a3340;
      --quiet: #3dd68c;
      --quiet-bg: #123526;
      --alert: #ffb020;
      --alert-bg: #3a2a0c;
      --none: #8b97a8;
      --none-bg: #232833;
      --fire: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }
    header {
      padding: 28px 32px 14px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      align-items: flex-end;
    }
    h1 { margin: 0; font-size: 1.8rem; letter-spacing: -0.03em; }
    .tag { color: var(--muted); font-size: 0.95rem; margin-top: 6px; max-width: 46rem; }
    button {
      font: inherit;
      background: var(--ink);
      color: var(--bg);
      border: 0;
      padding: 10px 16px;
      border-radius: 999px;
      cursor: pointer;
    }
    main { padding: 24px 32px 48px; display: grid; gap: 20px; }
    .hero, section {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px 22px;
    }
    .pill {
      display: inline-block;
      font-size: 0.78rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      padding: 6px 12px;
      border-radius: 999px;
      font-weight: 700;
    }
    .quiet { background: var(--quiet-bg); color: var(--quiet); }
    .alert { background: var(--alert-bg); color: var(--alert); }
    .none { background: var(--none-bg); color: var(--none); }
    ul { margin: 8px 0 0; padding-left: 1.1rem; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 920px) { .grid { grid-template-columns: 1fr; } }
    h2 { margin: 0 0 12px; font-size: 1.05rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line); font-variant-numeric: tabular-nums; }
    tr.warn td { color: var(--alert); }
    tr.fire td { color: var(--fire); }
    footer { padding: 0 32px 32px; color: var(--muted); font-size: 0.88rem; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85em; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>StrikeWatch</h1>
      <div class="tag">Options-alpha pager for a paper desk. Not a chatbot. Most cycles stay QUIET. An ALERT is a defined-risk structure that cleared every risk gate.</div>
    </div>
    <form method="post" action="/cycle">
      <button type="submit">Run watch cycle</button>
    </form>
  </header>
  <main>
    <div class="hero">
      <div>
        <span class="pill __KLASS__">__DECISION__</span>
        <span class="tag"> __WHEN__ · broker __BROKER__ · paper / mock</span>
      </div>
      <div>
        <strong>Why</strong>
        <ul>__REASONS__</ul>
      </div>
      <div class="tag">Gates fired: __FIRED__ · P&amp;L __PNL__ · equity __EQUITY__</div>
    </div>
    <div class="grid">
      <section>
        <h2>Universe</h2>
        <table>
          <thead><tr><th>Name</th><th>Spot</th><th>IV rank</th><th>IV−RV</th><th>Signal</th></tr></thead>
          <tbody>__UNIVERSE__</tbody>
        </table>
      </section>
      <section>
        <h2>Open legs</h2>
        <table>
          <thead><tr><th>Contract</th><th>Side</th><th>Qty</th><th>uP&amp;L</th></tr></thead>
          <tbody>__LEGS__</tbody>
        </table>
      </section>
    </div>
    <section>
      <h2>Gates last cycle</h2>
      <table>
        <thead><tr><th>Gate</th><th>Pass</th><th>Note</th></tr></thead>
        <tbody>__GATES__</tbody>
      </table>
    </section>
  </main>
  <footer>
    Options Alpha Agents · lablab.ai Alpaca hackathon · Jordi / XnOwOCodes · Spain · MIT.
    Kill switch: <code>STRIKEWATCH_KILL=1</code>. Paper host only.
  </footer>
</body>
</html>
"""


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _klass(decision: str) -> str:
    if decision == "alert":
        return "alert"
    if decision == "quiet":
        return "quiet"
    return "none"


def render_board(settings: Settings) -> str:
    last = load_last_decision(settings)
    reasons = last.get("reasons") or ["No cycle yet."]
    reason_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in reasons)
    fired = last.get("gates_fired") or []
    fired_txt = ", ".join(fired) if fired else "none"
    account = last.get("account") or {}
    equity = account.get("equity")
    pnl = account.get("daily_pnl")
    uni_rows = []
    universe = last.get("universe")
    if not universe:
        try:
            universe = [row.as_dict() | {"signal": False} for row in load_market(settings.market_path)]
        except FileNotFoundError:
            universe = []
    for row in universe:
        hit = bool(row.get("signal"))
        uni_rows.append(
            "<tr class='{cls}'><td>{sym}</td><td>{spot}</td><td>{rank}</td><td>{gap}</td><td>{sig}</td></tr>".format(
                cls="warn" if hit else "",
                sym=html.escape(str(row.get("symbol"))),
                spot=html.escape(str(row.get("spot"))),
                rank=html.escape(str(row.get("iv_rank"))),
                gap=html.escape(str(row.get("iv_minus_rv"))),
                sig="yes" if hit else "no",
            )
        )
    if not uni_rows:
        uni_rows.append("<tr><td colspan='5'>No snapshot.</td></tr>")
    leg_rows = []
    for leg in last.get("open_legs") or []:
        leg_rows.append(
            "<tr><td>{sym}</td><td>{side}</td><td>{qty}</td><td>{pl}</td></tr>".format(
                sym=html.escape(str(leg.get("symbol"))),
                side=html.escape(str(leg.get("side"))),
                qty=html.escape(str(leg.get("qty"))),
                pl=html.escape(str(leg.get("unrealized_pl"))),
            )
        )
    if not leg_rows:
        leg_rows.append("<tr><td colspan='4'>Flat.</td></tr>")
    gate_rows = []
    for gate in last.get("gates") or []:
        ok = bool(gate.get("passed"))
        gate_rows.append(
            "<tr class='{cls}'><td>{name}</td><td>{ok}</td><td>{why}</td></tr>".format(
                cls="" if ok else "fire",
                name=html.escape(str(gate.get("name"))),
                ok="pass" if ok else "FIRE",
                why=html.escape(str(gate.get("reason"))),
            )
        )
    if not gate_rows:
        gate_rows.append("<tr><td colspan='3'>Run a cycle.</td></tr>")
    equity_txt = "—" if equity is None else f"{float(equity):,.0f}"
    pnl_txt = "—" if pnl is None else f"{float(pnl):+,.2f}"
    return (
        PAGE.replace("__KLASS__", _klass(str(last.get("decision"))))
        .replace("__DECISION__", html.escape(str(last.get("decision", "none")).upper()))
        .replace("__WHEN__", html.escape(str(last.get("cycle_at") or "never")))
        .replace("__BROKER__", html.escape(str(last.get("broker") or "mock")))
        .replace("__REASONS__", reason_html)
        .replace("__FIRED__", html.escape(fired_txt))
        .replace("__PNL__", html.escape(pnl_txt))
        .replace("__EQUITY__", html.escape(equity_txt))
        .replace("__UNIVERSE__", "\n".join(uni_rows))
        .replace("__LEGS__", "\n".join(leg_rows))
        .replace("__GATES__", "\n".join(gate_rows))
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="StrikeWatch", docs_url=None, redoc_url=None)
    app.state.settings = settings or Settings.from_env()

    @app.get("/", response_class=HTMLResponse)
    def board(request: Request) -> str:
        return render_board(_settings(request))

    @app.get("/api/status")
    def status(request: Request) -> dict[str, Any]:
        return load_last_decision(_settings(request))

    @app.post("/api/cycle")
    def api_cycle(request: Request) -> dict[str, Any]:
        return run_cycle(_settings(request))

    @app.post("/cycle")
    def form_cycle(request: Request) -> HTMLResponse:
        run_cycle(_settings(request))
        return HTMLResponse(render_board(_settings(request)))

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"ok": True, "service": "strikewatch"})

    return app


app = create_app()
