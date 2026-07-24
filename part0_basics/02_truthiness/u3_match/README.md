# u3. match 문 — switch가 아니라 구조 분해다

## 지도 확인

02장의 마지막. u1에서 진리값, u2에서 and/or를 봤다면
이번엔 조건 분기의 또 다른 형태인 `match`다.
3.10에서 추가됐고, 이름만 보면 자바 `switch` 같지만 **성격이 완전히 다르다.**

## 개념 1 — switch가 아니다

자바 `switch`는 **값 하나를 여러 상수와 비교**한다.

```java
switch (code) {
    case 200: ...; break;
    case 404: ...; break;
}
```

파이썬 `match`는 **값의 구조를 분해하며 매칭**한다. 이름도 "구조적 패턴 매칭
(structural pattern matching)"이다. 값 비교는 그중 가장 단순한 경우일 뿐이다.

```python
match point:
    case (0, 0):           # 튜플이고 두 원소가 0,0인가
        print("원점")
    case (x, 0):           # 튜플이고 두 번째가 0인가 → x에 첫 원소를 담아라
        print(f"x축 위 {x}")
    case (x, y):           # 튜플이면 → x,y에 각각 담아라
        print(f"({x}, {y})")
```

**핵심**: `case (x, 0)`은 `x`와 비교하는 게 아니라 **`x`라는 이름에 값을
바인딩**한다. 매칭과 분해가 동시에 일어난다.

## 개념 2 — 패턴의 종류

```python
match value:
    case 42:              # 리터럴 패턴 — == 로 비교
    case "hello":         # 리터럴
    case None:            # 리터럴 (None/True/False는 is 로 비교)
    case [1, 2, *rest]:   # 시퀀스 패턴 — 리스트/튜플 분해, rest에 나머지
    case {"key": v}:      # 매핑 패턴 — dict에서 key를 꺼내 v에 바인딩
    case Point(x=0):      # 클래스 패턴 — isinstance 검사 + 속성 추출
    case str() | int():   # or 패턴 — 둘 중 하나
    case x if x > 10:     # 가드 — 패턴 매칭 후 추가 조건
    case _:               # 와일드카드 — 항상 매칭 (default)
```

**주의할 함정**: 그냥 이름을 쓰면 **비교가 아니라 바인딩**이다.

```python
STATUS_OK = 200
match code:
    case STATUS_OK:      # 버그! 200과 비교하는 게 아니라
        ...              # STATUS_OK라는 이름에 code를 담고 무조건 매칭됨
```

상수와 비교하려면 **점이 있는 이름**이어야 한다.

```python
class Status:
    OK = 200

match code:
    case Status.OK:      # 올바름 — 점이 있으면 값 비교
        ...
```

이 규칙("이름 단독 = 바인딩, 점 있음 = 비교")이 match에서 제일 헷갈리는 부분이다.

## 개념 3 — 내부적으로 무엇을 하나

`match`는 마법이 아니다. 각 패턴은 이미 아는 연산으로 번역된다.

| 패턴 | 실제 검사 |
|---|---|
| `case 42:` | `value == 42` |
| `case None:` | `value is None` (u3/01장) |
| `case [a, b]:` | 시퀀스인가 + 길이 2인가 + 분해 |
| `case {"k": v}:` | 매핑인가 + `"k" in value` + 꺼내기 |
| `case Point(x=0):` | `isinstance(value, Point)` + `value.x == 0` |

01장에서 배운 `==` vs `is`가 여기서 그대로 쓰인다.
`None`, `True`, `False`만 `is`로 비교되고 나머지 리터럴은 `==`다.

## 개념 4 — 시퀀스 패턴의 주의점

시퀀스 패턴은 **문자열을 시퀀스로 취급하지 않는다.**

```python
match "ab":
    case [a, b]:         # 매칭 안 됨! 문자열은 제외
        ...
    case str():          # 이렇게 잡아야 함
        ...
```

문자열도 시퀀스지만, `case [a, b]`가 `"ab"`를 `a='a', b='b'`로 분해하면
거의 항상 의도치 않은 동작이라 언어 차원에서 제외했다.

그리고 리스트와 튜플은 **구분하지 않는다.**

```python
match [1, 2]:
    case (a, b):         # 매칭됨 — 대괄호/소괄호 무관
        ...
```

패턴에서 `[]`와 `()`는 같은 의미다. "시퀀스인가"만 본다.

## 개념 5 — 언제 쓰나

**match가 나은 경우**: 구조를 분해해야 할 때
```python
match command.split():
    case ["go", direction]:
        move(direction)
    case ["take", item, "from", place]:
        take(item, place)
    case _:
        print("알 수 없는 명령")
```

**if/elif가 나은 경우**: 단순 조건 나열
```python
if score >= 90: grade = "A"
elif score >= 80: grade = "B"
```
범위 비교는 match로 쓰면 오히려 장황하다 (`case x if x >= 90:`).

**dict가 나은 경우**: 값 → 값 매핑
```python
handlers = {200: ok, 404: not_found}   # match보다 이게 낫다
```

정리: **분해할 구조가 있으면 match, 아니면 기존 문법.**

## 자바와 비교

자바도 최근 패턴 매칭이 들어왔다 (Java 16 `instanceof` 패턴, 21 switch 패턴).

```java
// Java 21
switch (obj) {
    case Integer i when i > 10 -> ...;
    case String s -> ...;
}
```

방향이 같다. 다만 자바는 **타입 중심**(어떤 클래스인가)이고,
파이썬은 **구조 중심**(어떤 모양인가)에 더 가깝다. 파이썬은 dict나
리스트의 내부 모양을 직접 분해할 수 있다.

## 백엔드 관점

- API 응답이나 이벤트 메시지 같은 **중첩 dict 처리**에 강하다.
```python
  match event:
      case {"type": "user.created", "data": {"id": uid}}:
          handle_new_user(uid)
      case {"type": "user.deleted", "data": {"id": uid}}:
          handle_delete(uid)
```
  기존 방식이면 `event.get("type")`, `event["data"]["id"]`를 KeyError
  방어하며 꺼내야 하는데, 패턴이 **존재 검사와 추출을 동시에** 한다.
- 파서, 상태 머신, 명령어 처리에도 잘 맞는다.
- 단, 3.10+ 전용이다. 지원 버전 확인 필요.

## 실무 규칙

- 상수와 비교할 땐 반드시 **점 있는 이름**(`Status.OK`)을 쓴다.
  이름 단독은 바인딩이라 무조건 매칭된다.
- `case _:`로 기본 케이스를 명시한다. 아무것도 매칭 안 되면 조용히 통과한다
  (자바 switch와 달리 에러가 안 난다).
- 단순 값 분기는 dict나 if/elif가 더 읽기 쉽다.

## 3문장 요약 (직접 작성)

1. match는 구조를 파악하고 분해할 수 있는 조건분기문법이다.
2. match에 그냥 변수이름을 쓰면 해당 값과 비교하는게 아니라 바인딩된다.
3. 중첩된 dict 처리에 쓰자. 단순분기는 if/elif를 사용하자.