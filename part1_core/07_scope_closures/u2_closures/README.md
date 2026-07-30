# u2. 클로저 — 죽은 프레임의 변수가 사는 법

## 지도 확인

00장 u4에서 프레임은 **호출할 때 생기고 반환하면 소멸**한다고 했다.
그런데 `make_counter()`가 반환한 함수는 `count`를 계속 기억한다.
프레임이 죽었는데 그 안의 변수가 살아 있는 것이다.

이 모순의 해답이 **cell 객체**다. 01장 u2 유제에서 `double.__closure__`를
찍어봤던 그것이고, u1 예제 2 dis에서 본 `MAKE_CELL`/`LOAD_DEREF`의 정체다.

## 개념 1 — 클로저란

**중첩 함수가 자신을 감싼 함수의 지역 변수를 기억하는 것**, 그리고
그렇게 만들어진 함수 자체를 클로저라 부른다.

```python
def make_counter():
    count = 0                  # outer의 지역 변수
    def increment():
        nonlocal count
        count += 1
        return count
    return increment           # outer는 여기서 끝나는데...

c = make_counter()
c()  # 1
c()  # 2                       # count가 살아있다
```

`make_counter`의 프레임은 `return` 순간 사라진다. 그런데 `count`는 남는다.

## 개념 2 — cell 객체가 답이다

컴파일러가 "이 변수는 안쪽 함수가 참조한다"는 걸 발견하면,
그 변수를 **프레임의 지역 배열이 아니라 `cell`이라는 별도 객체**에 담는다.

```
일반 지역 변수                 클로저 변수
프레임                        프레임
┌──────────┐                 ┌──────────┐
│ count: 0 │                 │ count: ──┼──→ cell 객체
└──────────┘                 └──────────┘        │
프레임 죽으면 같이 소멸          프레임 죽어도      ↓ 안에 값
                              cell은 남음      [ 0 ]
                                                 ↑
                              함수 객체 ─────────┘
                              (__closure__가 가리킴)
```

핵심은 **누가 cell을 가리키느냐**다. 프레임이 죽어도 반환된 함수 객체가
`__closure__`로 cell을 가리키고 있으니, 01장 u1의 refcount 규칙에 따라
cell은 살아남는다. **참조 카운트가 0이 아니니까 소멸하지 않는 것이다.**

```python
c = make_counter()
c.__closure__                    # (<cell at 0x...: int object at 0x...>,)
c.__closure__[0].cell_contents   # 현재 count 값
```

## 개념 3 — 세 가지 이름 목록

00장 u3에서 `co_varnames`(지역)와 `co_names`(전역·속성)를 봤다.
클로저 때문에 두 개가 더 있다.

| 목록 | 무엇 | 명령 |
|---|---|---|
| `co_varnames` | 일반 지역 | `LOAD_FAST` |
| `co_cellvars` | **내가 만들고 안쪽이 쓰는 변수** | `MAKE_CELL` + `LOAD_DEREF` |
| `co_freevars` | **바깥에서 물려받아 내가 쓰는 변수** | `LOAD_DEREF` |
| `co_names` | 전역·속성 | `LOAD_GLOBAL`/`LOAD_ATTR` |

같은 변수가 관점에 따라 다르게 불린다.

```python
def outer():
    count = 0        # outer 입장: cellvar (내가 만들어 넘겨줌)
    def inner():
        return count # inner 입장: freevar (밖에서 받아 씀)
    return inner
```

```python
outer.__code__.co_cellvars           # ('count',)
outer().__code__.co_freevars         # ('count',)
```

`LOAD_DEREF`는 "cell에서 꺼내라"는 명령이다. 배열 인덱싱(`LOAD_FAST`)보다
한 단계 간접 참조가 더 있어서 아주 약간 느리다.

## 개념 4 — 클로저는 값이 아니라 변수를 캡처한다

**이게 제일 중요하다.** 클로저는 그 시점의 **값을 복사하는 게 아니라
변수 자체(cell)를 공유**한다.

```python
def outer():
    x = 1
    def show():
        print(x)
    x = 99          # 함수를 만든 뒤에 바꿨는데
    return show

outer()()           # 99 — 최신 값이 나온다!
```

`show`가 만들어질 때 `x`가 1이었지만, 출력은 99다.
cell을 공유하니 **나중에 바뀐 값이 보인다.**

이 성질이 u3(늦은 바인딩)의 원인이 된다. 반대로 이 성질 덕에
`nonlocal count; count += 1`로 상태를 갱신할 수 있는 것이기도 하다.

