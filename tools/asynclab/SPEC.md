# asynclab — 코루틴·이벤트 루프 시각화 도구 (구현 명세)

> 이 문서는 Claude Code에게 넘기는 구현 명세다. python-lab 레포의 `tools/asynclab/`에 새 lab을 만든다.
> pvmlab의 형제 도구이며, pvmlab이 "바이트코드 한 명령"을 스테핑했다면 asynclab은 **"이벤트 루프 한 사건"** 을 스테핑한다.

---

## 0. 한 줄 목적

`asyncio.run()` 이후 벌어지는 일 — **콜 스택 / 힙의 코루틴 객체 / 함수·코드 객체 / 이벤트 루프 내부(준비큐·셀렉터·타이머·Task) / OS 알림** — 을 한 화면에서 ←/→ 스텝으로 관찰한다. 예시 시나리오는 metric-lab의 `mini_server` + `mini_framework` 요청 처리 흐름의 축약판이다.

학습자가 이 대화에서 도달한 결론들을 화면으로 재확인하는 것이 목표다:

1. 이벤트 루프는 `asyncio.run()`이 콜 스택에 올려놓는 **상주 프레임**이다 (배경 데몬이 아님)
2. 코루틴 = **보관된 프레임**. 콜 스택에는 재개되는 동안만 얹혔다 내려간다
3. 루프의 준비큐에 들어가는 건 코루틴이 아니라 **콜백**이고, Task가 코루틴을 콜백(`__step`)으로 번역한다
4. "응답이 온 걸 아는" 주체는 파이썬이 아니라 **OS(셀렉터)** 다 — 루프는 장부를 보고 누굴 깨울지 안다
5. 손님(연결) 1개 = 코루틴 1개 = 프레임 1개, 프레임의 멈춘 줄이 곧 **연결의 상태**다

## 1. 설계 원칙 — pvmlab 철학 계승

pvmlab: "바이트코드는 진짜, 엔진만 재현". asynclab은 이렇게 잇는다:

> **코루틴은 진짜(`async def` + 네이티브 코루틴 객체), 이벤트 루프와 네트워크만 재현한다.**

- 태스크 본문은 진짜 `async def`로 쓰고, `cr_frame.f_lineno` / `cr_await` / `cr_suspended`를 **실제로 읽어서** 표시한다. (pvmlab eventloop.py가 제너레이터+`gi_frame`으로 한 것의 코루틴판)
- 이벤트 루프는 asyncio를 쓰지 않고 **미니 루프를 직접 구현**한다. 준비큐(deque) · 타이머 힙(heapq) · 미니 셀렉터(각본 재생기) · 미니 Task를 노출된 구조로 만든다. asyncio API 모사 금지 — 원리만 드러낸다.
- 네트워크는 **각본(scripted)** 이다. "T=3에 클라이언트A의 요청 라인 바이트가 fd 4에 도착" 같은 이벤트 목록을 미리 정의하고, 미니 셀렉터가 가상 시계에 맞춰 재생한다. 실제 소켓 금지 — 결정성(determinism)이 최우선이다. 같은 입력이면 트레이스가 바이트 단위로 동일해야 한다.
- pvmlab처럼 **진짜와 대조하는 검증**을 넣는다 (§8).

## 2. 위치와 파일 구조

```
tools/asynclab/
  README.md            # pvmlab README와 같은 톤: 개념 모델 표 + 실행법 + 구조
  run.py               # 유일한 진입점. python run.py → asynclab_trace.html
  engine/
    __init__.py
    loop.py            # MiniEventLoop — 준비큐/타이머힙/셀렉터를 멤버로 노출
    task.py            # MiniTask — 코루틴을 콜백(step)으로 번역하는 어댑터
    selector.py        # ScriptedSelector — 각본 이벤트 재생기 (가상 시계)
    channel.py         # MiniReader/MiniWriter — await 가능한 바이트 통로
    tracer.py          # 매 사건마다 전 계층 스냅샷을 기록
  demos/
    __init__.py
    mini_web.py        # mini_server/mini_framework 축약판 (아래 §5)
  viewer.py            # 트레이스 → 단일 자족 HTML (pvmlab viewer.py 관례 따름)
```

