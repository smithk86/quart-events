import asyncio
import json
from uuid import uuid4

import pytest
import quart
from async_timeout import timeout


@pytest.mark.asyncio
async def test_websocket(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(3) as _events:
        await app_test_client.get('/send/event0')
        await app_test_client.get('/send/event1')
        await app_test_client.get('/send/event2')

    assert len(_events) == 3
    for i, _event in enumerate(_events):
        assert _event.get('data') == f'event{i}'


@pytest.mark.asyncio
async def test_websocket_events(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(4) as _events:
        await app_test_client.get('/generate')

    _events.assert_events([
        'ns0:test0',
        'ns0:test1',
        'ns1:test2',
        'ns1:test3'
    ])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0]['data'] == '1c1c5907-d262-468c-9eca-34092fd87b06'
    assert _event_list[0]['event'] == 'ns0:test0'
    assert _event_list[1]['data'] == '8e7e1f98-9df1-42cf-8896-aeba658053d3'
    assert _event_list[1]['event'] == 'ns0:test1'
    assert _event_list[2]['data'] == '30db7186-e66a-43eb-a32a-d0311ca8d153'
    assert _event_list[2]['event'] == 'ns1:test2'
    assert _event_list[3]['data'] == '6ca404d0-7416-4409-aa2a-c9120360c04f'
    assert _event_list[3]['event'] == 'ns1:test3'


@pytest.mark.asyncio
async def test_keepalive(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(4) as _events:
        pass

    _events.assert_events([
        'keepalive',
        'keepalive',
        'keepalive',
        'keepalive'
    ])

    # assert event values
    for _event in _events:
        assert _event['event'] == 'keepalive'


@pytest.mark.asyncio
async def test_namespaced_events(app_test_client, event_catcher_with_namespace):
    async with event_catcher_with_namespace.events(2) as _events:
        await app_test_client.get('/generate')

    _events.assert_events([
        'ns1:test2',
        'ns1:test3'
    ])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0]['data'] == '30db7186-e66a-43eb-a32a-d0311ca8d153'
    assert _event_list[0]['event'] == 'ns1:test2'
    assert _event_list[1]['data'] == '6ca404d0-7416-4409-aa2a-c9120360c04f'
    assert _event_list[1]['event'] == 'ns1:test3'


@pytest.mark.asyncio
async def test_namespaced_events2(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(3, namespace='ns0') as _events:
        await app_test_client.get('/generate')

    _events.assert_events([
        'ns0:test0',
        'ns0:test1'
    ])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0]['data'] == '1c1c5907-d262-468c-9eca-34092fd87b06'
    assert _event_list[0]['event'] == 'ns0:test0'
    assert _event_list[1]['data'] == '8e7e1f98-9df1-42cf-8896-aeba658053d3'
    assert _event_list[1]['event'] == 'ns0:test1'
