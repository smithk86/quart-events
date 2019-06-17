import aiohttp
import pytest


def pytest_addoption(parser):
    parser.addoption('--endpoint', default='http://localhost:5000')


@pytest.fixture(name='endpoint')
@pytest.mark.asyncio
async def _endpoint(request):
    endpoint = request.config.getoption('endpoint')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint) as r:
                return endpoint
    except aiohttp.ClientConnectorError:
        raise Exception('plase run app.py before testing')


@pytest.yield_fixture
@pytest.mark.asyncio
async def session(request, event_loop):
    s = aiohttp.ClientSession(loop=event_loop, raise_for_status=True)
    yield s
    await s.close()


@pytest.fixture
@pytest.mark.asyncio
async def token(endpoint, session):
    async with session.get(f'{endpoint}/events/auth') as r:
        data = await r.json()
        return data.get('token')
