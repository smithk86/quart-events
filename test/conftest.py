# add the project directory to the pythonpath
import path_patch

# add plugin
pytest_plugins = ['quart_events.pytest_plugin']

import asyncio

import pytest
from quart_events.pytest_plugin import EventsCatcher

from testapp import create_app


# override the default event_loop fixture
@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def app():
    app_ = create_app()
    await app_.startup()
    yield app_
    await app_.shutdown()


@pytest.fixture(scope='session')
def app_test_client(app):
    return app.test_client()


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def token(app_test_client):
    r = await app_test_client.get('/events/auth')
    data = await r.get_json()
    return data.get('token')


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def token(app_test_client):
    r = await app_test_client.get('/events/auth')
    data = await r.get_json()
    return data.get('token')


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def event_catcher_with_namespace(app):
    """ catch events as they happen in the background """
    async with EventsCatcher(
        app,
        blueprint_path='/events',
        namespace='ns1'
    ) as _catcher:
        yield _catcher
