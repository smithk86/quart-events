class EventBrokerError(Exception):
    pass


class EventBrokerAuthError(Exception):
    def __init__(self, message, token):
        self.token = token
        super(EventBrokerAuthError, self).__init__(message)
