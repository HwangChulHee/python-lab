"""
mini_web.py — weblab(mini_server + mini_framework)의 축약판 (관찰 대상 코드)

tools/weblab의 실제 코드에서 줄 구조·변수명·ASGI 이벤트(dict)를 그대로 유지하고
print / lifespan / 연결 정리만 덜어냈다. 코루틴은 전부 진짜 async def다 —
미니 루프에서도, 진짜 asyncio(= uvicorn이 서는 자리) 위에서도 그대로 돈다.
"""
from urllib.parse import unquote


async def serve(loop, app, listener):
    """uvicorn / asyncio.start_server의 자리 — 접속마다 handle_connection 하나씩.
    손님 1명 = 코루틴 1개 = 프레임 1개."""
    while True:
        name, reader, writer = await listener.accept()
        loop.start_task(handle_connection(app, reader, writer),
                        label=f"client_{name}")


async def handle_connection(app, reader, writer):
    """연결 하나를 처리한다. '서버(mini_server)'의 일이 전부 이 함수 안에 있다."""
    # 1) 요청 라인 읽기: b"POST /echo HTTP/1.1\r\n"
    request_line = await reader.readline()
    method, target, _http_version = request_line.decode().split(" ", 2)
    path, _, query = target.partition("?")

    # 2) 헤더 읽기: 빈 줄까지. ASGI 규약대로 (소문자 이름 bytes, 값 bytes) 쌍
    headers = []
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break
        name, _, value = line.decode().partition(":")
        headers.append((name.strip().lower().encode(), value.strip().encode()))

    # 3) 바디 읽기: Content-Length 만큼 정확히
    content_length = 0
    for name, value in headers:
        if name == b"content-length":
            content_length = int(value)
    body = await reader.readexactly(content_length) if content_length else b""

    # 4) scope 구성: "이 연결의 불변 메타데이터"
    scope = {"type": "http", "http_version": "1.1", "method": method,
             "path": unquote(path), "query_string": query.encode(),
             "headers": headers}

    # 5) receive / send — 앱과 통신할 두 개의 통로
    body_delivered = False

    async def receive():
        """앱이 요청 바디를 달라고 할 때 호출 (서버 → 앱 방향)."""
        nonlocal body_delivered
        if not body_delivered:
            body_delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        """앱이 응답 이벤트를 보낼 때 호출 (앱 → 서버 방향). 이벤트 → HTTP 바이트."""
        if message["type"] == "http.response.start":
            writer.write(f"HTTP/1.1 {message['status']} X\r\n".encode())
            for name, value in message.get("headers", []):
                writer.write(name + b": " + value + b"\r\n")
            writer.write(b"connection: close\r\n\r\n")
        elif message["type"] == "http.response.body":
            writer.write(message.get("body", b""))
            await writer.drain()

    # 6) ★ 서버가 앱을 호출한다 — ASGI라는 약속의 전부가 이 한 줄
    await app(scope, receive, send)


class MiniAPI:
    """'프레임워크(mini_framework)'의 일 — ASGI 저수준 계약을 개발자 대신 상대한다.
    (lifespan / scope["type"] 검사는 축약에서 생략)"""

    def __init__(self):
        self.routes = {}                  # ("GET", "/hello") → 핸들러

    def add_route(self, method, path, handler):
        self.routes[(method.upper(), path)] = handler

    async def __call__(self, scope, receive, send):
        # 일 1: 라우팅 (scope를 보고 핸들러 결정)
        handler = self.routes.get((scope["method"], scope["path"]))
        if handler is None:
            await self._respond(send, 404, b"not found\n")
            return
        # 일 2: 저수준 이벤트 → 편한 값
        body = await self._read_body(receive)
        # 일 3: 개발자 코드 호출
        status, response_body = await handler(scope, body)
        # 일 4: 반환값 → 다시 ASGI 이벤트
        await self._respond(send, status, response_body)

    async def _read_body(self, receive):
        """receive 이벤트들을 모아 바디 bytes 하나로."""
        chunks = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                break
        return b"".join(chunks)

    async def _respond(self, send, status, body):
        """(status, bytes) → ASGI 응답 이벤트 두 개."""
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


# ── 데모 앱: 프레임워크 사용자의 코드는 이만큼만 (weblab verify.py와 동일) ──
async def hello(scope, body):
    return 200, "안녕, weblab\n".encode()


async def echo(scope, body):
    return 200, body if body else b"(empty)\n"


def make_app():
    app = MiniAPI()
    app.add_route("GET", "/hello", hello)
    app.add_route("POST", "/echo", echo)
    return app
