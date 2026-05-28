import pytest
from httpx import ASGITransport

from app.core.max_client import MaxClient, MaxApiError, MaxUserBlocked
from tests.fixtures.mock_max import create_mock_max_app


@pytest.fixture
def mock_max():
    app = create_mock_max_app()
    transport = ASGITransport(app=app)
    return app, transport


async def test_send_message_to_user(mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)
    result = await client.send_message(user_id=12345, text="привет")
    assert result["message"]["body"]["text"] == "привет"
    assert result["message"]["user_id"] == 12345
    await client.close()


async def test_get_me(mock_max):
    _, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)
    me = await client.get_me()
    assert me["is_bot"] is True
    assert me["username"] == "test_bot"
    await client.close()


async def test_send_message_inline_keyboard(mock_max):
    app, transport = mock_max
    client = MaxClient(token="test-token", base_url="http://mock-max", transport=transport)
    await client.send_message(
        user_id=999,
        text="меню",
        keyboard=[[{"type": "callback", "text": "OK", "payload": "ok"}]],
    )
    sent = app.state.mock["sent_messages"]
    assert sent[-1]["body"]["attachments"][0]["type"] == "inline_keyboard"
    await client.close()


async def test_answer_callback(mock_max):
    app, transport = mock_max
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    await client.answer_callback(callback_id="cb1", notification="принято")
    answers = app.state.mock["answers"]
    assert answers[-1]["callback_id"] == "cb1"
    assert answers[-1]["body"]["notification"] == "принято"
    await client.close()


async def test_typing_on(mock_max):
    app, transport = mock_max
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    await client.typing_on(chat_id=42)
    actions = app.state.mock["actions"]
    assert actions[-1]["chat_id"] == 42
    assert actions[-1]["action"]["action"] == "typing_on"
    await client.close()


async def test_upload_file(mock_max):
    _, transport = mock_max
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    result = await client.upload_file(data=b"hello", kind="image")
    assert "token" in result
    assert result["url"].startswith("https://")
    await client.close()


async def test_4xx_raises_api_error(mock_max):
    app, transport = mock_max
    app.state.mock["fail_next"] = 400
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    with pytest.raises(MaxApiError) as exc:
        await client.send_message(user_id=1, text="x")
    assert exc.value.status == 400
    await client.close()


async def test_403_raises_user_blocked(mock_max):
    app, transport = mock_max
    app.state.mock["fail_next"] = 403
    client = MaxClient(token="t", base_url="http://mock-max", transport=transport)
    with pytest.raises(MaxUserBlocked):
        await client.send_message(user_id=1, text="x")
    await client.close()


async def test_edit_message_sends_put_with_message_id_and_attachments():
    import json as _json

    import httpx

    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["json"] = _json.loads(request.content.decode())
        return httpx.Response(200, json={"ok": True})

    client = MaxClient(token="t", transport=httpx.MockTransport(handler))
    await client.edit_message(
        message_id="mid-1",
        text="новый",
        attachments=[{"type": "image", "payload": {"token": "tok"}}],
    )
    await client.close()
    assert captured["method"] == "PUT"
    assert "/messages" in captured["url"]
    assert "message_id=mid-1" in captured["url"]
    assert captured["json"]["text"] == "новый"
    assert captured["json"]["attachments"][0] == {"type": "image", "payload": {"token": "tok"}}


async def test_edit_message_omits_attachments_when_none():
    import json as _json

    import httpx

    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = _json.loads(request.content.decode())
        return httpx.Response(200, json={"ok": True})

    client = MaxClient(token="t", transport=httpx.MockTransport(handler))
    await client.edit_message(message_id="mid-2", text="только текст")
    await client.close()
    assert "attachments" not in captured["json"]


async def test_upload_image_for_attachment_two_step_flow():
    """MAX upload: POST /uploads?type=image → {url}, потом POST на url → {token}."""
    import httpx
    import json as _json
    calls: list[dict] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append({"method": request.method, "url": url})
        if "/uploads" in url and "type=image" in url:
            return httpx.Response(200, json={"url": "https://upload.example/file?sig=abc"})
        if "upload.example" in url:
            assert request.content == b"PNG-bytes"
            return httpx.Response(200, json={"token": "tok-XYZ"})
        return httpx.Response(404)

    client = MaxClient(token="t", transport=httpx.MockTransport(handler))
    att = await client.upload_image_for_attachment(data=b"PNG-bytes")
    await client.close()
    assert att == {"type": "image", "payload": {"token": "tok-XYZ"}}
    # Должны быть оба шага.
    assert len(calls) == 2
    assert "/uploads" in calls[0]["url"]
    assert "upload.example" in calls[1]["url"]
