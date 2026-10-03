"""판 고정 목록 -- ga_rlo 가 의존하는 두 SDK 의 커밋 sha. **이 파일이 원본이다**(GA_RLO.md §3).

`pyproject.toml` 의 dependencies 는 이 목록과 뜻이 같아야 한다(tests/test_pins.py 가 붙든다).

    ga-sdk   af904fe  GA19 (guard_summary state lines, report/2 forms; GA17 runner.guards before it)
    rlo-sdk  a152e14  stage-8, extras [sensor](훅 판정은 Sensor 가 필요하다)

두 SDK 를 한 venv 에 깔았을 때 충돌이 없다(baseline 확인, 2026-10-03, `pip check` 정상).
"""
from __future__ import annotations

_GH = "https://github.com/cogito5170/"

# 이름 -> (배포 이름, extras, 저장소 URL, 커밋 sha)
PINS = {
    "ga": ("ga-sdk", (), _GH + "ga-SDK", "af904fe7fe1a0da2ef817ca981422040cccc0718"),
    "rlo": ("rlo-sdk", ("sensor",), _GH + "rlo-SDK", "a152e14bc84dc282f66bb3426a12a70934fc530d"),
}


def requirement(pin: tuple) -> str:
    dist, extras, url, sha = pin
    ex = f"[{','.join(extras)}]" if extras else ""
    return f"{dist}{ex} @ git+{url}@{sha}"


def requirements() -> list[str]:
    return [requirement(p) for p in PINS.values()]
