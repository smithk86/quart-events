from __future__ import annotations

import asyncio
import collections.abc
import json
import logging
from contextlib import asynccontextmanager

import pytest

from _pytest.fixtures import SubRequest
from asyncio_multisubscriber_queue import MultisubscriberQueue
from asyncio_service import AsyncioService
from typing import Any, AsyncGenerator, Iterator, List, Optional, TYPE_CHECKING


if TYPE_CHECKING:
    from quart.typing import TestClientProtocol


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addini('quart_events_path', 'url path for quart-events blueprint')
    parser.addini('quart_events_namespace', 'optional namespace for quart-events')


@pytest.fixture(scope='session')
@pytest.mark.asyncio
async def quart_events_catcher(app_test_client: TestClientProtocol, request: SubRequest):
    def _getini(name, default=None):
        """
            getini returns an empty string instead of None;
            this helper fixes that
        """
        _val = request.config.getini(name)
        return _val if len(_val) > 0 else default

    """ catch events from quart-events as they are generated in the background """
    _catcher = EventsCatcher(
        app_test_client=app_test_client,
        blueprint_path=_getini('quart_events_path', default='/events'),
        namespace=_getini('quart_events_namespace', default=None)
    )

    def teardown():
        _catcher.stop()
    request.addfinalizer(teardown)

    async with _catcher:
        yield _catcher


class EventsCatcher(MultisubscriberQueue, AsyncioService):
    def __init__(
        self,
        app_test_client: TestClientProtocol,
        blueprint_path: Optional[str],
        namespace: Optional[str] = None
    ):
        MultisubscriberQueue.__init__(self)
        AsyncioService.__init__(self)
        self.app_test_client = app_test_client
        self.blueprint_path = blueprint_path
        self.namespace = namespace
        self._ws_ready: asyncio.Event = asyncio.Event()

        @self.after
        async def _teardown(**kwargs):
            await self.close()

    async def ready(self) -> None:
        await self._ws_ready.wait()

    async def run(self):
        r = await self.app_test_client.get(f'{self.blueprint_path}/auth')

        if r.status_code != 200:
            _payload = await r.get_data()
            raise RuntimeError(f'auth request failed; payload: {_payload}')

        data = await r.get_json()
        assert data['authorized'] is True

        url = f'{self.blueprint_path}/ws'
        if self.namespace:
            url = f'{url}/{self.namespace}'

        async with self.app_test_client.websocket(url) as ws:
            _event = await ws.receive()
            _event = json.loads(_event)
            assert _event.get('event') == '_open'

            self._ws_ready.set()

            while True:
                _event = await ws.receive()
                _event = json.loads(_event)
                if _event.get('event') == '_token_expire':
                    break
                else:
                    await self.put(_event)

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
        namespace: Optional[str] = None
    ):
        super().__init__(join_timeout=timeout)
        self.catcher = catcher
        self.expected = expected
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
        async for _event in self.catcher.subscribe():
            if (
                _event.get('event') == '_open' or
                (
                    self.namespace and (
                        _event.get('event') is None or
                        _event.get('event') == '_open' or
                        not _event['event'].startswith(self.namespace)
                    )
                )
            ):
                continue
            self._events.append(_event)
            if len(self._events) >= self.expected:
                break

    def event_names(self) -> List[str]:
        return [event.get('event') for event in self._events]

    def assert_events(self, event_list: List[str]) -> None:
        assert event_list == self.event_names()
