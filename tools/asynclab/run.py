"""
run.py — asynclab 유일한 진입점

    python run.py            # 검증 3종 통과 → asynclab_trace.html 생성

검증 (하나라도 실패하면 HTML을 만들지 않는다):
  1. 응답 정합   — 미니 루프가 만든 A/B 응답 바이트 == 기대값
  2. 진짜와 대조 — 같은 handle_connection/MiniAPI를 진짜 asyncio 위에서 돌려도
                   같은 응답 (코루틴 코드는 진짜다 — 루프만 재현했다)
  3. 결정성     — 두 번 실행한 트레이스의 재개 순서가 동일
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.selector import ScriptedSelector
from engine.channel import MiniListener
from engine.loop import MiniEventLoop
from engine.tracer import Tracer
from demos import mini_web
import viewer

LISTEN_FD = 3

# 각본: 나중에 접속한 B의 바이트가 먼저 도착한다 — "A가 느려도 B는 안 막힌다".
REQ_LINE = b"GET /ping HTTP/1.1\r\n"
REQ_REST = b"host: local\r\ncontent-length: 0\r\n\r\n"
SCRIPT = [
    (1, "connect", LISTEN_FD, ("A", 4), "T=1 A 접속(fd 4)"),
    (2, "connect", LISTEN_FD, ("B", 5), "T=2 B 접속(fd 5)"),
    (3, "data", 5, REQ_LINE, "T=3 B 요청라인 도착"),
    (4, "data", 5, REQ_REST, "T=4 B 헤더+바디 도착"),
    (5, "data", 4, REQ_LINE, "T=5 A 요청라인 도착"),
    (6, "data", 4, REQ_REST, "T=6 A 헤더+바디 도착"),
]
EXPECTED = b"HTTP/1.1 200 OK\r\ncontent-length: 5\r\n\r\npong\n"


def build_trace():
    """미니 루프로 각본을 1회 실행 → (스텝 리스트, 재개 순서, fd별 응답 바이트)."""
    selector = ScriptedSelector(SCRIPT, {LISTEN_FD: "listen"})
    tracer = Tracer(selector, mini_web.__file__)
    loop = MiniEventLoop(selector, tracer)
    tracer.loop = loop
    tracer.func_cards = [
        {"name": "serve", "note": "함수 객체 — 호출하면 코루틴 객체가 나온다"},
        {"name": "handle_connection", "note": "함수 객체 — 손님마다 한 번씩 호출된다"},
        {"name": "app (MiniAPI 인스턴스)", "note": "async __call__ 을 가진 콜러블"},
        {"name": "ping", "note": "라우트 핸들러 함수 객체"},
    ]

    app = mini_web.make_app()
    listener = MiniListener(selector, LISTEN_FD)
    loop.run_until_complete(mini_web.serve(loop, app, listener), label="serve")

    order = [s["running"] for s in tracer.steps if s["kind"] == "resume"]
    return tracer.steps, order, {fd: bytes(b) for fd, b in selector.sent.items()}


def verify_against_real_asyncio():
    """검증 2 — 같은 코루틴 코드를 진짜 asyncio 위에서 돌려 응답을 대조한다."""
    class CollectWriter:                       # StreamWriter 대역: write/drain만
        def __init__(self):
            self.sent = bytearray()

        def write(self, data):
            self.sent.extend(data)

        async def drain(self):
            pass

    async def one_request():
        reader = asyncio.StreamReader()
        reader.feed_data(REQ_LINE + REQ_REST)
        reader.feed_eof()
        writer = CollectWriter()
        await mini_web.handle_connection(mini_web.make_app(), reader, writer)
        return bytes(writer.sent)

    return asyncio.run(one_request())


def main():
    ap = argparse.ArgumentParser(description="asynclab — 코루틴·이벤트 루프 시각화")
    ap.add_argument("-o", "--out", default="asynclab_trace.html")
    args = ap.parse_args()

    steps, order, sent = build_trace()

    # 검증 1 — 응답 정합
    assert sent[4] == EXPECTED, f"A 응답 불일치: {sent[4]!r}"
    assert sent[5] == EXPECTED, f"B 응답 불일치: {sent[5]!r}"
    print(f"검증 1 OK — 미니 루프 응답 A/B == 기대값 ({EXPECTED!r})")

    # 검증 2 — 진짜 asyncio와 대조
    real = verify_against_real_asyncio()
    assert real == sent[4] == sent[5], f"진짜 asyncio 응답 불일치: {real!r}"
    print("검증 2 OK — 같은 코루틴 코드가 진짜 asyncio에서도 같은 응답을 낸다")

    # 검증 3 — 재개 순서 결정성
    steps2, order2, _ = build_trace()
    assert order == order2, f"재개 순서 비결정: {order} != {order2}"
    print(f"검증 3 OK — 재개 순서 결정적: {' → '.join(order)}")

    src_lines = Path(mini_web.__file__).read_text(encoding="utf-8").splitlines()
    html = viewer.build_html({
        "title": "asynclab — 코루틴·이벤트 루프",
        "subtitle": "코루틴은 진짜, 이벤트 루프와 네트워크만 재현 — 한 스텝 = 루프의 사건 하나",
        "src": src_lines,
        # 호출부 — 이 소스가 실행되기까지의 배선 (build_trace()의 실제 코드 요약)
        "boot": [
            'selector = ScriptedSelector(SCRIPT, {3: "listen"})  # 각본 네트워크 = 가짜 OS',
            "loop     = MiniEventLoop(selector, tracer)          # 미니 이벤트 루프",
            "app      = make_app()                               # MiniAPI + GET /ping 라우트",
            "listener = MiniListener(selector, fd=3)             # listen 소켓의 축약",
            "loop.run_until_complete(serve(loop, app, listener)) # ← asyncio.run(...)에 해당",
        ],
        "script": [{"t": e[0], "desc": e[4]} for e in SCRIPT],
        "steps": steps,
    })
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"\n생성 완료 → {out}  (스텝 {len(steps)}개)")


if __name__ == "__main__":
    main()
