#  quart-events

quart_events.EventBroker loads a blueprint into Quart which allows clients to subscribe to events via a WebSockets. The app can then generate events that can be sent to all subscribed clients in real-time.

Please see [test/app.py](https://github.com/smithk86/quart-events/blob/main/test/testapp/) for an example app. This app is used when running testing via py.test but can also be run standalone.

## Change Log

### [0.4.0] - 2021-11-08

- add type hints and type validation with mypy
- requires asyncio-multisubscriber-queue 0.3.0
- pytest plugin to facilitate capturing events while other tests are running; plugin name is *quart_events_catcher*
- added optional callbacks
- websocket auth improvements
    - token is now seemlessly managed using the user's session data
    - token has an expiration; user is disconnected from the socket upon expiration
    - a callback is available to further validate user using other criteria (like Flask-Login)
