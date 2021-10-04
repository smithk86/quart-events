#!/usr/bin/env python

import os.path
from uuid import uuid4

from quart import Quart, current_app, render_template
from quart_events import EventBroker


dir_ = os.path.dirname(os.path.abspath(__file__))


def create_app():
    app = Quart(__name__, template_folder=dir_)
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    @app.before_serving
    def register_extensions():
        # provide a very low keepalive interval to make testing faster
        EventBroker(app, keepalive=1)

    @app.route('/')
    async def index():
        return await render_template('index.html')

    @app.route('/send/<msg>')
    async def message(msg):
        events = current_app.extensions['events']
        await events.put(event='message', data=msg)
        return 'OK'

    @app.route('/uuid')
    async def uuid():
        events = current_app.extensions['events']
        await events.put(event='uuid', data=str(uuid4()))
        return 'OK'

    @app.route('/generate')
    async def generate():
        events = current_app.extensions['events']
        await events.put(
            data='1c1c5907-d262-468c-9eca-34092fd87b06',
            event='ns0:test0'
        )
        await events.put(
            data='8e7e1f98-9df1-42cf-8896-aeba658053d3',
            event='ns0:test1'
        )
        await events.put(
            data='30db7186-e66a-43eb-a32a-d0311ca8d153',
            event='ns1:test2'
        )
        await events.put(
            data='6ca404d0-7416-4409-aa2a-c9120360c04f',
            event='ns1:test3'
        )
        return 'OK'

    return app
