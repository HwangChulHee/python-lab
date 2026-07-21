"""
generator.py — MiniGenerator: 보관된 프레임을 태워 재개하는 제너레이터

여기가 '비재귀 평가 루프'의 보상이 나오는 자리다. 제너레이터는 '소멸시키지 않고
보관했다가 재개하는 프레임'이다. 프레임을 파이썬 콜스택이 아니라 명시적 리스트로
다뤄 왔기 때문에, YIELD에서 프레임을 스택에서 떼어내 이 객체 안에 보관했다가
(ip·값 스택·지역/셀 변수 그대로) 나중에 다시 스택으로 올려 이어서 실행할 수 있다.

상태:
  CREATED    — 만들어졌지만 본문을 아직 한 줄도 실행하지 않음 (RETURN_GENERATOR 직후)
  RUNNING    — 지금 프레임 스택 위에서 실행 중
  SUSPENDED  — yield로 멈춰 프레임이 보관된 상태 (ip·값 스택 보존)
  COMPLETED  — 본문이 끝남 (StopIteration 의미)
"""


class MiniGenerator:
    """보관된 Frame + 상태. resume은 엔진(MiniPVM)이 프레임 스택을 통해 수행한다."""

    def __init__(self, frame, label):
        self.frame = frame                     # 보관되는 프레임 (ip·값 스택이 그대로 산다)
        self.label = label                     # 표시용 라벨 (예: countdown#1)
        self.state = "CREATED"
        self.on_stop = None                    # 소진 시 뒤처리 정보: ("for", frame, jump) / ("next", frame)

    def __iter__(self):
        return self                            # 제너레이터는 자기 자신이 이터레이터 (GET_ITER용)

    def __repr__(self):
        return f"<gen {self.label} {self.state}>"


def gsend(gen, value):
    """제너레이터에 값을 주입하는 마커. gen.send(v)는 LOAD_ATTR(P4)이 필요하므로,
    P3에서는 이 엔진 제공 함수를 대신 쓴다. 실제 실행은 하지 않고 MiniPVM이 CALL
    지점에서 가로채 resume 경로로 보낸다. (엔진 밖에서 직접 부르면 에러)"""
    raise RuntimeError("gsend는 pvmlab 엔진이 가로채는 마커입니다 — 엔진 밖에서 호출 불가")
