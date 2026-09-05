"""Consumer abandonment must release a queue-blocked stream producer."""

# pyright: reportPrivateUsage=false

import threading
import time

import httpx
import pytest

from global_medicines_atlas import platinum_checkpoint


def test_size_rejection_releases_producer(monkeypatch):
    threads = []
    original = threading.Thread

    def capture(*args, **kwargs):
        thread = original(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(platinum_checkpoint.threading, "Thread", capture)

    class ManyChunks(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(8):
                yield b"x" * (64 * 1024)

    response = httpx.Response(200, stream=ManyChunks())
    with pytest.raises(ValueError, match="size"):
        platinum_checkpoint._read_until_deadline(
            response, limit=1, deadline=time.monotonic() + 2
        )
    assert len(threads) == 1
    threads[0].join(timeout=0.5)
    assert not threads[0].is_alive()


def test_late_chunk_after_deadline_does_not_leak_completion_put(monkeypatch):
    threads = []
    original = threading.Thread
    release = threading.Event()

    def capture(*args, **kwargs):
        thread = original(*args, **kwargs)
        threads.append(thread)
        return thread

    monkeypatch.setattr(platinum_checkpoint.threading, "Thread", capture)

    class LateChunk(httpx.SyncByteStream):
        def __iter__(self):
            release.wait(timeout=1)
            yield b"late"

    response = httpx.Response(200, stream=LateChunk())
    try:
        with pytest.raises(ValueError, match="deadline"):
            platinum_checkpoint._read_until_deadline(
                response, limit=10, deadline=time.monotonic() + 0.01
            )
    finally:
        release.set()
    threads[0].join(timeout=0.5)
    assert not threads[0].is_alive()
