# ga_rlo

ga-SDK 와 rlo-SDK 를 한 입구로 묶는다. **ga 가 일을 굴리고 기록 · 판정한다. rlo 가 그 안의 모형 턴을 지킨다. 둘을 한 번에 설치하고 한 번에 설정한다.** 명세는 baseline `GA_RLO.md`(ga_rlo-1 rev 1, BD-164)다.

- **결합층이다.** 두 SDK 를 고정 판으로 의존하고, 둘을 잇는 코드만 가진다. 두 SDK 의 코드를 복사하지 않는다.
- **닫는 쪽으로만.** 가드는 막거나 손대지 않는다(`allow` 를 내지 않는다). 허락(`ga permit`)은 사람이 남긴다. ga_rlo 는 그 명령을 출력만 한다.
- **가드는 작업 턴에만.** ga 가 턴마다 쓰는 전용 설정에만 들어간다. 사람의 설정(`~/.claude`)과 허브 세션 설정은 건드리지 않는다.

## 설치

```sh
pip install "ga-rlo @ git+https://github.com/cogito5170/ga_rlo@<sha>"
ga-rlo doctor --install-only        # 빈 디렉터리에서도 돈다
```

고정 판(`ga_rlo/_pins.py` 가 원본, `pyproject.toml` 과 같은지 시험이 본다):

| 배포 | 커밋 | 무엇 |
|---|---|---|
| `ga-sdk` | `645f8da` | GA17 통합 머리(`runner.guards`, BD-165) |
| `rlo-sdk[sensor]` | `a152e14` | stage-8. 훅 판정에 Sensor 가 필요하다 |

## 명령

| 명령 | 하는 일 |
|---|---|
| `ga-rlo init` | (G3) `ga.json` 과 rlo 모형 사본(`.ga-rlo/cc_tools_model.json`)을 쓴다. 사람이 칠 `ga-rlo permit …` 을 출력한다 |
| `ga-rlo doctor` | (G4) 실행 전 점검. 하나라도 어긋나면 exit 1 |
| `ga-rlo evidence` | (G2) 턴마다 rlo 의 수와 라벨(`.ga-rlo/evidence.jsonl`) |
| `ga-rlo preset` | (G1) `runner.guards` 항목 하나 |
| `ga-rlo <ga 하위 명령>` | (G5) `tick` · `send` · `answer` · `permit` · `post` · `prompt` · `check` · `review` · `render` · `setup` · `sandbox` 를 그대로 ga 로 넘긴다 |
| `ga-rlo hooks …` | (G5) `python -m rlo.hooks …` 그대로. `install-hook` · `uninstall-hook` 은 `--settings` 가 있어야 하고 사람의 설정은 거절한다 |

### 가드 프리셋 (G1)

`ga-rlo init` 이 `runner.guards` 에 넣는 것:

```json
{"name": "rlo",
 "command": "<python> -m rlo.hooks --model <hub>/.ga-rlo/cc_tools_model.json --mode enforce --grant Bash --record '{home}/rlo-{session}.jsonl'",
 "record": "{home}/rlo-{session}.jsonl"}
```

- **enforce** 다. 판정이 ALLOW 가 아니면 막는다.
- grant 는 **Bash 하나**다. 모형에서 Bash 는 `external` 이라, grant 가 없으면 enforce 에서 모든 Bash 가 A7 로 막힌다(BD-163).
- 모형에 없는 도구(Agent · WebFetch …)는 A1 로 막힌다.
- matcher 는 `*` 다. ga 의 문자열 가드(bash_guard) 다음 순서로 돈다.
- 같은 설정에 ga 의 가드 켬 · 샌드박스 `require` 가 함께 들어간다. rlo 는 도구 단위 · 상태 단위로 판정하고, 명령 내용 · 쓰는 곳은 ga 의 샌드박스 · 격리 · bash_guard 가 맡는다(P5).

### 증거 (G2)

- ga 는 rlo 기록에서 늘어난 줄의 허락 · 거부 · 오류 수와 거부 라벨을 턴 증거(`.ga/state.json` 의 `turns[].guards`)에 싣는다. 거부가 있으면 회차 기록의 note 에 남는다. 예: `guard rlo refused 1 tool call(s) in W's CMD-W1 rev 1 turn: A1`.
- ga_rlo 는 `send` · `tick` · `answer` 앞뒤로 그 위에 rlo 만 아는 것을 더한다. 결과는 `.ga-rlo/evidence.jsonl` 에 턴마다 한 줄이다.
  - 판정 기록에서: DC 가 불완전했던 판정 수, 빠진 필수 상태 이름, 막힌 도구 이름.
  - 턴의 transcript 에서: Sensor 상태의 값 이름(`execution_health` · `progress_state` · `liveness_state` · `resource_state` …). 지금(now)은 transcript 마지막 시각 + 1 초다.
- 명령 · 까닭 글 · 도구 입력 값 · 비밀값은 어디에도 싣지 않는다.

### 점검 (G4)

