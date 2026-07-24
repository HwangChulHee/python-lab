"""u2 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 반환값 예측
# ═══════════════════════════════════════════════════
# 각 식의 결과를 예측할 것. True/False가 아니라 "무엇이 반환되는지".
print("=== 유제1 ===")
exprs = [
    '5 and 3',
    '0 and 3',
    '5 or 3',
    '0 or 3',
    '"" or [] or "끝"',
    '1 and 2 and 3',
    '1 and 0 and 3',
    'None or False or 0',
]
for e in exprs:
    print(f"  {e:<22} = {eval(e)!r}    예측:__3,0,5,3,'끝',3,0,0")

# 규칙을 한 문장으로 (언제 멈추고 무엇을 반환하는가):
#   or → True값을 찾을때까지 오른쪽으로 이동하며 그 값이 True 면 그 값을 출력하고 모두 False라면 맨 오른쪽걸 출력한다.
#   and → False값을 찾을때까지 오른쪽으로 이동하며, False면 그 값을 출력하고 모두 True라면 맨 오른쪽걸 출력한다.


# ═══════════════════════════════════════════════════
# 유제 2. 단축 평가 — 실행 순서 추적
# ═══════════════════════════════════════════════════
print("\n=== 유제2 ===")

def trace(name, value):
    print(f"    [{name} 실행]")
    return value

# (a) 각 줄에서 무엇이 출력될지, 결과는 무엇일지 예측:
#     A: 예측 → 5
print("  A: trace('x',0) or trace('y',5) or trace('z',9)")
r = trace("x", 0) or trace("y", 5) or trace("z", 9)
print("    결과:", r)

#     B: 예측 → 0
print("  B: trace('x',1) and trace('y',0) and trace('z',9)")
r = trace("x", 1) and trace("y", 0) and trace("z", 9)
print("    결과:", r)

# z가 두 경우 모두 실행되지 않는 이유:
#   → a의 경우는 y일때 false가 아닌 값인 5가 나왔고, b의 경우에는 y일때 false값인 0이 나와서


# ═══════════════════════════════════════════════════
# 유제 3. 버그 수정 — 설정 로더
# ═══════════════════════════════════════════════════
# 아래 함수는 서버 설정을 읽어 기본값을 채운다.
# 사용자가 명시적으로 0이나 False를 설정한 경우 무시당하는 버그가 있다.

def load_config(user_config):
    return {
        "port":    user_config.get("port") or 8080,
        "debug":   user_config.get("debug") or True,
        "retries": user_config.get("retries") or 3,
        "prefix":  user_config.get("prefix") or "/api",
    }

print("\n=== 유제3 ===")
user = {"port": 3000, "debug": False, "retries": 0, "prefix": ""}
result = load_config(user)
for k, v in result.items():
    print(f"  {k:<9}: 사용자설정={user[k]!r:<8} 최종={v!r}")

# (a) 사용자가 설정한 값 중 무시된 것은 무엇이고, 왜인가:
#   → debug, retries, perfix 값이 무시되었다. 셋다 false 값이기 때문.
# (b) 네 항목 모두 사용자 설정이 존중되도록 고쳐라 (한 가지 방법으로 통일):
#   →  user_config.get("debug", True) 이런식으로 설정.
# (c) 만약 "빈 문자열 prefix는 무효로 치고 기본값을 쓰고 싶다"면
#     그 항목만 어떻게 다르게 처리해야 하나:
#   → 그냥 그대로 놔두면 된다.