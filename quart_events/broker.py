import asyncio
import json

from asyncio_multisubscriber_queue import MultisubscriberQueue
from async_timeout import timeout
from quart import Blueprint, make_response, jsonify, websocket
from quart.json import JSONEncoder


class EventBroker(MultisubscriberQueue):
    def __init__(self, app, url_prefix='/events', keepalive=30, loop=None, encoding='utf-8'):
        """
        The constructor for EventBroker class

        Parameters:
            app (quart.Quart): Quart app
            url_prefix (str): prefix for the blueprint
            keepalive (int): how often to sent a "keepalive" event when no new
                events are being generated
            loop (asyncio.AbstractEventLoop): explicitly define an event loop
            encoding (str): character encoding to use

        """
        self.keepalive = keepalive
        self.encoding = encoding
        self.index = 0
        super(EventBroker, self).__init__(loop=loop)

        if app:
            self.init_app(app, url_prefix)

    def init_app(self, app, url_prefix):
        """
        Register the blueprint with the application

        """
        app.extensions['events'] = self
        app.register_blueprint(self.create_blueprint(), url_prefix=url_prefix)
        return self

    def create_blueprint(self):
        """
        Generate the blueprint

        Returns:
            quart.Blueprint

        """
        blueprint = Blueprint('events', __name__)
        @blueprint.route('/sse')
        async def server_sent_events():
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
        async def ws():
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
        async for val in super(EventBroker, self).subscribe():
            try:
                async with timeout(self.keepalive):
                    yield val
            except asyncio.TimeoutError:
                yield {'event': 'keepalive'}

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
