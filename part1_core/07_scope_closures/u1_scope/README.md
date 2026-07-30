# u1. 스코프 — 이름은 어디서 찾는가

## 지도 확인

00장 u3에서 "지역은 `LOAD_FAST`, 전역은 `LOAD_GLOBAL`"까지 봤다.
그런데 명령은 두 개가 아니라 **네 개**다. 중첩 함수가 바깥 변수를 읽을 때
쓰이는 `LOAD_DEREF`가 남아 있고, 그게 다음 유닛(클로저)의 열쇠다.
이번 유닛은 이름 탐색 규칙 전체를 정리하고, `global`/`nonlocal`을 다룬다.

## 개념 1 — LEGB 규칙

이름을 찾는 순서는 안쪽에서 바깥쪽이다.

```
L (Local)      현재 함수의 지역
E (Enclosing)  나를 감싼 함수의 지역     ← 여기가 클로저의 무대
G (Global)     모듈 전역
B (Builtin)    내장 (len, print, ...)
```

```python
x = "global"

def outer():
    x = "enclosing"
    def inner():
        print(x)        # enclosing — E에서 찾음
    inner()
```

**중요**: LEGB는 "실행 중에 네 곳을 차례로 뒤진다"는 뜻이 **아니다.**
대부분 컴파일 시점에 어느 스코프인지 확정되고, 그에 맞는 명령이 박힌다.
실제로 런타임 탐색이 일어나는 건 G → B 두 단계뿐이다 (00장 u3).

## 개념 2 — 네 가지 명령

| 스코프 | 명령 | 결정 시점 | 저장 위치 |
|---|---|---|---|
| Local | `LOAD_FAST` | 컴파일 | 프레임의 배열 (인덱스) |
| Enclosing | `LOAD_DEREF` | 컴파일 | **cell 객체** (u2에서) |
| Global/Builtin | `LOAD_GLOBAL` | 런타임 탐색 | 모듈 dict → builtins dict |
| 모듈 레벨 | `LOAD_NAME` | 런타임 | 지역·전역·내장 순서로 |

`LOAD_NAME`은 모듈 최상단이나 클래스 본문처럼 "지역과 전역이 같은 곳"인
특수한 경우에만 쓰인다. 함수 안에서는 안 나온다.

## 개념 3 — 파이썬은 함수 스코프다 (자바와 결정적 차이)

**자바는 블록 스코프**다. `{}` 안에서 선언한 변수는 그 블록을 벗어나면 사라진다.

```java
if (true) { int x = 1; }
System.out.println(x);    // 컴파일 에러 — x는 블록 밖에서 안 보임
for (int i = 0; i < 3; i++) { }
System.out.println(i);    // 컴파일 에러
```

**파이썬은 함수 스코프**다. `if`, `for`, `while`, `try`는 **스코프를 만들지 않는다.**

```python
if True:
    x = 1
print(x)          # 1 — 잘 보인다

for i in range(3):
    pass
print(i)          # 2 — 루프 변수가 살아남는다!
```

`for`의 루프 변수가 루프 종료 후에도 남아 있다는 게 자바 하던 사람에게
제일 낯선 부분이다. 이게 u3(늦은 바인딩) 함정의 뿌리이기도 하다.

스코프를 만드는 것은 **함수, 클래스, 모듈, 컴프리헨션** 넷뿐이다.
(컴프리헨션이 자체 스코프를 갖는 건 3.0부터다 — 05장에서 다룬다)

## 개념 4 — 대입이 스코프를 결정한다 (00장 u3 회수)

```python
x = 10

def f():
    print(x)      # UnboundLocalError!
    x = 20
```

함수 본문 어딘가에 `x`에 대한 **대입이 있으면** `x`는 그 함수 전체에서
지역 변수다. 대입 줄보다 위에서 읽어도 지역이고, 아직 값이 없으니 에러다.

이 규칙 때문에 **바깥 변수를 함수 안에서 수정하려 하면 막힌다.**

