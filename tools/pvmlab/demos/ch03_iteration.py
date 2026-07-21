"""
ch03_iteration.py — 03장 '시퀀스와 반복문' 데모

관찰 포인트:
  · for 루프의 정체 = GET_ITER → FOR_ITER ↔ JUMP_BACKWARD 사이클, 소진 시 END_FOR
  · 리스트 컴프리헨션은 3.12부터 인라인 실행(PEP 709) — 별도 프레임이 생기지 않고,
    LIST_APPEND 전용 명령으로 결과를 쌓는다. 같은 결과를 내는 for 루프와 바이트코드를
    나란히 비교해 볼 것.

★ 데모 함수는 모듈 레벨 정의. (P1 §12 지뢰 참조)
"""

from demos import demo


@demo("① for 루프 해부 — GET_ITER · FOR_ITER · JUMP_BACKWARD 사이클")
def for_loop():
    total = 0
    for x in [1, 2, 3]:
        total += x
    return total


@demo("② 컴프리헨션 vs for — 인라인 실행과 LIST_APPEND (PEP 709)")
def comprehension():
    return [x * 2 for x in [1, 2, 3]]
