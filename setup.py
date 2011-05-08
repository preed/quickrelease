
import os
from setuptools import setup

setup(
    name = "quickrelease",
    version = "0.10.0pre",
    author = "J. Paul Reed",
    author_email = "jpreed@gmail.com",
    description = ("A lightweight release harness[0] that aims to provide a "
                   "framework and supporting infrastructure to help define a "
                   "process."),
    license = "MIT",
    keywords = "build release automation framework",
    url = "https://github.com/preed/quickrelease",
    packages=['quickrelease',],

    long_description=open(os.path.join(os.path.dirname(__file__),
     'README')).read()

    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Utilities",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License"
        "Programming Language :: Python :: 2",
    ],
)
