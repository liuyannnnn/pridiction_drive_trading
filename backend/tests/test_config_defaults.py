from app.config import Settings


def test_default_postgres_user_is_postgres() -> None:
    settings = Settings()
    assert settings.postgres_user == "postgres"
