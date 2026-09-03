import pytest

from app.services.access_denylist import deny_access_jti, is_access_jti_denied


@pytest.mark.asyncio
async def test_denylist_blocks_jti(fake_redis):
    jti = "0195a000-0000-7000-8000-000000000001"
    assert await is_access_jti_denied(jti) is False
    await deny_access_jti(jti, ttl=60)
    assert await is_access_jti_denied(jti) is True


@pytest.mark.asyncio
async def test_denylist_empty_jti_is_not_denied(fake_redis):
    assert await is_access_jti_denied("") is False
