from setuptools import setup
from re import search

with open('osu/__init__.py', 'r') as f:
    version = search(r"__version__ = '(.*)'", f.read()).group(1)

try:
    _ = version
except NameError:
    raise ValueError('Could not find version')

setup(
    name='osu',
    description='Python bindings for osu! api',
    author='Hazel Rella',
    author_email='hazelrella11@gmail.com',
    version='0.0.1',
    packages=['osu'],
    install_requires=[
        'aiohttp==3.4.1'
    ]
)
