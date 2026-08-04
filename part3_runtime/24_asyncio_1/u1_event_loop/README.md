# u1. 이벤트 루프를 직접 만들어본다

## 지도 확인

10장 u2 유제 5에서 손으로 스케줄러를 만들었다. 태스크들을 돌아가며
한 스텝씩 실행하는 구조였다. 그런데 그건 "그냥 번갈아 실행"일 뿐이었다.

**실제 이벤트 루프는 하나가 더 있다: "이 태스크가 지금 실행 가능한가"를
확인하는 부분.** IO를 기다리는 태스크는 건너뛰고, 준비된 것만 깨운다.

이 유닛은 그 차이를 메우고, `async`/`await`가 결국 제너레이터의
`yield`/`send` 위에 세워진 문법임을 확인한다.

## 개념 1 — 왜 이벤트 루프인가

21장에서 IO-bound에는 스레드가 효과적이라고 했다. 그런데 문제가 있다.

- 스레드 하나당 스택 ~8MB. 동시 연결 1만 개면 메모리가 안 된다.
- OS가 스레드를 전환하는 비용(컨텍스트 스위칭)이 있다.
- 공유 상태에 락이 필요하다 (21장 u1).

**이벤트 루프의 발상**: 스레드는 하나만 쓰되, IO를 기다리는 동안
다른 일을 한다. 어차피 대기 중에는 CPU가 노니까.

```
스레드 방식              이벤트 루프 방식
스레드1: [요청][대기][처리]   루프: [요청A][요청B][요청C]
스레드2: [요청][대기][처리]         [A준비?][B준비?][C준비?]
스레드3: [요청][대기][처리]         [A처리][C처리][B처리]
→ 스레드 3개, 메모리 24MB   → 스레드 1개, 코루틴 3개 (수 KB)
```

**핵심 조건**: 한 태스크가 CPU를 오래 붙들면 안 된다.
전부 한 스레드에서 도니까, 하나가 막히면 전부 막힌다 (25장 주제).

## 개념 2 — 협조적 vs 선점적

| | 스레드 (21장) | 코루틴 |
|---|---|---|
| 전환 시점 | OS가 결정 (5ms 등) | **코드가 `await`에서 양보** |
| 방식 | 선점형(preemptive) | 협조형(cooperative) |
| 예측 | 어디서 끊길지 모름 | **양보 지점이 코드에 보임** |
| 락 필요 | 필요 | 대부분 불필요 |

**락이 대부분 불필요한 이유**: `await` 없는 구간은 절대 중간에 끊기지 않는다.
21장의 `count += 1` 문제가 코루틴에서는 안 생긴다. `await`가 없으면
그 사이에 다른 코루틴이 끼어들 수 없기 때문이다.

```python
async def increment():
    global count
    count += 1        # await가 없으므로 원자적으로 실행됨
```

단, `await`를 사이에 끼우면 얘기가 달라진다.

```python
async def bad():
    global count
    temp = count
    await something()     # ← 여기서 다른 코루틴이 count를 바꿀 수 있다
    count = temp + 1
```

## 개념 3 — 최소 이벤트 루프 만들기

10장 u2의 스케줄러에 "준비됐는지 확인"을 붙이면 된다.

```python
import time
import heapq

class MiniLoop:
    def __init__(self):
        self.ready = []       # 지금 실행 가능한 태스크
        self.sleeping = []    # 시간을 기다리는 태스크 (힙)

    def call_soon(self, task):
        self.ready.append(task)

    def call_later(self, delay, task):
        heapq.heappush(self.sleeping, (time.time() + delay, id(task), task))

    def run(self):
        while self.ready or self.sleeping:
            # 1) 깨어날 시간이 된 것들을 ready로 옮긴다
            now = time.time()
            while self.sleeping and self.sleeping[0][0] <= now:
                _, _, task = heapq.heappop(self.sleeping)
                self.ready.append(task)

            # 2) ready가 비었으면 가장 가까운 깨울 시각까지 잔다
            if not self.ready and self.sleeping:
                time.sleep(self.sleeping[0][0] - now)
                continue

            # 3) ready에서 하나 꺼내 한 스텝 실행
            task = self.ready.pop(0)
            try:
                delay = task.send(None)      # 코루틴을 재개
                if delay is None:
                    self.ready.append(task)  # 즉시 재실행
                else:
                    self.call_later(delay, task)
            except StopIteration:
                pass                          # 태스크 완료
```

**10장 u2의 스케줄러와 딱 두 가지가 다르다.**
1. 태스크가 `yield`로 "얼마나 기다릴지"를 알려준다
2. 루프가 그 시간을 관리해서 준비된 것만 `ready`에 넣는다

실제 asyncio는 시간 대신 **소켓 준비 상태**(`select`/`epoll`)를 확인한다.
"이 소켓에 읽을 데이터가 왔나?"를 OS에 물어보는 것이다 (23장 주제).

## 개념 4 — async def는 제너레이터의 후손이다

```python
async def hello():
    return 1

h = hello()
print(h)                    # <coroutine object hello at 0x...>
```

