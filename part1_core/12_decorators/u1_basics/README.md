# u1. 데코레이터 — @는 f = deco(f)일 뿐이다

## 지도 확인

필요한 재료가 전부 모였다.

- `def`는 실행문이고, 함수 객체를 이름에 대입한다 (00장 u2)
- `@deco`는 `f = deco(f)`의 문법 설탕이다 (00장 u2 유제 3)
- 클로저가 cell로 값을 기억한다 (07장 u2)
- `*args, **kwargs`로 어떤 인자든 받아 넘긴다 (04장 u1)

데코레이터는 **새로운 개념이 아니라 이 넷의 조합**이다.
이번 유닛은 그 조합을 정확히 맞추고, `functools.wraps`로 마무리한다.

## 개념 1 — 문법 설탕 다시 확인

```python
@logger
def add(x, y):
    return x + y

# 완전히 동일:
def add(x, y):
    return x + y
add = logger(add)
```

`@deco`는 **함수 정의 직후에 그 함수 객체를 `deco`에 넘기고,
반환값을 같은 이름에 대입**한다. 그게 전부다.

00장 u4에서 바이트코드로 확인했듯, 데코레이터 버전은
"장식 전의 함수가 이름에 묶이는 순간"조차 없다.

## 개념 2 — 최소 데코레이터의 뼈대

```python
def logger(fn):                    # ① 원본 함수를 받는다
    def wrapper(*args, **kwargs):  # ② 대체할 함수를 만든다
        print(f"{fn.__name__} 호출")
        result = fn(*args, **kwargs)   # ③ 원본을 호출한다
        print(f"{fn.__name__} 완료")
        return result              # ④ 결과를 그대로 반환
    return wrapper                 # ⑤ 대체 함수를 돌려준다
```

각 줄의 근거:

- **`fn`을 기억하는 것** = 클로저. `wrapper`가 `fn`을 cell로 캡처한다 (07 u2)
- **`*args, **kwargs`** = 어떤 시그니처의 함수가 와도 그대로 받아 넘기기 (04 u1)
- **`return result`** = 이걸 빠뜨리면 모든 데코레이트된 함수가 `None`을 반환한다

```python
logger_wrapped = logger(add)
logger_wrapped.__closure__[0].cell_contents   # <function add> — cell에 원본이 있다
```

## 개념 3 — 이름이 사라지는 문제

```python
@logger
def add(x, y): ...

add.__name__      # 'wrapper'  ← add가 아니다
add.__doc__       # None       ← 원본 독스트링 소실
add.__module__    # 데코레이터가 정의된 모듈
```

당연하다. `add`라는 이름이 이제 **`wrapper` 함수 객체**를 가리키니까.
`wrapper`의 메타데이터가 나오는 게 맞다.

문제는 이게 실무에서 아프다는 것이다:

- 디버깅: 트레이스백에 전부 `wrapper`로 찍힌다
- 문서화 도구: `help(add)`가 쓸모없어진다
- 프레임워크: 함수 이름으로 라우팅·등록하는 경우 깨진다
- 테스트: `pytest`가 함수를 식별 못 한다

## 개념 4 — functools.wraps

해결책은 **원본의 메타데이터를 wrapper에 복사**하는 것이다.

```python
from functools import wraps

def logger(fn):
    @wraps(fn)                     # ← 이 한 줄
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper
```

`wraps`가 복사하는 것: `__name__`, `__doc__`, `__module__`, `__qualname__`,
`__annotations__`, 그리고 `__dict__` 갱신.

추가로 **`__wrapped__`에 원본 함수를 저장**한다. 이게 중요하다 —
`inspect.signature()`가 이걸 따라가서 원본 시그니처를 복원한다.

```python
add.__wrapped__          # 원본 add 함수
inspect.signature(add)   # (x, y) — wrapper의 (*args, **kwargs)가 아님
```

**`@wraps`는 선택이 아니라 필수다.** EP Item 38이 이 이야기다.

## 개념 5 — 파라미터가 있는 데코레이터

`@retry(3)`처럼 인자를 받으려면 **한 겹 더** 감싼다.

```python
def retry(times):                      # ① 인자를 받는 함수
    def decorator(fn):                 # ② 진짜 데코레이터
        @wraps(fn)
        def wrapper(*args, **kwargs):  # ③ 대체 함수
            for i in range(times):
                try:
                    return fn(*args, **kwargs)
                except Exception:
                    if i == times - 1:
                        raise
        return wrapper
    return decorator

@retry(3)
def flaky(): ...
```

**왜 세 겹인가**: `@` 뒤에는 "함수를 받아 함수를 반환하는 것"이 와야 한다.
`retry(3)`은 호출식이므로, 그 **반환값**이 데코레이터여야 한다.

