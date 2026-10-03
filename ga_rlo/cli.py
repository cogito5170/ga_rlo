"""G5 한 입구 -- `ga-rlo`. 자기 명령 넷과, `ga` · `rlo.hooks` 의 하위 명령을 그대로 넘기는 길(GA_RLO.md §2).

    ga-rlo init     --hub H --repo N=PATH … --session N:P:BRANCH:REPOS …   G3: ga.json + rlo 모형 (허락은 출력만)
    ga-rlo doctor   [--install-only] [--json]                               G4: 실행 전 점검 (어긋나면 exit 1)
    ga-rlo evidence [--json]                                                G2: 턴마다 rlo 의 수와 라벨
    ga-rlo preset   [--model PATH]                                          G1: runner.guards 항목 하나(JSON)

    ga-rlo <ga 하위 명령> …     tick · send · answer · permit · post · prompt · check · review · render · setup · sandbox
                                (그대로 ga 로. 턴을 열 수 있는 send · tick · answer 는 앞뒤로 증거 다리를 돈다)
    ga-rlo hooks …              python -m rlo.hooks … 그대로. install-hook · uninstall-hook 은 --settings 가 있어야 하고
                                사람의 설정(~/.claude · CLAUDE_CONFIG_DIR)은 거절한다(P4)

공통: --config PATH (기본 ga.json) · --ga-dir PATH (기본 <설정 디렉터리>/.ga) -- ga 와 같다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

GA_COMMANDS = ("tick", "setup", "sandbox", "post", "send", "review", "permit", "answer", "prompt", "check", "render")
TURN_COMMANDS = ("send", "tick", "answer")
OWN = ("init", "doctor", "evidence", "preset")
GLOBAL = ("--config", "--ga-dir")


def _split(argv: list[str]) -> tuple[dict[str, str], str | None, int]:
    """(전역 옵션, 하위 명령, 그 자리)."""
    opts: dict[str, str] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in GLOBAL and i + 1 < len(argv):
            opts[a] = argv[i + 1]
            i += 2
            continue
        if any(a.startswith(g + "=") for g in GLOBAL):
            k, _, v = a.partition("=")
            opts[k] = v
            i += 1
            continue
        if a.startswith("-"):
            return opts, None, i
        return opts, a, i
    return opts, None, i


def person_settings_paths() -> list[Path]:
    paths = [Path.home() / ".claude" / "settings.json", Path.home() / ".claude" / "settings.local.json"]
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        paths.append(Path(os.environ["CLAUDE_CONFIG_DIR"]) / "settings.json")
    return [p.expanduser().resolve() for p in paths]


def hooks(rest: list[str]) -> int:
    from rlo.hooks import main as rlo_main

    if rest and rest[0] in ("install-hook", "uninstall-hook"):
        ap = argparse.ArgumentParser(add_help=False)
        ap.add_argument("--settings")
        a, _ = ap.parse_known_args(rest[1:])
        if not a.settings:
            print(f"ga-rlo hooks {rest[0]}: --settings is required (ga-rlo never installs into the person's settings, P4)",
                  file=sys.stderr)
            return 2
        if Path(a.settings).expanduser().resolve() in person_settings_paths():
            print(f"ga-rlo hooks {rest[0]}: {a.settings} is the person's settings -- refused (P4: guards go only in a "
                  "work turn's own settings)", file=sys.stderr)
            return 2
    return rlo_main(rest)


def passthrough(argv: list[str], opts: dict[str, str], cmd: str) -> int:
    from ga.__main__ import main as ga_main

    config = Path(opts.get("--config", "ga.json"))
    bridge = snap = None
    if cmd in TURN_COMMANDS and config.exists():
        try:
            from .bridge import Bridge

            bridge = Bridge(config, opts.get("--ga-dir"))
            snap = bridge.before()
        except Exception as e:  # noqa: BLE001 -- 다리가 못 서도 ga 명령은 그대로 돈다
            print(f"ga-rlo: evidence bridge not set up ({type(e).__name__})", file=sys.stderr)
            bridge = None
    try:
        return ga_main(argv)
    finally:
        if bridge is not None:
            try:
                rows = bridge.after(snap)
                if rows:
                    print(f"ga-rlo: rlo evidence for {len(rows)} turn(s) -> {bridge.out}", file=sys.stderr)
            except Exception as e:  # noqa: BLE001
                print(f"ga-rlo: evidence bridge failed ({type(e).__name__})", file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="ga-rlo", formatter_class=argparse.RawDescriptionHelpFormatter,
        description="ga-SDK 와 rlo-SDK 를 한 입구로: ga 가 일을 굴리고 기록 · 판정하고, rlo 가 그 안의 모형 턴을 지킨다.",
        epilog="ga 하위 명령(그대로 넘김): " + " · ".join(GA_COMMANDS) + "\n"
               "rlo 훅(그대로 넘김):       ga-rlo hooks …  (python -m rlo.hooks)\n"
               "허락(ga permit)은 사람이 친다. ga-rlo init 은 그 명령을 출력만 한다.")
    ap.add_argument("--config", default="ga.json")
    ap.add_argument("--ga-dir", default=None)
    sub = ap.add_subparsers(dest="cmd", metavar="{init,doctor,evidence,preset,hooks,<ga command>}")
    p = sub.add_parser("init", help="G3: ga.json 과 rlo 모형을 쓴다(허락은 출력만)")
    p.add_argument("--dir", default=None, help="설정을 쓸 디렉터리(기본: --config 의 디렉터리)")
    p.add_argument("--profile", default="local", choices=("local", "remote"))
    p.add_argument("--hub", default="hub")
    p.add_argument("--repo", action="append", default=[], metavar="NAME=PATH", help="local profile (one or more)")
    p.add_argument("--session", action="append", default=[], metavar="NAME:PREFIX:BRANCH:REPO[,REPO]",
                   help="local profile (one or more)")
    p.add_argument("--work-repo", default=None, help="remote profile: the worker's repository checkout")
    p.add_argument("--name", default="worker", help="remote profile: the worker session's name (record file name)")
    p.add_argument("--integration-branch", default="integration")
    p.add_argument("--runner", default="headless", choices=("headless", "agent_sdk"))
    p.add_argument("--model", default=None)
    p.add_argument("--budget", action="append", default=[], metavar="NAME=NUMBER", help="기본 runs=6")
    p.add_argument("--max-budget-usd", type=float, default=0.5, help="턴 하나의 비용 상한")
    p.add_argument("--judge", default="file", choices=("file", "llm"))
    p.add_argument("--guidance", default=None, help="허브 안내 파일(설정 디렉터리 기준, ga prompt --hub)")
    p.add_argument("--session-guidance", default=None, help="작업 세션 안내 파일(ga prompt <세션>)")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("doctor", help="G4: 실행 전 점검(어긋나면 exit 1)")
    p.add_argument("--install-only", action="store_true", help="설정 없이 설치만 본다")
    p.add_argument("--profile", default="local", choices=("local", "remote"))
    p.add_argument("--work-repo", default=".", help="remote profile: the worker's repository checkout")
    p.add_argument("--venv", default=None, help="remote profile: a venv with rlo installed (default: this one)")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("evidence", help="G2: 턴마다 rlo 의 수와 라벨")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("preset", help="G1: runner.guards 항목 하나")
    p.add_argument("--model", default=None, help="모형 경로(기본: <설정 디렉터리>/.ga-rlo/cc_tools_model.json)")
    sub.add_parser("hooks", help="python -m rlo.hooks … 그대로", add_help=False)
    return ap


def cmd_init(a) -> int:
    from . import init

    if a.profile == "remote":
        try:
            out = init.run(directory=".", profile="remote", force=a.force, work_repo=a.work_repo, name=a.name)
        except init.InitError as e:
            print(f"ga-rlo init: {e}", file=sys.stderr)
            return 2
        for rel in out["written"]:
            print(f"wrote {Path(out['repo']) / rel}")
        print("\nga-rlo does not commit or push guard files (an AI may not change another session's guard, BD-196).")
        print("A human reviews them, then runs:")
        for c in out["commands"]:
            print(f"  {c}")
        print("Give the hub ownership of these paths in its ga.json:")
        for row in out["ownership"]:
            print(f"  {json.dumps(row)}")
        print("Then: ga-rlo doctor --profile remote --work-repo <checkout>")
        return 0
    if not a.repo or not a.session:
        print("ga-rlo init: the local profile needs --repo and --session", file=sys.stderr)
        return 2
    try:
        repos = dict(init.parse_repo(r) for r in a.repo)
        sessions = dict(init.parse_session(s) for s in a.session)
        budget = {k: float(v) if "." in v else int(v) for k, v in (x.split("=", 1) for x in a.budget)} or None
        out = init.run(directory=a.dir or Path(a.config).resolve().parent, profile=a.profile, force=a.force, hub=a.hub,
                       repos=repos, sessions=sessions, integration_branch=a.integration_branch, runner=a.runner,
                       model=a.model, budget=budget, max_budget_usd=a.max_budget_usd, judge=a.judge,
                       guidance=a.guidance, session_guidance=a.session_guidance)
    except (init.InitError, ValueError) as e:
        print(f"ga-rlo init: {e}", file=sys.stderr)
        return 2
    print(f"wrote {out['config']}")
    print(f"wrote {out['model']}")
    print("\n다음은 사람이 한다(ga-rlo 는 허락을 만들지 않는다, METHOD §4c 5):")
    print(f"  1. {out['permit']}")
    print('  2. 나온 BD-n 을 ga.json 의 "runner": {..., "permission": "BD-n"} 에 넣는다')
    print("  3. ga-rlo doctor")
    return 0


def cmd_doctor(a) -> int:
    from . import doctor

    if a.profile == "remote":
        ok, checks = doctor.run_remote(a.work_repo, a.venv)
    else:
        ok, checks = doctor.run(a.config, a.ga_dir, install_only=a.install_only)
    print(doctor.render(ok, checks, a.json))
    return 0 if ok else 1


def cmd_evidence(a) -> int:
    from .bridge import read_evidence

    rows = read_evidence(a.config)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    if not rows:
        print("no rlo evidence yet (it is written when ga-rlo send · tick · answer runs a turn)")
    for r in rows:
        g = r.get("guard") or {}
        st = r.get("state")
        print(f"turn {r['turn']} {r['session']} {r.get('directive')} rev {r.get('rev')}: "
              f"allow {g.get('allow', '-')} deny {g.get('deny', '-')} errors {g.get('errors', '-')} "
              f"labels {','.join(g.get('labels', [])) or '-'} missing {','.join(g.get('missing', [])) or '-'} | "
              + (", ".join(f"{k}={v}" for k, v in st.items()) if st else "state unknown"))
    return 0


def cmd_preset(a) -> int:
    from . import preset

    model = a.model or str(Path(a.config).resolve().parent / preset.STATE_DIR / preset.MODEL_FILE)
    print(json.dumps(preset.rlo_guard(model), ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    opts, cmd, at = _split(argv)
    if cmd == "hooks":
        return hooks(argv[at + 1:])
    if cmd in GA_COMMANDS:
        return passthrough(argv, opts, cmd)
    a = _parser().parse_args(argv)
    if a.cmd is None:
        _parser().print_help()
        return 0
    return {"init": cmd_init, "doctor": cmd_doctor, "evidence": cmd_evidence, "preset": cmd_preset}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
