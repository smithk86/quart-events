from __future__ import annotations

import asyncio
import collections.abc
import json
from contextlib import asynccontextmanager

import pytest
from asyncio_multisubscriber_queue import MultisubscriberQueue
from asyncio_service import AsyncioService, asyncio_service
from quart import Quart
from typing import Any, List, Union


from async_timeout import timeout as Timeout


def pytest_addoption(parser):
    parser.addini('quart_events_path', 'url path for quart-events blueprint')
    parser.addini('quart_events_namespace', 'optional namespace for quart-events')


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def quart_events_catcher(app: Quart, request: pytest.SubRequest):
    def _getini(name, default=None):
        """
            getini returns an empty string instead of None;
            this helper fixes that
        """
        _val = request.config.getini(name)
        return _val if len(_val) > 0 else default

    """ catch events from quart-events as they are generated in the background """
    async with EventsCatcher(
        app,
        blueprint_path=_getini('quart_events_path', default='/events'),
        namespace=_getini('quart_events_namespace', default=None)
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
        assert r.status_code == 200
        data = await r.get_json()
        assert data['authorized'] is True

        url = f'{self.blueprint_path}/ws'
        if self.namespace:
            url = f'{url}/{self.namespace}'

        async with _client.websocket(url) as ws:
            while self.running:
                try:
                    async with Timeout(1):
                        data = await ws.receive()
                except asyncio.TimeoutError:
                    data = None
                if data:
                    await self.put(json.loads(data))

    def events(self, expected, timeout=5, namespace=None):
        return CaughtEvents(
            catcher=self,
            expected=expected,
            timeout=timeout,
            namespace=namespace
        )


class CaughtEvents(AsyncioService):
    def __init__(
        self,
        catcher: EventsCatcher,
        expected: int,
        timeout: int = 5,
        namespace: Union[str, None] = None
    ):
        super().__init__()
        self.catcher = catcher
        self.expected = expected
        self.timeout = timeout
        self.namespace = namespace
        self._events: List[Any] = list()

    def __repr__(self) -> str:
        return f'{type(self).__name__} object events={self.event_names()}'

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator:
        yield from iter(self._events)

    async def run(self):
        self._events = list()
        async with Timeout(self.timeout):
            async for _event in self.catcher.subscribe():
                if (
                    self.namespace and (
                        _event.get('event') is None or
                        not _event['event'].startswith(self.namespace)
                    )
                ):
                    continue
                self._events.append(_event)
                if len(self._events) >= self.expected:
                    return

    def event_names(self) -> List[str]:
        return [event.get('event') for event in self._events]

    def assert_events(self, event_list: List[str]) -> None:
        assert event_list == self.event_names()
