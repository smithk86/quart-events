#!/usr/bin/env python

from setuptools import setup

setup(
    name='quart-events',
    version='0.1.0',
    license='MIT',
    author='Kyle Smith',
    author_email='smithk86@gmail.com',
    description='quart plugin to facilitate event messages',
    packages=['quart_events'],
    install_requires=[
        'asyncio-multisubscriber-queue',
        'quart'
    ],
    setup_requires=[
        'pytest-runner'
    ],
    tests_require=[
        'pytest',
        'pytest-asyncio',
        'aiohttp'
    ],
    classifiers=[
        'Framework :: Quart',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
