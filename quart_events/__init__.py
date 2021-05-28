import sys


__VERSION__ = '0.3.4-dev'
__DATE__ = '2021-05-28'
__MIN_PYTHON__ = (3, 7)


if sys.version_info < __MIN_PYTHON__:
    sys.exit('python {}.{} or later is required'.format(*__MIN_PYTHON__))


from .broker import EventBroker
from .errors import EventBrokerError, EventBrokerAuthError
