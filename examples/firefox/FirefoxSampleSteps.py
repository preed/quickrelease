
import os
import re
import time

from quickrelease.command import RunShellCommand
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.step import Step
from quickrelease.utils import GetBuildPlatform, GetSHA1FileHash

def PlatformCheck(conf):
   thisPlatform = GetBuildPlatform()
   supportedPlatforms = conf.Get('official_platforms', list)

   if thisPlatform not in supportedPlatforms:
       raise ReleaseFrameworkError("This example has only been tested on the "
        "following platforms: %s. Your platform: %s" % (', '.join(
        supportedPlatforms), thisPlatform))

def GetSourceDirRoot(conf):
    return os.path.join(conf.rootDir, conf.Get('source_root_dir'))

def VerifyFirefoxDownload(conf):
    sourceFile = os.path.basename(conf.Get('source_download_url'))
    sourceFileFullPath = os.path.join(conf.rootDir, sourceFile)

    if not os.path.isfile(sourceFileFullPath):
        raise ReleaseFrameworkError("Couldn't find downloaded firefox "
         "source code: %s" % (sourceFileFullPath))

    sourceSha1 = conf.Get('source_checksum')

    downloadSha1 = GetSHA1FileHash(sourceFileFullPath)

    if sourceSha1 != downloadSha1:
        raise ReleaseFrameworkError("Download doesn't match expected SHA1: "
         "expected: %s; download checksum: %s" % (sourceSha1, downloadSha1))


def VerifyFirefoxBuildConfigured(conf):
    autoconfTestFiles = conf.Get('autoconf_output_testfiles', list)
    sourceRoot = GetSourceDirRoot(conf)

    for f in autoconfTestFiles:
        testFile = os.path.join(sourceRoot, f)
        if not os.path.isfile(testFile):
            raise ReleaseFrameworkError("Autoconf test file not present: %s"                 % (testFile))

    confStatusFile = os.path.join(sourceRoot, conf.Get('autoconf_status_file'))

    lastLine = None
    confStatusFileHandle = open(confStatusFile, 'r')
    for l in confStatusFileHandle:
        lastLine = l
    confStatusFileHandle.close()

    if lastLine.strip() != 'exit 0':
        raise ReleaseFrameworkError("Last %s line didn't match successful "
         "exit: %s" % (confStatusFile, lastLine))

class FirefoxDownloadSource(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        PlatformCheck(self.config)

    def Execute(self):
        conf = self.config

        cmd = [ conf.GetConstant('WGET'),
                '--progress=dot',
                '--no-check-certificate',
                conf.Get('source_download_url') ]

        rv = RunShellCommand(command=cmd,
                             verbose=True)

    def Verify(self):
        VerifyFirefoxDownload(self.config)

class FirefoxExtractSource(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        conf = self.config
        PlatformCheck(conf)
        VerifyFirefoxDownload(conf)

    def Execute(self):
        conf = self.config

        sourceTarball = os.path.join(conf.rootDir,
         os.path.basename(conf.Get('source_download_url')))

        cmd = [ conf.GetConstant('TAR'),
                '-xvjf',
                sourceTarball ]

        rv = RunShellCommand(command=cmd,
                             workdir=conf.rootDir,
                             verbose=True)

    def Verify(self):
        conf = self.config

        firefoxTestFiles = conf.Get('source_test_files', list)
        sourceRoot = GetSourceDirRoot(conf)

        for f in firefoxTestFiles:
            testFile = os.path.join(sourceRoot, f)
            if not os.path.isfile(testFile):
                raise ReleaseFrameworkError("Missing Firefox source file: %s"
                 % (testFile))

class FirefoxConfigureBuild(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def _GetMozconfigFilename(self):
        conf = self.config
        return os.path.join(GetSourceDirRoot(conf), conf.Get('mozconfig_file'))

    def Preflight(self):
        PlatformCheck(self.config)
        mcFile = self._GetMozconfigFilename()

        if os.path.isfile(mcFile):
            raise ReleaseFrameworkError("Existing Mozconfig is in the way: %s" %
             mcFile)

    def Execute(self):
        conf = self.config

        mozConfigHandle = open(self._GetMozconfigFilename(), 'w')

        for line in re.split('\n+', self.config.Get('mozconfig_lines')):
            line.strip()
            print >> mozConfigHandle, line

        mozConfigHandle.close()

        #print "sleeping!"
        #time.sleep(11)
        RunShellCommand(command=['configure'],
                        workdir=GetSourceDirRoot(conf),
                        verbose=True )

    def Verify(self):
        VerifyFirefoxBuildConfigured(self.config)

class FirefoxDoBuild(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        conf = self.config
        PlatformCheck(conf)
        VerifyFirefoxBuildConfigured(conf)

    def Execute(self):
        conf = self.config

        rv = RunShellCommand(command=["make"],
                             workdir=GetSourceDirRoot(conf),
                             verbose=True,
                             timeout=7200,
                             logfile=os.path.join(conf.rootDir,
                              conf.Get('full_build_log')))

        print "\n\n***\nFull firefox build took %d seconds.\n***\n\n" % (
         rv.runningtime)

    def Verify(self):
        pass 

