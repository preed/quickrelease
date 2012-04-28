
import os
import re
import shutil
import sys
import tempfile

from quickrelease.command import RunShellCommand
from quickrelease.deliverable import FindDeliverables, GetDeliverable, GetAllDeliverables
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

def GetObjDir(conf):
    return os.path.join(GetSourceDirRoot(conf), conf.Get('objdir'))

def VerifyFirefoxDownload(conf):
    sourceFile = conf.Get('source_download_file')
    sourceFileFullPath = os.path.join(conf.rootDir, sourceFile)

    if not os.path.isfile(sourceFileFullPath):
        raise ValueError("Couldn't find downloaded firefox source code: %s" %
         (sourceFileFullPath))

    sha1SumsFile = os.path.basename(conf.Get('sha1_checksum_download_url'))

    sha1SumHandle = open(sha1SumsFile, 'r')

    sumFilePath = "./source/%s" % (sourceFile)
    sourceSha1 = None
    for line in sha1SumHandle.readlines():
        (sha1, filename) = line.split(None, 1)
        if filename.strip() == sumFilePath:
            sourceSha1 = sha1
            break

    sha1SumHandle.close()

    if sourceSha1 is None:
        raise ValueError("Couldn't find entry for %s in %s" %
         (sumFilePath, sha1SumsFile))

    downloadSha1 = GetSHA1FileHash(sourceFileFullPath)

    if sourceSha1 != downloadSha1:
        raise ValueError("Download doesn't match expected SHA1: expected: %s; "
         "download checksum: %s" % (sourceSha1, downloadSha1))

def VerifyFileList(fileList, commonPrefix=None):
    for f in fileList:
        testFile = f
        if commonPrefix is not None:
            testFile = os.path.join(commonPrefix, f)

        if not os.path.isfile(testFile):
            raise ValueError(testFile)

def VerifyFirefoxBuildConfigured(conf):
    autoconfTestFiles = conf.Get('autoconf_output_testfiles', list)
    objDir = GetObjDir(conf)

    try:
        VerifyFileList(autoconfTestFiles, objDir)
    except ValueError, ex:
        raise ValueError("Autoconf test file not present: %s" % (ex))

    confStatusFile = os.path.join(objDir, conf.Get('autoconf_status_file'))

    lastLine = None
    confStatusFileHandle = open(confStatusFile, 'r')
    for l in confStatusFileHandle:
        lastLine = l
    confStatusFileHandle.close()

    if lastLine.strip() != 'exit 0':
        raise ValueError("Last %s line didn't match successful exit: %s" %
         (confStatusFile, lastLine))

def VerifySuccessfulFirefoxBuild(conf):
    firefoxBuildTestFiles = conf.Get('build_test_files', list)
    distDir = os.path.join(GetObjDir(conf), 'dist')

    try:
        VerifyFileList(firefoxBuildTestFiles, distDir)
    except ValueError, ex:
        raise ValueError("Expected Firefox build output missing: %s" % (ex))

class FirefoxDownloadKeyAndSums(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

        self.dlFiles = [ self.config.Get('pgp_key_download_url'),
                         self.config.Get('sha1_checksum_download_url'),
                         self.config.Get('sha1_checksum_sig_download_url') ]

    def Preflight(self):
        PlatformCheck(self.config)

    def Execute(self):
        for f in self.dlFiles:
            cmd = [ self.config.GetConstant('WGET'),
                    '--progress=dot',
                    '--no-check-certificate',
                    f ]

            rv = RunShellCommand(command=cmd,
                                 verbose=True)

    def Verify(self):
        for f in self.dlFiles:
            # Probably shouldn't use os.path.basename here for realsies;
            # should really use urlparse, but for this simple case, it 
            # seems to work fine.
            fileName = os.path.basename(f)

            if not os.path.isfile(fileName):
                raise self.SimpleStepError("Key/checksum file %s missing." %
                 (fileName))

        keyFile = os.path.join(os.getcwd(),
         os.path.basename(self.config.Get('sha1_checksum_sig_download_url')))
        sha1SumsFile = os.path.join(os.getcwd(),
         os.path.basename(self.config.Get('sha1_checksum_download_url')))

        validationReqd = self.config.Get('require_pgp_validation', bool)

        # Could (should?) probably do this via PyCrypto, but for example-
        # purposes, I'm feeling lazy.
        gpgCommand = self.config.GetConstant('GPG')
        cmd = [ gpgCommand,
                '--verify',
                keyFile,
                sha1SumsFile ]

        rv = None
        try:
            rv = RunShellCommand(command=cmd,
                                 verbose=True,
                                 printOutput=False,
                                 raiseErrors=False)
        except ReleaseFrameworkError, ex:
            if str(ex) == "Invalid command or working dir":
                if validationReqd:
                    raise self.SimpleStepError("%s validation required, but "
                     "it looks like PGP isn't installed. Please install it."
                     % (gpgCommand))

                print >> sys.stderr, ("It appears %s isn't installed. "
                 "Checksum cannot be considered valid. Continuing anyway..."
                 % (gpgCommand))

        #print "%s, %d, %s, %s" % (rv, rv, rv.stdout, rv.stderr)

        try: 
            if int(rv) != 0:
                if re.search('No public key', rv.stderr[-1]):
                    error = ("Can't validate key; please import KEY (file: %s)"
                     % (keyFile))
                else:
                    error = "%s failed; exit code: %d; stderr: %s" % (
                     gpgCommand, rv, '\n'.join(rv.stderr))

                if validationReqd:
                    raise self.SimpleStepError("%s validation required: %s" %
                     (gpgCommand, error))
                else:
                    print >> sys.stderr, error + "; continuing anyway."
            else:
                if (rv.stderr[1].find('Good signature') == -1 or
                 rv.stderr[1].find(self.config.Get('pgp_key_owner')) == -1):
                    raise self.SimpleStepError("%s claims %s is invalid: %s" %
                     (gpgCommand, keyFile, '\n'.join(rv.stderr)))
        except IndexError:
            raise self.SimpleStepError("Unexpected output from %s; bailing."
             % gpgCommand)

        print '\n'.join(rv.stderr)

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
        try:
            VerifyFirefoxDownload(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))

