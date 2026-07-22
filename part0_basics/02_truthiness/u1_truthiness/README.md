# u1. if x: 가 실제로 검사하는 것 — 진리값

## 지도 확인

`if x:`, `while x:`, `if not x:` — 매일 쓴다. 그런데 `x`가 불린이 아니라
리스트나 정수나 객체일 때, 파이썬은 무엇을 보고 참/거짓을 정하는가?
이 유닛은 그 판정 규칙과, 거기서 나오는 흔한 버그를 다룬다.

## 개념 1 — 파이썬은 모든 객체에 진리값이 있다

자바에서 `if`의 조건은 **반드시 boolean**이어야 한다.

```java
if (list) { }        // 컴파일 에러 — boolean이 아님
if (list.size() > 0) // 명시적으로 비교해야 함
```

파이썬은 **모든 객체가 진리값을 가진다.** `if`가 알아서 판정한다.

```python
if [1, 2]:      # 비어있지 않은 리스트 → 참
if []:          # 빈 리스트 → 거짓
if 0:           # 0 → 거짓
if "hi":        # 비어있지 않은 문자열 → 참
if None:        # None → 거짓
```

## 개념 2 — falsy 목록과 판정 순서

**거짓(falsy)으로 취급되는 것들:**

- `None`, `False`
- 숫자 0: `0`, `0.0`, `0j`, `Decimal(0)`
- 빈 컬렉션: `""`, `[]`, `()`, `{}`, `set()`, `range(0)`

**나머지는 전부 참(truthy).** 판정 규칙은 이렇다.

`if x:`를 만나면 파이썬은 `bool(x)`를 부르고, 그건 순서대로:

1. `x.__bool__()`이 있으면 그걸 호출 (True/False 반환)
2. 없으면 `x.__len__()`을 호출해서 **0이면 거짓, 아니면 참**
3. 둘 다 없으면 무조건 참

```python
class Always:
    pass
bool(Always())        # True — __bool__도 __len__도 없으니 참

class Empty:
    def __len__(self): return 0
bool(Empty())         # False — len이 0
```

리스트가 비면 거짓인 이유가 2번이다. `[].__len__()`이 0이니까.
사용자 정의 클래스도 `__bool__`이나 `__len__`을 정의하면 `if obj:`가
의미를 갖는다 (09장 데이터 모델의 예고편).

## 개념 3 — 함정 1: 0과 None을 뭉개는 실수

falsy가 여러 개라서 생기는 대표적 버그다.

```python
def get_count(data):
    count = data.get("count")     # 없으면 None, 있으면 정수(0일 수도)
    if not count:                 # ← 버그!
        return "카운트 없음"
    return f"카운트: {count}"

get_count({"count": 0})           # "카운트 없음" — 0인데!
get_count({})                     # "카운트 없음" — 이건 맞음
```

`0`과 `None`이 **둘 다 falsy**라 `if not count:`가 구분을 못 한다.
"값이 없음(None)"과 "값이 0"은 완전히 다른데 뭉개진 것이다. 올바르게:

```python
if count is None:                 # None만 정확히 검사
    return "카운트 없음"
```

u3에서 `is 0`이 위험했던 것과 **짝을 이루는 함정**이다.
그때는 `is`로 값을 봤고, 여기선 truthiness로 None을 봤다.
규칙: **None을 확인할 땐 `is None`, 값을 확인할 땐 명시적으로.**

## 개념 4 — 함정 2: 빈 컬렉션 vs None

같은 실수의 다른 버전이다.

```python
def process(items=None):
    if not items:                 # [] 와 None을 못 구분
        print("항목 없음")
    ...
```

빈 리스트 `[]`를 넘겨도 "항목 없음"이 된다. 만약 "None이면 기본값,
빈 리스트면 그대로 처리"가 의도라면 이건 버그다.

```python
if items is None:
    items = default_items
# 이제 빈 리스트는 빈 리스트대로 처리됨
```

**단, 많은 경우 `if not items:`가 오히려 맞다.** "비어있거나 없으면
똑같이 처리"가 의도라면 이게 간결하다. 핵심은 **의도적으로 선택**하는 것이다.
None과 빈 값을 구분해야 하는지 아닌지를 먼저 정하고 코드를 쓴다.

## 개념 5 — bool은 int의 자식이다

파이썬에서 `True`는 사실 `1`, `False`는 `0`이다.

```python
True == 1             # True
False == 0            # True
True + True           # 2
isinstance(True, int) # True — bool은 int의 서브클래스
sum([True, False, True, True])   # 3 — 참을 세는 관용구
```

이건 실용적이다. `sum(x > 10 for x in nums)`로 조건 만족 개수를 셀 수 있다.
다만 `True == 1`이 성립한다는 건 예상 밖 버그의 원인이 되기도 한다.

```python
{True: "a", 1: "b"}   # {True: 'b'} — True와 1이 같은 키로 취급!
```

## 자바와 비교

| | 자바 | 파이썬 |
|---|---|---|
| if 조건 | boolean만 허용 | 모든 객체 (자동 판정) |
| 빈 리스트 검사 | `list.isEmpty()` | `if not lst:` |
| null 검사 | `x == null` | `x is None` |
| boolean과 int | 별개 타입 | bool ⊂ int |

자바의 명시성(항상 비교 연산을 써야 함)이 파이썬에선 편의성과 맞바뀐다.
편한 대신, 0/None/빈 값이 전부 falsy라 **구분이 필요한 곳에서 실수하기 쉽다.**

## 백엔드 관점

- API에서 `if not request.count:`는 count가 0인 정상 요청을 "없음"으로
  처리하는 버그가 된다. 숫자 필드는 `is None`으로 존재 여부를 확인한다.
- Pydantic/ORM에서 "필드 미제공"과 "0/빈 문자열 제공"을 구분해야 할 때
  이 함정이 자주 나온다. `Optional`과 기본값 설계가 여기 걸린다.
- DB 쿼리 결과가 빈 리스트인지 None인지: "결과 없음"과 "조회 실패"는
  다르다. truthiness로 뭉개면 에러를 놓친다.

## 실무 규칙

- **None 검사는 `is None`**. `if not x:`로 None을 검사하지 않는다.
- "비었거나 없으면 같게 처리"가 확실할 때만 `if not x:`를 쓴다 —
  의도를 확인하고 선택한다.
- 숫자 0이 유효값일 수 있는 필드는 절대 truthiness로 존재 검사하지 않는다.

## 3문장 요약 (직접 작성)

1. 파이썬의 모든 객체에는 진리값이 있다.
2. None, false, 빈 컬렉션, 빈 문자열, 0 등이 false로 취급된다. 객체는 __bool__과 __len__ 가 없으면 true값을 있다면 각 메서드의 값을 통해 진리값을 출력한다.
3. 조건문을 활용할때 요구사항에 따라 0과 None을 주의해서 쓰자.