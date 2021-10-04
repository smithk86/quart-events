from __future__ import annotations

import asyncio
import collections.abc
import json
from contextlib import asynccontextmanager

import pytest
from asyncio_multisubscriber_queue import MultisubscriberQueue
from asyncio_service import AsyncioService, asyncio_service
from quart import Quart
from typing import Dict, Union


from async_timeout import timeout as Timeout


def pytest_addoption(parser):
    _group = parser.getgroup('pytest_quart_events')
    _group.addoption(
        '--quart-events-path',
        default='/events',
        help='url path for quart-events blueprint'
    )
    _group.addoption(
        '--quart-events-namespace',
        default=None,
        help='optional namespace for quart-events'
    )


@pytest.fixture(scope='session')
def quart_events_options(request):
    """ config options for the quart-events pytest plugin """
    _config = request.config
    return {
        'blueprint_path': _config.getoption('quart_events_path'),
        'namespace': _config.getoption('quart_events_namespace')
    }


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def quart_events_catcher(app: Quart, quart_events_options: Dict):
    """ catch events from quart-events as they are generated in the background """
    async with EventsCatcher(
        app,
        blueprint_path=quart_events_options['blueprint_path'],
        namespace=quart_events_options['namespace']
    ) as _catcher:
        yield _catcher


class EventsCatcher(MultisubscriberQueue, AsyncioService):
    def __init__(
        self,
        app: Quart,
        blueprint_path: Union[str, None],
        namespace: Union[str, None] = None
    ):
        MultisubscriberQueue.__init__(self)
        AsyncioService.__init__(self)
        self.app = app
        self.blueprint_path = blueprint_path
        self.namespace = namespace

    async def run(self):
        _client = self.app.test_client()
        r = await _client.get(f'{self.blueprint_path}/auth')
        data = await r.get_json()
        token = data.get('token')
        url = f'{self.blueprint_path}/ws'

        if self.namespace:
            url = f'{url}/{self.namespace}'

        async with _client.websocket(url) as ws:
            await ws.send(token)
            while self.running:
                try:
                    with Timeout(1):
                        data = await ws.receive()
                except asyncio.TimeoutError:
                    data = None
                if data:
                    await self.put(json.loads(data))

    def events(self, expected, timeout=5):
        return CaughtEvents(
            catcher=self,
            expected=expected,
            timeout=timeout
        )


class CaughtEvents(AsyncioService):
    def __init__(
        self,
        catcher: EventsCatcher,
        expected,
        timeout=5
    ):
        super().__init__()
        self.catcher = catcher
        self.expected = expected
        self.timeout = timeout
        self._events = list()

    def __repr__(self) -> str:
        return f'{type(self).__name__} object events={self.event_names()}'

    def __len__(self):
        return len(self._events)

    def __iter__(self):
        yield from iter(self._events)

    async def run(self):
        self._events = list()
        async with Timeout(self.timeout):
            async for _event in self.catcher.subscribe():
                self._events.append(_event)
                if len(self._events) >= self.expected:
                    return

    def event_names(self):
        return [event.get('event') for event in self._events]

    def assert_events(self, event_list):
        assert event_list == self.event_names()