class FirefoxExtractSource(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        conf = self.config
        PlatformCheck(conf)
        try:
            VerifyFirefoxDownload(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))

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

        try:
            VerifyFileList(firefoxTestFiles, sourceRoot)
        except ValueError, ex:
            raise self.SimpleStepError("Missing Firefox source file: %s" % (ex))

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
            raise self.SimpleStepError("Existing Mozconfig is in the way: %s" %
             mcFile)

    def Execute(self):
        conf = self.config

        mozConfigHandle = open(self._GetMozconfigFilename(), 'w')

        for line in re.split('\n+', self.config.Get('mozconfig_lines')):
            print >> mozConfigHandle, line.strip()

        mozConfigHandle.close()

        RunShellCommand(command=[conf.GetConstant('MAKE'),
                                 '-f', 'client.mk', 'configure'],
                        workdir=GetSourceDirRoot(conf),
                        verbose=True )

    def Verify(self):
        try:
            VerifyFirefoxBuildConfigured(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))

class FirefoxDoBuild(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        conf = self.config
        PlatformCheck(conf)
        try:
            VerifyFirefoxBuildConfigured(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))

    def Execute(self):
        conf = self.config

        rv = RunShellCommand(command=[conf.GetConstant('MAKE')],
                             workdir=GetObjDir(conf),
                             verbose=True,
                             timeout=7200,
                             logfile=os.path.join(conf.rootDir,
                              conf.Get('full_build_log')))

        print "\n\n***\nFull firefox build took %d seconds.\n***\n\n" % (
         rv.runningtime)

    def Verify(self):
        try:
            VerifySuccessfulFirefoxBuild(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))


class FirefoxDoInstallerBuild(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Preflight(self):
        conf = self.config
        PlatformCheck(conf)
        try:
            VerifySuccessfulFirefoxBuild(self.config)
        except ValueError, ex:
            raise self.SimpleStepError(str(ex))

    def Execute(self):
        conf = self.config

        rv = RunShellCommand(command=[conf.GetConstant('MAKE'),
                                     '-C', 'browser/installer'],
                             workdir=GetObjDir(conf),
                             verbose=True,
                             logfile=os.path.join(conf.rootDir,
                              conf.Get('installer_build_log')))

    def Verify(self):
        conf = self.config
        distDir = os.path.join(GetObjDir(conf), 'dist')

        delivsFound = FindDeliverables(distDir, conf)

        if delivsFound <= 0:
            raise self.SimpleStepError("No deliverables found after installer "
             "build?")
        else:
            print "Deliverables found in %s: %d" % (distDir, delivsFound)

        for d in GetAllDeliverables():
           print "Name %s -> %s" % (d.name, d.file)

        installerObj = GetDeliverable('installer:linux:en-US')
        if installerObj is None:
            raise self.SimpleStepError("No installer found after installer "
             "build")
        else:
            tmpDir = tempfile.gettempdir()
            print "Copying installer %s to %s" % (installerObj, tmpDir)
            shutil.copy(installerObj.fileName, tmpDir)

        # You probably don't need to do this, but as an example of some
        # of the utility functions...

        ourInstallerHash = GetSHA1FileHash(installerObj.fileName)
        tmpInstallerHash = GetSHA1FileHash(os.path.join(tmpDir,
         installerObj.file))

        if ourInstallerHash != tmpInstallerHash:
            raise self.SimpleStepError("Hashes do not match; orig: %s; copy: %s"
             % (ourInstallerHash, tmpInstallerHash))

