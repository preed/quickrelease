
from quickrelease.process import Process
from quickrelease.steps.FirefoxSampleSteps import *

class FirefoxGetSource(Process):
    steps = [ FirefoxDownloadSource,
              FirefoxExtractSource,
            ]

    def __init__(self, *args, **kwargs):
        Process.__init__(self, *args, **kwargs)

class FirefoxBuild(Process):
    steps = [ FirefoxConfigureBuild,
              FirefoxDoBuild,
            ]

    def __init__(self, *args, **kwargs):
        Process.__init__(self, *args, **kwargs)
