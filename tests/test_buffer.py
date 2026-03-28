from src.observer.buffer import FrameBuffer


def test_add_frame():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    buf.add_frame(b"fake-jpeg-data")
    assert len(buf._frames) == 1


def test_snapshot_returns_frames():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    for i in range(5):
        buf.add_frame(f"frame-{i}".encode())
    snapshot = buf.snapshot()
    assert len(snapshot) == 5
    assert all(isinstance(ts, str) and isinstance(data, bytes) for ts, data in snapshot)


def test_snapshot_clears_buffer():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    for i in range(5):
        buf.add_frame(f"frame-{i}".encode())
    buf.snapshot()
    assert len(buf._frames) == 0


def test_should_dispatch_false_when_empty():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    assert not buf.should_dispatch()


def test_expected_frame_count():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    assert buf.expected_frame_count == 10
