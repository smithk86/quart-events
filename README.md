#  quart-events

quart_events.EventBroker loads a blueprint into Quart which allows clients to subscribe to events via WebSockets or SSE (ServerSentEvent). The app can then generate server-side events and send them to all subscribed clients in real-time.

Please see [test/app.py](https://github.com/smithk86/quart-events/blob/master/test/app.py) for an example app.