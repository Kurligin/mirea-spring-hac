from app.core.qr_render import render_qr_png


def test_render_qr_returns_png_bytes():
    data = render_qr_png("hello-world")
    # PNG-magic = 89 50 4E 47 0D 0A 1A 0A
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 200


def test_render_qr_is_deterministic_for_same_input():
    a = render_qr_png("abc")
    b = render_qr_png("abc")
    assert a == b


def test_render_qr_changes_with_payload():
    a = render_qr_png("abc")
    b = render_qr_png("abd")
    assert a != b
