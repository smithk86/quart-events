class EventBrokerError(Exception):
    pass


class EventBrokerAuthError(Exception):
    def __init__(self, message, token):
        self.token = token
        super().__init__(message)
