from __future__ import annotations

import asyncio
import collections.abc
import json
from contextlib import asynccontextmanager

import pytest
from asyncio_multisubscriber_queue import MultisubscriberQueue
from asyncio_service import AsyncioService, asyncio_service

from async_timeout import timeout as Timeout


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def event_catcher(app):
    """ catch events as they happen in the background """
    async with EventCatcher(app, url_prefix='/') as _catcher:
        yield _catcher


class EventCatcher(MultisubscriberQueue, AsyncioService):
    def __init__(
        self,
        app: Quart,
        url_prefix=''
    ):
        MultisubscriberQueue.__init__(self)
        AsyncioService.__init__(self)
        self.app = app
        self.url_prefix = url_prefix

    async def run(self):
        _client = self.app.test_client()
        r = await _client.get(f'{self.url_prefix}/events/auth')
        data = await r.get_json()
        token = data.get('token')
        url = f'{self.url_prefix}/events/ws'
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

    def events(self, expected, timeout=5, namespace=None):
        return CaughtEvents(self, expected, timeout=timeout, namespace=namespace)


class CaughtEvents(AsyncioService):
    def __init__(self, catcher: EventCatcher, expected, timeout=5, namespace=None):
        super().__init__()
        self.catcher = catcher
        self.expected = expected
        self.timeout = timeout
        self.namespace = namespace
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
