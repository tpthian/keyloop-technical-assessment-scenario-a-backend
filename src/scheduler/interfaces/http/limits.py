"""Request body size cap (ADR-014): bounded work per request at the HTTP edge.

``BodySizeLimitMiddleware`` is a plain ASGI middleware that wraps ``receive``. The first read of
the body checks a declared ``Content-Length``; every read counts the bytes received, so a body
sent without ``Content-Length`` is capped too. Over the cap, the read raises ``BodyTooLarge``,
which ``errors.py`` answers with 413 ``validation`` in the house error body. The check runs when
the handler reads the body (ADR-008 step 1), so the request has a route and a wide event, and is
never stored on the key. A route that never reads a body is unaffected.
"""

from __future__ import annotations

from scheduler.interfaces.http.events import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 16 * 1024  # a valid booking body stays under 4 KiB with every string at its cap


class BodyTooLarge(Exception):  # noqa: N818 (a 413, named for what the client sent)
    """The request body exceeds ``MAX_BODY_BYTES``."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"request body exceeds {limit} bytes")
        self.message = str(self)


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers") or []:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class BodySizeLimitMiddleware:
    """Mount with ``app.add_middleware(BodySizeLimitMiddleware)`` inside the wide-event one."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = _declared_length(scope)
        received = 0

        async def capped_receive() -> Message:
            nonlocal received
            if declared is not None and declared > self.max_bytes:
                raise BodyTooLarge(self.max_bytes)
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge(self.max_bytes)
            return message

        await self.app(scope, capped_receive, send)
