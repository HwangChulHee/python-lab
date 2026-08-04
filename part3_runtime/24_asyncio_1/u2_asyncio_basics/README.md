# u2. asyncio 실전 — run, task, gather

## 지도 확인

u1에서 이벤트 루프의 원리를 봤다. 이제 실제 API를 쓴다.
`asyncio.run`, `create_task`, `gather`가 각각 무엇을 하는지,
그리고 코루틴과 태스크의 차이가 무엇인지 정리한다.

## 개념 1 — 진입점: asyncio.run

```python
async def main():
    ...

asyncio.run(main())
```

`asyncio.run`이 하는 일:
1. 새 이벤트 루프를 만든다
2. `main()` 코루틴을 실행한다
3. 끝나면 루프를 닫고 정리한다

**프로그램당 한 번만 호출**하는 게 원칙이다. 이미 루프가 도는 중에
호출하면 `RuntimeError`가 난다.

```python
async def bad():
    asyncio.run(other())     # RuntimeError!
```

Jupyter나 FastAPI 안에서는 이미 루프가 돌고 있으므로 `run`을 쓰지 않는다.
그냥 `await`한다.

## 개념 2 — 코루틴 vs 태스크

**코루틴 객체**는 아직 실행되지 않은 "실행 계획"이다.

```python
coro = fetch()          # 아직 아무 일도 안 함
await coro              # 여기서 실행
```

**태스크**는 이벤트 루프에 **등록된** 실행 단위다.

```python
task = asyncio.create_task(fetch())    # 즉시 스케줄됨
result = await task                     # 완료를 기다림
```

결정적 차이: `create_task`는 **바로 실행을 시작**시킨다.

```python
# 순차 실행 — 0.3초
await fetch("A", 0.1)
await fetch("B", 0.2)

# 동시 실행 — 0.2초
t1 = asyncio.create_task(fetch("A", 0.1))
t2 = asyncio.create_task(fetch("B", 0.2))
await t1
await t2
```

두 번째는 `create_task` 시점에 둘 다 시작되고, `await`는 결과를 회수할 뿐이다.

## 개념 3 — gather: 여러 개를 한 번에

```python
results = await asyncio.gather(
    fetch("A"), fetch("B"), fetch("C")
)
# results = [A결과, B결과, C결과]  ← 순서 보장
```

`gather`는 넘긴 코루틴들을 전부 태스크로 만들어 동시 실행하고,
**모두 끝나면** 결과를 리스트로 돌려준다. **입력 순서대로** 정렬된다.

**예외 처리가 중요하다.**

```python
# 기본: 하나라도 실패하면 즉시 예외 전파
results = await asyncio.gather(a(), b(), c())

# 예외도 결과로 받기
results = await asyncio.gather(a(), b(), c(), return_exceptions=True)
# [결과, ValueError(...), 결과]
```

기본 동작에서는 하나가 실패해도 **나머지는 계속 실행된다**(취소되지 않는다).
결과만 못 받을 뿐이다. 이게 자원 누수의 원인이 되기도 한다.

## 개념 4 — TaskGroup (3.11+, 권장)

```python
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(fetch("A"))
    t2 = tg.create_task(fetch("B"))
# 블록을 나갈 때 모두 완료됨

print(t1.result(), t2.result())
```

`gather`보다 나은 점:
- 하나가 실패하면 **나머지를 자동 취소**한다
- 블록을 벗어날 때 모든 태스크가 완료됨을 보장한다 (누수 없음)
- 여러 예외를 `ExceptionGroup`으로 모아준다

**3.11+에서는 TaskGroup을 쓰는 게 권장**이다. 구조적 동시성
(structured concurrency)이라 부르는 패턴이다.

## 개념 5 — 태스크를 놓치면 안 된다

```python
asyncio.create_task(background_job())    # 위험!
```

