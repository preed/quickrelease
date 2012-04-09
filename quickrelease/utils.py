# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import hashlib
import os
import platform
import re
import sys
from urllib import FancyURLopener

from quickrelease.config import ConfigSpec, ConfigSpecError
from quickrelease.exception import ReleaseFrameworkError

def PrintReleaseFrameworkError(ex):
    sys.stdout.flush()
    sys.stderr.flush()
    print >> sys.stderr, "Release Framework Error: " + str(ex)
    sys.stderr.flush()

def GetDeliverableRootPath(configSpec):
    return os.path.join(configSpec.Get('root_dir'),
     configSpec.SectionGet('deliverables', 'release_deliverables_dir'))

def GetActivePartnerList(configSpec):
    partners = configSpec.Get('active_partners', list)
    for p in partners:
        assert configSpec.ValidPartner(p), ("Invalid partner '%s' specified in " 
         "active_partners" % (p))

    return partners

def GetAllPartnerList(configSpec):
    partners = []
    for s in configSpec.GetSectionList():
        # TODO: make 'partner:' a constant, not a string
        partnerMatch = re.match('^partner:(\w+)$', s)
        if partnerMatch:
             partners.append(partnerMatch.group(1))

    return partners

def GetSHA1FileHash(path):
    if not os.path.isfile(path):
        raise ValueError("GetSHA1FileHash(): invalid path: %s" % (path))

    sha1 = hashlib.sha1()
    try:
        f = open(path, 'rb')
        sha1.update(f.read())
    finally:
        f.close()
    return sha1.hexdigest()

def GetBuildPlatform():
    plat = platform.system()
    arch = platform.machine()

    keyName = "%s-%s" % (plat, arch)

    try:
        return ConfigSpec.GetConstant('BUILD_PLATFORMS_MAP')[keyName]
    except KeyError:
        raise ConfigSpecError("GetBuildPlatform() returned unknown platform "
         "'%s'; define it in BUILD_PLATFORMS_MAP." % (keyName))

def Makedirs(path):
    if os.path.isdir(path):
        return
    return os.makedirs(path)

# May seem weird, but some programs (the Perforce client, most notably) actually
# look at PWD to figure out their current working directory, not getcwd(3)
def Chdir(path):
    oldcwd = os.getcwd()
    rv = os.chdir(path)
    os.environ['OLDPWD'] = oldcwd
    os.environ['PWD'] = path
    return rv

class ExceptionURLopener(FancyURLopener):
    def __init__(self, *args, **kwargs):
        FancyURLopener.__init__(self, *args, **kwargs)

    def http_error_default(self, url, fp, errcode, errmsg, headers, data=None):
        if errcode == 403 or errcode == 404:
            raise IOError("HTTP %d error on %s" % (errcode, url))

        return FancyURLopener.http_error_default(self, url, fp, errcode, errmsg,
         headers, data)

def ImportModule(moduleName):
    module = __import__(moduleName)
    moduleComponents = moduleName.split('.')
    for comp in moduleComponents[1:]:
        module = getattr(module, comp)

    return module

def ImportFunction(functionName):
    moduleNameParts = functionName.split('.')
    moduleName = '.'.join(moduleNameParts[:-1])
    function = getattr(ImportModule(moduleName), moduleNameParts[-1])
    return function