- `run.py`만 실행 진입점. 엔진 모듈 직접 실행 금지 (pvmlab과 동일 규칙).
- 의존성 없음. 표준 라이브러리만.
- Python 3.12 기준.

## 3. 화면 구성 — 6개 패널

pvmlab viewer의 시각 언어를 따른다: `:root` CSS 변수(`--bg:#faf9f5` 계열), 카드형 패널, ←/→ 키 스테핑, 상단 진행 바, 각 스텝의 내레이션 문장. 단일 자족 HTML(트레이스 JSON 인라인).

```
┌─────────────┬──────────────────┬─────────────────┐
│ ① 소스 코드  │ ② 콜 스택         │ ③ 이벤트 루프 내부 │
│ (현재 줄     │ (아래→위,         │  preadv큐/타이머/  │
│  하이라이트)  │  루프 프레임 상주)  │  셀렉터 장부/페이즈 │
├─────────────┼──────────────────┼─────────────────┤
│ ④ 힙         │ ⑤ 네트워크 타임라인 │ ⑥ 내레이션        │
│ (코루틴 객체· │ (각본 이벤트,      │ (이번 스텝에서    │
│  함수·코드    │  도착 여부 표시)    │  일어난 일 1~3문장)│
│  객체 카드)   │                  │                 │
└─────────────┴──────────────────┴─────────────────┘
```

### ① 소스 코드
- `demos/mini_web.py`의 소스를 그대로 표시. 현재 재개 중인 코루틴의 `cr_frame.f_lineno`를 하이라이트.
- 멈춰 있는 코루틴들의 보관 지점은 옅은 색 마커로 표시 (여러 개 동시 표시 — "책갈피들").

### ② 콜 스택
- 아래에서 위로 쌓는다. 맨 아래 `<module>` → `run.py` → **`MiniEventLoop.run` (상주, 항상 강조 테두리)** → 그 위에 재개 중 코루틴 프레임.
- 코루틴 프레임이 얹힐 때/내려갈 때 상태 변화가 시각적으로 구분되어야 한다 (pvmlab `.fr.act` 클래스 방식).
- 루프가 잠들어 있는 스텝(§6의 SELECT 페이즈)에서는 콜 스택에 루프 프레임만 남고, "OS 대기 중 — CPU 0%" 배지를 붙인다.

### ③ 이벤트 루프 내부 — 이 도구의 심장. 반드시 다음 4개 구획으로:
1. **페이즈 표시등**: `SELECT`(셀렉터 대기) → `WAKE`(이벤트 수거) → `RUN`(준비큐 소진) 3단계 중 현재 위치. 루프 while문의 어느 줄에 있는지와 대응.
2. **준비큐 (deque)**: 항목은 콜백이다. `Task(client_A).step` 처럼 표기해 "코루틴이 아니라 콜백이 들어있다"를 드러낸다. popleft되는 항목 애니메이션 불필요, 하이라이트면 충분.
3. **셀렉터 장부 (watch list)**: `fd 4 (client_A) → Task(client_A) 깨우기` 형태의 표. OS 알림이 온 fd는 행 강조.
4. **타이머 힙**: `(깨울 시각, Task)` 목록. 본 시나리오에서 비어 있어도 구획 자체는 표시 (구조를 보여주는 게 목적).

### ④ 힙
- 카드 3종: **코드 객체**(공유, 1개씩) / **함수 객체** / **코루틴 객체**.
- 코루틴 카드에 표시: 이름(예: `handle_connection(A)`), 상태(`CREATED/SUSPENDED/RUNNING/DONE`), `cr_frame.f_lineno`(멈춘 줄), 지역변수 스냅샷 요약(예: `scope['path']='/ping'` — 핵심 2~3개만).
- 같은 코드 객체를 쓰는 코루틴 2개(손님 A/B)가 코드 카드 1개를 화살표로 공유하는 그림 — "악보는 공유, 무대는 각자"를 시각화.
- DONE 시 코루틴 카드가 흐려지고 `cr_frame=None` 표기 (프레임 소멸).