| 점검 | 무엇을 보나 |
|---|---|
| `install.pins` | 두 SDK 와 rlo 의 일곱 의존이 고정 sha 로 깔렸나(pip 의 `direct_url.json`) |
| `install.contracts` | `action-model/1` · Sensor `state-export` 판 |
| `config` · `preset` | ga 의 검사, 그리고 작업 턴 기본값 그대로인가: 가드 있음 · enforce · grant Bash 하나 · matcher `*` · 기록 · ga 가드 · 샌드박스 require · `--now-ms` 없음 |
| `model` | 가드의 모형이 `action-model/1` 로 읽히나 |
| `guard.program` | ga 가 턴을 열기 전에 보는 그대로, 가드 프로그램이 있나 |
| `replay` | 설정된 가드 명령 그대로 기록된 transcript 를 재생한다(`--now-ms` = 마지막 시각 + 1 초). 정상 일 여섯은 막히지 않고, WebFetch · Agent 는 A1 로 막히며, 어디에도 allow 가 없다. shadow 이거나 모형이 넓어지면 여기서 잡힌다 |
| `permission` | 사람의 허락(decision/1, by user)이 이 Runner · 모형 · 샌드박스 · 예산을 덮나(ga 의 검사 그대로) |
| `sandbox` | OS 쓰기 샌드박스가 여기서 되나 |
| `person.settings` | 사람의 설정 · `CLAUDE_CONFIG_DIR` · 허브 세션의 프로젝트 설정에 rlo 가드가 없나 |

## 빠른 시작 (G6)

### 1. 로컬 CLI (헤드리스 Runner)

```sh
pip install "ga-rlo @ git+https://github.com/cogito5170/ga_rlo@<sha>"
cd hub/
ga-rlo init --repo work=../work --session W:W:claude/w:work --model haiku \
            --guidance GUIDANCE.md --session-guidance SESSION_GUIDANCE.md
# 출력된 명령을 사람이 친다. --note 에는 사람이 직접 한 답의 요지를 적는다
ga-rlo permit --runner headless --model haiku --sandbox require --budget runs=6 --note '…'
# 나온 BD-n 을 ga.json 의 "runner": {..., "permission": "BD-n"} 에 넣는다
ga-rlo doctor
ga-rlo send CMD-W1.md        # 작업 턴 하나: claude -p, 턴 전용 설정에 ga 가드 → rlo 가드
ga-rlo tick                   # 받기 · 통합 · 재현 · 판정 · 기록
ga-rlo evidence
```

- Linux 에서 비특권 user namespace 가 되어야 샌드박스가 선다(`ga-rlo doctor` 의 `sandbox`). 없으면 `require` 는 턴을 열지 않는다.
- `claude` CLI 가 PATH 에 있어야 한다. 턴의 HOME · `CLAUDE_CONFIG_DIR` 은 `.ga/headless/home/<세션>` 이다. 첫 턴 전에 인증이 필요할 수 있다.

### 2. 직접 돌리는 호스트 (Agent SDK Runner)

```sh
pip install "ga-rlo @ git+https://github.com/cogito5170/ga_rlo@<sha>" claude-agent-sdk
ga-rlo init --runner agent_sdk --repo … --session … --model haiku
ga-rlo permit --runner agent_sdk --model haiku --sandbox require --budget runs=6 --note '…'
ga-rlo doctor && ga-rlo send CMD-W1.md
```

- 가드는 같은 턴 전용 설정으로 SDK 에 넘어간다(`setting_sources=[]`: 사람 · 프로젝트 설정 파일을 읽지 않는다).
- 바깥 권한 검사 자리를 ga_rlo 가 맡는 것은 P4 단계의 일이다. 지금은 Claude Code 의 권한 검사와 ga 의 샌드박스가 그 자리다.

### 3. 클라우드 세션 (Claude Code on the web)

- **한계: 바깥 권한 검사가 앞에 있다.** 클라우드 세션 안에서 ga_rlo 를 돌리면 그 세션의 권한 검사(자동 모드 분류기 등)가 ga_rlo 보다 먼저 판단한다.
  - 허브 안에서 헤드리스 턴을 여는 길(`claude -p`)은 거기서 막힐 수 있다(BD-154 · 160). 막히면 ga 는 `refused:…` 로 기록하고 게이트 6 으로 묻는다. 다른 길로 다시 시도하지 않는다.
  - ga_rlo 의 가드는 그 검사를 대신하지도, 피해 가지도 않는다.
- git 에서 받는 설치(`pip install git+…`)도 그 검사에 걸릴 수 있다. 사람이 허락한 뒤 설치한다.
- 원격 작업 세션에 rlo 가드를 작업 저장소의 프로젝트 설정(`.claude/settings.json`)으로 거는 꼴(`ga-rlo init --profile remote`)은 CMD-GR2 에서 정한다. 지금은 아무것도 쓰지 않고 멈춘다.

## 시험

```sh
python -m unittest discover -s tests      # 또는 pytest
```

- 실제 모형 호출 · 네트워크가 없다. Runner 는 ga 의 진짜 헤드리스 Runner 이고, `claude` 자리에 가짜(`tests/fake_claude.py`)를 둔다.
- 가짜는 Claude Code 처럼 턴 전용 설정의 PreToolUse 훅을 실제로 부른다. 지금 시각의 transcript 를 함께 쓴다.
- `test_loop`(§4 2): init → 막힐 도구(WebFetch)가 든 가짜 턴 → tick. 회차 기록에 `A1` 거부 수가 남는지 본다.
- `test_mutations`(§4 3): 가드 빠짐 · shadow · grant 넓어짐 · 빠짐 · 모형 넓어짐 · matcher 좁아짐 · 사람 설정 · 허브 세션 설정에 가드가 들어가면 doctor 가 잡는지 본다.
