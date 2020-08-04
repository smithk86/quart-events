import sys


__version__ = '0.3.3'
__MIN_PYTHON__ = (3, 7)


if sys.version_info < __MIN_PYTHON__:
    sys.exit('python {}.{} or later is required'.format(*__MIN_PYTHON__))


from .broker import EventBroker
from .errors import EventBrokerError, EventBrokerAuthError
