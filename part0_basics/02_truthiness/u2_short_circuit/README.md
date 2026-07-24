# u2. and / or 는 불린을 반환하지 않는다

## 지도 확인

u1에서 "모든 객체가 진리값을 가진다"를 봤다.
그럼 `and`, `or`는 그 진리값으로 뭘 하는가?
답은 예상 밖이다 — **True/False가 아니라 피연산자 중 하나를 그대로 돌려준다.**

## 개념 1 — 반환값은 불린이 아니다

```python
1 and 2           # 2      (True 아님!)
0 or "기본값"      # '기본값'
[] or {}          # {}
"a" and "b"       # 'b'
None or 0         # 0
```

`and`/`or`는 **판정만 하고 값을 그대로 반환**한다.
`if`에 넣으면 그 반환값이 다시 truthiness로 판정되니 결과적으로
조건문에서는 자연스럽게 동작하지만, 값을 꺼내 쓰면 불린이 아니다.

## 개념 2 — 규칙: 언제 멈추고 무엇을 반환하나

**`or` — 참인 것을 찾을 때까지 간다**
- 왼쪽이 참이면 → **왼쪽을 반환**하고 오른쪽은 평가조차 안 함
- 왼쪽이 거짓이면 → **오른쪽을 반환**

```python
"값" or "기본"     # '값'   — 왼쪽이 참이라 바로 반환
"" or "기본"       # '기본' — 왼쪽이 거짓이라 오른쪽
0 or None         # None  — 둘 다 거짓이면 마지막 것
```

**`and` — 거짓인 것을 찾을 때까지 간다**
- 왼쪽이 거짓이면 → **왼쪽을 반환**하고 오른쪽은 평가 안 함
- 왼쪽이 참이면 → **오른쪽을 반환**

```python
"값" and "다음"    # '다음' — 왼쪽이 참이라 오른쪽까지
"" and "다음"      # ''     — 왼쪽이 거짓이라 바로 반환
1 and 0           # 0
```

한 문장 요약: **결과를 확정지은 그 피연산자를 반환한다.**

## 개념 3 — 단축 평가 (short-circuit)

오른쪽을 **평가조차 하지 않는다**는 게 핵심이다. 이건 성능 문제가 아니라
**의미론적으로 중요**하다.

```python
# 안전한 순서
if user is not None and user.name == "kim":
    ...
# user가 None이면 왼쪽에서 멈춘다 → user.name 접근 자체를 안 함 → 에러 없음

# 순서를 바꾸면
if user.name == "kim" and user is not None:   # AttributeError!
```

```python
def expensive():
    print("무거운 계산 실행")
    return True

False and expensive()    # 아무것도 출력 안 됨 — 호출 자체가 안 일어남
True or expensive()      # 마찬가지
```

## 개념 4 — 바이트코드로 보면

단축 평가의 실체는 **점프**다.

```python
def f(a, b):
    return a and b
```

```
LOAD_FAST a
COPY 1                    ← a를 복제 (반환값 후보로 남겨둠)
POP_JUMP_IF_FALSE  →끝    ← 거짓이면 b를 건너뛰고 a를 반환
POP_TOP                   ← 참이면 a를 버리고
LOAD_FAST b               ← b를 평가해서 반환
```

`and`/`or`는 함수가 아니라 **제어 흐름**이다. 그래서 오른쪽을 건너뛸 수 있다.
(비교: `f(a, b)` 형태의 함수 호출은 인자를 항상 다 평가해야 한다 — u4/00장의
CALL 규약을 떠올릴 것. 스택에 인자를 다 올려야 CALL이 가능하니까.)

## 개념 5 — 실무 관용구와 그 함정

**기본값 채우기**
```python
name = user_input or "익명"        # 빈 문자열이면 '익명'
port = config.get("port") or 8080  # 없거나 falsy면 8080
```

편리하지만 **u1의 함정이 그대로 재현된다.**

```python
port = config.get("port") or 8080
# config = {"port": 0} 이면? → 0은 falsy → 8080이 됨!
```

"0을 명시적으로 설정했는데 무시당하는" 버그다. 정확히 하려면:

```python
port = config.get("port")
if port is None:
    port = 8080
# 또는
port = config.get("port", 8080)    # dict.get의 기본값 인자 사용
```

**조건부 접근**
```python
length = data and len(data)        # data가 falsy면 data를 그대로 반환
```
이것도 반환 타입이 들쭉날쭉해진다(`[]` 또는 `int`). 명시적으로 쓰는 게 낫다.

## 개념 6 — 삼항 연산자와의 차이

```python
x = a if cond else b        # 삼항 — 조건과 값이 분리됨
x = cond and a or b         # 옛날 관용구 — 위험!
```

두 번째는 **`a`가 falsy면 깨진다.**

```python
cond = True
a = 0
b = "기본"
cond and a or b       # '기본' — a를 원했는데!
```

`True and 0` → `0`(falsy) → `0 or "기본"` → `"기본"`. 삼항 연산자가
생기기 전의 관용구이고, 지금은 절대 쓰면 안 된다. **항상 삼항을 쓴다.**

## 자바와 비교 — "비슷해 보이지만 다르다"

자바의 `&&`, `||`도 단축 평가를 한다. **거기까지는 같다.**

```java
if (user != null && user.getName().equals("kim"))   // 단축 평가, 파이썬과 동일
```

**다른 것: 반환 타입.**
- 자바 `&&`는 항상 `boolean`을 반환. `int x = a && b;` 불가능
- 파이썬 `and`는 피연산자를 반환. `x = a and b`로 값을 꺼낼 수 있음

그래서 자바에는 `name = input or "익명"` 같은 관용구가 없고,
삼항(`input != null ? input : "익명"`)이나 `Objects.requireNonNullElse`를 쓴다.
파이썬의 이 유연함이 편리함과 함정을 동시에 준다.

## 백엔드 관점

- `value = request.get("x") or default` 패턴은 흔하지만, x가 `0`, `""`,
  `False`인 정상 요청을 뭉갠다. 설정값·수량·플래그에서 특히 위험하다.
- 안전한 대안 순서: `dict.get(key, default)` → `if x is None` → 마지막에 `or`
- 단축 평가는 **None 가드**로 유용하다.
  `if conn is not None and conn.is_alive():` 같은 패턴은 정석이다.

## 실무 규칙

- `or`로 기본값을 채울 땐 **falsy 값이 유효한 입력인지** 먼저 확인한다.
  유효하면 `is None` 검사로 바꾼다.
- dict 기본값은 `d.get(k, default)`가 `d.get(k) or default`보다 정확하다.
- `cond and a or b`는 쓰지 않는다. 삼항 연산자 `a if cond else b`를 쓴다.

## 3문장 요약 (직접 작성)

1. and/or는 boolean을 반환하지 않는다.
2. and는 거짓을 찾을때까지, or는 참을 찾을때까지 오른쪽으로 이동하고 그 값을 출력한다.
3. 따라서 조건에 충족하면 나머지 항목을 평가하지않으므로 코드 작성에 주의해야한다.