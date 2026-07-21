"""
ch10_generators.py — 10장 '제너레이터' 데모

관찰 포인트:
  · 제너레이터 함수를 '호출'해도 본문은 0줄 실행된다 — RETURN_GENERATOR가 프레임을
    보관한 객체만 돌려준다.
  · YIELD_VALUE는 프레임을 '보관'하고, RETURN은 '소멸'한다. 이 차이가 프레임이
    스택 ↔ '보관된 프레임' 패널을 오가는 왕복으로 눈에 보인다.
  · next(gen)로 재개하면 보관 프레임이 멈췄던 ip부터 이어 실행되고, gsend로 보낸
    값이 보관 프레임의 값 스택에 꽂힌다(= yield 표현식의 결과).

★ 제너레이터 함수는 모듈 레벨. 제너레이터 안에서 또 함수를 호출하는 케이스는 P3
  범위 밖(프레임 소유권 복잡) — 단순 케이스만 둔다.
  gen.send(v)는 LOAD_ATTR(속성 접근, P4)이 필요하므로, P3에서는 엔진 제공 마커
  gsend(gen, v)를 대신 쓴다. 대조값은 실제 .send()를 쓰는 ref 함수로 계산한다.
"""

from demos import demo
from engine import gsend


def countdown(n):
    while n:
        yield n
        n -= 1


@demo("① countdown — 프레임이 스택↔보관 패널을 오가는 왕복 (next 3회)")
def countdown_demo():
    g = countdown(3)
    return (next(g), next(g), next(g))     # (3, 2, 1)


@demo("② 제너레이터를 for로 — FOR_ITER가 내부적으로 resume을 반복")
def for_gen_demo():
    total = 0
    for v in countdown(3):
        total += v
    return total                           # 3 + 2 + 1 = 6


def accum():
    total = 0
    while True:
        x = yield total                    # 보낸 값이 x로 들어온다
        total += x


def _accum_ref():
    """진짜 CPython 대조용 — 실제 .send()를 쓴다(엔진 밖에서 정상 실행)."""
    g = accum()
    next(g)                                # 프라이밍 → 0을 yield
    a = g.send(10)                         # 10을 보냄 → 10을 yield
    b = g.send(20)                         # 20을 보냄 → 30을 yield
    return (a, b)


@demo("③ send로 값 주입 — 누적기 제너레이터 (gsend)", ref=_accum_ref)
def accum_demo():
    g = accum()
    next(g)                                # 프라이밍 → 0을 yield
    a = gsend(g, 10)                       # 10을 보냄 → 10
    b = gsend(g, 20)                       # 20을 보냄 → 30
    return (a, b)                          # (10, 30)
