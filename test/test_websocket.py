import asyncio
import json
from uuid import uuid4

import pytest
import quart
from async_timeout import timeout


@pytest.mark.asyncio
async def test_bad_token(app_test_client):
    # test sending "123" as the token
    async with app_test_client.websocket('/events/ws') as ws:
        await ws.send('123')
        wsdata_raw = await ws.receive()
        wsdata = json.loads(wsdata_raw)
        assert wsdata.get('error') == 'token must be a uuid'
    # test using a randomly generated uuid
    async with app_test_client.websocket('/events/ws') as ws:
        await ws.send(str(uuid4()))
        wsdata_raw = await ws.receive()
        wsdata = json.loads(wsdata_raw)
        assert wsdata.get('error') == 'token does not exist'


@pytest.mark.asyncio
async def test_not_sending_token(app_test_client):
    async def send():
        await asyncio.sleep(.25)
        await app_test_client.get('/send/event0')
        await app_test_client.get('/send/event1')
        await app_test_client.get('/send/event2')

    loop = asyncio.get_running_loop()
    # subscribe to events
    task = loop.create_task(send())

    async with app_test_client.websocket('/events/ws') as ws:
        try:
            async with timeout(1) as this_timeout:
                await ws.receive()
        except asyncio.TimeoutError:
            pass
        assert this_timeout.expired is True


@pytest.mark.asyncio
async def test_token_receive_timeout(app_test_client):
    async with app_test_client.websocket('/events/ws') as ws:
        msg = await ws.receive()
        data = json.loads(msg)
        assert data.get('error') == 'no authentication token received'


@pytest.mark.asyncio
async def test_websocket(app_test_client, token):
    async def send():
        await asyncio.sleep(.25)
        await app_test_client.get('/send/event0')
        await app_test_client.get('/send/event1')
        await app_test_client.get('/send/event2')

    loop = asyncio.get_running_loop()
    # subscribe to events
    task = loop.create_task(send())

    async with app_test_client.websocket('/events/ws') as ws:
        await ws.send(token)
        for i in range(3):
            msg = await ws.receive()
            data = json.loads(msg)
            assert data.get('data') == f'event{i}'

    # wait for send() to end
    await task


@pytest.mark.asyncio
async def test_websocket_events(app_test_client, token):
    async def send():
        await asyncio.sleep(.25)
        await app_test_client.get('/generate')

    loop = asyncio.get_running_loop()
    # subscribe to events
    task = loop.create_task(send())

    events = list()
    async with app_test_client.websocket('/events/ws') as ws:
        await ws.send(token)
        for i in range(4):
            msg = await ws.receive()
            data = json.loads(msg)
            events.append(data)

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
async def test_keepalive(app_test_client, token):
    events = list()
    async with app_test_client.websocket('/events/ws') as ws:
        await ws.send(token)
        for i in range(4):
            msg = await ws.receive()
            data = json.loads(msg)
            events.append(data)

    # assert event values
    for i in range(4):
        assert events[0]['event'] == 'keepalive'
