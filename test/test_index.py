import pytest


@pytest.mark.asyncio
async def test_index(session, endpoint):
    async with session.get(endpoint) as r:
        assert r.status == 200
        assert '<title>quart-sse example app</title>' in await r.text()
