"""weblab mini_framework — FastAPI의 역할을 최소한으로 재현한 프레임워크.

이 파일이 보여주는 것:
  "프레임워크"의 일 = ASGI 규약(scope, receive, send)이라는 저수준 계약을
  개발자 대신 상대해 주고, 개발자에게는 편한 인터페이스(핸들러 함수)만
  노출하는 것.

  MiniAPI 인스턴스 자체가 ASGI callable이다. 그래서 mini_server 위에서도,
  진짜 uvicorn 위에서도 똑같이 돈다. 이것이 표준 규약의 힘이다.

핸들러 계약 (u1 시점의 임시 계약 — 이후 장에서 FastAPI처럼 진화한다):
  async def handler(scope, body: bytes) -> (status: int, response_body: bytes)

현재 구현 범위 (u1 시점):
  - 정확히 일치하는 (메서드, 경로) 라우팅만. 경로 파라미터 없음 (→ 이후 장)
  - Depends, Pydantic 검증, 미들웨어 없음 (→ 각각 해당 장에서 추가)
  - lifespan은 "규약대로 응답만" 한다 (startup/shutdown에 할 일이 아직 없으므로)
"""


class MiniAPI:
    def __init__(self):
        # 라우팅 테이블: ("GET", "/hello") -> 핸들러 함수
        self.routes = {}

    def add_route(self, method, path, handler):
        """개발자가 쓰는 유일한 등록 인터페이스.
        (FastAPI의 @app.get("/hello") 데코레이터가 하는 일의 본질도
         결국 이 dict에 함수를 넣는 것이다 — 데코레이터 버전은 이후 장에서)"""
        self.routes[(method.upper(), path)] = handler

    # ── MiniAPI 인스턴스를 "호출 가능"하게 만드는 던더 메서드 ──────────
    # 서버는 await app(scope, receive, send) 라고 부른다.
    # app이 함수든, __call__을 가진 객체든 서버는 구분하지 않는다.
    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return

        if scope["type"] != "http":
            return  # websocket 등은 아직 모르는 척

        # ── 프레임워크의 일 1: 라우팅 (scope를 보고 핸들러 결정) ──────
        handler = self.routes.get((scope["method"], scope["path"]))
        print(f"[mini_framework] 라우팅: {scope['method']} {scope['path']}"
              f" -> {handler.__name__ if handler else '없음(404)'}")
        if handler is None:
            await self._respond(send, 404, b"not found\n")
            return

        # ── 프레임워크의 일 2: 저수준 이벤트를 편한 값으로 변환 ────────
        body = await self._read_body(receive)

        # ── 프레임워크의 일 3: 개발자 코드 호출 ──────────────────────
        status, response_body = await handler(scope, body)

        # ── 프레임워크의 일 4: 반환값을 다시 ASGI 이벤트로 변환 ────────
        await self._respond(send, status, response_body)

    async def _read_body(self, receive):
        """receive 이벤트들을 모아 바디 bytes 하나로 만든다.
        핸들러가 이벤트 스트림을 몰라도 되는 건 이 함수 덕분이다."""
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
        """(status, bytes)를 ASGI 응답 이벤트 두 개로 변환해 전송한다."""
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def _handle_lifespan(self, receive, send):
        """서버 기동/종료 알림에 규약대로 응답한다.
        나중에 'DB 커넥션 풀 만들기' 같은 일이 startup 자리에 들어온다."""
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                print("[mini_framework] lifespan: startup 수신")
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                print("[mini_framework] lifespan: shutdown 수신")
                await send({"type": "lifespan.shutdown.complete"})
                return
