# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import os
from setuptools import setup

from quickrelease.console_driver import QUICK_RELEASE_VERSION

setup(
    name = "quickrelease",

    version = QUICK_RELEASE_VERSION,

    author = "J. Paul Reed",
    author_email = "jpreed@gmail.com",
    description = ("A lightweight release harness that aims to provide a "
                   "framework and supporting infrastructure to help define a "
                   "process."),
    license = "MIT",
    keywords = "build release automation framework",
    url = "https://github.com/preed/quickrelease",

    packages = ['quickrelease',
                'quickrelease.steps',
                'quickrelease.processes',
               ],

    long_description=open(os.path.join(os.path.dirname(__file__),
     'README')).read(),

    entry_points = {
        'console_scripts': [
            'quickrelease = quickrelease.console_driver:main',
        ],
    },

    #package_data = {
    #   # Include the examples
    #   '': ['examples/*.py', 'examples/*.cfg'],
    #},

    classifiers = [
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License"
        "Programming Language :: Python :: 2",
    ],
)
