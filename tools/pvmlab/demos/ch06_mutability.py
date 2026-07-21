"""
ch06_mutability.py — 06장 '가변성과 별칭' 데모

관찰 포인트:
  · 별칭(aliasing): b = a 는 리스트를 복사하지 않는다. 두 이름이 '같은 객체'를
    가리킨다. 값 스택에 실린 값에 붙는 <objN> 라벨이 같으면 같은 객체다.
    b += [3] 은 그 하나의 객체를 제자리에서 늘리므로 a도 함께 바뀐다.
  · 첨자 접근/언패킹: BINARY_SUBSCR·STORE_SUBSCR·UNPACK_SEQUENCE의 스택 동작.

★ 데모 함수는 모듈 레벨 정의.
"""

from demos import demo


@demo("③ 별칭과 복사 — b = a 는 같은 객체 (<objN> 라벨로 확인)")
def aliasing():
    a = [1, 2]
    b = a            # 복사가 아니라 같은 객체에 이름 하나 더
    b += [3]         # 그 하나의 객체를 제자리에서 늘림 → a도 [1, 2, 3]
    return a


@demo("④ 첨자와 언패킹 — SUBSCR · UNPACK_SEQUENCE")
def subscript_unpack():
    pair = (10, 20)
    x, y = pair      # UNPACK_SEQUENCE
    nums = [x, y]
    nums[0] = nums[1]  # BINARY_SUBSCR(읽기) + STORE_SUBSCR(쓰기)
    return nums[0]
