import asyncio
import logging
import functools
import json
from collections import namedtuple
from copy import copy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from asyncio_multisubscriber_queue import MultisubscriberQueue
from async_timeout import timeout
from quart import Blueprint, make_response, jsonify, request, websocket
from quart.json import JSONEncoder

from .errors import EventBrokerError, EventBrokerAuthError


logger = logging.getLogger(__name__)
Session = namedtuple('Session', ['token', 'remote_addr', 'user_agent', 'created'])


class EventBroker(MultisubscriberQueue):
    def __init__(self, app, url_prefix='/events', keepalive=30, auth=True, encoding='utf-8'):
        """
        The constructor for EventBroker class

        Parameters:
            app (quart.Quart): Quart app
            url_prefix (str): prefix for the blueprint
            keepalive (int): how often to send a "keepalive" event when no new
                events are being generated
            auth (bool): enable/disable token validation
            toke
            encoding (str): character encoding to use

        """
        self.keepalive = keepalive
        self.auth = auth
        self.encoding = encoding
        self.authorized_sessions = dict()
        super().__init__()

        if app:
            self.init_app(app, url_prefix)

    def init_app(self, app, url_prefix):
        """
        Register the blueprint with the application

        """
        app.extensions['events'] = self
        app.register_blueprint(self.create_blueprint(), url_prefix=url_prefix)
        return self

    def token_generate(self, remote_addr):
        if self.auth is False:
            raise EventBrokerError('token validation is disabled')

        token = uuid4()
        token_str = str(token)
        self.authorized_sessions[token_str] = Session(
            token=token,
            remote_addr=remote_addr,
            user_agent=request.headers.get('User-Agent'),
            created=datetime.now()
        )
        return token

    def token_verify(self, token, remote_addr):
        if self.auth is not True:
            return

        if token is None:
            raise EventBrokerAuthError('no token was provided', None)
        elif type(token) is not UUID:
            raise EventBrokerAuthError('token must be a uuid', None)

        token_str = str(token)
        session = self.authorized_sessions.get(token_str)
        if session is None:
            raise EventBrokerAuthError('token does not exist', token_str)
        elif remote_addr != session.remote_addr:
            logger.error(f"token address mismatch: {remote_addr} != {session.remote_addr}")
            raise EventBrokerAuthError('token could not be validated', token_str)

    def create_blueprint(self):
        """
        Generate the blueprint

        Returns:
            quart.Blueprint

        """
        blueprint = Blueprint('events', __name__)

        @blueprint.route('/sessions')
        async def sessions():
            session_list = list()
            queue_info_list = list()
            for s in self.authorized_sessions.values():
                session_list.append(s._asdict())
            for i, q in enumerate(self.subscribers):
                queue_info_list.append({
                    'index': i,
                    'size': q.qsize()
                })
            return jsonify(
                subscriber_count=len(self.subscribers),
                subscribers=queue_info_list,
                sessions=session_list
            )

        @blueprint.route('/auth')
        async def auth():
            def _get_token_by_remote_addr(addr):
                for token, data in self.authorized_sessions.items():
                    if data.remote_addr == addr:
                        return token
                return None

            try:
                remote_addr = EventBroker.remote_addr(request.headers)
                token = _get_token_by_remote_addr(remote_addr)
                if token is None:
                    token = self.token_generate(remote_addr)

                token_str = str(token)
                created = self.authorized_sessions[token_str].created
                return jsonify(token=token, created=created)
            except Exception as e:
                r = jsonify(token=None, created=None, error=str(e))
                r.status_code = 400
                return r

        @blueprint.websocket('/ws')
        async def ws():
            if self.auth:
                remote_addr = EventBroker.remote_addr(websocket.headers)

                # receive token from client
                try:
                    async with timeout(5):
                        token = await websocket.receive()
                except asyncio.TimeoutError:
                    token = None

                # if toekn is null, return an error
                if token is None:
                    await websocket.send(json.dumps({'error': 'no authentication token received'}))
                    return

                # convert the token to a UUID and verify
                try:
                    token = UUID(token)
                except Exception:
                    await websocket.send(json.dumps({'error': 'token must be a uuid', 'token': token}))
                    return

                try:
                    self.token_verify(token, remote_addr)
                except EventBrokerAuthError as e:
                    logger.exception(e)
                    await websocket.send(json.dumps({'error': str(e), 'token': e.token}))
                    return

            # enter subscriber loop
            async for val in self.subscribe():
                try:
                    json_str = json.dumps(val, cls=JSONEncoder)
                    await websocket.send(json_str)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(e)
                    logger.warning('ending subscriber loop')
                    break

        return blueprint

    async def put(self, **data):
        """
        Put a new data on the event broker

        Parameters:
            data: event data keyword arguments

        """
        await super().put(data)

    async def subscribe(self):
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

    @staticmethod
    def remote_addr(headers):
        if 'X-Forwarded-For' in headers:
            remote_addr = headers['X-Forwarded-For']
        else:
            remote_addr = headers.get('Remote-Addr')
        logger.debug(f'remote address is {remote_addr}')
        return remote_addr
