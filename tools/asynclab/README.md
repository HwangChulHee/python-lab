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
A보다 앞선다. 스텝마다 요약 한 줄 + 쉬운 개념 해설 + "지금 볼 곳"(어느 패널의
어떤 데이터) 목록이 붙는다.

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

## 미니 루프와 진짜의 대응 (pvmlab eventloop.py → asynclab)

pvmlab `eventloop.py`가 제너레이터+가상 시계로 스케줄링 원리를 보였다면, asynclab은
진짜 asyncio에서 그 각 부품이 어디에 있는지 보인다: 준비큐=`loop._ready`(Handle),
장부=셀렉터에 등록된 transport 콜백, 태스크의 신호=튜플이 아니라 `_fut_waiter`
(Future), 재개=`Task.__step`/`__wakeup`. 미니에서 한 겹이던 "fd → task 깨우기"가
진짜에서는 "fd → transport._read_ready → StreamReader/Future 완료 → Task.__wakeup"
릴레이로 두꺼워진 것을 트레이스에서 확인할 수 있다.
