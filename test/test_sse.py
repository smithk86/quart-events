from asyncio import sleep

import pytest
import aiohttp


@pytest.mark.asyncio
async def test_message(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/send/event0')
        await session.get(f'{endpoint}/send/event1')
        await session.get(f'{endpoint}/send/event2')

    # subscribe to events
    task = event_loop.create_task(send())

    data = ''
    async with session.get(f'{endpoint}/events/sse', headers={'Content-Type': 'text/event-stream'}) as r:
        for _ in range(6):
            s = await r.content.read(12)
            data += s.decode('utf-8')
    events = data.split('\n\n')

    # assert event values
    assert 'data: event0' in events[0]
    assert 'data: event1' in events[1]
    assert 'data: event2' in events[2]

    # wait for send() to end
    await task

@pytest.mark.asyncio
async def test_message_events(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/generate')

    # subscribe to events
    task = event_loop.create_task(send())

    data = ''
    async with session.get(f'{endpoint}/events/sse', headers={'Content-Type': 'text/event-stream'}) as r:
        for _ in range(4):
            s = await r.content.read(66)
            data += s.decode('utf-8')
    events = data.split('\n\n')

    # assert event values
    assert "event: test0\ndata: 1c1c5907-d262-468c-9eca-34092fd87b06" in events[0]
    assert "event: test1\ndata: 8e7e1f98-9df1-42cf-8896-aeba658053d3" in events[1]
    assert "event: test2\ndata: 30db7186-e66a-43eb-a32a-d0311ca8d153" in events[2]
    assert "event: test3\ndata: 6ca404d0-7416-4409-aa2a-c9120360c04f" in events[3]

    # wait for send()
    await task


@pytest.mark.asyncio
async def test_keepalive(session, endpoint, event_loop):
    data = ''
    async with session.get(f'{endpoint}/events/sse', headers={'Content-Type': 'text/event-stream'}) as r:
        for _ in range(4):
            s = await r.content.read(20)
            data += s.decode('utf-8')
    events = data.split('\n\n')

    # assert event values
    for i in range(4):
        assert "event: keepalive" in events[i]