태스크 객체를 어디에도 저장하지 않으면 **가비지 컬렉션될 수 있다**.
이벤트 루프는 태스크를 약한 참조로만 들고 있기 때문이다.

```python
background_tasks = set()

task = asyncio.create_task(background_job())
background_tasks.add(task)
task.add_done_callback(background_tasks.discard)
```

FastAPI의 `BackgroundTasks`가 이 관리를 대신해준다.

## 개념 6 — 흔한 실수들

**(1) await 빠뜨리기**

```python
async def main():
    fetch()          # 코루틴이 만들어지고 버려짐
    # RuntimeWarning: coroutine 'fetch' was never awaited
```

경고가 나오지만 프로그램은 계속 돈다. 조용한 버그가 된다.

**(2) 동기 함수에서 코루틴 호출**

```python
def sync_func():
    result = fetch()      # 코루틴 객체를 받을 뿐, 실행 안 됨
```

`async def` 안에서만 `await`할 수 있다. "함수 색깔 문제"라 부른다.

**(3) 루프에서 순차 await**

```python
# 나쁨 — 순차 실행
results = []
for url in urls:
    results.append(await fetch(url))

# 좋음 — 동시 실행
results = await asyncio.gather(*[fetch(url) for url in urls])
```

이게 asyncio를 쓰면서도 효과를 못 보는 가장 흔한 원인이다.

**(4) 동시성 제한 없이 수천 개 실행**

```python
await asyncio.gather(*[fetch(u) for u in 10000_urls])   # 상대 서버 폭격
```

`asyncio.Semaphore`로 제한한다.

```python
sem = asyncio.Semaphore(20)

async def limited_fetch(url):
    async with sem:
        return await fetch(url)
```

## 개념 7 — 동기 코드와 섞기

**동기 함수를 async에서 호출**: 짧으면 그냥 호출, 길면 executor로.

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_func, arg)
# 또는 3.9+
result = await asyncio.to_thread(blocking_func, arg)
```

이게 21장 u2 유제 4(d)에서 나온 "PDF 생성" 문제의 해법 중 하나다.
CPU 작업이면 `ProcessPoolExecutor`를 넘긴다.

25장에서 자세히 다룬다.

## 자바와 비교

| | 자바 CompletableFuture | asyncio |
|---|---|---|
| 여러 개 대기 | `allOf(...)` | `gather(...)` |
| 즉시 시작 | `supplyAsync` | `create_task` |
| 결과 회수 | `.get()` / `.join()` | `await task` |
| 예외 | `exceptionally` | try/except |
| 스레드 | 스레드풀에서 실행 | **단일 스레드** |

가장 큰 차이는 실행 주체다. `CompletableFuture`는 스레드풀에서 진짜
병렬로 돌지만, asyncio는 한 스레드에서 번갈아 돈다.

## 백엔드 관점

- **마이크로서비스 호출 병렬화**가 가장 흔한 사용처다.
```python
  user, orders, prefs = await asyncio.gather(
      get_user(uid), get_orders(uid), get_prefs(uid)
  )
```
  순차로 하면 300ms인 게 100ms가 된다.
- FastAPI 엔드포인트를 `async def`로 쓰면 이벤트 루프에서 돈다.
  **비동기 드라이버를 써야 의미가 있다** (asyncpg, httpx, aioredis).
- 외부 API 호출에는 반드시 `Semaphore`로 동시성을 제한하고
  타임아웃을 건다 (25장).
- 배경 작업은 태스크 참조를 유지하거나 작업 큐로 넘긴다.

## 실무 규칙

- 3.11+면 `gather`보다 `TaskGroup`을 쓴다.
- 루프 안에서 `await`하지 말고 `gather`로 묶는다.
- `create_task` 결과는 반드시 어딘가에 저장한다.
- 동시 요청 수는 `Semaphore`로 제한한다.
- `async def` 안에서 동기 블로킹 호출을 하지 않는다 (25장).

## 3문장 요약 (직접 작성)

1.
2.
3.