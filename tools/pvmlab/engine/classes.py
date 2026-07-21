"""
classes.py — 클래스 생성 관련 공용 마커

LOAD_BUILD_CLASS는 스택에 '클래스를 짓는 함수'(__build_class__)를 올린다. 진짜
__build_class__는 C 함수라 그걸 그대로 부르면 클래스 본문이 C 안에서 실행돼 우리
루프에 안 잡힌다. 그래서 엔진은 이 마커를 대신 올려 두고, CALL 지점에서 가로채
클래스 본문을 '우리 프레임'으로 실행한다 — '클래스 본문도 프레임에서 실행되는 코드'
라는 장면을 위해서다.
"""


class _BuildClassMarker:
    """LOAD_BUILD_CLASS가 스택에 올리는 마커. MiniPVM이 CALL에서 이걸 알아보고
    클래스 본문을 프레임으로 실행한다."""
    _pvm_label = "__build_class__ (엔진 가로채기)"

    def __repr__(self):
        return "__build_class__"


BUILD_CLASS = _BuildClassMarker()