```python
@retry(3)
def flaky(): ...

# 풀어쓰면:
decorator = retry(3)      # ① 먼저 호출 → decorator 반환
flaky = decorator(flaky)  # ② 그 결과로 장식
```

`times`는 `decorator`와 `wrapper`가 클로저로 기억한다 (07 u2).

## 개념 6 — 실행 시점 정리

헷갈리기 쉬운 부분이다.

```python
def deco(fn):
    print("A: 데코레이터 실행")
    def wrapper(*args, **kwargs):
        print("C: wrapper 실행")
        return fn(*args, **kwargs)
    print("B: wrapper 생성됨")
    return wrapper

@deco
def f(): print("D: 원본 실행")
# 여기까지 A, B가 출력됨 (임포트 시점!)

f()      # C, D 출력
```

**데코레이터 본체는 임포트(정의) 시점에 한 번, wrapper는 호출할 때마다.**

이게 FastAPI 라우팅의 원리다. `@app.get("/users")`가 임포트 시점에 실행되어
라우팅 테이블에 등록하고, wrapper는 요청이 올 때마다 돈다.

## 개념 7 — 여러 개 쌓기

```python
@a
@b
def f(): ...

# = f = a(b(f))
```

**아래에서 위로** 적용된다. `b`가 먼저 감싸고, `a`가 그 결과를 감싼다.
호출 시에는 바깥(`a`)부터 실행된다.

```
정의 시점:  f → b(f) → a(b(f))
호출 시점:  a의 wrapper → b의 wrapper → 원본 f
```

순서가 중요한 경우가 많다. 예를 들어 `@app.get` + `@require_auth`에서
인증이 라우팅보다 안쪽이어야 한다.

## 자바와 비교 — "어노테이션과 다르다"

자바 어노테이션은 **메타데이터**일 뿐이다. 그 자체로는 아무 동작도 안 한다.

```java
@Transactional
public void save() { ... }
```

`@Transactional`은 "이 메서드에 이런 표시가 있다"는 정보만 남기고,
실제 동작은 **프레임워크가 리플렉션이나 프록시로 별도 구현**한다.
Spring AOP가 런타임에 프록시 객체를 만들어 끼워넣는 식이다.

파이썬 데코레이터는 **그 자체가 실행되는 코드**다. 함수를 받아 다른 함수로
바꿔치기한다. 프레임워크의 도움 없이 언어 기능만으로 완결된다.

| | 자바 어노테이션 | 파이썬 데코레이터 |
|---|---|---|
| 본질 | 메타데이터 표시 | 실행되는 함수 |
| 동작 주체 | 프레임워크(리플렉션/프록시) | 언어 자체 |
| 적용 시점 | 런타임에 프레임워크가 처리 | 정의(임포트) 시점 즉시 |
| 직접 구현 | 어노테이션 + 프로세서 필요 | 함수 하나면 끝 |

`def`가 실행문이라는 사실(00장 u2)이 이 차이를 만든다.

## 백엔드 관점

데코레이터가 실무에서 쓰이는 곳은 사실상 전부다.

- **라우팅**: `@app.get("/users")` — 임포트 시점에 등록
- **인증/인가**: `@require_admin` — 호출 전 검사
- **캐싱**: `@lru_cache`, `@cache` — 결과 저장 (13장)
- **재시도/타임아웃**: `@retry(3)`, `@timeout(5)`
- **로깅/메트릭**: 호출 시간 측정, 에러 카운트
- **트랜잭션**: `@transactional` — 앞뒤로 commit/rollback (11장 컨텍스트 매니저와 조합)
- **테스트**: `@pytest.fixture`, `@pytest.mark.parametrize` (33장)

**공통 구조**: "원본 함수 앞뒤에 뭔가를 끼워넣되, 원본 코드는 안 건드린다."
관심사 분리(cross-cutting concern)의 파이썬식 해법이다.

## 실무 규칙 (EP 연결)

- **`@wraps`를 항상 쓴다** (EP Item 38). 예외 없다.
- wrapper는 반드시 `return`한다. 안 하면 원본 반환값이 사라진다.
- `*args, **kwargs`로 받아서 그대로 넘긴다. 시그니처를 고정하지 않는다.
- 데코레이터가 상태를 갖거나 로직이 길어지면 클래스 데코레이터를 고려한다 (u2).

## 3문장 요약 (직접 작성)

1. 데코레이터는 함수를 받아 함수를 반환하는 함수이며, @deco는 f = deco(f)의 문법 설탕이다.
2. 이름이 wrapper로 바뀌면서 __name__·__doc__ 같은 메타데이터가 가려지므로 @wraps로 원본 것을 복사해둔다.
3. 데코레이터에 인자를 주려면 "데코레이터를 반환하는 함수"를 한 겹 더 씌운다 — factory(arg)(func).