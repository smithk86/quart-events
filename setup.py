#!/usr/bin/env python

import os.path

from setuptools import setup  # type: ignore


dir_ = os.path.abspath(os.path.dirname(__file__))

# get the version to include in setup()
with open(f'{dir_}/quart_events/__init__.py') as fh:
    for line in fh:
        if '__VERSION__' in line:
            exec(line)
# get long description from README.md
with open(f'{dir_}/README.md') as fh:
    long_description = fh.read()


setup(
    name='quart-events',
    version=__VERSION__,  # type: ignore
    license='MIT',
    author='Kyle Smith',
    author_email='smithk86@gmail.com',
    url='https://github.com/smithk86/quart-events',
    description='quart extension to facilitate event message brokering',
    long_description=long_description,
    long_description_content_type='text/markdown',
    package_data={'quart_events': ['py.typed']},
    packages=['quart_events'],
    entry_points={'pytest11': ['quart_events = quart_events.pytest_plugin']},
    install_requires=[
        'asyncio-multisubscriber-queue',
        'quart'
    ],
    setup_requires=[
        'pytest-runner'
    ],
    tests_require=[
        'mypy',
        'pytest',
        'pytest-asyncio',
        'pytest-mypy'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
