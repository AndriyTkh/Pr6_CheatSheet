"""§15 app skeleton + §11 secret discipline.

`/health` is liveness only — it must answer without a database, because the
thing you ask when the DB is down is exactly whether the app is up. The
readiness probe (`/health/ready`) is where dependencies get touched, and it is
covered by the DB-backed suite, not here.

The rest of this file is the §11 half of the task: no secret has a value in
the code, and nothing that reports config ever prints one.
"""

import httpx

from app.core.config import Settings, settings
from app.main import app

# Every field whose value is a credential. Adding a provider means adding its
# field here — an unlisted secret is a secret nothing checks.
SECRET_FIELDS = (
    "openrouter_api_key",
    "youcontrol_api_key",
    "r2_access_key_id",
    "r2_secret_access_key",
)


async def test_health_is_200_without_touching_the_database():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_every_secret_field_is_declared_and_defaults_empty():
    # Read the *class* defaults, not the live instance: `settings` may legitimately
    # be populated from the environment on a developer machine.
    fields = Settings.model_fields

    for name in SECRET_FIELDS:
        assert name in fields, f"{name} is no longer a setting — update SECRET_FIELDS"
        assert fields[name].default == "", f"{name} has a value baked into the code"


def test_no_field_named_like_a_secret_escapes_the_list():
    """A new `*_api_key`/`*_secret*`/`*_token` field must be checked, not just added."""
    suspicious = {
        name
        for name in Settings.model_fields
        if any(mark in name for mark in ("api_key", "secret", "token", "password"))
    }
    assert suspicious <= set(SECRET_FIELDS), (
        f"unchecked credential field(s): {sorted(suspicious - set(SECRET_FIELDS))}"
    )


def test_masked_reports_presence_never_values():
    configured = Settings(
        openrouter_api_key="sk-or-REAL",
        youcontrol_api_key="yc-REAL",
        r2_bucket_name="bucket",
        r2_access_key_id="AK-REAL",
        r2_secret_access_key="SK-REAL",
        database_url="postgresql+asyncpg://user:PGPASS@db.example/cheatsheet",
    )
    printed = repr(configured.masked())

    for leaked in ("sk-or-REAL", "yc-REAL", "AK-REAL", "SK-REAL", "PGPASS"):
        assert leaked not in printed
    # Presence still has to be reported — masking that told you nothing would
    # make the readiness probe useless.
    assert configured.masked()["openrouter_configured"] is True
    assert configured.masked()["youcontrol_configured"] is True


def test_health_ready_payload_carries_only_masked_config():
    """The readiness route serves `masked()` — assert that's the whole contract."""
    assert set(settings.masked()) == {
        "environment",
        "database",
        "openrouter_configured",
        "youcontrol_configured",
        "r2_configured",
    }
