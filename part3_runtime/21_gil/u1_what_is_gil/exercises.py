"""u1 유제"""
import dis
import threading

# ═══════════════════════════════════════════════════
# 유제 1. 어떤 연산이 위험한가
# ═══════════════════════════════════════════════════
# 아래 각 연산의 바이트코드를 보고, 멀티스레드에서
# race condition이 생길 수 있는지 판단하라.

shared = {"count": 0}
shared_list = []

def op_a(): shared_list.append(1)
def op_b(): shared["count"] += 1
def op_c(): 
    global x
    x = 5
def op_d():
    if "key" not in shared:
        shared["key"] = 1

print("=== 유제1 ===")
for name, fn in [("a: list.append", op_a), ("b: dict값 +=", op_b),
                 ("c: 단순 대입", op_c), ("d: 검사 후 대입", op_d)]:
    print(f"\n  --- {name} ---")
    dis.dis(fn)

# 각각 위험한지 판단하고 이유를 쓰라:
#   a → 
#   b → 
#   c → 
#   d → 
#
# 판단 기준을 한 문장으로:
#   →


# ═══════════════════════════════════════════════════
# 유제 2. race condition 관찰
# ═══════════════════════════════════════════════════
# 스레드 수와 반복 횟수를 바꿔가며 손실률이 어떻게 변하는지 관찰하라.

def run_test(n_threads, n_loops):
    counter = 0
    def worker():
        nonlocal counter
        for _ in range(n_loops):
            counter += 1
    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads: t.start()
    for t in threads: t.join()
    return counter, n_threads * n_loops

print("\n=== 유제2 ===")
for nt, nl in [(2, 1000), (2, 100_000), (8, 100_000)]:
    actual, expected = run_test(nt, nl)
    loss = expected - actual
    print(f"  스레드{nt} x 반복{nl:>7}: {actual:>8}/{expected:<8} 손실 {loss}")

# (a) 반복이 적을 때(1000)는 손실이 거의 없다. 왜인가:
#   →   (힌트: sys.getswitchinterval())
# (b) 스레드 수가 늘면 손실이 어떻게 되나:
#   →
# (c) 이 실험이 "테스트에서 잘 안 잡히는 버그"에 대해 시사하는 바:
#   →


# ═══════════════════════════════════════════════════
# 유제 3. 오해 교정
# ═══════════════════════════════════════════════════
# 아래 문장들의 참/거짓을 판단하고, 거짓이면 올바르게 고쳐라.

print("\n=== 유제3 ===")

statements = [
    "1. 파이썬은 GIL 때문에 멀티스레드를 쓸 수 없다.",
    "2. GIL이 있어서 파이썬 멀티스레드는 항상 스레드 안전하다.",
    "3. GIL은 파이썬 언어 명세의 일부다.",
    "4. 스레드를 늘리면 CPU 작업이 빨라진다.",
    "5. GIL은 IO 대기 중에도 계속 붙들려 있다.",
    "6. numpy 연산은 GIL 때문에 병렬화가 불가능하다.",
]
for s in statements:
    print(" ", s)

# 각각 판단 (참/거짓 + 거짓이면 교정):
#   1 →
#   2 →
#   3 →
#   4 →
#   5 →
#   6 →


# ═══════════════════════════════════════════════════
# 유제 4. 설계 판단
# ═══════════════════════════════════════════════════
# 아래 시나리오 각각에서 멀티스레드가 효과적인지 판단하고,
# 아니라면 대안을 제시하라.

print("\n=== 유제4 ===")
scenarios = [
    "A. 100개 URL에서 HTTP로 데이터 수집",
    "B. 이미지 1000장을 순수 파이썬으로 리사이징",
    "C. DB에서 10개 테이블을 각각 조회",
    "D. 큰 CSV를 pandas로 집계 연산",
    "E. 암호화 해시를 100만 번 계산 (hashlib)",
]
for s in scenarios:
    print(" ", s)

# 각각 판단:
#   A →
#   B →
#   C →
#   D →
#   E →   (힌트: hashlib은 C 구현이다. GIL을 놓을까?)
#
# 판단할 때 던져야 할 질문 하나를 정리하면:
#   →