"""24 u1 유제"""
import asyncio
import inspect
import time

# ═══════════════════════════════════════════════════
# 유제 1. 코루틴 객체 이해
# ═══════════════════════════════════════════════════
print("=== 유제1 ===")

async def compute():
    print("    [계산 시작]")
    return 100

c = compute()
print("  compute() 결과:", c)          # 예측:__
print("  [계산 시작]이 출력됐나?")       # 예측:__

try:
    c.send(None)
except StopIteration as e:
    print("  send(None) 후 value:", e.value)   # 예측:__

# (a) 10장 u1의 제너레이터와 무엇이 같은가:
#   →
# (b) 코루틴을 만들고 await하지 않으면 어떤 경고가 나는지 확인해보라:
#   →   (힌트: 아래 줄 주석 해제 후 실행)
# compute()

# (c) 이 경고가 실무에서 어떤 버그를 잡아주나:
#   →


# ═══════════════════════════════════════════════════
# 유제 2. 순차 vs 동시 — 시간 예측
# ═══════════════════════════════════════════════════
async def task(name, sec):
    await asyncio.sleep(sec)
    return name

async def case_a():
    """순차 await"""
    start = time.perf_counter()
    await task("A", 0.2)
    await task("B", 0.3)
    await task("C", 0.1)
    return time.perf_counter() - start

async def case_b():
    """gather"""
    start = time.perf_counter()
    await asyncio.gather(task("A", 0.2), task("B", 0.3), task("C", 0.1))
    return time.perf_counter() - start

print("\n=== 유제2 ===")
# 예측: case_a → __초,  case_b → __초
print(f"  순차  : {asyncio.run(case_a()):.2f}초")
print(f"  gather: {asyncio.run(case_b()):.2f}초")

# (a) 각 결과가 왜 그 시간인지 계산식으로:
#   순차 →
#   gather →
# (b) gather가 0.3초인 이유를 "양보"라는 말로 설명:
#   →


# ═══════════════════════════════════════════════════
# 유제 3. 양보 지점 찾기
# ═══════════════════════════════════════════════════
print("\n=== 유제3 ===")
log = []

async def a():
    log.append("a1")
    await asyncio.sleep(0)
    log.append("a2")
    await asyncio.sleep(0)
    log.append("a3")

async def b():
    log.append("b1")
    log.append("b2")          # 양보 없이 연속
    await asyncio.sleep(0)
    log.append("b3")

async def main():
    await asyncio.gather(a(), b())

asyncio.run(main())
print("  실행 순서:", log)
# 예측:__

# (a) b1과 b2가 붙어서 나온 이유:
#   →
# (b) 이 성질이 21장의 "락이 필요한가" 질문과 어떻게 연결되나:
#   →
# (c) await 사이에서 공유 변수를 수정하면 위험한 경우를 코드로 써보라:
#   →


# ═══════════════════════════════════════════════════
# 유제 4. 미니 루프 확장
# ═══════════════════════════════════════════════════
# examples.py의 MiniLoop를 확장하라.
# 요구: 태스크가 끝날 때 반환값을 수집해서 run()이 리스트로 돌려준다.

# (a) StopIteration에서 값을 어떻게 꺼내나 (10장 u2 회수):
#   →
# (b) 실제 asyncio에서 이 역할을 하는 것은 무엇인가:
#   →   (힌트: Task 객체의 메서드)
# (c) 우리 MiniLoop가 진짜 이벤트 루프와 결정적으로 다른 점:
#   →   (힌트: 우리는 시간만 기다린다. 실제로는 무엇을 기다려야 하나?)


# ═══════════════════════════════════════════════════
# 유제 5. 판단 — asyncio가 답인가
# ═══════════════════════════════════════════════════
print("\n=== 유제5 ===")
scenarios = [
    "A. 외부 API 50개를 동시 호출해 결과 취합",
    "B. 100만 건 데이터를 정렬",
    "C. 웹소켓으로 동시 접속 5000명 처리",
    "D. 이미지 1000장 썸네일 생성 (Pillow)",
    "E. DB에서 사용자 조회 (psycopg2 = 동기 드라이버)",
]
for s in scenarios:
    print(" ", s)

# 각각 asyncio가 적합한지, 아니면 무엇을 써야 하는지:
#   A →
#   B →
#   C →
#   D →
#   E →   (함정 주의)
#
# 판단 기준을 정리하면:
#   →