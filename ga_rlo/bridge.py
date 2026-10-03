"""G2 증거 다리 -- rlo 판정 기록(JSONL)과 Sensor 상태를 턴마다 **수와 라벨로** 줄인다(GA_RLO.md §2).

ga 는 이미 `runner.guards[].record` 의 늘어난 줄을 허락 · 거부 · 오류 수와 거부 라벨로 줄여 턴 증거(`turns[].guards`)와
회차 근거 note 에 싣는다(METHOD rev 15 §4c 7, `ga.hub.guard_summary`). 이 모듈은 그 위에 rlo 만 아는 것을 더한다:

- 판정 기록에서: DC 가 불완전했던 판정 수, 빠진 필수 상태의 이름, 막힌 도구의 이름(라벨)
- 턴의 transcript 에서: Sensor 상태(실행 건강 · 정체 · 생존 · 끝남 · 자원 …)의 값 이름. 지금(now)은 transcript 의 마지막
  시각 + 1 초다 -- 벽시계로 재생하면 낡은 상태로 보여 모두 모름(D)이 된다(baseline CMD-GR1 보탬)

원문(명령 · 까닭 글 · 도구 입력 값)과 비밀값은 싣지 않는다. 결과는 `<설정 디렉터리>/.ga-rlo/evidence.jsonl` 에 턴마다 한 줄이다.
ga 의 턴 증거 칸 자체에 싣는 길은 ga 에 없다 -- 그것은 ga 쪽 요청이다(baseline#15 보고).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import preset

# agent · task · runtime 실체의 상태 가운데 턴을 말해 주는 것(Sensor state-export/2 의 이름 그대로)
STATE_KEYS = ("execution_health", "execution_interruption", "progress_state", "liveness_state", "completion_state",
              "resource_state", "resource_pressure", "context_pressure", "rate_limit_state", "runtime_reliability")
LABEL_MAX = 40


def _label(x: Any) -> str:
    return str(x)[:LABEL_MAX]


def record_summary(lines: Iterable[str]) -> dict[str, Any]:
    """rlo.hooks --record 의 줄들 -> 수와 라벨. ga 의 `guard_summary` 를 그대로 쓰고 rlo 칸을 더한다."""
    from ga.hub import guard_summary

    lines = list(lines)
    out = guard_summary(lines)
    incomplete = 0
    missing: set[str] = set()
    denied_tools: set[str] = set()
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict) or d.get("kind") != "guard":
            continue
        if d.get("complete") is False:
            incomplete += 1
        for m in d.get("missing_required") or []:
            missing.add(_label(m))
        res = d.get("result") if isinstance(d.get("result"), dict) else {}
        if str(res.get("verdict", "")).upper() not in ("", "ALLOW") and d.get("tool_name"):
            denied_tools.add(_label(d["tool_name"]))
    out.update(incomplete=incomplete, missing=sorted(missing), denied_tools=sorted(denied_tools))
    return out


def last_ms(transcript: str | Path) -> float | None:
    """transcript 마지막 줄의 시각(unix ms). 시각이 없으면 None."""
    last = None
    for line in Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            ts = json.loads(line).get("timestamp")
        except (ValueError, AttributeError):
            continue
        if isinstance(ts, str):
            last = ts
    if last is None:
        return None
    return datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp() * 1000


def transcript_state(transcript: str | Path, model: Any, *, now_ms: float | None = None) -> dict[str, str]:
    """transcript -> rlo `TranscriptJudge.collect` -> Sensor 상태의 값 이름(값이 없으면 상태 이름: UNKNOWN …).
    now_ms 가 없으면 transcript 마지막 시각 + 1 초."""
    from rlo.hooks import TranscriptJudge

    if now_ms is None:
        end = last_ms(transcript)
        now_ms = None if end is None else end + 1000
    judge = TranscriptJudge(model, grants=preset.GRANTS, clock=(lambda: now_ms) if now_ms is not None else None)
    run, rs = judge.collect({"transcript_path": str(transcript), "session_id": "turn"})
    subjects = rs.subjects(run) if run in rs.runs else {}
    catalog = rs.catalog()["states"]
    out: dict[str, str] = {}
    for key in STATE_KEYS:
        meta = catalog.get(key)
        entity = subjects.get(meta["entity"]) if meta else None
        if not isinstance(entity, str):
            continue
        r = rs.read(entity, key)
        label = r.get("value") or r.get("status") or "UNKNOWN"
        if r.get("freshness") == "STALE":
            label += "|STALE"
        out[key] = _label(label)
    return out


def find_transcript(home: str | Path, session_id: str | None) -> Path | None:
    """턴의 Claude 홈(`<Runner 집>/<세션>/.claude/projects/*/<session id>.jsonl`)에서 그 턴의 transcript."""
    if not session_id or "/" in session_id or session_id.startswith("."):
        return None
    hits = sorted(Path(home, ".claude", "projects").glob(f"*/{session_id}.jsonl"))
    return hits[0] if hits else None


# ---------------------------------------------------------------------------------------------- ga 명령 둘레

def _line_count(path: Path) -> int:
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


class Bridge:
    """ga 명령(턴을 열 수 있는 send · tick · answer) 앞뒤로: 앞에서 기록의 줄 수를 세고, 뒤에서 새로 생긴 턴마다 늘어난 줄과
    그 턴의 transcript 를 줄여 `.ga-rlo/evidence.jsonl` 에 덧붙인다."""

    def __init__(self, config: str | Path, ga_dir: str | Path | None = None):
        from ga import config as gacfg
        from ga.__main__ import make_runner

        self.config_path = Path(config).resolve()
        self.cfg = gacfg.load(self.config_path)
        self.ga = Path(ga_dir).resolve() if ga_dir else self.config_path.parent / ".ga"
        self.runner = make_runner(self.cfg, self.ga)
        self.out = self.config_path.parent / preset.STATE_DIR / "evidence.jsonl"
        found = preset.rlo_guards(self.cfg.runner)
        self.guard_name = (found[0][1].get("name") or f"guard{found[0][0] + 1}") if found else None
        self.model_path = found[0][2].model if found else None

    def _records(self) -> dict[str, Path]:
        if self.guard_name is None or not hasattr(self.runner, "guard_records"):
            return {}
        out = {}
        for s in self.cfg.sessions:
            for name, path in self.runner.guard_records(s):
                if name == self.guard_name:
                    out[s] = path
        return out

    def _turns(self) -> list[dict[str, Any]]:
        p = self.ga / "state.json"
        if not p.exists():
            return []
        return json.loads(p.read_text(encoding="utf-8")).get("turns", [])

    def before(self) -> dict[str, Any]:
        return {"turns": len(self._turns()), "lines": {s: _line_count(p) for s, p in self._records().items()}}

    def after(self, snap: dict[str, Any]) -> list[dict[str, Any]]:
        turns = self._turns()[snap["turns"]:]
        if not turns:
            return []
        records = self._records()
        model = None
        if self.model_path:
            try:
                model = preset.load_model(self.model_path)
            except Exception:  # noqa: BLE001 -- 모형이 틀리면 상태 칸만 빈다(가드는 이미 닫는 쪽으로 돌았다)
                model = None
        per_session: dict[str, int] = {}
        for t in turns:
            per_session[t["session"]] = per_session.get(t["session"], 0) + 1
        rows = []
        for i, t in enumerate(turns, snap["turns"]):
            s = t["session"]
            row: dict[str, Any] = {"schema": "ga-rlo-turn/1", "turn": i, "session": s, "directive": t.get("directive"),
                                   "rev": t.get("rev"), "runner": t.get("runner")}
            if s in records:
                path = records[s]
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[snap["lines"].get(s, 0):]
                except OSError:
                    lines = []
                row["guard"] = dict(record_summary(lines), guard=self.guard_name)
                if per_session[s] > 1:
                    row["guard"]["shared_with_turns"] = per_session[s]  # 한 명령에 같은 세션의 턴이 여럿이면 줄을 가르지 못한다
            home = self.runner.session_home(s) if hasattr(self.runner, "session_home") else None
            tr = find_transcript(home, t.get("session_id")) if home else None
            if tr is not None and model is not None:
                try:
                    row["state"] = transcript_state(tr, model)
                except Exception as e:  # noqa: BLE001 -- 종류만 남긴다
                    row["state_error"] = type(e).__name__
            elif t.get("runner") in ("headless", "agent_sdk"):
                row["state"] = None  # transcript 를 찾지 못했다(모름)
            rows.append(row)
        self.out.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out, "a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return rows


def read_evidence(config: str | Path) -> list[dict[str, Any]]:
    p = Path(config).resolve().parent / preset.STATE_DIR / "evidence.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
