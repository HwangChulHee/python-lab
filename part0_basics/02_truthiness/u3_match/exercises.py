"""u3 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 매칭 예측
# ═══════════════════════════════════════════════════
def what(v):
    match v:
        case []:
            return "빈 시퀀스"
        case [x]:
            return f"원소1개: {x}"
        case [x, y]:
            return f"원소2개: {x},{y}"
        case [x, *rest]:
            return f"첫={x} 나머지={rest}"
        case {"a": v2}:
            return f"a키 있음: {v2}"
        case str() as s:
            return f"문자열: {s}"
        case _:
            return "기타"

print("=== 유제1 ===")
for v in [[], [1], (1,2), [1,2,3], {"a":9}, {"a":9,"b":8}, "ab", 42]:
    print(f"  {str(v):<15} → {what(v)}   예측:__빈 시퀀스, 원소 1개, 원소 2개, 원소 2개, 첫 1 나머지 2,3, a키있음 9, a키 있음 9, 문자열: ab, 기타")

# 헷갈린 것과 이유:
#   - (1,2)가 [x,y]에 매칭되나?           → 매칭될 것이다. 시퀀스는 다 ok이므로
#   - "ab"가 [x,y]에 매칭되나?            → x 문자열은 시퀀스로 처리안하는것으로 알고있음
#   - {"a":9,"b":8}이 {"a":v2}에 매칭되나? → ㅇㅇ. 매칭되지 않을까?


# ═══════════════════════════════════════════════════
# 유제 2. 버그 찾기 — 왜 항상 첫 케이스인가
# ═══════════════════════════════════════════════════
OK = 200
NOT_FOUND = 404

class Status:
    OK = 200
    NOT_FOUND = 404
    

def status_message(code):
    match code:
        case Status.OK:
            return "정상"
        case Status.NOT_FOUND:
            return "없음"
        case _:
            return "기타"

print("\n=== 유제2 ===")
for c in [200, 404, 500]:
    print(f"  {c} → {status_message(c)}")

# (a) 무엇이 잘못됐나 (전부 같은 결과가 나오는 이유):
#   → OK, NOT_FOUND를 클래스화 안시키고 일반변수로서 사용해서 값이 바인딩되어 같은 결과가 나온다.
# (b) 두 가지 방법으로 고쳐라:
#   방법1 (클래스나 Enum 사용) → 했음
#   방법2 (match를 안 쓰고) → 귀찮


# ═══════════════════════════════════════════════════
# 유제 3. 직접 작성 — API 응답 파서
# ═══════════════════════════════════════════════════
# 아래 형태의 응답들을 match로 처리하는 함수를 작성하라.
#
#   {"status": "ok", "data": [...]}          → f"성공: {len(데이터)}건"
#   {"status": "error", "message": msg}      → f"실패: {msg}"
#   {"status": "ok", "data": []}             → "성공: 결과 없음"
#   그 외                                     → "알 수 없는 응답"
#
# 힌트: 빈 리스트를 먼저 잡아야 한다. 케이스 순서가 중요하다.

def parse_response(res):
    match res:
        # TODO: 작성
        case {"status": "ok", "data" : x} if len(x) > 0 :
            return f"성공 : {len(x)}건"
        case {"status": "ok", "data" : x} if len(x) == 0 :
                return f"성공 : 결과 없음"
        case {"status": "error", "message" : msg} :
            return f"실패 : {msg}"
        case _:
            return "알 수 없는 응답"

print("\n=== 유제3 ===")
tests = [
    {"status": "ok", "data": [1,2,3]},
    {"status": "ok", "data": []},
    {"status": "error", "message": "타임아웃"},
    {"status": "weird"},
    "문자열",
]
for t in tests:
    print(f"  {str(t):<45} → {parse_response(t)}")

# (a) 케이스 순서를 왜 그렇게 잡았나:
#   → 딱히 신경 안썼는데..
# (b) 만약 {"status":"ok","data":[]} 케이스를 맨 아래에 두면 어떻게 되나:
#   → 흠 모르겠다