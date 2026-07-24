# asynclab — 진짜 asyncio를 눈으로 보는 학습 도구

**전부 진짜다.** 관찰 대상은 weblab의 3파일(mini_server / mini_framework / verify의
app·hello·echo)을 한 글자도 안 고치고 가져온 것이고, 그 코드를 **진짜
`asyncio.SelectorEventLoop` + 진짜 `asyncio.Task` + 진짜 소켓(127.0.0.1)** 위에서
실행한다. 후킹은 관찰용 세 군데뿐:

1. **task factory** — Task 생성을 가로채 라벨을 붙이고 `__step` 앞뒤를 스냅샷
   (순수 파이썬 `_PyTask`를 써서 C 가속판과 동작은 같되 콜 스택에 '보인다')
2. **selector 프록시** — `loop._selector.select()`를 감싸 진짜 epoll 잠듦(SELECT)과
   기상(WAKE)을 포착. timeout=0 논블로킹 폴링은 기록하지 않는다
3. **driver 코루틴** — verify.py `check()`의 2-클라이언트 확장판이 진짜 소켓으로
   각본을 수행: A가 먼저 접속하지만 요청라인만 보내고 굼뜨는 사이, B가 전체
   요청을 보내 **먼저 끝난다**

그래서 뷰어의 콜 스택에는 `Handle._run(events.py:88)` →
`BaseEventLoop._run_once(base_events.py)` → `run_forever(진짜 루프의 while)` 같은
**실제 CPython asyncio 프레임이 파일:줄번호 그대로** 찍히고,
`_create_server_getaddrinfo`·`_accept_connection2` 같은 asyncio 내부 태스크까지
그대로 드러난다. 보관된 코루틴은 `cr_frame.f_lineno`·`cr_await`·`_fut_waiter`를
실제로 읽어 표시한다.

## 실행

```bash
cd tools/asynclab
python run.py                 # 검증 통과 → asynclab_trace.html (←/→ 스테핑)
```

검증: ① A(GET /hello)/B(POST /echo) 응답 바이트 == 기대값 ② B의 완료 스텝이
A보다 앞선다 ③ 이야기 모드 스텝 수 ≤ 30. 스텝마다 요약 한 줄 + 쉬운 개념 해설 +
"지금 볼 곳"(어느 패널의 어떤 데이터) 목록이 붙는다.

## 이야기 모드 (기본) vs 전체 모드

진짜 asyncio를 돌리면 학습 서사 사이에 내부 배관(`_accept_connection2`,
`_create_server_getaddrinfo`, driver(check)의 재개/중단, transport 콜백…)이
끼어든다. 뷰어 기본값은 **이야기 모드** — 서사 스텝 ~30개만 걷고, 숨긴 배관
구간은 타임라인에 `···n`으로 존재만 알린다(누르면 그 지점의 전체 모드로 진입).
숨겼다는 사실 자체가 교훈이다: **진짜라서 배관이 있다.**

- 상단 챕터 버튼 5개로 장면 점프: 기동 → A 도착 → B 도착 → **B 완주**(이때
  "client_A는 아직 :37" 배지가 상시 표시) → A 마무리
- 같은 개념 해설은 첫 등장에서만 전문이 펼쳐지고, 이후엔 한 줄 요약 + 펼치기
- 준비큐 항목은 `함수명(핵심 인자)` 60자 이하로 축약, 관찰 태스크는 제 색·배관은 회색

소스 패널은 파일 탭(3파일)이고, ←/→로 스텝을 넘기면 지금 실행 중인 위치의
파일로 자동 전환된다. `MiniAPI.__call__`·`hello`/`echo`처럼 await 없이 즉시
끝나는 함수는 보관 스냅샷에 잡히지 않으므로, `sys.monitoring`(PY_START)으로
함수 '진입' 사건을 따로 잡아 세 파일의 실행 경로 전체를 스텝으로 보여준다.

주의: 진짜 OS(fd·포트·타이머)를 쓰므로 트레이스 세부는 실행마다 다를 수 있다.

## 구조

```
run.py                    유일한 진입점 — 요청/기대값 정의, 검증, HTML 생성
engine/realtrace.py       진짜 asyncio 계측: TracingTask·TracingSelector·RealTracer
demos/weblab/             관찰 대상 — metric-lab tools/weblab에서 그대로 복사
  mini_server.py            handle_connection + serve (uvicorn의 자리)
  mini_framework.py         MiniAPI (ASGI callable)
  verify.py                 app / hello / echo (데모 앱 정의를 그대로 import)
viewer.py                 트레이스 → 단일 자족 HTML (6패널, 태스크별 색, 상세 해설)
```

## 세 파일이 각각 보여주는 것

- **mini_server.py** — 서버의 일: 소켓 바이트 → HTTP 파싱 → scope/receive/send 조립
  → `await app(...)`. `handle_connection`이 await마다 프레임을 내려놓는 것이
  트레이스의 주인공이고, `await reader.readline()` 한 줄 뒤에 "transport가 바이트를
  버퍼에 넣고 Future를 완료시켜 Task.__wakeup을 예약하는" 릴레이가 숨어 있다.
- **mini_framework.py** — 프레임워크의 일: 라우팅 → `_read_body` → 핸들러 호출 →
  `_respond`. `MiniAPI.__call__` 프레임이 `handle_connection` 위에 얹히는 것이
  콜 스택에서 ASGI 왕복으로 보인다.
- **verify.py** — 사용자의 일: `app`/`hello`/`echo` 정의. run.py의 driver가
  `check()`와 같은 방식(create_task(serve) → sleep(0.2) → open_connection)으로
  각본을 수행한다.