```python
count = 0
def increment():
    count += 1    # UnboundLocalError — count가 지역으로 확정됨
```

읽기만 하면 문제없다. **대입하는 순간** 지역이 된다.

## 개념 5 — global 과 nonlocal

이 규칙을 뚫는 두 키워드가 있다.

**`global`** — "이 이름은 모듈 전역이다"

```python
count = 0
def increment():
    global count
    count += 1    # 이제 전역 count를 수정
increment()
print(count)      # 1
```

**`nonlocal`** — "이 이름은 나를 감싼 함수의 지역이다" (3.0+)

```python
def outer():
    count = 0
    def inner():
        nonlocal count
        count += 1
    inner(); inner()
    return count      # 2
```

차이가 중요하다:
- `global`은 **모듈 전역**을 가리킨다. 없으면 새로 만든다.
- `nonlocal`은 **enclosing 함수의 기존 지역**을 가리킨다.
  없으면 **SyntaxError** — 새로 만들지 않는다.

```python
def outer():
    def inner():
        nonlocal missing   # SyntaxError: no binding for nonlocal 'missing'
        missing = 1
```

## 개념 6 — 읽기는 되는데 왜 쓰기는 안 되나

"읽을 땐 바깥 변수가 보이는데 쓰려면 키워드가 필요하다"는 게 비대칭으로
느껴진다. 이유는 **의도치 않은 전역 오염을 막기 위해서**다.

함수 안에서 `x = 1`이라고 썼는데 그게 모듈 전역을 덮어쓴다면, 어느 함수가
어떤 전역을 바꾸는지 추적이 불가능해진다. 그래서 파이썬은 **대입은 기본적으로
지역**으로 두고, 바깥을 건드리려면 명시적으로 선언하게 했다.

자바는 이 문제가 없다. 필드와 지역 변수가 문법적으로 구분되고
(`this.count` vs `count`), 선언(`int count`)이 명시적이기 때문이다.
파이썬은 선언이 없어서 규칙으로 해결한 것이다.

## 개념 7 — global은 대부분 나쁜 신호다

`global`을 쓰고 싶어질 때는 보통 설계가 잘못된 경우다.

```python
# 나쁨
total = 0
def add(n):
    global total
    total += n

# 나음 — 값을 반환
def add(total, n):
    return total + n

# 나음 — 클래스로 상태를 캡슐화
class Accumulator:
    def __init__(self): self.total = 0
    def add(self, n): self.total += n
```

전역 상태는 테스트를 어렵게 하고(순서 의존), 동시성에서 위험하다(21장).
반면 `nonlocal`은 클로저 패턴에서 정당한 쓰임이 있다 (u2, u3에서).

## 백엔드 관점

- 모듈 레벨 전역은 **프로세스 전체에서 공유**된다. gunicorn 워커마다
  별도 프로세스라 워커 간에는 안 공유되고, 스레드 간에는 공유된다.
  이 구분이 21장(GIL)·22장에서 중요해진다.
- 설정값을 모듈 전역으로 두는 건 흔하지만, 런타임에 수정하면
  어느 요청이 언제 바꿨는지 추적 불가가 된다. 읽기 전용으로 유지한다.
- FastAPI의 의존성 주입(Depends)이 존재하는 이유가 전역 회피다.

## 실무 규칙 (EP 연결)

- `global`은 피한다. 상태가 필요하면 클래스나 명시적 인자로.
- `nonlocal`은 짧은 클로저 안에서만 쓴다. 깊어지면 클래스로 (EP Item 33).
- 함수 안에서 바깥 변수를 읽기만 한다면 아무 키워드도 필요 없다.

## 3문장 요약 (직접 작성)

1. 변수는 LEGB, Local, Enclosing, Global, Built-in의 범위대로 찾아진다.
2. 파이썬은 블록 스코프가 아니다. 따라서 if, while 같은 등이 변수의 스코프를 만들지 않는다.
3. global 키워드를 통해 전역변수를, nonlocal 키워드를 통해 enclosing 범위에 있는 변수라는것을 컴파일에게 알려준다.