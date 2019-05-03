import aiohttp
import pytest

from quart_events import EventBroker


def pytest_addoption(parser):
    parser.addoption('--endpoint', default='http://localhost:5000')


@pytest.fixture
def endpoint(request):
    return request.config.getoption('endpoint')


@pytest.fixture
@pytest.mark.asyncio
async def session(request, event_loop):
    s = aiohttp.ClientSession(loop=event_loop, raise_for_status=True)

    def fin():
        async def afin():
            await s.close()
        event_loop.run_until_complete(afin())
    request.addfinalizer(fin)
    return s


@pytest.fixture
async def event_broker(request, event_loop):
    return EventBroker()
