# u1. 제너레이터 — 프레임을 살려둔 채 나가기

## 지도 확인

00장 u4에서 **프레임은 호출할 때 생기고 반환하면 소멸**한다고 했다.
07장에서 클로저가 cell로 **변수만** 살려두는 걸 봤다.

제너레이터는 한 걸음 더 간다. **프레임 자체를 통째로 살려둔다.**
실행 위치, 지역 변수, 값 스택이 전부 보존된 채로 함수 밖으로 나갔다가,
다음 호출에서 **그 자리부터 이어서** 실행된다.

이게 24~25장 asyncio의 뿌리다. 코루틴은 제너레이터의 직계 후손이다.

## 개념 1 — yield가 있으면 함수가 아니다

```python
def gen():
    yield 1
    yield 2

g = gen()          # 본문이 실행되지 않는다!
print(g)           # <generator object gen at 0x...>
```

함수 본문에 `yield`가 하나라도 있으면, 그 `def`는 **일반 함수가 아니라
제너레이터 함수**가 된다. 호출해도 본문이 실행되지 않고
**제너레이터 객체**가 반환된다.

컴파일 시점에 이미 결정된다.

```python
gen.__code__.co_flags & 0x20    # CO_GENERATOR 플래그
```

## 개념 2 — 실행은 next()가 시작한다

```python
def gen():
    print("A")
    yield 1
    print("B")
    yield 2
    print("C")

g = gen()
print("생성됨")     # 여기까지 아무것도 출력 안 됨
next(g)            # "A" 출력 → 1 반환
next(g)            # "B" 출력 → 2 반환
next(g)            # "C" 출력 → StopIteration
```

`next()`를 부를 때마다 **다음 `yield`까지 실행하고 멈춘다.**
멈춘 자리는 기억된다. 다음 `next()`는 거기서 이어간다.

**`yield`는 "값을 내놓고 일시정지"다.** `return`은 "값을 내놓고 종료"고.

## 개념 3 — 프레임이 살아있다는 증거

```python
import inspect

def gen():
    x = 10
    yield x
    x = 20
    yield x

g = gen()
next(g)                          # 첫 yield에서 멈춤
print(g.gi_frame)                # 프레임 객체가 있다!
print(g.gi_frame.f_locals)       # {'x': 10} — 지역 변수 보존
print(g.gi_frame.f_lasti)        # 마지막 실행 명령 위치
print(inspect.getgeneratorstate(g))   # GEN_SUSPENDED
```

일반 함수는 반환하면 프레임이 사라지지만, 제너레이터는 **프레임이
제너레이터 객체에 붙어서 보존된다.** 그래서:

- 지역 변수가 그대로 남는다
- 어느 줄까지 실행했는지 기억한다
- 값 스택 상태도 유지된다

00장 u4에서 "호출할 때마다 프레임이 생기고 반환하면 소멸"이라고 했던 것의
**유일한 예외**다. 정확히는 소멸하는 대신 **콜 스택에서 떼어내 보관**한다.

```
일반 함수 호출              제너레이터
콜 스택                    콜 스택
┌────────┐                ┌────────┐
│ caller │                │ caller │
├────────┤                └────────┘
│ callee │ ← 반환 시 소멸        ↓ next()마다 붙였다 뗐다
└────────┘                ┌────────┐
                          │  gen   │ ← 제너레이터 객체가 보관
                          └────────┘
```

## 개념 4 — 03장 이터레이터 클래스와 비교

03장 u1에서 `Reverse`를 만들 때 클래스 두 개가 필요했다.

```python
class Reverse:
    def __init__(self, data):
        self.data = data
    def __iter__(self):
        return ReverseIterator(self.data)

class ReverseIterator:
    def __init__(self, data):
        self.data = data
        self.index = len(data)      # ← 상태를 인스턴스 속성에 저장
    def __iter__(self):
        return self
    def __next__(self):
        if self.index <= 0:
            raise StopIteration
        self.index -= 1
        return self.data[self.index]
```

제너레이터로 쓰면:

```python
def reverse(data):
    for i in range(len(data) - 1, -1, -1):
        yield data[i]
```

**클래스 두 개와 메서드 다섯 개가 함수 셋 줄이 됐다.**

차이의 본질: 이터레이터 클래스는 **상태를 인스턴스 속성에 수동으로 저장**하는데,
제너레이터는 **프레임이 상태를 자동으로 보존**한다. `index`를 직접 관리할
필요가 없다 — 실행 위치 자체가 상태이기 때문이다.

`StopIteration`도 자동이다. 함수가 끝나면 파이썬이 알아서 던진다.

## 개념 5 — 제너레이터는 이터레이터다

03장의 구분(이터러블 vs 이터레이터)에서 제너레이터는 **이터레이터** 쪽이다.

```python
g = gen()
iter(g) is g           # True — 자기 자신 반환
hasattr(g, "__next__") # True
list(g)                # [1, 2]
list(g)                # []  ← 소진됨!
```

**한 번 쓰면 끝난다.** 03장 u1 유제 2에서 본 그 함정이 그대로 적용된다.

여러 번 순회해야 하면 **제너레이터 함수를 다시 호출**하거나,
`list()`로 실체화한다.

```python
def numbers():
    yield from [1, 2, 3]

list(numbers())    # [1, 2, 3]
list(numbers())    # [1, 2, 3]  ← 매번 새 제너레이터
```

## 개념 6 — 메모리: 왜 쓰는가

