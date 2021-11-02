import sys


__VERSION__ = '0.4.0-dev'
__DATE__ = '2021-10-02'
__MIN_PYTHON__ = (3, 8)


if sys.version_info < __MIN_PYTHON__:
    sys.exit('python {}.{} or later is required'.format(*__MIN_PYTHON__))


from .broker import EventBroker
from .errors import EventBrokerError, EventBrokerAuthError

