"""The VALID portal: one page, one question endpoint.

  uvicorn valid.web:app --port 8080

Cost guards: a whole-service daily question cap (in memory, resets at 00:00 UTC and on restart),
a question length limit, and a scope question ("ask") that costs nothing and is not counted.
"""
from __future__ import annotations

import datetime as dt
import hmac
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from . import config

PAGE = Path(__file__).parent / "static" / "index.html"


class AskBody(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    generations: list[str] | None = Field(default=None, max_length=4)


class Cap:
    """Counts answered-or-attempted questions per UTC day. Thread safe."""

    def __init__(self, limit: int):
        self.limit, self._day, self._n, self._lock = limit, None, 0, threading.Lock()

    def _roll(self) -> None:
        today = dt.datetime.now(dt.timezone.utc).date()
        if today != self._day:
            self._day, self._n = today, 0

    def left(self) -> int:
        with self._lock:
            self._roll()
            return max(0, self.limit - self._n)

    def take(self) -> bool:
        with self._lock:
            self._roll()
            if self._n >= self.limit:
                return False
            self._n += 1
            return True

    def give_back(self) -> None:
        with self._lock:
            self._n = max(0, self._n - 1)


def _default_agent():
    from . import store
    from .agent import Agent
    from .retrieve import Corpus
    from .scheme import load_scheme
    scheme = load_scheme(config.scheme_path())
    return Agent(scheme, Corpus.load(scheme), store.db().collection(config.COLLECTION))


FAIL_LIMIT, FAIL_WINDOW_S = 8, 900          # wrong codes allowed per client address per 15 minutes


def create_app(agent=None, cap: Cap | None = None, access_code: str | None = None) -> FastAPI:
    app = FastAPI(title="VALID", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.agent, app.state.cap = agent, cap or Cap(config.DAILY_CAP)
    lock = threading.Lock()
    code = config.ACCESS_CODE if access_code is None else access_code
    fails: dict[str, deque] = defaultdict(deque)

    def client_ip(request: Request) -> str:
        fwd = request.headers.get("x-forwarded-for", "")
        return (fwd.split(",")[-1].strip() if fwd else "") or (request.client.host if request.client else "?")

    def check_code(request: Request) -> None:
        if not code:
            return
        ip, now = client_ip(request), time.time()
        with lock:
            q = fails[ip]
            while q and now - q[0] > FAIL_WINDOW_S:
                q.popleft()
            if len(q) >= FAIL_LIMIT:
                raise HTTPException(429, "Too many wrong access codes from this address. Try again in 15 minutes.")
        given = request.headers.get("x-access-code", "")
        if not hmac.compare_digest(given.encode(), code.encode()):
            with lock:
                fails[ip].append(now)
            raise HTTPException(401, "Access code missing or wrong.")

    def get_agent():
        with lock:
            if app.state.agent is None:
                app.state.agent = _default_agent()
        return app.state.agent

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["Content-Security-Policy"] = ("default-src 'none'; script-src 'unsafe-inline'; "
                                                   "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    @app.get("/", response_class=HTMLResponse)
    def index():
        return PAGE.read_text(encoding="utf-8")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/config")
    def cfg():
        a = get_agent()
        return {"generations": [{"key": g.key, "name": g.name} for g in a.scheme.generations],
                "left_today": app.state.cap.left(), "daily_cap": app.state.cap.limit,
                "needs_code": bool(code), "max_chars": config.MAX_QUESTION_CHARS, "corpus_base": config.CORPUS_WEB_BASE}

    @app.post("/api/ask")
    def ask(body: AskBody, request: Request):
        check_code(request)
        q = body.question.strip()
        if len(q) < 3:
            raise HTTPException(400, "Please type a question.")
        if len(q) > config.MAX_QUESTION_CHARS:
            raise HTTPException(400, f"Please keep the question under {config.MAX_QUESTION_CHARS} characters.")
        if not app.state.cap.take():
            return JSONResponse({"detail": "Today's question limit for this demo has been reached. It resets at 00:00 UTC.",
                                 "left_today": 0}, status_code=429)
        try:
            r = get_agent().ask(q, body.generations)
        except ValueError as e:
            app.state.cap.give_back()
            raise HTTPException(400, str(e))
        except Exception:
            app.state.cap.give_back()
            raise HTTPException(500, "Something went wrong on the server. Nothing was answered.")
        if r["outcome"] in ("ask", "unavailable"):
            app.state.cap.give_back()          # a scope question or a busy model used nothing worth counting
        r["left_today"] = app.state.cap.left()
        return r

    return app


app = create_app()
