"""Authenticated language preference persistence and user isolation."""

import pytest
from httpx import AsyncClient

from app.models.enums import Role
from tests._auth_helpers import make_user_headers


@pytest.mark.asyncio
async def test_chinese_language_preference_persists_for_the_current_user(async_client: AsyncClient):
    """Chinese is selectable, survives a fresh read, and remains scoped to its user."""
    user, headers = await make_user_headers(role=Role.USER)

    definitions = await async_client.get("/api/v1/settings/definitions", headers=headers)
    assert definitions.status_code == 200
    language = next(
        definition
        for definition in definitions.json()["definitions"]
        if definition["key"] == "localization.language"
    )
    options = {option["value"]: option["label_key"] for option in language["options"]}
    assert options["zh"] == "settings.language_zh"
    assert "en" in options

    saved = await async_client.put(
        "/api/v1/settings/user",
        headers=headers,
        json={"key": "localization.language", "value": "zh"},
    )
    assert saved.status_code == 200

    effective = await async_client.get("/api/v1/settings/effective", headers=headers)
    assert effective.status_code == 200
    assert effective.json()["settings"]["localization.language"] == "zh"
    assert effective.json()["sources"]["localization.language"] == "user"

    _, other_headers = await make_user_headers(role=Role.USER, tenant_id=user.tenant_id)
    other_effective = await async_client.get("/api/v1/settings/effective", headers=other_headers)
    assert other_effective.status_code == 200
    assert other_effective.json()["settings"]["localization.language"] == "en"
    assert other_effective.json()["sources"]["localization.language"] == "default"

    restored = await async_client.put(
        "/api/v1/settings/user",
        headers=headers,
        json={"key": "localization.language", "value": "en"},
    )
    assert restored.status_code == 200
    restored_effective = await async_client.get("/api/v1/settings/effective", headers=headers)
    assert restored_effective.status_code == 200
    assert restored_effective.json()["settings"]["localization.language"] == "en"
    assert restored_effective.json()["sources"]["localization.language"] == "user"