**호출해도 실행되지 않는다.** 코루틴 객체가 반환될 뿐이다.
10장 u1에서 제너레이터가 그랬던 것과 똑같다.

```python
h.send(None)                # 여기서 실제 실행 → StopIteration(1)
```

`send`로 재개하고 `StopIteration`으로 끝난다. **제너레이터와 같은 프로토콜이다.**

```python
import inspect
inspect.iscoroutinefunction(hello)      # True
hello.__code__.co_flags & 0x80          # CO_COROUTINE 플래그
```

10장 u1에서 `yield`가 `CO_GENERATOR` 플래그를 켰듯,
`async def`는 `CO_COROUTINE` 플래그를 켠다.

## 개념 5 — await는 yield from이다

```python
# 3.4 시절 (레거시)
@asyncio.coroutine
def fetch():
    data = yield from read()
    return data

# 3.5+ (현재)
async def fetch():
    data = await read()
    return data
```

`await x`가 하는 일은 10장 u2의 `yield from x`와 같다.

- 하위 코루틴에게 제어를 넘긴다
- 하위가 양보하면 그 양보가 위로 전파된다
- 하위가 끝나면 반환값을 받는다
- `send`/`throw`가 하위로 위임된다

**즉 `await`는 문법이 다를 뿐, 위임 메커니즘은 `yield from`이다.**

차이는 타입 안전성이다. `async def`로 만든 것끼리만 `await`할 수 있어서,
"값 생성용 제너레이터"와 "동시성용 코루틴"이 섞이는 실수를 막는다.

## 개념 6 — 실제로 양보하는 지점

**`await`를 쓴다고 항상 양보하는 게 아니다.**

```python
async def inner():
    return 1                # 즉시 반환 — 양보 없음

async def outer():
    x = await inner()       # 양보 없이 바로 진행
```

양보는 **실제로 기다려야 할 때**만 일어난다. 최종적으로는
`asyncio.sleep`, 소켓 읽기 같은 **저수준 대기 지점**에서 이벤트 루프에
제어가 돌아간다.

```python
await asyncio.sleep(0)      # 관용구: 강제로 한 번 양보
```

이 구분이 25장의 "블로킹" 이해에 중요하다. `await`를 썼는데도
전체가 멈추는 경우가 있는데, 그건 대기가 아니라 **CPU 작업**이거나
**동기 IO**이기 때문이다.

## 개념 7 — 동시성 ≠ 병렬성

**동시성(concurrency)**: 여러 일을 번갈아 처리한다. 논리적으로 동시.
**병렬성(parallelism)**: 여러 일이 물리적으로 동시에 실행된다.

asyncio는 **동시성만** 제공한다. 스레드 하나에서 도니까 병렬이 아니다.
21장의 GIL 논의와 이어지는데 — asyncio는 GIL 문제를 우회하는 게 아니라,
**애초에 CPU를 쓰지 않는 대기 시간을 활용**하는 것이다.

| | 동시성 | 병렬성 |
|---|---|---|
| asyncio | O | X |
| 스레드 (CPython) | O | X (GIL) |
| 프로세스 | O | **O** |

CPU-bound에는 여전히 프로세스가 답이다. asyncio로는 안 된다.

## 자바와 비교

자바의 비동기는 오랫동안 콜백과 `CompletableFuture`였다.

```java
fetchUser(id)
    .thenCompose(user -> fetchOrders(user))
    .thenApply(orders -> summarize(orders))
    .exceptionally(e -> handleError(e));
```

파이썬은 순차 코드처럼 쓴다.

```python
user = await fetch_user(id)
orders = await fetch_orders(user)
return summarize(orders)
```

**가독성이 결정적 차이다.** 콜백 체인은 흐름이 뒤집히지만,
`await`는 동기 코드와 같은 모양을 유지한다.

Java 21 가상 스레드는 또 다른 답이다. 블로킹 코드를 그대로 쓰면서
JVM이 알아서 양보한다. "함수 색깔 문제"(async 함수는 async에서만 호출 가능)가
없다는 게 장점이고, 양보 지점이 코드에 안 보인다는 게 단점이다.

## 백엔드 관점

- FastAPI가 ASGI 기반이라 엔드포인트를 `async def`로 쓰면 이벤트 루프에서 돈다.
  `def`로 쓰면 스레드풀로 밀려난다 (FastAPI가 알아서 처리).
- 동시 연결이 많은 서비스(웹소켓, SSE, 롱폴링)에서 asyncio가 강하다.
  스레드로는 메모리가 감당이 안 된다.
- **DB 드라이버가 비동기를 지원해야 의미가 있다.** `psycopg2`(동기)를
  `async def` 안에서 쓰면 이벤트 루프가 막힌다. `asyncpg`를 써야 한다.
- 마이크로서비스에서 여러 서비스를 동시 호출할 때 `gather`로 묶으면
  대기 시간이 합산이 아니라 최댓값이 된다 (u2).

## 3문장 요약 (직접 작성)

1.
2.
3.