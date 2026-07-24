"""weblab mini_server — uvicorn의 역할을 최소한으로 재현한 서버.

이 파일이 보여주는 것:
  "서버"의 일 = 소켓에서 바이트를 읽고 → HTTP를 파싱하고 → scope/receive/send를
  만들어서 → 앱(ASGI callable)을 호출하고 → 앱이 보내온 이벤트를 바이트로
  되돌려 소켓에 쓰는 것.

  즉 서버는 우리 비즈니스 로직을 전혀 모른다. 표준 시그니처
  app(scope, receive, send) 하나만 알고, 그걸 호출할 뿐이다.

현재 구현 범위 (u1 시점):
  - HTTP/1.1, 요청 1개당 연결 1개 (keep-alive 없음 → u2에서)
  - 바디는 Content-Length 방식만 (chunked 없음)
  - lifespan 미지원 (u2에서 추가 — 진짜 lifespan은 uvicorn 대조 실행으로 관찰)

실행 예시는 verify.py와 examples.py 참고.
"""
import asyncio
from urllib.parse import unquote


async def handle_connection(app, reader, writer):
    """연결 하나를 처리한다. 서버의 일이 전부 이 함수 안에 있다."""

    # ── 1) 요청 라인 읽기: b"POST /echo?x=1 HTTP/1.1\r\n" ──────────
    request_line = await reader.readline()
    if not request_line:
        writer.close()
        return
    method, target, _http_version = request_line.decode().split(" ", 2)
    path, _, query = target.partition("?")
    print(f"[mini_server] 요청 수신: {method} {target.strip()}")

    # ── 2) 헤더 읽기: 빈 줄(\r\n)이 나올 때까지 ─────────────────────
    headers = []
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        name, _, value = line.decode().partition(":")
        # ASGI 규약: 헤더는 (소문자 이름 bytes, 값 bytes) 쌍의 리스트
        headers.append((name.strip().lower().encode(), value.strip().encode()))

    # ── 3) 바디 읽기: Content-Length 만큼 정확히 ────────────────────
    content_length = 0
    for name, value in headers:
        if name == b"content-length":
            content_length = int(value)
    body = await reader.readexactly(content_length) if content_length else b""

    # ── 4) scope 구성: "이 연결의 불변 메타데이터"를 dict로 ─────────
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": unquote(path),
        "query_string": query.encode(),   # 파싱하지 않는다. bytes 그대로.
        "headers": headers,               # 디코딩하지 않는다. bytes 그대로.
        "client": writer.get_extra_info("peername"),
    }
    print(f"[mini_server] scope 구성 완료: path={scope['path']!r}")

    # ── 5) receive / send 만들기: 앱과 통신할 두 개의 통로 ──────────
    body_delivered = False

    async def receive():
        """앱이 요청 바디를 달라고 할 때 호출하는 함수 (서버 → 앱 방향)."""
        nonlocal body_delivered
        if not body_delivered:
            body_delivered = True
            # 지금은 바디를 이미 다 읽어놨으므로 한 번에 준다.
            # (진짜 서버는 도착한 만큼 청크로 나눠 more_body=True로 준다)
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        """앱이 응답 이벤트를 보낼 때 호출하는 함수 (앱 → 서버 방향).
        이벤트(dict)를 받아 진짜 HTTP 바이트로 바꿔 소켓에 쓴다."""
        if message["type"] == "http.response.start":
            status = message["status"]
            writer.write(f"HTTP/1.1 {status} X\r\n".encode())
            for name, value in message.get("headers", []):
                writer.write(name + b": " + value + b"\r\n")
            writer.write(b"connection: close\r\n\r\n")
            print(f"[mini_server] 응답 시작: status={status}")
        elif message["type"] == "http.response.body":
            writer.write(message.get("body", b""))
            await writer.drain()

    # ── 6) ★ 서버가 앱을 호출한다 — ASGI라는 약속의 전부가 이 한 줄 ──
    await app(scope, receive, send)

    # ── 7) 앱이 리턴했으므로 이 요청은 끝. 연결 정리 ────────────────
    print("[mini_server] 앱 리턴, 연결 종료\n")
    writer.close()
    await writer.wait_closed()


async def serve(app, host="127.0.0.1", port=8900):
    """앱(ASGI callable) 하나를 받아 서빙을 시작한다.
    uvicorn app.main:app 이 하는 일의 뼈대가 이것이다."""
    server = await asyncio.start_server(
        lambda reader, writer: handle_connection(app, reader, writer),
        host, port,
    )
    print(f"[mini_server] http://{host}:{port} 대기 중 (Ctrl+C 종료)")
    async with server:
        await server.serve_forever()


def run(app, host="127.0.0.1", port=8900):
    """동기 세계에서의 진입점."""
    try:
        asyncio.run(serve(app, host, port))
    except KeyboardInterrupt:
        print("\n[mini_server] 종료")
