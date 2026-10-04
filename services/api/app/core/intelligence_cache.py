"""Prevent a browser or proxy from retaining scoped intelligence, including errors."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class IntelligenceCacheMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        private = scope["type"] == "http" and scope.get("path", "").startswith(
            "/intelligence/v2/forecasts"
        )

        async def private_send(message: Message) -> None:
            if private and message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"cache-control", b"vary"}
                ]
                vary = [
                    value for key, value in message.get("headers", []) if key.lower() == b"vary"
                ]
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"vary", b", ".join([*vary, b"Authorization"])),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, private_send)
