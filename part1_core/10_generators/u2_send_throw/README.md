# u2. send / throw / close — yield는 양방향이다

## 지도 확인

u1에서 `yield`를 **값을 내보내는** 것으로만 봤다.
그런데 `yield`는 **표현식**이라 값을 받을 수도 있다.

```python
x = yield 1        # 1을 내보내고, 받은 값을 x에 넣는다
```

이 양방향성이 제너레이터를 "값을 만드는 것"에서
**"멈췄다 재개할 수 있는 실행 흐름"**으로 바꾼다.
그게 코루틴이고, `async`/`await`의 직접적 전신이다. 24장의 토대가 되는 유닛이다.

## 개념 1 — yield는 표현식이다

```python
def echo():
    while True:
        received = yield        # 받은 값을 변수에 담는다
        print(f"받음: {received}")

g = echo()
next(g)              # 첫 yield까지 진행 (필수!)
g.send("hello")      # 받음: hello
g.send("world")      # 받음: world
```

`g.send(x)`가 하는 일:
1. 멈춰 있던 `yield` 표현식의 **값으로 `x`를 넣는다**
2. 다음 `yield`까지 **실행을 재개한다**
3. 다음 `yield`가 내보낸 값을 **반환한다**

즉 `send`는 **값을 주면서 동시에 값을 받는다.**

## 개념 2 — 첫 next()가 필요한 이유 (priming)

```python
g = echo()
g.send("hello")      # TypeError: can't send non-None value to a just-started generator
```

제너레이터를 막 만들면 **아직 첫 `yield`에 도착하지 않았다.**
값을 받을 자리(`yield` 표현식)가 없는 상태다.

그래서 먼저 `next(g)`나 `g.send(None)`으로 **첫 yield까지 진행**시켜야 한다.
이걸 priming(점화)이라고 부른다.

```python
g = echo()
next(g)              # priming — 첫 yield까지
g.send("hello")      # 이제 가능
```

`next(g)`는 사실 `g.send(None)`과 같다.

## 개념 3 — 값을 주고받는 흐름

```python
def accumulator():
    total = 0
    while True:
        n = yield total       # total을 내보내고, n을 받는다
        total += n

acc = accumulator()
print(next(acc))       # 0    (첫 total 내보냄)
print(acc.send(10))    # 10   (10을 받아 더하고, 새 total 내보냄)
print(acc.send(5))     # 15
print(acc.send(3))     # 18
```

한 줄 `n = yield total`에서 **두 방향**이 일어난다.

```
        ┌── total 내보냄 ──→ 호출자
n = yield total
        ←── send(n) 받음 ──┘
```

07장에서 클로저로 상태를 유지한 것과 비슷한데, 여기서는
**프레임 자체가 상태**라 `nonlocal` 같은 게 필요 없다.

## 개념 4 — throw: 밖에서 예외 던지기

```python
def worker():
    while True:
        try:
            item = yield
            print(f"처리: {item}")
        except ValueError as e:
            print(f"오류 처리: {e}, 계속 진행")

w = worker()
next(w)
w.send("a")                      # 처리: a
w.throw(ValueError("문제 발생"))   # 오류 처리: 문제 발생, 계속 진행
w.send("b")                      # 처리: b — 살아있다
```

`g.throw(예외)`는 **멈춰 있던 `yield` 지점에서 예외가 발생한 것처럼**
만든다. 제너레이터가 잡으면 계속 진행하고, 안 잡으면 밖으로 전파된다.

## 개념 5 — close: 정리하고 종료

```python
def resource_gen():
    print("자원 획득")
    try:
        while True:
            yield "데이터"
    finally:
        print("자원 해제")      # close될 때 실행

g = resource_gen()
next(g)                 # 자원 획득
g.close()               # 자원 해제
```

`g.close()`는 멈춰 있던 지점에서 `GeneratorExit` 예외를 던진다.
`finally` 블록이 실행되므로 **정리 코드를 보장**할 수 있다.

**주의**: `GeneratorExit`를 잡고 계속 `yield`하면 `RuntimeError`가 난다.
정리만 하고 나가야 한다.

제너레이터가 GC될 때도 자동으로 `close()`가 호출된다.
이게 11장(컨텍스트 매니저)의 `@contextmanager`가 동작하는 원리이기도 하다.

## 개념 6 — yield from의 진짜 역할

u1에서 `yield from x`를 "`for i in x: yield i`의 축약"이라고 했다.
**단순 축약이 아니다.**

```python
def inner():
    while True:
        x = yield
        print(f"inner 받음: {x}")

def outer():
    yield from inner()       # send를 하위로 위임

o = outer()
next(o)
o.send("hello")              # inner 받음: hello  ← inner까지 전달됨
```

`yield from`은 **투명한 통로**를 만든다.

- 하위 제너레이터의 `yield` 값이 그대로 위로 나간다
- 위에서 온 `send`/`throw`가 그대로 하위로 내려간다
- 하위가 끝나면 그 `return` 값이 `yield from`의 결과가 된다

