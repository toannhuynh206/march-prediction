"""Server-Sent Events endpoint for live bracket pruning updates."""

import asyncio
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api", tags=["events"])

# Simple in-memory event bus for SSE
# In production, use Redis pub/sub or similar
_event_queue: asyncio.Queue | None = None


def get_event_queue() -> asyncio.Queue:
    """Get or create the global event queue."""
    global _event_queue
    if _event_queue is None:
        _event_queue = asyncio.Queue(maxsize=100)
    return _event_queue


async def publish_event(event_type: str, data: dict) -> None:
    """Publish an event to all SSE listeners."""
    queue = get_event_queue()
    event = {"type": event_type, "data": data}
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        # Drop oldest event if queue is full
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        queue.put_nowait(event)


async def _event_generator():
    """Generate SSE events."""
    queue = get_event_queue()
    yield "data: {\"type\": \"connected\"}\n\n"

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            # Send keepalive
            yield ": keepalive\n\n"


@router.get("/events")
async def sse_events():
    """SSE stream for real-time bracket updates."""
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
