#  quart-events

quart_events.EventBroker loads a blueprint into Quart which allows clients to subscribe to events via a WebSockets. The app can then generate events that can be sent to all subscribed clients in real-time.

Please see [test/app.py](https://github.com/smithk86/quart-events/blob/main/test/testapp/) for an example app. This app is used when running testing via py.test but can also be run standalone.
