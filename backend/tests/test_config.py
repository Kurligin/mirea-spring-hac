from app.core.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@h/db")
    monkeypatch.setenv("JWT_SECRET", "test-secret-32-bytes-minimum-please")
    monkeypatch.setenv("MAX_BOT_TOKEN", "max-token-123")
    monkeypatch.setenv("QR_SERVER_SECRET", "qr-secret-32-bytes-minimum-please")
    monkeypatch.setenv("WEBHOOK_SECRET", "wh-secret")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://x:y@h/db"
    assert settings.jwt_secret == "test-secret-32-bytes-minimum-please"
    assert settings.environment == "development"
