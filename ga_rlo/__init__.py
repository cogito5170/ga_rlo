"""ga_rlo -- ga-SDK 와 rlo-SDK 를 한 입구로(GA_RLO.md, baseline 소유). 결합층: 두 SDK 를 고정 판으로 의존하고 잇는 코드만 가진다.

    preset   G1  rlo 가드를 ga `runner.guards` 항목으로
    bridge   G2  rlo 판정 기록 · Sensor 상태 -> 턴마다 수와 라벨
    init     G3  `ga-rlo init`
    doctor   G4  `ga-rlo doctor`
    cli      G5  `ga-rlo` 한 입구
    hook     CMD-GR3  the local guard command: rlo.hooks + Sensor state lines in the record
    remote   CMD-GR2  the guard as project settings for a remote worker (`init/doctor --profile remote`)
"""
__version__ = "0.4.0"
