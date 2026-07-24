# asynclab — 코루틴·이벤트 루프를 눈으로 보는 학습 도구

**코루틴은 진짜(`async def`)를 쓰고, 이벤트 루프와 네트워크만 재현한다.** 태스크
본문은 네이티브 코루틴이고 `cr_frame.f_lineno`(멈춘 줄)·`cr_await`(대기 사슬)·
`cr_suspended`(보관 여부)를 실제로 읽어서 표시한다. 재현한 것은 미니 루프
(준비큐·타이머 힙·셀렉터 장부)와 각본(scripted) 네트워크뿐이다. pvmlab이
"바이트코드 한 명령"을 스테핑했다면, asynclab은 **"이벤트 루프 한 사건"** 을
스테핑한다.

## 개념 모델 — 다섯 층

| 층 | 실체 | 성질 |
|---|---|---|
| 코드 객체 | `coro.cr_code` 그대로 | 불변·공유. 손님 A/B의 코루틴이 같은 카드 하나를 가리킨다 |
| 함수 객체 | `async def`한 것 그대로 | 호출하면 실행되지 않고 코루틴 객체가 나온다 |
| 코루틴 객체 | 진짜 네이티브 코루틴 | **보관된 프레임**. 멈춘 줄(`f_lineno`)이 곧 연결의 상태 |
| MiniTask | 엔진이 구현 | 코루틴을 콜백(`step`)으로 **번역**하는 어댑터 — 큐에 들어가는 건 이것 |
| MiniEventLoop | 엔진이 구현 | 콜 스택의 **상주 프레임**. 단일 while = SELECT → WAKE → RUN |

시나리오는 metric-lab `mini_server`+`mini_framework`의 축약판: 손님 A가 먼저
접속하지만 바이트는 B가 먼저 도착한다 — **나중에 온 B가 먼저 끝난다**. "A가
느려도 B는 안 막힌다"가 화면에서 증명된다.

## 실행

```bash
cd tools/asynclab
python run.py                 # 검증 3종 → asynclab_trace.html
python run.py -o out.html     # 출력 경로 지정
```

검증(하나라도 실패하면 HTML을 만들지 않는다):
① 미니 루프 응답 == 기대 바이트 ② 같은 `handle_connection`/`MiniAPI`를 **진짜
asyncio**(`StreamReader.feed_data`) 위에서 돌려도 같은 응답 ③ 두 번 실행한
트레이스의 재개 순서 동일(결정성).

## 구조

```
run.py                유일한 진입점 (엔진 모듈을 직접 실행하지 말 것)
engine/
  loop.py             MiniEventLoop — 준비큐/타이머 힙/셀렉터 장부, 단일 while
  task.py             MiniTask — 코루틴을 콜백(step)으로 번역
  selector.py         ScriptedSelector — 각본 재생기 = 가짜 OS (수신 버퍼·backlog)
  channel.py          MiniListener/Reader/Writer — 튜플 신호를 yield하는 awaitable
  tracer.py           매 사건마다 전 계층 스냅샷 (코루틴 속성은 관찰, 재현 아님)
demos/mini_web.py     관찰 대상 — handle_connection + MiniAPI (~80줄)
viewer.py             트레이스 → 단일 자족 HTML (6패널, ←/→ 스테핑)
```

## pvmlab eventloop.py와의 관계

pvmlab의 `eventloop.py`는 제너레이터+가상 시계로 **스케줄링의 원리**(보관된
프레임들을 번갈아 재개한다)를 보였다. asynclab은 그 다음 층이다: 진짜 코루틴 +
셀렉터 장부 + Task 어댑터로 **asyncio의 구조**를 보인다 — 루프는 상주 프레임이고,
큐에 들어가는 건 코루틴이 아니라 콜백이며, "응답이 온 걸 아는" 주체는 파이썬이
아니라 OS(셀렉터)다.