## 개념 5 — 같은 코드 객체, 다른 cell

01장 u2 유제에서 본 그 구조가 이제 완전히 설명된다.

```python
def factory(n):
    def multiply(x):
        return x * n
    return multiply

double = factory(2)
triple = factory(3)

double.__code__ is triple.__code__    # True  — 악보는 하나
double is triple                       # False — 연주자는 둘
double.__closure__[0].cell_contents    # 2
triple.__closure__[0].cell_contents    # 3    — 각자 다른 cell
```

- **코드 객체**: 컴파일 시 1개 (본문이 같으니까)
- **함수 객체**: `def multiply` 줄이 실행될 때마다 (2개)
- **cell**: `factory` 호출마다 새로 (2개, 각각 2와 3)

00장 u2의 "악보와 연주자" 비유에 이제 **악보 여백의 메모(cell)**가 추가된다.
같은 악보, 다른 연주자, 각자 다른 조율.

## 개념 6 — 자바와 비교: "값 캡처 vs 변수 캡처"

자바 람다도 바깥 변수를 캡처한다. 하지만 **방식이 다르다.**

```java
int x = 1;
Runnable r = () -> System.out.println(x);
x = 99;    // 컴파일 에러! "effectively final이어야 함"
```

자바는 **값을 복사**해서 캡처한다. 그래서 캡처된 변수는 바뀌면 안 되고,
`final`이거나 사실상 final이어야 한다. 캡처 후 변경을 아예 금지한 것이다.

파이썬은 **변수(cell)를 공유**한다. 그래서 나중에 바뀐 값이 보이고,
`nonlocal`로 안쪽에서 바깥 변수를 수정할 수도 있다.

| | 자바 | 파이썬 |
|---|---|---|
| 캡처 대상 | 값 (복사) | 변수 (cell 공유) |
| 캡처 후 변경 | 금지 (effectively final) | 가능 |
| 안쪽에서 수정 | 불가 | `nonlocal`로 가능 |
| 상태 유지 | 배열/객체 감싸기 트릭 필요 | 자연스럽게 됨 |

자바에서 카운터를 만들려면 `int[] count = {0}` 같은 트릭을 쓰는데,
파이썬은 `nonlocal`로 직접 된다. 대신 파이썬은 **의도치 않은 공유**의
위험이 있다 (u3).

## 개념 7 — 클로저는 객체의 가벼운 대안이다

"상태를 가진 무언가"를 만드는 방법이 둘이다.

```python
# 클로저
def make_counter():
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    return inc

# 클래스
class Counter:
    def __init__(self):
        self.count = 0
    def __call__(self):
        self.count += 1
        return self.count
```

둘 다 "상태 + 동작"이다. 실제로 **클로저와 객체는 이론적으로 동등**하다
(같은 것을 다르게 표현한 것).

선택 기준:
- 상태가 하나, 동작이 하나 → **클로저**가 간결
- 상태가 여럿, 동작이 여럿 → **클래스**가 명확
- 상태를 밖에서 조회·수정해야 함 → **클래스** (cell은 접근이 불편)
- 데코레이터 → 거의 항상 **클로저** (12장)

EP Item 33의 기준: 클로저 안에 `nonlocal`이 여러 개 생기거나 로직이
길어지면 클래스로 바꿔라.

## 백엔드 관점

- **데코레이터의 전부가 클로저다.** `@app.get("/users")`에서 경로 문자열을
  기억하는 것, `@retry(3)`에서 횟수를 기억하는 것 — 전부 cell에 담긴다 (12장).
- 콜백에 설정값을 담아 넘길 때 클로저가 편하다. 다만 **캡처된 변수가
  나중에 바뀌면 콜백 동작도 바뀐다**는 걸 의식해야 한다 (u3).
- 클로저가 큰 객체를 캡처하면 **그 객체가 해제되지 않는다.** cell이 참조를
  들고 있으니 refcount가 0이 안 된다. 메모리 누수의 한 원인이다 (20장).

## 실무 규칙 (EP 연결)

- 클로저에서 바깥 변수를 **수정**하려면 `nonlocal`이 필수다. 읽기만 하면 불필요.
- `nonlocal`이 두 개 이상 필요하거나 로직이 길어지면 클래스로 (EP Item 33).
- 루프 안에서 클로저를 만들 때는 캡처 시점을 반드시 확인한다 (u3).

## 3문장 요약 (직접 작성)

1.
2.
3.