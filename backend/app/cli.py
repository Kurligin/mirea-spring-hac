import asyncio

import typer
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.admin_account import AdminAccount, AdminRole

cli = typer.Typer()


@cli.command("create-admin")
def create_admin(
    email: str,
    password: str,
    role: AdminRole = typer.Option(AdminRole.SUPER, help="Роль админа"),
    full_name: str = typer.Option("", help="ФИО"),
) -> None:
    """Создать админа в БД."""

    async def _create() -> None:
        async with AsyncSessionLocal() as session:
            existing = (
                await session.execute(select(AdminAccount).where(AdminAccount.email == email))
            ).scalar_one_or_none()
            if existing:
                typer.echo(f"Админ {email} уже существует", err=True)
                raise typer.Exit(1)
            admin = AdminAccount(
                email=email,
                password_hash=hash_password(password),
                role=role,
                full_name=full_name or None,
            )
            session.add(admin)
            await session.commit()
            typer.echo(f"Создан админ {email} ({role.value}) id={admin.id}")

    asyncio.run(_create())


@cli.command("set-webhook")
def set_webhook(
    url: str = typer.Option(
        "", help="URL вебхука; по умолчанию PUBLIC_BASE_URL + /max/webhook"
    ),
) -> None:
    """Зарегистрировать webhook бота в MAX (переключение с long-poll на webhook)."""

    async def _run() -> None:
        from app.core.config import get_settings
        from app.core.max_client import MaxClient

        settings = get_settings()
        hook_url = url or f"{settings.public_base_url.rstrip('/')}/max/webhook"
        if not hook_url.startswith("https://"):
            typer.echo(f"Webhook URL должен быть https:// — получено: {hook_url}", err=True)
            raise typer.Exit(1)
        client = MaxClient(token=settings.max_bot_token, base_url=settings.max_api_base_url)
        try:
            result = await client.set_webhook(url=hook_url, secret=settings.webhook_secret)
            typer.echo(f"Webhook зарегистрирован: {hook_url}\n{result}")
        finally:
            await client.close()

    asyncio.run(_run())


if __name__ == "__main__":
    cli()
