from __future__ import annotations

import asyncio
import collections.abc
import json
import logging
import warnings
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, InitVar
from datetime import datetime

import pytest
import pytest_asyncio

from asyncio_multisubscriber_queue import MultisubscriberQueue
from typing import Dict, TYPE_CHECKING


if TYPE_CHECKING:
    from _pytest.fixtures import SubRequest
    from quart.typing import TestClientProtocol
    from typing import Any, AsyncGenerator, Iterator, List, Optional


logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addini("quart_events_path", "url path for quart-events blueprint")
    parser.addini("quart_events_namespace", "optional namespace for quart-events")


def ignore_cancelled_error(func):
    """
    Decorator for functions that can be cancelled
    without requiring any cleanup
    """

    async def wrapper(*args, **kwargs):
        try:
            await func(*args, **kwargs)
        except asyncio.CancelledError:
            pass

    return wrapper


@pytest_asyncio.fixture(scope="session")
async def quart_events_catcher(
    app_test_client: TestClientProtocol, request: SubRequest
):
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
        blueprint_path=_getini("quart_events_path", default="/events"),
        namespace=_getini("quart_events_namespace", default=None),
    )

    async with _catcher:
        yield _catcher


@dataclass(frozen=True)
class Event:
    name: str = field(init=False)
    payload: InitVar[str]
    date: datetime = field(init=False)
    data: Dict = field(init=False)
    seconds_since_last: float = field(init=False)
    last: Event = field(repr=False)

    def __post_init__(self, payload: str):
        object.__setattr__(self, "date", datetime.utcnow())

        try:
            object.__setattr__(self, "data", json.loads(payload))
        except Exception as e:
            logger.error(f"could not decode json for event payload: {payload}")
            raise e

        object.__setattr__(self, "name", self._name())
        object.__setattr__(self, "seconds_since_last", self._seconds_since_last())

    def _name(self) -> Optional[str]:
        if isinstance(self.data, Dict) and "event" in self.data:
            return self.data.pop("event")
        else:
            logger.debug(f'event data does not contain an "event" key: {self.data}')
            return None

    def _seconds_since_last(self) -> float:
        if self.last:
            return self.seconds_since(self.last)
        else:
            return 0.0

    def seconds_since(self, event: Event) -> float:
        assert self is not event
        return (self.date - event.date).total_seconds()

    def get(self, key, default=None) -> Any:
        return self.data.get(key, default)


class EventsCatcher(MultisubscriberQueue):
    def __init__(
        self,
        app_test_client: TestClientProtocol,
        blueprint_path: Optional[str],
        namespace: Optional[str] = None,
    ):
        super().__init__()
        self.app_test_client = app_test_client
        self.blueprint_path = blueprint_path
        self.namespace = namespace
        self._task: Optional[asyncio.Task] = None
        self._ready: asyncio.Event = asyncio.Event()

    async def __aenter__(self):
        self._task = asyncio.create_task(self.run())
        return self

    async def __aexit__(self, *args, **kwargs):
        self._task.cancel()
        await self._task

    def __del__(self):
        if self._task and not self._task.done():
            warnings.warn(f"task for {type(self).__name__} is still running")

    @ignore_cancelled_error
    async def run(self):
        _auth_url = f"{self.blueprint_path}/auth"
        logger.debug(f"authorizing events session via {_auth_url}")
        r = await self.app_test_client.get(_auth_url)

        if r.status_code != 200:
            _payload = await r.get_data()
            logger.error(f"auth request failed [path={_auth_url}]")
            logger.error(f"auth request payload: {_payload}")
            raise RuntimeError("auth request payload")

        data = await r.get_json()
        assert data["authorized"] is True

        url = f"{self.blueprint_path}/ws"
        if self.namespace:
            url = f"{url}/{self.namespace}"

        logger.debug(f"subscribing to events via {self.blueprint_path}/auth")
        _last: Optional[Event] = None
        async with self.app_test_client.websocket(url) as ws:
            _event = await ws.receive()
            _event = json.loads(_event)
            assert _event.get("event") == "_open"

            self._ready.set()

            while True:
                _data = await ws.receive()
                _event = Event(_data, _last)
                if _event.name == "_token_expire":
                    break
                else:
                    await self.put(_event)
                    _last = _event

    def events(self, expected, timeout=5, namespace=None):
        return CaughtEvents(
            catcher=self, expected=expected, timeout=timeout, namespace=namespace
        )


class CaughtEvents:
    def __init__(
        self,
        catcher: EventsCatcher,
        expected: int,
        namespace: Optional[str] = None,
        timeout: int = 5,
    ):
        self.catcher = catcher
        self.expected = expected
        self.namespace = namespace
        self._timout = timeout
        self._task: Optional[asyncio.Task] = None
        self._events: List[Event] = list()

    def __repr__(self) -> str:
        return f"{type(self).__name__} object events={self.event_names()}"

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator:
        yield from iter(self._events)

    async def __aenter__(self):
        await asyncio.wait_for(self.catcher._ready.wait(), timeout=5)
        self._task = asyncio.create_task(self.run())
        return self

    async def __aexit__(self, *args, **kwargs):
        try:
            await asyncio.wait_for(self._task, self._timout)
        except asyncio.TimeoutError:
            pass
        await self._task

    def __del__(self):
        if self._task and not self._task.done():
            warnings.warn(f"task for {type(self).__name__} is still running")

    @ignore_cancelled_error
    async def run(self):
        self._events = list()
        async for _event in self.catcher.subscribe():
            if _event.get("event") == "_open" or (
                self.namespace
                and (
                    _event.name is None
                    or _event.name == "_open"
                    or not _event.name.startswith(self.namespace)
                )
            ):
                continue
            self._events.append(_event)
            if len(self._events) >= self.expected:
                break

    def event_names(self) -> List[str]:
        return [event.name for event in self._events if isinstance(event.name, str)]

    def assert_events(self, event_list: List[str]) -> None:
        assert event_list == self.event_names()
