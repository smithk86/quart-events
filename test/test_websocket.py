import json
from asyncio import sleep

import pytest
import aiohttp


@pytest.mark.asyncio
async def test_websocket(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/send/event0')
        await session.get(f'{endpoint}/send/event1')
        await session.get(f'{endpoint}/send/event2')

    # subscribe to events
    task = event_loop.create_task(send())

    async with session.ws_connect(f'{endpoint}/events/ws') as ws:
        for i in range(3):
            msg = await ws.__anext__()
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                assert data.get('data') == f'event{i}'
            else:
                raise Exception()

    # wait for send() to end
    await task


@pytest.mark.asyncio
async def test_websocket_events(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/generate')

    # subscribe to events
    task = event_loop.create_task(send())

    events = list()
    async with session.ws_connect(f'{endpoint}/events/ws') as ws:
        for i in range(4):
            msg = await ws.__anext__()
            if msg.type == aiohttp.WSMsgType.TEXT:
                e = json.loads(msg.data)
                events.append(e)
            else:
                raise Exception()

    # assert event values
    assert events[0]['data'] == '1c1c5907-d262-468c-9eca-34092fd87b06'
    assert events[0]['event'] == 'test0'
    assert events[1]['data'] == '8e7e1f98-9df1-42cf-8896-aeba658053d3'
    assert events[1]['event'] == 'test1'
    assert events[2]['data'] == '30db7186-e66a-43eb-a32a-d0311ca8d153'
    assert events[2]['event'] == 'test2'
    assert events[3]['data'] == '6ca404d0-7416-4409-aa2a-c9120360c04f'
    assert events[3]['event'] == 'test3'

    # wait for send() to end
    await task


@pytest.mark.asyncio
async def test_keepalive(session, endpoint, event_loop):
    events = list()
    async with session.ws_connect(f'{endpoint}/events/ws') as ws:
        for i in range(4):
            msg = await ws.__anext__()
            if msg.type == aiohttp.WSMsgType.TEXT:
                e = json.loads(msg.data)
                events.append(e)
            else:
                raise Exception()

    # assert event values
    for i in range(4):
        assert events[0]['event'] == 'keepalive'
