import asyncio
import json

from asyncio_multisubscriber_queue import MultisubscriberQueue
from quart import Blueprint, make_response, jsonify, websocket
from quart.json import JSONEncoder


class EventBroker(MultisubscriberQueue):
    def __init__(self, app, url_prefix='/events', keepalive=30, keepalive_value={'event': 'keepalive'}, loop=None, encoding='utf-8'):
        self.keepalive = keepalive
        self.keepalive_value = keepalive_value
        self.encoding = encoding
        self.index = 0
        super(EventBroker, self).__init__(maxsize=0, loop=loop)

        if app:
            self.init_app(app, url_prefix)

    def init_app(self, app, url_prefix):
        if 'events' not in app.extensions:
            app.extensions['events'] = self
        app.register_blueprint(self.create_blueprint(), url_prefix=url_prefix)
        return self

    def create_blueprint(self):
        blueprint = Blueprint('events', __name__)

        @blueprint.route('/sse')
        async def server_sent_events():
            response = await make_response(
                self.subscribe_sse(),
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
            async for data in self.subscribe_websocket():
                try:
                    await websocket.send(data)
                except asyncio.CancelledError:
                    break

        return blueprint

    async def put(self, event=None, data=None):
        self.index += 1
        _data = {
            'id': self.index
        }
        if event:
            _data['event'] = event
        if data:
            _data['data'] = data
        await super(EventBroker, self).put(_data)

    async def subscribe_sse(self):
        async for data in self.subscribe(timeout=self.keepalive, timeout_value=self.keepalive_value):
            msglist = [f'{k}: {v}' for k, v in data.items()]
            msg = '\n'.join(msglist) + '\n\n'
            yield bytes(msg, encoding=self.encoding)

    async def subscribe_websocket(self):
        async for data in self.subscribe(timeout=self.keepalive, timeout_value=self.keepalive_value):
            yield json.dumps(data, cls=JSONEncoder)
