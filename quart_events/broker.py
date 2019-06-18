import asyncio
import logging
import functools
import json
from copy import copy
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from asyncio_multisubscriber_queue import MultisubscriberQueue
from async_timeout import timeout
from quart import Blueprint, make_response, jsonify, request, websocket
from quart.json import JSONEncoder

from .errors import EventBrokerError, EventBrokerAuthError


logger = logging.getLogger(__name__)


class EventBroker(MultisubscriberQueue):
    def __init__(self, app, url_prefix='/events', keepalive=30, token_validation=False, encoding='utf-8'):
        """
        The constructor for EventBroker class

        Parameters:
            app (quart.Quart): Quart app
            url_prefix (str): prefix for the blueprint
            keepalive (int): how often to sent a "keepalive" event when no new
                events are being generated
            token_validation (bool): enable/disable token validation
            toke
            encoding (str): character encoding to use

        """
        self.keepalive = keepalive
        self.token_validation = token_validation
        self.encoding = encoding
        self.index = 0
        self.authorized_sessions = dict()
        super(EventBroker, self).__init__()

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
        token = uuid4()
        session = {
            'token': token,
            'remote_addr': remote_addr,
            'user_agent': request.headers.get('User-Agent'),
            'created': datetime.now()
        }
        token_str = str(token)
        self.authorized_sessions[token_str] = session
        return token

    def token_verify(self, token, remote_addr):
        if self.token_validation is not True:
            return

        if type(token) is not UUID:
            raise EventBrokerAuthError('no token was provided', None)

        token_str = str(token)
        session = self.authorized_sessions.get(token_str)
        if session is None:
            raise EventBrokerAuthError('token does not exist', token_str)
        elif remote_addr != session.get('remote_addr'):
            logger.error(f"token address mismatch: {remote_addr} != {session.get('remote_addr')}")
            raise EventBrokerAuthError('token could not be validated', token_str)

    def create_blueprint(self):
        """
        Generate the blueprint

        Returns:
            quart.Blueprint

        """
        blueprint = Blueprint('events', __name__)

        @blueprint.route('/auth')
        async def auth():
            def _get_token_by_remote_addr(addr):
                for token, data in self.authorized_sessions.items():
                    if data['remote_addr'] == addr:
                        return token
                return None

            remote_addr = EventBroker.remote_addr(request.headers)
            token = _get_token_by_remote_addr(remote_addr)
            if token is None:
                token = self.token_generate(remote_addr)

            token_str = str(token)
            created = self.authorized_sessions[token_str].get('created')
            return jsonify(token=token, created=created)

        @blueprint.route('/sse')
        @blueprint.route('/sse/<uuid:token>')
        async def server_sent_events(token=None):
            remote_addr = EventBroker.remote_addr(request.headers)
            try:
                self.token_verify(token, remote_addr)
            except EventBrokerAuthError as e:
                r = jsonify(error=str(e), token=e.token)
                r.status_code = 400
                return r

            response = await make_response(
                self.sse_events(),
                {
                    'Content-Type': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Transfer-Encoding': 'chunked',
                }
            )
            response.timeout = None
            return response

        @blueprint.websocket('/ws')
        @blueprint.websocket('/ws/<uuid:token>')
        async def ws(token=None):
            remote_addr = EventBroker.remote_addr(websocket.headers)
            try:
                self.token_verify(token, remote_addr)
            except EventBrokerAuthError as e:
                await websocket.send(json.dumps({'error': str(e), 'token': e.token}))
                return

            async for event in self.websocket_events():
                try:
                    await websocket.send(event)
                except asyncio.CancelledError:
                    break

        return blueprint

    async def put(self, event=None, data=None):
        """
        Put a new event on the event broker

        Parameters:
            event (str): event name
            data: event data

        """
        self.index += 1
        _data = {
            'id': self.index
        }
        if event:
            _data['event'] = event
        if data:
            _data['data'] = data
        await super(EventBroker, self).put(_data)

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

    async def sse_events(self):
        """
        Format events as Server Sent Events

        """
        async for data in self.subscribe():
            msglist = [f'{k}: {v}' for k, v in data.items()]
            msg = '\n'.join(msglist) + '\n\n'
            yield bytes(msg, encoding=self.encoding)

    async def websocket_events(self):
        """
        Json-encode events for Websockets

        """
        async for data in self.subscribe():
            yield json.dumps(data, cls=JSONEncoder)

    @staticmethod
    def remote_addr(headers):
        if 'X-Forwarded-For' in headers:
            remote_addr = headers['X-Forwarded-For']
        else:
            remote_addr = headers.get('Remote-Addr')
        logger.debug(f'remote address is {remote_addr}')
        return remote_addr
