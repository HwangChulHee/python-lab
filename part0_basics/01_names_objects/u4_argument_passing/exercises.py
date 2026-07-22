"""u4 유제"""

# ═══════════════════════════════════════════════════
# 유제 1. 예측 — 함수가 바깥을 바꾸나
# ═══════════════════════════════════════════════════
# 각 함수 호출 후 바깥 변수의 값을 예측하고, 변경/재대입 중 무엇인지 쓸 것.

def f1(x): x.append(0)
def f2(x): x = x + [0]
def f3(x): x += [0]
def f4(x): x[0] = 99
def f5(x): x = 999

print("=== 유제1 ===")

a = [1, 2]; f1(a); print("  f1:", a, " 예측:__[1,2,0]  (변경/재대입:__변경)")
a = [1, 2]; f2(a); print("  f2:", a, " 예측:__[1,2]  (변경/재대입:__재대입)")
a = [1, 2]; f3(a); print("  f3:", a, " 예측:__[1,2,0]  (변경/재대입:__변경)")
a = [1, 2]; f4(a); print("  f4:", a, " 예측:__[99, 2]  (변경/재대입:__변경)")
a = 1;      f5(a); print("  f5:", a, " 예측:__1  (변경/재대입:__재대입)")

# f2와 f3의 결과가 다르다면 왜? (u2 유제 1에서 본 것):
#   → +=가 mutation이기 때문에.


# ═══════════════════════════════════════════════════
# 유제 2. 방어적 복사
# ═══════════════════════════════════════════════════
# 아래 함수는 입력 리스트를 정렬해서 반환하려 한다.
# 그런데 호출자의 원본까지 바꿔버린다. 문제와 해결.

def get_sorted(data):
    data.sort()          # sort는 in-place (변경)
    return data

original = [3, 1, 2]
result = get_sorted(original)
print("\n=== 유제2 ===")
print("  result   :", result)
print("  original :", original)     # 원본도 정렬돼버림!

# (a) 왜 original까지 바뀌나 (화살표로):
#   → .sort가 mutation 연산이라서
# (b) original을 지키려면 get_sorted를 어떻게 고치나 (두 가지 방법):
#   방법1 → data = data.sort() / 맞는지 모르겠네
#   방법2 →   (힌트: sorted() 내장 함수는 sort()와 뭐가 다른가)


# ═══════════════════════════════════════════════════
# 유제 3. 함정 종합 — 이 코드의 출력은?
# ═══════════════════════════════════════════════════
# u1~u4 전체를 동원해야 한다. 실행 전에 예측할 것.

def add_user(name, users=[]):
    users.append(name)
    return users

print("\n=== 유제3 ===")
list_a = add_user("Alice")           # 예측:__[Alice]
list_b = add_user("Bob")             # 예측:__[Alice, Bob]
list_c = add_user("Carol", [])       # 예측:__[Carol]
list_d = add_user("Dave")            # 예측:__[Alice, Bob, Dave]

print("  a:", list_a)
print("  b:", list_b)
print("  c:", list_c)
print("  d:", list_d)
print("  a is b:", list_a is list_b)   # 예측:__True
print("  a is c:", list_a is list_c)   # 예측:__False

# (a) list_c만 다른 결과인 이유:
#   → 인자로 새로운 리스트를 주니까
# (b) list_a, list_b, list_d가 같은 객체인 이유:
#   → 인자 없으면 __default__에 저장된 리스트 객체를 쓰니까
# (c) 이 함수를 올바르게 고치면:
#   → 
'''
def add_user(name, users=None):
    if users is None :
        users = []
    users.append(name)
    return users
'''