### ⑤ 네트워크 타임라인
- 각본 이벤트를 가로 타임라인으로: `T=1 A 접속`, `T=3 A 요청라인 도착`, ... 현재 가상 시계 위치 커서. 이미 소비된 이벤트는 체크 표시.

### ⑥ 내레이션
- 스텝마다 1~3문장. 이 대화에서 쓴 어휘를 그대로 쓴다: "프레임을 내려놓는다", "책갈피", "OS에 맡기고 잠든다", "장부를 보고 깨운다", "콜백으로 번역". 말투는 pvmlab 내레이션과 동일하게 건조한 설명체.

## 4. 미니 루프 구현 요구

`engine/loop.py`의 `MiniEventLoop`:

```python
class MiniEventLoop:
    def __init__(self, selector):
        self.ready = deque()        # 콜백(Handle)만 들어간다
        self.timers = []            # heapq [(wake_time, seq, callback)]
        self.selector = selector    # ScriptedSelector
        self.clock = 0              # 가상 시계 (셀렉터가 진행시킴)

    def call_soon(self, cb, *args): ...
    def add_reader(self, fd, cb): ...      # 셀렉터 장부 등록
    def remove_reader(self, fd): ...
    def run_until_complete(self, coro): ...  # 단일 while — 진실의 원천
```

- while 본문은 반드시 `SELECT → WAKE → RUN` 순서가 코드에서 그대로 읽혀야 한다 (스텝 페이즈와 1:1 대응).
- `engine/task.py`의 `MiniTask`: `step()` 메서드가 `coro.send(value)`를 부르고, 결과(`Future`류 신호)에 따라 셀렉터 장부/타이머에 재등록. `StopIteration`이면 DONE. **큐에 들어가는 건 `task.step`이라는 평범한 바운드 메서드**임이 트레이스에 드러나야 한다.
- 코루틴이 루프에 신호를 보내는 통로: 커스텀 awaitable (`__await__`에서 `yield ("read", fd)` / `("write", fd, data)` / `("sleep", n)`). `channel.py`의 `MiniReader.readline()/readexactly(n)`이 내부적으로 이걸 쓴다. asyncio Future 모사 금지 — 튜플 신호로 충분하다.
- 취소/예외 전파는 범위 밖 (§9).

## 5. 시나리오 — mini_web.py

metric-lab의 `mini_server.py`/`mini_framework.py`를 **한 파일 ~80줄로 축약**해 넣는다 (metric-lab에 의존하지 않는다 — python-lab은 독립 레포). 유지할 것:

- `handle_connection(app, reader, writer)`: 요청 라인 파싱(`split(" ", 2)`, `partition("?")`) → 헤더 while 루프 → `content-length` → body → scope dict 조립 → `await app(scope, receive, send)` → 응답 쓰기. **줄 구조와 변수명은 metric-lab 원본과 최대한 같게** — 학습자가 metric-lab STEP 2에서 읽은 코드를 여기서 재회해야 한다.
- `MiniAPI`: `add_route` + `async def __call__(self, scope, receive, send)` + 라우팅 dict. 핸들러는 `ping` 하나 (`GET /ping` → `b"pong\n"`).
- 축약 허용: 예외 처리 생략, 헤더는 2개만, lifespan 없음.

**각본** (두 손님 인터리브 — 프레임 전환이 보이는 최소 구성):

```
T=0  루프 시작, listen fd(3) 등록
T=1  A 접속(fd 4)          → handle_connection 코루틴 A 생성·Task 등록
T=2  B 접속(fd 5)          → 코루틴 B 생성 (A는 요청라인 대기로 SUSPENDED)
T=3  B 요청라인 도착         ← 먼저 온 건 B! A는 계속 멈춰 있음
T=4  B 헤더+바디 도착 → B가 app 호출 → 응답 → B DONE
T=5  A 요청라인 도착
T=6  A 헤더+바디 도착 → A 처리 → A DONE
T=7  각본 종료 → 루프 종료
```

