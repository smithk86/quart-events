#!/usr/bin/env python

import os.path
from uuid import uuid4

from quart import Quart, current_app, render_template, websocket
from quart_events import EventBroker


dir_ = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Quart(__name__, template_folder=dir_)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SECRET_KEY'] = b'00000000000000000000000000000000'

    @app.before_serving
    def register_extensions():
        # provide a very low keepalive interval to make testing faster
        events = EventBroker(app, keepalive=1)

        @events.on_auth
        def _on_auth():
            # print('init')
            pass

        @events.on_verify
        def _on_verify():
            # print('verify')
            pass

        @events.on_send
        def _on_send(data):
            # print(f'send: {data}')
            pass

    @app.route('/')
    async def index():
        return await render_template('index.html')

    @app.route('/send/<msg>')
    async def message(msg):
        await current_app.events.put(event='message', data=msg)
        return 'OK'

    @app.route('/uuid')
    async def uuid():
        await current_app.events.put(event='uuid', data=str(uuid4()))
        return 'OK'

    @app.route('/generate')
    async def generate():
        await current_app.events.put(
            data='1c1c5907-d262-468c-9eca-34092fd87b06',
            event='ns0:test0'
        )
        await current_app.events.put(
            data='8e7e1f98-9df1-42cf-8896-aeba658053d3',
            event='ns0:test1'
        )
        await current_app.events.put(
            data='30db7186-e66a-43eb-a32a-d0311ca8d153',
            event='ns1:test2'
        )
        await current_app.events.put(
            data='6ca404d0-7416-4409-aa2a-c9120360c04f',
            event='ns1:test3'
        )
        return 'OK'

    return app
