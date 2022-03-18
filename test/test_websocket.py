import asyncio
import json
from datetime import datetime
from typing import Dict
from uuid import uuid4

import pytest
import quart

from quart_events.pytest_plugin import Event


@pytest.mark.asyncio
async def test_auth_callbacks(app):
    assert app.events_callback_data["auth"] is False
    assert app.events_callback_data["verify"] is False
    assert app.events_callback_data["send"] is False


@pytest.mark.asyncio
async def test_websocket(app, app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(3) as _events:
        await app_test_client.get("/send/event0")
        await app_test_client.get("/send/event1")
        await app_test_client.get("/send/event2")

    assert len(_events) == 3
    for i, _event in enumerate(_events):
        assert isinstance(_event.name, str)
        assert isinstance(_event.date, datetime)
        assert isinstance(_event.data, Dict)
        assert isinstance(_event.seconds_since_last, float)
        if i > 0:
            assert isinstance(_event.last, Event)
            assert _event.seconds_since_last > 0

        assert _event.get("data") == f"event{i}"

    assert app.events_callback_data["auth"] is True
    assert app.events_callback_data["verify"] is True
    assert app.events_callback_data["send"] is True


@pytest.mark.asyncio
async def test_websocket_events(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(4) as _events:
        await app_test_client.get("/generate")

    _events.assert_events(["ns0:test0", "ns0:test1", "ns1:test2", "ns1:test3"])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0].get("data") == "1c1c5907-d262-468c-9eca-34092fd87b06"
    assert _event_list[0].name == "ns0:test0"
    assert _event_list[1].get("data") == "8e7e1f98-9df1-42cf-8896-aeba658053d3"
    assert _event_list[1].name == "ns0:test1"
    assert _event_list[2].get("data") == "30db7186-e66a-43eb-a32a-d0311ca8d153"
    assert _event_list[2].name == "ns1:test2"
    assert _event_list[3].get("data") == "6ca404d0-7416-4409-aa2a-c9120360c04f"
    assert _event_list[3].name == "ns1:test3"


@pytest.mark.asyncio
async def test_keepalive(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(1) as _events:
        pass

    _events.assert_events(["_keepalive"])

    # assert event values
    for _event in _events:
        assert _event.name == "_keepalive"
        break


@pytest.mark.asyncio
async def test_namespaced_events(app_test_client, event_catcher_with_namespace):
    async with event_catcher_with_namespace.events(2) as _events:
        await app_test_client.get("/generate")

    _events.assert_events(["ns1:test2", "ns1:test3"])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0].get("data") == "30db7186-e66a-43eb-a32a-d0311ca8d153"
    assert _event_list[0].name == "ns1:test2"
    assert _event_list[1].get("data") == "6ca404d0-7416-4409-aa2a-c9120360c04f"
    assert _event_list[1].name == "ns1:test3"


@pytest.mark.asyncio
async def test_namespaced_events2(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(2, namespace="ns0") as _events:
        await app_test_client.get("/generate")

    _events.assert_events(["ns0:test0", "ns0:test1"])

    # assert event values
    _event_list = list(_events)
    assert _event_list[0].get("data") == "1c1c5907-d262-468c-9eca-34092fd87b06"
    assert _event_list[0].name == "ns0:test0"
    assert _event_list[1].get("data") == "8e7e1f98-9df1-42cf-8896-aeba658053d3"
    assert _event_list[1].name == "ns0:test1"


@pytest.mark.asyncio
async def test_plugin_timeout(app_test_client, quart_events_catcher):
    async with quart_events_catcher.events(5, namespace="ns0", timeout=1) as _events:
        await app_test_client.get("/generate")
