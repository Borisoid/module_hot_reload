from setuptools import setup
from pathlib import Path


README = Path("README.md").read_text()

setup(
    name='module_hot_reload',
    packages=['module_hot_reload'],
    version='0.0.7',
    license='MIT',
    description='Package for reloading other packages and modules while Python is running',
    long_description=README,
    long_description_content_type='text/markdown',
    author='borisoid',
    url='https://github.com/Borisoid/module_hot_reload',
    keywords=[
        'module', 'hot', 'reload', 'runtime', 'watch'
    ],
    install_requires=[
        'watchdog==2.1.3',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
    ],
)
