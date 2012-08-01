
from quickrelease.process import Process
from quickrelease.steps.FirefoxSampleSteps import *

class FirefoxGetSource(Process):
    steps = [ FirefoxDownloadKeyAndSums,
              FirefoxDownloadSource,
              FirefoxExtractSource,
            ]

class FirefoxBuild(Process):
    steps = [ FirefoxConfigureBuild,
              FirefoxDoBuild,
              FirefoxDoInstallerBuild,
            ]

