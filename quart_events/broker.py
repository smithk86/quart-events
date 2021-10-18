from __future__ import annotations

import asyncio
import logging
import functools
import json
from copy import copy
from datetime import datetime
from typing import AsyncGenerator, Union
from uuid import UUID, uuid4

from asyncio_multisubscriber_queue import MultisubscriberQueue
from async_timeout import timeout
from quart import Blueprint, make_response, jsonify, Quart, request, Response, session, websocket
from werkzeug.datastructures import Headers

from .errors import EventBrokerError, EventBrokerAuthError


logger = logging.getLogger(__name__)


class EventBroker(MultisubscriberQueue):
    def __init__(
        self,
        app: Quart,
        url_prefix: str = '/events',
        keepalive: int = 30,
        auth: bool = True,
        encoding: str = 'utf-8'
    ):
        """
        The constructor for EventBroker class

        Parameters:
            app (quart.Quart): Quart app
            url_prefix (str): prefix for the blueprint
            keepalive (int): how often to send a "keepalive" event when no new
                events are being generated
            auth (bool): enable/disable session validation
            encoding (str): character encoding to use

        """
        if auth is True and app.config.get('SECRET_KEY') is None:
            raise RuntimeError('session support is required for EventBroker authentication; please specify a SECRET_KEY')

        self.keepalive = keepalive
        self.encoding = encoding
        self._auth_enabled = auth
        self._auth_callbacks = list()
        self._verify_callbacks = list()
        self._send_callbacks = list()
        self._tokens = list()
        super().__init__()

        if app:
            self.init_app(app, url_prefix)

    def init_app(self, app: Quart, url_prefix: str) -> Quart:
        """
        Register the blueprint with the application

        """
        app.events = self
        app.register_blueprint(self.create_blueprint(), url_prefix=url_prefix)
        return self

    def on_auth(self, callable_: Callable):
        self._auth_callbacks.append(callable_)

    def on_verify(self, callable_: Callable):
        self._verify_callbacks.append(callable_)

    def on_send(self, callable_: Callable):
        self._send_callbacks.append(callable_)

    @staticmethod
    async def _execute_callbacks(callbacks: List[Callable], *args):
        for _callable in callbacks:
            if asyncio.iscoroutinefunction(_callable):
                await _callable(*args)
            else:
                _callable(*args)

    async def auth(self) -> None:
        if self._auth_enabled is False:
            return
        elif 'quart_events' not in session:
            raise EventBrokerError('session support is required for authentication')

        try:
            await self._execute_callbacks(self._auth_callbacks)
            _token = uuid4()
            session['quart_events']['date'] = datetime.now()
            session['quart_events']['token'] = _token
            self._tokens.append(_token)
        except Exception as e:
            session['quart_events']['token'] = None
            raise

    async def verify(self) -> None:
        if self._auth_enabled is False:
            return

        _is_authorized = False
        try:
            _token = session['quart_events'].pop('token')
            if _token in self._tokens:
                self._tokens.remove(_token)
                _is_authorized = True
        except Exception:
            _is_authorized = False

        if _is_authorized is not True:
            raise EventBrokerAuthError('not authorized')

        await self._execute_callbacks(self._verify_callbacks)

    def create_blueprint(self) -> Blueprint:
        """
        Generate the blueprint

        Returns:
            quart.Blueprint

        """
        blueprint = Blueprint('events', __name__)

        @blueprint.route('/auth')
        async def auth() -> Response:
            try:
                # init session data
                if 'quart_events' not in session:
                    session['quart_events'] = dict()

                session['quart_events']['token'] = None

                await self.auth()
                return jsonify(authorized=isinstance(session['quart_events']['token'], UUID))
            except EventBrokerAuthError as e:
                r = jsonify(authorized=False, error=str(e))
                r.status_code = 401
                return r
            except Exception as e:
                logger.exception(e)
                r = jsonify(authorized=False, error='not authorized')
                r.status_code = 401
                return r

        @blueprint.websocket('/ws')
        @blueprint.websocket('/ws/<namespace>')
        async def ws(namespace: Union[str, None] = None) -> Response:
            if self._auth_enabled:
                try:
                    await self.verify()
                except EventBrokerAuthError as e:
                    await websocket.send_json({'event': 'error', 'message': str(e)})
                    return
                except Exception as e:
                    logger.warning(e)
                    await websocket.send_json({'event': 'error', 'message': 'not authorized'})
                    return

            # enter subscriber loop
            async for data in self.subscribe():
                try:
                    """
                        * if a namespace is given but the "event"
                        field is not, skip this event.
                        * if a namespace is given but does not match
                        the "event" field, skip this event.
                    """
                    if (
                        namespace and (
                            data.get('event') is None or
                            not data['event'].startswith(namespace)
                        )
                    ):
                        continue

                    await self._execute_callbacks(self._send_callbacks, data)

                    await websocket.send_json(data)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(e)
                    logger.warning('ending subscriber loop')
                    break

        return blueprint

    async def put(self, event=None, **data) -> None:
        """
        Put a new data on the event broker

        Parameters:
            event: name of the event [optional]
            data: event data keyword arguments

        """

        if event:
            _data = {'event': event}
        else:
            _data = {}
        _data.update(data)
        await super().put(_data)

    async def subscribe(self) -> AsyncGenerator:
        """
        Override subscribe() to add a timeout for the keepalive event

        """
        with self.queue_context() as q:
            while True:
                try:
                    async with timeout(self.keepalive):
                        val = await q.get()
                except asyncio.TimeoutError:
                    yield {'event': 'keepalive'}
                else:
                    if val is StopAsyncIteration:
                        break
                    else:
                        yield val
