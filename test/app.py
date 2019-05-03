#!/usr/bin/env python

import asyncio
import logging
from uuid import uuid4

from quart import Quart, abort, current_app, render_template
from quart_events import EventBroker


logging.basicConfig(level=logging.DEBUG)

app = Quart(
    'example',
    template_folder=''
)
EventBroker(app)


@app.route('/')
async def index():
    return await render_template('app.html')


@app.route('/send/<msg>')
async def message(msg):
    broker = current_app.extensions['events']
    await broker.put(data=msg)
    return 'OK'


@app.route('/uuid')
async def uuid():
    broker = current_app.extensions['events']
    await broker.put(event='uuid', data=str(uuid4()))
    return 'OK'


@app.route('/generate')
async def generate():
    broker = current_app.extensions['events']
    await broker.put(
        data='1c1c5907-d262-468c-9eca-34092fd87b06',
        event='test0'
    )
    await broker.put(
        data='8e7e1f98-9df1-42cf-8896-aeba658053d3',
        event='test1'
    )
    await broker.put(
        data='30db7186-e66a-43eb-a32a-d0311ca8d153',
        event='test2'
    )
    await broker.put(
        data='6ca404d0-7416-4409-aa2a-c9120360c04f',
        event='test3'
    )
    return 'OK'
