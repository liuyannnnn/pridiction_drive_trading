from collections.abc import Awaitable, Callable


Handler = Callable[[object], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def subscribe(self, topic: str, handler: Handler) -> None:
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    async def publish(self, topic: str, payload: object) -> None:
        for handler in self._handlers.get(topic, []):
            await handler(payload)
