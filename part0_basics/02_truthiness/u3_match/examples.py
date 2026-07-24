"""u3 예제: match의 패턴들을 관측한다.

실행: python examples.py  (Python 3.10+ 필요)
"""
import sys
assert sys.version_info >= (3, 10), "match는 3.10+ 필요"

# ── 예제 1: 구조 분해 ────────────────────────────────
print("=== 시퀀스 패턴 ===")

def describe(point):
    match point:
        case (0, 0):
            return "원점"
        case (x, 0):
            return f"x축 위, x={x}"
        case (0, y):
            return f"y축 위, y={y}"
        case (x, y):
            return f"일반점 ({x}, {y})"
        case _:
            return "점이 아님"

for p in [(0,0), (3,0), (0,5), (2,3), "hello", [1,2]]:
    print(f"  {str(p):<10} → {describe(p)}")
# [1,2]도 매칭된다 — 리스트/튜플 구분 안 함
# "hello"는 매칭 안 됨 — 문자열은 시퀀스 패턴에서 제외


# ── 예제 2: 이름 단독 = 바인딩 (함정) ────────────────
print("\n=== 함정: 이름 단독은 바인딩 ===")
STATUS_OK = 200

# def check_bad(code):
#     match code:
#         case STATUS_OK:          # 비교가 아니라 바인딩!
#             return f"매칭됨 (STATUS_OK={STATUS_OK})"
#         case _:
#             return "여기 도달 못함"

# print("  code=200:", check_bad(200))
# print("  code=404:", check_bad(404))   # 404도 매칭됨!

class Status:
    OK = 200

def check_good(code):
    match code:
        case Status.OK:          # 점이 있으면 값 비교
            return "OK"
        case _:
            return "OK 아님"

print("  [수정] code=200:", check_good(200))
print("  [수정] code=404:", check_good(404))


# ── 예제 3: 매핑 패턴 — 중첩 dict ────────────────────
print("\n=== 매핑 패턴 ===")

def handle(event):
    match event:
        case {"type": "user.created", "data": {"id": uid, "name": name}}:
            return f"신규 유저 {name}({uid})"
        case {"type": "user.deleted", "data": {"id": uid}}:
            return f"삭제 {uid}"
        case {"type": t}:
            return f"미처리 타입: {t}"
        case _:
            return "형식 불명"

events = [
    {"type": "user.created", "data": {"id": 1, "name": "kim"}},
    {"type": "user.deleted", "data": {"id": 2}},
    {"type": "other", "data": {}},
    "잘못된 데이터",
]
for e in events:
    print(f"  → {handle(e)}")
# 매핑 패턴은 "적어도 이 키들이 있으면" 매칭 (추가 키가 있어도 됨)


# ── 예제 4: 클래스 패턴 + 가드 ───────────────────────
print("\n=== 클래스 패턴과 가드 ===")

class Point:
    __match_args__ = ("x", "y")      # 위치 인자 패턴을 쓰려면 필요
    def __init__(self, x, y):
        self.x, self.y = x, y

def classify(obj):
    match obj:
        case Point(x=0, y=0):
            return "Point 원점"
        case Point(x=x, y=y) if x == y:      # 가드
            return f"대각선 위 Point({x})"
        case Point():
            return "일반 Point"
        case int() | float() as n:            # or 패턴 + as
            return f"숫자 {n}"
        case _:
            return "기타"

for o in [Point(0,0), Point(3,3), Point(1,2), 42, 3.14, "s"]:
    print(f"  → {classify(o)}")


# ── 예제 5: *rest 와 부분 매칭 ───────────────────────
print("\n=== 나머지 수집 ===")

def parse(cmd):
    match cmd.split():
        case ["go", direction]:
            return f"이동: {direction}"
        case ["take", item, "from", place]:
            return f"{place}에서 {item} 획득"
        case ["say", *words]:
            return f"발화: {' '.join(words)}"
        case []:
            return "빈 명령"
        case _:
            return "알 수 없음"

for c in ["go north", "take key from box", "say hello world", "", "xyz abc"]:
    print(f"  {c!r:<25} → {parse(c)}")