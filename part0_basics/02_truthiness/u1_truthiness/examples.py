"""u1 예제: 진리값 판정을 관측한다.

실행: python examples.py
"""

# ── 예제 1: falsy 목록 ───────────────────────────────
print("=== falsy 인 것들 ===")
for v in [None, False, 0, 0.0, "", [], (), {}, set(), range(0)]:
    print(f"  bool({str(v)!r:<10}) = {bool(v)}")

print("\n=== truthy 인 것들 ===")
for v in [1, -1, 0.1, "a", " ", [0], (0,), {0:0}, [None]]:
    print(f"  bool({str(v)!r:<10}) = {bool(v)}")
# 주의: " "(공백), [0], [None]은 참! 비어있지 않으니까


# ── 예제 2: __bool__ vs __len__ ──────────────────────
print("\n=== 판정 순서 ===")

class WithBool:
    def __bool__(self): 
        print("    __bool__ 호출됨")
        return False

class WithLen:
    def __len__(self):
        print("    __len__ 호출됨")
        return 0

class WithNothing:
    pass

print("  WithBool:", bool(WithBool()))      # __bool__ 사용
print("  WithLen :", bool(WithLen()))       # __len__ 사용 (0→False)
print("  WithNothing:", bool(WithNothing()))# 둘 다 없음 → True


# ── 예제 3: 0/None 함정 ──────────────────────────────
print("\n=== 0과 None 함정 ===")
def get_count_buggy(data):
    count = data.get("count")
    if not count:
        return "없음"
    return f"카운트: {count}"

def get_count_fixed(data):
    count = data.get("count")
    if count is None:
        return "없음"
    return f"카운트: {count}"

for d in [{"count": 5}, {"count": 0}, {}]:
    print(f"  {str(d):<15} buggy={get_count_buggy(d):<10} fixed={get_count_fixed(d)}")
# count=0 에서 두 함수가 갈린다


# ── 예제 4: bool은 int ───────────────────────────────
print("\n=== bool ⊂ int ===")
print("  True == 1     :", True == 1)
print("  True + True   :", True + True)
print("  sum([T,F,T,T]):", sum([True, False, True, True]))
print("  isinstance(True, int):", isinstance(True, int))
print("  {True:'a', 1:'b'} :", {True: "a", 1: "b"})   # 키 충돌!