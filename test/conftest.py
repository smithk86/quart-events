from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from quart_events.pytest_plugin import EventsCatcher

from testapp import create_app


if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest
    from quart.typing import Quart, TestClientProtocol
    from typing import AsyncGenerator, Generator


# override the default event_loop fixture
@pytest.fixture(scope='session')
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def app() -> AsyncGenerator:
    app_ = create_app()
    await app_.startup()
    yield app_
    await app_.shutdown()


@pytest.fixture(scope='session')
def app_test_client(app: Quart) -> TestClientProtocol:
    return app.test_client()


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def event_catcher_with_namespace(app_test_client: TestClientProtocol, request: SubRequest):
    """ catch events as they happen in the background """
    _catcher = EventsCatcher(
        app_test_client=app_test_client,
        blueprint_path='/events',
        namespace='ns1'
    )

    def teardown():
        _catcher._stop.set()
    request.addfinalizer(teardown)

    async with _catcher:
        yield _catcher