의도: **나중에 온 손님 B가 먼저 끝난다.** "A가 느려도 B는 안 막힌다"가 화면에서 증명된다.

## 6. 스텝 의미론

한 스텝 = 다음 중 하나의 **사건**:

| 사건 | 예 |
|---|---|
| 루프 페이즈 전환 | RUN→SELECT (잠듦), SELECT→WAKE (OS 알림) |
| 콜백 실행 시작/종료 | 준비큐 popleft → `task.step` 호출 |
| 코루틴 재개/보관 | send → 프레임 얹힘 / awaitable에서 프레임 내려감 |
| 힙 변화 | 코루틴 객체 생성, DONE으로 프레임 소멸 |
| 각본 이벤트 | 접속, 바이트 도착 |

바이트코드 단위 스테핑은 **하지 않는다** (그건 pvmlab의 일). 예상 총 스텝 40~80개.

`tracer.py`는 매 사건 후 전 계층을 스냅샷: `{step, clock, phase, narration, call_stack, heap:{code_objs, func_objs, coros}, loop:{ready, timers, watch}, net_events_consumed, src_highlight:{coro_name, lineno}, bookmarks:[{coro,lineno}]}`. JSON 직렬화 가능해야 하며 viewer는 이 JSON만 사용한다.

## 7. README.md 요구

pvmlab README 형식을 따른다: (1) 한 줄 철학 — "코루틴은 진짜, 루프와 네트워크만 재현" (2) 개념 모델 표 — 5층: 코드 객체/함수 객체/코루틴 객체(=보관된 프레임)/미니 Task(콜백 번역기)/미니 루프 (3) 실행법 (4) 구조 (5) pvmlab eventloop.py와의 관계 한 단락: "eventloop.py는 제너레이터+가상시계로 스케줄링 원리를, asynclab은 진짜 코루틴+셀렉터로 asyncio의 구조를 보인다".

## 8. 검증 (run.py가 HTML 생성 전에 수행, 실패 시 생성 중단)

1. **응답 정합**: 미니 루프로 돌린 A/B의 응답 바이트가 기대값(`HTTP/1.1 200 ...pong`)과 `assert` 일치.
2. **진짜와 대조**: 동일한 `handle_connection`/`MiniAPI` 코드를 `asyncio` + `asyncio.StreamReader`(feed_data로 각본 주입)로 돌려 같은 응답이 나옴을 `assert`. — "이 코루틴 코드는 진짜 asyncio에서도 그대로 돈다" (metric-lab verify.py의 '검증 2'와 같은 정신).
3. **재개 순서 결정성**: 두 번 실행한 트레이스의 재개 순서 리스트가 동일.
4. 통과 시 pvmlab처럼 `검증 OK` 출력.

## 9. 범위 밖 (구현하지 말 것)

- 실제 소켓/네트워크, 스레드, `to_thread`
- 예외 전파·취소(`throw`/`CancelledError`), lifespan, keep-alive, 동시 write 백프레셔
- asyncio API 호환 (`get_running_loop` 등)
- 시나리오 편집 UI (각본은 코드에 고정)

## 10. 완료 기준

- [ ] `cd tools/asynclab && python run.py` → 검증 OK → `asynclab_trace.html` 생성
- [ ] 브라우저에서 ←/→ 스테핑, 6패널 모두 갱신
- [ ] "B가 먼저 끝나는" 순간의 내레이션이 그 의미를 명시
- [ ] SELECT 페이즈에서 콜 스택에 루프 프레임만 + "CPU 0%" 배지
- [ ] 준비큐 항목이 `Task(...).step` 표기 (코루틴 아님)
- [ ] 코루틴 카드 2개가 코드 객체 카드 1개를 공유하는 표시
- [ ] DONE 시 `cr_frame=None` 반영
- [ ] 표준 라이브러리만 사용, 파일당 ~150줄 이내 지향