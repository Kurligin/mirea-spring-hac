from app.bot.update_queue import update_queue


async def _drain_queue():
    while not update_queue.empty():
        update_queue.get_nowait()


async def test_webhook_with_valid_secret_enqueues_update(client):
    await _drain_queue()
    payload = {"update_type": "message_created", "message": {"text": "hi"}}
    resp = await client.post(
        "/max/webhook",
        json=payload,
        headers={"X-Max-Bot-Api-Secret": "paste-webhook-secret-here"},
    )
    assert resp.status_code == 200
    received = await update_queue.get()
    assert received["update_type"] == "message_created"


async def test_webhook_missing_secret_returns_401(client):
    resp = await client.post("/max/webhook", json={"x": 1})
    assert resp.status_code == 401


async def test_webhook_bad_secret_returns_401(client):
    resp = await client.post(
        "/max/webhook",
        json={"x": 1},
        headers={"X-Max-Bot-Api-Secret": "wrong"},
    )
    assert resp.status_code == 401