```python
def inner():
    yield 1
    yield 2
    return "완료"           # 제너레이터도 return 가능!

def outer():
    result = yield from inner()
    print(f"inner의 반환값: {result}")

list(outer())               # inner의 반환값: 완료
```

**이 위임 기능이 `await`의 원형이다.** `await coro`는 개념적으로
"이 코루틴에게 제어를 넘기고, 끝나면 결과를 받는다"인데,
`yield from`이 정확히 그 일을 한다.

## 개념 7 — 그래서 코루틴이란

제너레이터를 **값 생성**이 아니라 **실행 흐름 제어**로 쓰면 코루틴이 된다.

| | 서브루틴(일반 함수) | 코루틴(제너레이터) |
|---|---|---|
| 진입점 | 하나 (처음부터) | 여러 개 (재개 지점마다) |
| 제어권 | 반환하면 완전히 넘김 | 양보했다가 다시 받음 |
| 상태 | 반환하면 소멸 | 프레임이 보존됨 |
| 관계 | 호출자-피호출자 (수직) | 대등한 협력 (수평) |

핵심은 **협조적 멀티태스킹**이다. OS가 강제로 스레드를 전환하는 게 아니라
(21장의 선점형), 코드가 스스로 "여기서 양보하겠다"고 표시한다.

```python
def task_a():
    for i in range(3):
        print(f"A: {i}")
        yield              # 여기서 양보

def task_b():
    for i in range(3):
        print(f"B: {i}")
        yield

# 손으로 만든 스케줄러
tasks = [task_a(), task_b()]
while tasks:
    for t in list(tasks):
        try:
            next(t)        # 각 태스크를 한 스텝씩
        except StopIteration:
            tasks.remove(t)
```

**이게 이벤트 루프의 원형이다.** asyncio는 이 구조에
"IO가 준비됐는지 확인하는 부분"을 붙인 것이다 (24장).

## 개념 8 — 역사: yield from에서 async/await로

```python
# 3.4 — 제너레이터 기반 코루틴
@asyncio.coroutine
def fetch():
    data = yield from read()
    return data

# 3.5+ — 전용 문법 (같은 원리)
async def fetch():
    data = await read()
    return data
```

`async def`는 `yield from` 기반 코루틴에 **전용 문법과 타입**을 준 것이다.
내부 메커니즘은 같다 — 프레임을 보존하고, 양보하고, 재개한다.

차이는 안전성이다. 제너레이터 기반은 "이게 값 생성용인지 코루틴용인지"
구분이 안 됐는데, `async def`는 타입이 분리돼 실수를 막는다.

## 자바와 비교 — "가상 스레드가 방향은 비슷하다"

자바에는 오랫동안 이 기능이 없었다. 비동기는 콜백이나 `CompletableFuture`
체인으로 처리했고, 이게 "콜백 지옥"의 원인이었다.

Java 21의 **가상 스레드(Virtual Thread)**가 방향은 비슷하다.
스레드를 아주 가볍게 만들어 블로킹 코드를 그대로 쓰면서도 수만 개를
동시에 돌린다.

| | 파이썬 코루틴 | 자바 가상 스레드 |
|---|---|---|
| 양보 지점 | `await`로 **명시적** | 블로킹 호출에서 **암묵적** |
| 코드 변경 | `async`/`await` 전면 수정 | 기존 코드 그대로 |
| 함수 색깔 | async 함수는 async에서만 호출 | 구분 없음 |

파이썬은 "어디서 양보하는지 코드에 보인다"는 장점과 "async가 전염된다"는
단점을 동시에 갖는다. 자바 가상 스레드는 그 반대다.

## 백엔드 관점

- `send`를 직접 쓸 일은 드물다. **asyncio가 내부적으로 쓴다**는 걸
  아는 게 목적이다. `await`가 어떻게 값을 받아오는지의 원리다.
- `close`와 `finally`는 실무에서 중요하다. 제너레이터로 DB 커서나 파일을
  들고 있다가 소비자가 중간에 멈추면, `close`가 정리를 보장한다.
- FastAPI의 `Depends`에서 `yield`를 쓰는 의존성이 정확히 이 구조다.
```python
  def get_db():
      db = SessionLocal()
      try:
          yield db          # 요청 처리 중 여기서 멈춤
      finally:
          db.close()        # 응답 후 재개되어 정리
```
  요청이 끝나면 프레임이 재개되어 `finally`가 실행된다.
- 11장 `@contextmanager`도 같은 원리다. `yield` 앞이 `__enter__`,
  뒤가 `__exit__`.

## 실무 규칙

- `send`를 쓰기 전에 **priming**(첫 `next`)을 잊지 않는다.
- 자원을 들고 있는 제너레이터는 `try/finally`로 정리를 보장한다.
- 값 생성이 목적이면 제너레이터, 동시성이 목적이면 `async def`를 쓴다.
  제너레이터로 코루틴을 흉내내는 건 이제 레거시다.

## 3문장 요약 (직접 작성)

1.
2.
3.