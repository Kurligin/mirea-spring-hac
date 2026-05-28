from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request


def create_mock_max_app() -> FastAPI:
    """Минимальный FastAPI mock сервер MAX Bot API для тестов."""
    app = FastAPI()
    state: dict[str, Any] = {
        "sent_messages": [],
        "uploads": [],
        "actions": [],
        "answers": [],
        "subscriptions": [],
        "next_message_id": 1,
        "fail_next": None,
    }
    app.state.mock = state

    def _check_auth(authorization: str | None) -> None:
        if not authorization:
            raise HTTPException(401, "Missing Authorization")

    @app.get("/me")
    async def get_me(authorization: str | None = Header(None)):
        _check_auth(authorization)
        return {"user_id": 100500, "username": "test_bot", "is_bot": True}

    @app.post("/messages")
    async def post_message(
        request: Request,
        user_id: int | None = Query(None),
        chat_id: int | None = Query(None),
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        if state["fail_next"] is not None:
            code = state["fail_next"]
            state["fail_next"] = None
            raise HTTPException(code, f"forced failure {code}")
        body = await request.json()
        msg = {
            "user_id": user_id,
            "chat_id": chat_id,
            "body": body,
            "message_id": state["next_message_id"],
        }
        state["next_message_id"] += 1
        state["sent_messages"].append(msg)
        return {"message": msg}

    @app.post("/answers")
    async def post_answer(
        request: Request,
        callback_id: str = Query(...),
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        body = await request.json()
        state["answers"].append({"callback_id": callback_id, "body": body})
        return {"success": True}

    @app.post("/uploads")
    async def post_upload(
        request: Request,
        type: str = Query(...),
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        data = await request.body()
        token = f"tok-{len(state['uploads'])}"
        state["uploads"].append({"type": type, "size": len(data), "token": token})
        return {"url": f"https://mock-max.local/upload/{token}", "token": token}

    @app.post("/chats/{chat_id}/actions")
    async def post_action(
        chat_id: int,
        request: Request,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        body = await request.json()
        state["actions"].append({"chat_id": chat_id, "action": body})
        return {"success": True}

    @app.get("/updates")
    async def get_updates(
        limit: int = Query(10),
        timeout: int = Query(30),
        types: str | None = Query(None),
        marker: int | None = Query(None),
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        pending = state.get("pending_updates", [])
        state["pending_updates"] = []
        return {"updates": pending, "marker": 42 if pending else None}

    @app.post("/subscriptions")
    async def post_subscription(
        request: Request,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        body = await request.json()
        state["subscriptions"].append(body)
        return {"success": True}

    return app
