"""u2 유제"""
import time
from concurrent.futures import ThreadPoolExecutor

# ═══════════════════════════════════════════════════
# 유제 1. 실측 전 예측
# ═══════════════════════════════════════════════════
# measure.py 실행 전에 예측할 것. (배속 = 순차시간 / 병렬시간)
#
# IO-bound (sleep 0.3 x 4개):
#   순차 예상 시간     →
#   스레드 배속 예측    →
#   프로세스 배속 예측  →
#
# CPU-bound 순수 파이썬:
#   스레드 배속 예측    →
#   프로세스 배속 예측  →
#
# CPU-bound hashlib:
#   스레드 배속 예측    →
#
# 실행 후 실제 수치:
#   →
#
# 예측과 크게 달랐던 것과 그 이유:
#   → 이미 먼저.. 돌려봤음. pass.


# ═══════════════════════════════════════════════════
# 유제 2. 왜 IO-bound에 프로세스는 손해인가
# ═══════════════════════════════════════════════════
# measure.py 결과에서 IO-bound의 스레드 배속과 프로세스 배속을 비교하라.
#
# (a) 둘 중 어느 쪽이 빨랐나:
#   → 스레드 배속
# (b) 프로세스가 더 느리다면(또는 비슷하다면) 그 이유 두 가지:
#   → 프로세스가 오버헤드가 더 크니까. 인터프리터를 각각 만들어줘야하는 등의.
# (c) 그럼에도 IO-bound에 프로세스를 쓰는 경우가 있을까? 언제:
#   → 글쎄.. cpu bound가 섞여있는 IO bound에서 쓰지 않을까


# ═══════════════════════════════════════════════════
# 유제 3. 판단 — 이 코드를 어떻게 병렬화할까
# ═══════════════════════════════════════════════════
# 아래 각 함수를 병렬화한다면 스레드/프로세스/asyncio/그대로 중
# 무엇을 택할지 판단하고 근거를 쓰라.

def task_a(urls):
    """100개 URL을 순회하며 requests.get으로 수집"""
    pass

def task_b(images):
    """1000장 이미지를 Pillow로 리사이징 (Pillow는 C 구현)"""
    pass

def task_c(numbers):
    """1억 개 숫자를 순수 파이썬 루프로 합산"""
    pass

def task_d(df):
    """pandas DataFrame에 groupby 집계"""
    pass

def task_e(rows):
    """10만 행을 DB에 INSERT (한 건씩)"""
    pass

print("=== 유제3 ===")
# a → 선택:__스레드  근거: IO 바운드가 주로 있으니
# b → 선택:__스레드  근거: C구현은 GIL 해제도 하고, 이미지 저장이라는 IO bound도 꽤 있으니까
# c → 선택:__프로세스  근거: CPU bound니까
# d → 선택:__스레드  근거: cpu bound긴 하지만 C구현이니까
# e → 선택:__스레드  근거: IO 바운드니까


# ═══════════════════════════════════════════════════
# 유제 4. 워커 수 설계
# ═══════════════════════════════════════════════════
# 시나리오: FastAPI 앱을 gunicorn+uvicorn으로 배포한다.
#   - 컨테이너: CPU 4코어, 메모리 2GB
#   - 워커 하나당 메모리 사용량: 약 300MB
#   - 요청 처리: DB 조회 2회 + 외부 API 1회 (전형적 IO-bound)
#
# (a) 공식(2*코어+1)대로면 워커 수는:
#   → 9
# (b) 메모리 제약을 고려하면 실제 상한은:
#   → 6
# (c) 최종 몇 개로 정하고 왜인가:
#   → 6. 메모리 상한이 이거니까
# (d) 만약 요청 처리에 "PDF 생성"(CPU-bound, 2초 소요)이 추가된다면
#     구조를 어떻게 바꿔야 하나:
#   → 그대로 둘것 같은데


# ═══════════════════════════════════════════════════
# 유제 5. 직접 측정 — 순차 vs 스레드
# ═══════════════════════════════════════════════════
# 아래 IO 작업을 순차와 스레드로 비교하고 배속을 계산하라.


def fake_api_call(n):
    time.sleep(0.2)
    return n * 2

def bench(label, fn, worker_num, executor_cls=None):
    items = list(range(8))
    start = time.perf_counter()
    if executor_cls is None:
        results = [fn(i) for i in items]          # 순차
    else:
        with executor_cls(max_workers=worker_num) as ex:
            results = list(ex.map(fn, items))
    elapsed = time.perf_counter() - start
    print(f"  {label:<24} {elapsed:6.2f}초")
    return elapsed

def compare(name, fn, worker_num):
    print(f"\n=== {name} ===")
    seq = bench("순차", fn, worker_num)
    thr = bench("ThreadPoolExecutor", fn, worker_num, ThreadPoolExecutor)
    # print(f"  → 스레드 배속: {seq/thr:.2f}x   프로세스 배속: {seq/prc:.2f}x")
    

print("\n=== 유제5 ===")
compare("2 : fake_api_call (sleep 0.2s)", fake_api_call, 2)
compare("4 : fake_api_call (sleep 0.2s)", fake_api_call, 4)
compare("8 : fake_api_call (sleep 0.2s)", fake_api_call, 8)
compare("16 : fake_api_call (sleep 0.2s)", fake_api_call, 16)

# TODO: 순차 실행 시간 측정
# TODO: ThreadPoolExecutor(max_workers=8)로 측정
# TODO: max_workers를 2, 4, 8, 16으로 바꿔가며 측정

# (a) max_workers를 늘리면 계속 빨라지나? 어디서 멈추나:
#   → ㅇㅇ io 바운드니까 점점 빨라진다. 하지만 8개가 상한
# (b) 작업이 8개인데 max_workers=16으로 하면 어떻게 되나:
#   → 실행시간 똑같음.
# (c) 실무에서 max_workers를 정할 때 고려할 것:
#   → 해야될 작업의 개수보다 많은 스레드를 할당해봤자 의미는 없다