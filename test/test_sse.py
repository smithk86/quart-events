from asyncio import sleep

import pytest
import aiohttp


@pytest.mark.asyncio
async def test_message(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/send/event0')
        await sleep(.25)
        await session.get(f'{endpoint}/send/event1')
        await sleep(.25)
        await session.get(f'{endpoint}/send/event2')

    # subscribe to events
    tasks = list()
    tasks.append(event_loop.create_task(send()))

    events = list()
    async with session.get(f'{endpoint}/events/sse', headers={'Content-Type': 'text/event-stream'}) as r:
        for _ in range(6):
            s = await r.content.read(12)
            events.append(s.decode('utf-8'))
    return events

    # assert event values
    assert 'data: event0' in events[0]
    assert 'data: event1' in events[2]
    assert 'data: event2' in events[4]

    # wait for send() to end
    await asyncio.wait(tasks)


@pytest.mark.asyncio
async def test_message_events(session, endpoint, event_loop):
    async def send():
        await sleep(.25)
        await session.get(f'{endpoint}/generate')

    # subscribe to events
    tasks = list()
    tasks.append(event_loop.create_task(send()))

    events = list()
    async with session.get(f'{endpoint}/events/sse', headers={'Content-Type': 'text/event-stream'}) as r:
        for _ in range(4):
            s = await r.content.read(66)
            events.append(s.decode('utf-8'))
    return events

    # assert event values
    assert events[0] == "data: 1c1c5907-d262-468c-9eca-34092fd87b06\nevent: test0\nid: 1\n\n"
    assert events[1] == "data: 8e7e1f98-9df1-42cf-8896-aeba658053d3\nevent: test1\nid: 2\n\n"
    assert events[2] == "data: 30db7186-e66a-43eb-a32a-d0311ca8d153\nevent: test2\nid: 3\n\n"
    assert events[3] == "data: 6ca404d0-7416-4409-aa2a-c9120360c04f\nevent: test3\nid: 4\n\n"

    # wait for send() to end
    await asyncio.wait(tasks)
