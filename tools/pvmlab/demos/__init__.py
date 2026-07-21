"""
demos — 관찰 대상(데모) 등록

run.py가 장(chapter) 인자로 고르면 해당 데모 모듈만 import한다. 인자가 없으면
demos/ 전체를 import한다. @demo 데코레이터가 이 패키지의 DEMOS 리스트에 등록한다.

새 데모:
    @demo("제목", args=(인자...))          # 한 번 호출
    @demo("제목", calls=[(a,), (b,), ...])  # 같은 트레이스에 여러 번 이어 호출
"""

DEMOS = []   # [{func, args, title, calls}]


def demo(title, args=(), calls=None):
    """관찰 대상 함수를 등록하는 데코레이터.

    args  — 단일 호출용 인자 튜플.
    calls — 여러 번 호출할 때 각 호출의 인자 튜플 리스트. 같은 함수 객체를 이어
            호출해 상태 변화(예: __defaults__ 성장)를 한 트레이스에서 관찰한다.
    """
    def deco(fn):
        DEMOS.append({"func": fn, "args": tuple(args), "title": title, "calls": calls})
        return fn
    return deco