제너레이터의 실전 가치는 **한 번에 하나만 메모리에 둔다**는 것이다.

```python
import sys

lst = [i * i for i in range(1_000_000)]      # 리스트 컴프리헨션
gen = (i * i for i in range(1_000_000))      # 제너레이터 표현식

sys.getsizeof(lst)    # 8MB 이상
sys.getsizeof(gen)    # 200바이트 미만
```

리스트는 백만 개를 다 만들어 저장하고, 제너레이터는 **요청할 때 하나씩
계산**한다. 01장 u1에서 본 객체 하나당 28바이트가 백만 개면 어떻게 되는지
생각하면 차이가 명확하다.

**무한 시퀀스도 가능하다.**

```python
def naturals():
    n = 0
    while True:
        yield n
        n += 1

from itertools import islice
list(islice(naturals(), 5))    # [0, 1, 2, 3, 4]
```

리스트로는 불가능한 일이다.

## 개념 7 — 파이프라인

제너레이터를 이어붙이면 **각 단계가 한 항목씩만 처리**하는 파이프라인이 된다.

```python
def read_lines(path):
    with open(path) as f:
        for line in f:
            yield line.rstrip()

def filter_errors(lines):
    for line in lines:
        if "ERROR" in line:
            yield line

def parse(lines):
    for line in lines:
        parts = line.split(" ", 2)
        yield {"date": parts[0], "level": parts[1], "msg": parts[2]}

for record in parse(filter_errors(read_lines("app.log"))):
    print(record)
```

100GB 파일이어도 메모리는 한 줄 분량만 쓴다. 각 단계가 **필요할 때만
윗단계에 요청**하기 때문이다 (당기는 방식, pull-based).

이게 03장 u1 유제 4에서 zip이 게으르게 동작했던 것과 같은 원리다.

## 개념 8 — yield from

제너레이터 안에서 다른 이터러블을 그대로 흘려보낸다.

```python
def flatten(nested):
    for item in nested:
        if isinstance(item, list):
            yield from flatten(item)      # 재귀
        else:
            yield item

list(flatten([1, [2, [3, 4]], 5]))    # [1, 2, 3, 4, 5]
```

`yield from x`는 `for i in x: yield i`의 축약이다. 다만 단순 축약이
아니라 **`send`/`throw`도 하위 제너레이터에 위임**한다. 이 위임 기능이
`async`/`await`의 전신이 됐다 (24장).

## 자바와 비교 — "없는 기능이다"

자바에는 제너레이터가 없다. 같은 일을 하려면 `Iterator`를 직접 구현하며
**상태를 필드로 관리**해야 한다.

```java
class Fib implements Iterator<Integer> {
    private int a = 0, b = 1;        // 상태를 수동으로
    public boolean hasNext() { return true; }
    public Integer next() {
        int r = a; int t = a + b; a = b; b = t;
        return r;
    }
}
```

파이썬은 세 줄이다.

```python
def fib():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b
```

**핵심 차이**: 자바는 "다음 값을 계산하는 함수"를 매번 처음부터 실행하므로
상태를 밖에 저장해야 한다. 파이썬은 **실행을 멈췄다 재개**하므로 상태가
코드의 위치와 지역 변수에 자연히 남는다.

자바 Stream(8+)이 지연 평가를 제공하지만, 그건 미리 정의된 연산 조합이고
제너레이터처럼 임의의 제어 흐름(반복문, 조건문, 재귀)을 쓸 수는 없다.

Java 21의 가상 스레드나 Loom 프로젝트가 방향은 비슷하지만 목적이 다르다.

## 백엔드 관점

- **대용량 파일/DB 처리**: 100만 행 CSV를 `readlines()`로 읽으면 메모리가
  터지지만, 제너레이터로 흘리면 상수 메모리다.
- **SQLAlchemy `yield_per`**, Django `iterator()`가 이 원리다.
  전체를 메모리에 올리지 않고 커서에서 배치로 가져온다.
- **FastAPI `StreamingResponse`**: 제너레이터를 반환하면 응답을 조금씩
  흘려보낸다. 대용량 다운로드나 SSE(서버 전송 이벤트)에 쓴다.
- **ETL 파이프라인**: 읽기 → 필터 → 변환 → 저장을 제너레이터 체인으로
  구성하면 각 단계가 독립적이고 메모리가 일정하다.
- 주의: **한 번만 순회 가능**하다는 걸 잊으면 "두 번째 루프가 안 돈다"는
  버그가 난다 (03장 u1).

## 실무 규칙 (EP 연결)

- 리스트를 만들어 반환하는 함수가 크다면 제너레이터로 바꾼다 (EP Item 43).
- 제너레이터를 반환한다는 걸 **문서화**한다. 호출자가 재순회를 시도할 수 있다.
- 여러 번 순회해야 하면 이터러블(컨테이너나 팩토리)을 받는다 (EP Item 44).
- 제너레이터 표현식 `(x for x in y)`는 대괄호 버전보다 메모리를 아낀다 (EP Item 45).

## 3문장 요약 (직접 작성)

1. 제너레이터는 yield를 가진 함수가 반환하는 객체이다.
2. 내부적으로 제너레이터 객체 안에 프레임을 저장하기때문에 함수가 yield에 의해 중단되어도 중단된 위치까지의 값을 가지기 때문에 이어서 실행될 수 있다.
3.제너레이터는 한 번에 하나의 값만 메모리에 두고, 나머지는 요청받을 때 계산하기때문에 효율적이다.