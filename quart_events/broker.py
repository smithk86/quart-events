from __future__ import annotations

import asyncio
import logging
import functools
import json
from copy import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from asyncio_multisubscriber_queue import MultisubscriberQueue
from quart import (
    Blueprint, make_response, jsonify,
    Quart, request, Response, session, websocket
)
from werkzeug.datastructures import Headers

from .errors import EventBrokerError, EventBrokerAuthError


logger = logging.getLogger(__name__)


KeepAlive = object()


@dataclass
class Token:
    value: UUID
    date: datetime

    def __str__(self):
        return str(self.value)

    @staticmethod
    def new():
        return Token(
            value=uuid4(),
            date=datetime.utcnow()
        )


class NullToken(Token):
    def __init__(self):
        super().__init__(value=None, date=None)

    def __bool__(self) -> bool:
        return False


class EventBroker(MultisubscriberQueue):
    def __init__(
        self,
        app: Quart,
        url_prefix: str = '/events',
        keepalive: int = 30,
        auth: bool = True,
        token_expire_seconds: int = 3600,
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
        self._auth_enabled: bool = auth
        self._token_expire_seconds = token_expire_seconds
        self._auth_callbacks: List[Callable] = list()
        self._verify_callbacks: List[Callable] = list()
        self._send_callbacks: List[Callable] = list()
        self._tokens: Dict[str, Token] = dict()
        super().__init__()

        if app:
            self.init_app(app, url_prefix)

    def init_app(self, app: Quart, url_prefix: str) -> None:
        """
        Register the blueprint with the application

        """
        app.extensions['events'] = self
        app.register_blueprint(self.create_blueprint(), url_prefix=url_prefix)

    def auth(self, callable_: Callable) -> None:
        self._auth_callbacks.append(callable_)

    def verify(self, callable_: Callable) -> None:
        self._verify_callbacks.append(callable_)

    def send(self, callable_: Callable) -> None:
        self._send_callbacks.append(callable_)

    @staticmethod
    async def _execute_callbacks(callbacks: List[Callable], *args) -> None:
        for _callable in callbacks:
            if asyncio.iscoroutinefunction(_callable):
                await _callable(*args)
            else:
                _callable(*args)

    def _get_token_from_session(self) -> Token:
        _token = session.get('quart_events_token')
        if _token:
            return Token(
                value=_token['value'],
                date=_token['date']
            )
        else:
            return NullToken()

    def _token_is_expired(self, token: Token) -> bool:
        if type(token) is NullToken:
            return True

        _expire_time = datetime.utcnow() - timedelta(seconds=self._token_expire_seconds)
        return token.date < _expire_time

    def clear_expired_tokens(self):
        for _key in list(self._tokens.keys()):
            if self._token_is_expired(self._tokens[_key]):
                del self._tokens[_key]

    async def authorize_websocket(self):
        # gc expired tokens
        self.clear_expired_tokens()

        try:
            await self._execute_callbacks(self._auth_callbacks)

            _token = self._get_token_from_session()
            if (
                _token is type(NullToken) or
                self._token_is_expired(_token)
            ):
                _token = Token.new()
                session['quart_events_token'] = asdict(_token)
                self._tokens[str(_token.value)] = _token
        except Exception as e:
            if 'quart_events_token' in session:
                del session['quart_events_token']
            raise

    def verify_auth_token(self) -> Token:
        _token = self._get_token_from_session()
        if self._token_is_expired(_token):
            raise EventBrokerAuthError('token is expired')
        return _token

    async def verify_auth(self) -> Token:
        # verify a token exists in the user's session
        _token = self.verify_auth_token()

        # executes any additional verification callbacks
        await self._execute_callbacks(self._verify_callbacks)

        return _token

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
                if self._auth_enabled:
                    await self.authorize_websocket()
                return jsonify(authorized=True)
            except EventBrokerAuthError as e:
                r = jsonify(authorized=False, error=str(e))
                r.status_code = 401
                return r
            except Exception as e:
                logger.exception(e)
                r = jsonify(authorized=False, error='an unknown error occurred')
                r.status_code = 400
                return r

        @blueprint.websocket('/ws')
        @blueprint.websocket('/ws/<namespace>')
        async def ws(namespace: Optional[str] = None) -> Response:
            if self._auth_enabled:
                try:
                    _token = await self.verify_auth()
                except EventBrokerAuthError as e:
                    await websocket.send_json({'event': 'error', 'message': str(e)})
                    return jsonify(error=str(e))
                except Exception as e:
                    await websocket.send_json({'event': 'error', 'message': 'not authorized'})
                    return jsonify(error='not authorized')

            # initial message
            await websocket.send_json({'event': '_open'})

            # enter subscriber loop
            async for data in self.subscribe():
                try:
                    """
                        KeepAlive:
                            * dummy event send at a regular interval to keep the socket from closing
                        Namespace:
                            * if a namespace is given but the "event" field is not, skip this event.
                            * if a namespace is given but does not match the "event" field, skip this event.
                    """
                    if self._token_is_expired(_token):
                        await websocket.send_json({'event': '_token_expire', 'message': 'token is expired'})
                        break
                    elif data is KeepAlive:
                        await websocket.send_json({'event': '_keepalive'})
                    elif (
                        namespace and (
                            data.get('event') is None or
                            not data['event'].startswith(namespace)
                        )
                    ):
                        continue
                    else:
                        await self._execute_callbacks(self._send_callbacks, data)
                        await websocket.send_json(data)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(e)
                    logger.warning('ending subscriber loop')
                    break
            else:
                # final message
                await websocket.send_json({'event': '_close'})

            return jsonify(message='socket has ended')

        return blueprint

    async def put(self, **data: Any) -> None:  # type: ignore
        """
        Put a new data on the event broker

        """
        if 'event' not in data:
            data['event'] = None

        await super().put(data)

    async def subscribe(self) -> AsyncGenerator:
        """
        Override subscribe() to add a timeout for the keepalive event

        """
        with self.queue() as q:
            while True:
                try:
                    _value = await asyncio.wait_for(q.get(), self.keepalive)
                except asyncio.TimeoutError:
                    yield KeepAlive
                else:
                    if _value is StopAsyncIteration:
                        break
                    else:
                        yield _value
