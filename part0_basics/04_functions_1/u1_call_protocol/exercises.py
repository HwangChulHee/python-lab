"""u1 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 인자 배정 예측
# ═══════════════════════════════════════════════════
def f(a, b=10, *args, **kwargs):
    return f"a={a} b={b} args={args} kwargs={kwargs}"

print("=== 유제1 ===")
calls = [
    "f(1)",
    "f(1, 2)",
    "f(1, 2, 3)",
    "f(1, 2, 3, 4, x=5)",
    "f(1, x=5)",
    "f(1, b=2, x=5)",
    "f(*[1, 2, 3])",
    "f(**{'a': 1, 'b': 2})",
]
for c in calls:
    print(f"  {c:<28} → {eval(c)}    예측:__")

"""
1. "a={1} b={10} args={} kwargs={}"
2. "a={1} b={2} args={} kwargs={}"
3. "a={1} b={2} args={3} kwargs={}"
4. "a={1} b={2} args={3,4} kwargs={5}"
5. "a={1} b={2} args={} kwargs={5}"
6. "a={1} b={} args={} kwargs={}"
7. "a={} b={10} args={1,2,3} kwargs={}"
8. "a={} b={10} args={} kwargs={'a': 1, 'b': 2}"
"""
# 헷갈린 것:
#   → 


# ═══════════════════════════════════════════════════
# 유제 2. 에러 예측 — 어떤 호출이 실패하나
# ═══════════════════════════════════════════════════
def g(pos, /, normal, *, kw):
    return f"{pos} {normal} {kw}"

print("\n=== 유제2 ===")
attempts = [
    "g(1, 2, kw=3)",
    "g(1, normal=2, kw=3)",
    "g(pos=1, normal=2, kw=3)",
    "g(1, 2, 3)",
]
for a in attempts:
    try:
        print(f"  {a:<28} → {eval(a)}    예측:__")
    except TypeError as e:
        print(f"  {a:<28} → TypeError    예측:__")

# 각 실패의 이유:
#   →
"""  
1. g(1, 2, kw=3) ->  통과
2. g(1, normal=2, kw=3) -> 통과
3. g(pos=1, normal=2, kw=3) -> 에러. pos는 무조건 위치인자여야함
4. g(1, 2, 3) -> 에러. kw는 무조건 키워드 인자여야함
"""


# ═══════════════════════════════════════════════════
# 유제 3. 버그 찾기 — 캐시가 공유된다
# ═══════════════════════════════════════════════════
# 아래 함수는 결과를 캐시하려 한다. 그런데 다른 호출끼리 캐시가 섞인다.

def fetch(key, cache={}):
    if key in cache:
        return f"캐시 히트: {cache[key]}"
    cache[key] = f"데이터({key})"
    return f"새로 조회: {cache[key]}"

print("\n=== 유제3 ===")
print(" ", fetch("a"))
print(" ", fetch("a"))        # 캐시 히트 — 의도한 동작
print(" ", fetch("b"))
print("  fetch.__defaults__:", fetch.__defaults__)

# (a) 캐시가 호출 간에 유지되는 이유 (00장 u2 회수):
#   → 정의부에 작성한 기본값은 __defaults__에 저장되고, 재사용되기때문에
# (b) 이게 "버그"인 경우와 "의도된 기능"인 경우를 각각 들어라:
#   버그인 경우 → 객체를 전달하고 그게 갱신되기를 원할때는 버그
#   기능인 경우 → 위처럼 캐시기능으로 사용할때
# (c) 호출마다 독립된 캐시를 원한다면 어떻게 고치나:
#   → 정의부의 cache를 None으로 정의.


# ═══════════════════════════════════════════════════
# 유제 4. 직접 작성 — 안전한 시그니처 설계
# ═══════════════════════════════════════════════════
# 아래 함수는 호출부에서 실수하기 쉽다.
#
#   def send_email(to, subject, body, html, urgent, retry):
#       ...
#   send_email("a@b.c", "제목", "본문", True, False, 3)
#                                       ↑ 이게 뭐였지?
#
# 요구사항:
#   - to, subject, body는 위치로 받되, 이름 변경에 안전하게
#   - html, urgent는 반드시 키워드로 (기본 False)
#   - retry는 키워드, 기본 3
#   - 추가 헤더를 **kwargs로 받기

def send_email(to, subject, body, /, *, html=False, urgent=False, retry=3, **kwargs):    # TODO: 시그니처만 작성
    pass

# (a) 왜 그렇게 설계했는지 각 부분의 근거:
#   → * 기호를 통해 이후 인자를 키워드로만 받게했음
# (b) 다음 호출이 성공/실패하는지 예측:
#   send_email("a@b.c", "제목", "본문")           → 실패. html, urgent를 안보냈잖
#   send_email("a@b.c", "제목", "본문", True)     → 실패. html를 키워드로 전달 안했잖 
#   send_email("a@b.c", "제목", "본문", html=True) → 실패. urgent를 안보냈잖
#   send_email(to="a@b.c", subject="제", body="본") → 븅신