from distutils.core import setup


setup(
    name = 'module_hot_reload',
    packages = ['module_hot_reload'],
    version = '0.0.1',
    license = 'MIT',
    description = 'Module for reloading other .py files and modules while Python is running',
    author = 'borisoid',
    url = 'https://github.com/Borisoid/module_hot_reload',
    keywords = ['reload', 'runtime', 'watch'],
    install_requires = [
        'watchdog==2.1.3',
    ],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
    ],
)
