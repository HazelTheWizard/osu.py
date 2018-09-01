from setuptools import setup

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
