"""24 u2 유제"""
import asyncio
import time

async def work(name, sec):
    await asyncio.sleep(sec)
    return name

# ═══════════════════════════════════════════════════
# 유제 1. 시간 예측
# ═══════════════════════════════════════════════════
async def case_a():
    start = time.perf_counter()
    await work("A", 0.2)
    await work("B", 0.3)
    return time.perf_counter() - start

async def case_b():
    start = time.perf_counter()
    t1 = asyncio.create_task(work("A", 0.2))
    t2 = asyncio.create_task(work("B", 0.3))
    await t1
    await t2
    return time.perf_counter() - start

async def case_c():
    start = time.perf_counter()
    t1 = asyncio.create_task(work("A", 0.2))
    await asyncio.sleep(0.5)        # 먼저 다른 일
    await t1
    return time.perf_counter() - start

async def run_all():
    print("=== 유제1 ===")
    print(f"  a: {await case_a():.2f}초   예측:__")
    print(f"  b: {await case_b():.2f}초   예측:__")
    print(f"  c: {await case_c():.2f}초   예측:__")

asyncio.run(run_all())

# (a) a와 b의 차이를 "언제 실행이 시작되는가"로 설명:
#   →
# (b) c에서 t1은 언제 완료되나:
#   →


# ═══════════════════════════════════════════════════
# 유제 2. 버그 찾기 — 왜 안 빨라지나
# ═══════════════════════════════════════════════════
async def fetch_all_slow(items):
    results = []
    for item in items:
        r = await work(item, 0.1)
        results.append(r)
    return results

async def measure():
    print("\n=== 유제2 ===")
    start = time.perf_counter()
    await fetch_all_slow(["a", "b", "c", "d", "e"])
    print(f"  소요: {time.perf_counter()-start:.2f}초")

asyncio.run(measure())

# (a) async를 썼는데 왜 0.5초가 걸리나:
#   →
# (b) gather로 고쳐라:
#   →
# (c) TaskGroup으로도 고쳐라 (3.11+):
#   →


# ═══════════════════════════════════════════════════
# 유제 3. gather 예외 동작 확인
# ═══════════════════════════════════════════════════
async def ok(name, sec):
    await asyncio.sleep(sec)
    print(f"    {name} 완료")
    return name

async def fail(sec):
    await asyncio.sleep(sec)
    raise ValueError("에러!")

async def ex3():
    print("\n=== 유제3 ===")
    print("  기본 gather:")
    try:
        await asyncio.gather(ok("A", 0.3), fail(0.1), ok("C", 0.5))
    except ValueError as e:
        print(f"    예외 잡힘: {e}")
    await asyncio.sleep(0.6)      # 나머지가 끝날 시간을 줌
    print("  → 위에서 A, C 완료 메시지가 나왔나?")

asyncio.run(ex3())

# (a) 예외가 발생한 뒤에도 A와 C가 완료 메시지를 출력했나:
#   →
# (b) 이것이 의미하는 바 (gather는 실패 시 나머지를 취소하나?):
#   →
# (c) TaskGroup이라면 어떻게 다른가? 실험해보라:
#   →


# ═══════════════════════════════════════════════════
# 유제 4. 직접 작성 — 동시성 제한 크롤러
# ═══════════════════════════════════════════════════
# 요구사항:
#   - 20개의 "URL"을 처리 (각 0.1초 소요)
#   - 동시 실행은 최대 5개
#   - 결과를 입력 순서대로 반환
#   - 하나가 실패해도 나머지는 완료 (실패는 None으로)

async def fake_fetch(url_id):
    await asyncio.sleep(0.1)
    if url_id == 7:
        raise ValueError(f"url{url_id} 실패")
    return f"data{url_id}"

async def crawl(ids, limit=5):
    # TODO: Semaphore + gather(return_exceptions=True) 조합
    pass

async def ex4():
    print("\n=== 유제4 ===")
    start = time.perf_counter()
    # results = await crawl(list(range(20)))
    # print("  결과:", results)
    # print(f"  시간: {time.perf_counter()-start:.2f}초")

asyncio.run(ex4())

# (a) 20개를 5개씩 제한하면 이론상 몇 초 걸리나:
#   →
# (b) Semaphore를 async with로 쓰는 이유:
#   →
# (c) 실패한 항목을 None으로 바꾸려면 결과를 어떻게 후처리하나:
#   →


# ═══════════════════════════════════════════════════
# 유제 5. 판단 — 코드 리뷰
# ═══════════════════════════════════════════════════
# 아래 코드들의 문제점을 지적하라.

# (A)
async def a():
    asyncio.create_task(background_job())     # 저장 안 함
    return "ok"

# (B)
def b():
    result = fetch_data()                      # 동기 함수에서 코루틴 호출
    return result

# (C)
async def c(urls):
    return await asyncio.gather(*[fetch(u) for u in urls])   # urls가 10000개

# (D)
async def d():
    conn = psycopg2.connect(...)               # 동기 드라이버
    return conn.execute("SELECT ...")

# (E)
async def e():
    asyncio.run(sub_task())                    # 이미 루프 안

print("\n=== 유제5 ===")
# A →
# B →
# C →
# D →
# E →


# 참고용 더미 (실행되지 않음)
async def background_job(): pass
async def fetch_data(): pass
async def fetch(u): pass
class psycopg2:
    @staticmethod
    def connect(*a, **k): pass
async def sub_task(): pass