"""u2 예제: and/or의 반환값과 단축 평가를 관측한다.

실행: python examples.py
"""
import dis

# ── 예제 1: 반환값은 불린이 아니다 ───────────────────
print("=== 반환값 확인 ===")
cases = [
    ("1 and 2",      1 and 2),
    ("0 and 2",      0 and 2),
    ("1 or 2",       1 or 2),
    ("0 or 2",       0 or 2),
    ('"" or "기본"',  "" or "기본"),
    ('"a" and "b"',  "a" and "b"),
    ("[] or {}",     [] or {}),
    ("None or 0",    None or 0),
]
for expr, result in cases:
    print(f"  {expr:<14} → {result!r:<8} (타입: {type(result).__name__})")


# ── 예제 2: 단축 평가 — 오른쪽이 실행조차 안 됨 ──────
print("\n=== 단축 평가 ===")

def loud(name, value):
    print(f"    [{name} 평가됨]")
    return value

print("  False and loud('B', 1):")
r = False and loud("B", 1)          # B 평가 안 됨
print("    결과:", r)

print("  True or loud('B', 1):")
r = True or loud("B", 1)            # B 평가 안 됨
print("    결과:", r)

print("  True and loud('B', 1):")
r = True and loud("B", 1)           # B 평가됨
print("    결과:", r)


# ── 예제 3: None 가드 관용구 ─────────────────────────
print("\n=== None 가드 ===")

class User:
    def __init__(self, name): self.name = name

def check(user):
    if user is not None and user.name == "kim":
        return "kim 맞음"
    return "아님"

print("  User('kim'):", check(User("kim")))
print("  None       :", check(None))     # 에러 없이 통과 — 단축 평가 덕분


# ── 예제 4: or 기본값의 함정 ─────────────────────────
print("\n=== or 기본값 함정 ===")
for config in [{"port": 3000}, {"port": 0}, {}]:
    bad  = config.get("port") or 8080
    good = config.get("port", 8080)
    explicit = config.get("port")
    if explicit is None:
        explicit = 8080
    print(f"  {str(config):<16} or={bad:<6} get기본값={good:<6} isNone={explicit}")
# port=0 에서 or 방식만 8080이 되어버린다


# ── 예제 5: 바이트코드 ───────────────────────────────
print("\n=== 바이트코드: and는 점프다 ===")
def f(a, b):
    return a and b
dis.dis(f)
# POP_JUMP_IF_FALSE — 거짓이면 b를 건너뛴다