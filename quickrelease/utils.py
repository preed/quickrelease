# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""Various utility functions that may prove useful in a build/release
engineering-related context.
"""

import hashlib
import os
import platform
import re
import sys
from urllib import FancyURLopener

from quickrelease.config import ConfigSpec, ConfigSpecError

def PrintReleaseFrameworkError(ex):
    """
    Print the provided exception to STDERR, flushing all other output streams
    first. (This is generally necessary on Win32 platforms.)

    @param ex: The L{ReleaseFrameworkError<quickrelease.exception.ReleaseFrameworkError>} to print.
    @type ex: L{ReleaseFrameworkError<quickrelease.exception.ReleaseFrameworkError>}
    """
    sys.stdout.flush()
    sys.stderr.flush()
    print >> sys.stderr, "Release Framework Error: " + str(ex)
    sys.stderr.flush()

def GetDeliverableRootPath(configSpec):
    """
    Convenience method to return the root path of a directory to traverse
    for searching for deliverables.
    
    Useful when employing 
    L{FindDeliverables<quickrelease.deliverable.FindDeliverables>}.

    @note: Requires C{release_deliverables_dir} be defined in the configuration
    specification.

    @param configSpec: the L{ConfigSpec<quickrelease.config.ConfigSpec>} to
    search for partner names.
    @type configSpec: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @return: The path to the deliverable storage area, as defined by the user.
    @rtype: C{str}
    """
    return JoinPaths(configSpec.rootDir,
     configSpec.SectionGet('deliverables', 'release_deliverables_dir'))

def GetActivePartners(configSpec):
    """
    Get a list of all the active partners specified in the given 
    configuration specification.

    @note: QuickRelease provides a distinction between "partner" and 
    "active partner" so that you may (re-)run various processes on individual 
    partners without having to create an entirely new configuration file.

    @param configSpec: the L{ConfigSpec<quickrelease.config.ConfigSpec>} to
    search for partner names.
    @type configSpec: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @return: A list of "active" partners, as defined by the C{active_partners}
    item in the currently-selected section.
    @rtype: C{list}
    """

    partners = configSpec.Get('active_partners', list)
    for p in partners:
        assert configSpec.ValidPartner(p), ("Invalid partner '%s' specified in " 
         "active_partners" % (p))

    return partners

def GetAllPartners(configSpec):
    """
    Get all partner names defined in the given configuration specification.

    @param configSpec: the L{ConfigSpec<quickrelease.config.ConfigSpec>} to
    search for partner names.
    @type configSpec: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @return: A list of all partner names defined in the configuration
    specificiation.
    @rtype: C{list}
    """
    partners = []
    for s in configSpec.sectionList:
        # TODO: make 'partner:' a constant, not a string
        partnerMatch = re.match('^partner:(\w+)$', s)
        if partnerMatch:
             partners.append(partnerMatch.group(1))

    return partners

def GetSHA1FileHash(path):
    """
    Get the SHA1 file hash of a specific file.

    @param path: Path to the file to get a SHA1 sum for.
    @type path: C{str}

    @return: The SHA1 checksum of specified file.
    @rtype: C{str}

    @raise ValueError: If the specified path is not a valid file.

    """
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
    """
    Convenience method for converting Python's representation of the machine 
    architecture its running on (via its L{platform} module) to a string that
    is useful within your own organization.

    This is accomplished via the C{BUILD_PLATFORMS_MAP} in the 
    L{Constants<quickrelease.constants>} class.

    @return: A string specified by the user representing the architecture
    of the machine QuickRelease is currently running on.
    @rtype: C{str}
    """
    plat = platform.system()
    arch = platform.machine()

    keyName = "%s-%s" % (plat, arch)

    try:
        return ConfigSpec.GetConstant('BUILD_PLATFORMS_MAP')[keyName]
    except KeyError:
        raise ConfigSpecError("GetBuildPlatform() returned unknown platform "
         "'%s'; define it in BUILD_PLATFORMS_MAP." % (keyName))

def Makedirs(path):
    """
    A wrapper around os.makedirs() which will not throw an exception if the
    directory already exists.

    @param path: The directory path to attempt to create.
    @type path: C{str}

    @raise OSError: for any errors the underlying implementation of 
    C{os.makedirs()} would.
    @raise AttributeError: when invalid paths are passed.
    """
    if os.path.isdir(path):
        return
    return os.makedirs(path)

def Chdir(path):
    """
    A wrapper around os.chdir() to mimic shell behavior when changing
    directories.

    This may seem weird, but some programs (the 
    U{Perforce<http://www.perforce.com/>} client, most notably) actually
    look at PWD to figure out their current working directory, not getcwd(3)

    @param path: The directory path to chdir() into.
    @type path: C{str}

    @raise OSError: for any errors the underlying implementation of 
    C{os.chdir()} would.
    @raise TypeError: when invalid paths are passed.
    """
    oldcwd = os.getcwd()
    rv = os.chdir(path)
    os.environ['OLDPWD'] = oldcwd
    os.environ['PWD'] = path
    return rv

def JoinPaths(*args):
    """
    A wrapper around C{os.path.join()} which passes the result to
    C{os.path.normpath()} to ensure correct path separators.

    os.path.join() will not alter arguments that contain a[n incorrect]
    platform-specific path separator, to normalize them for the current
    operating system.

    This case can occur when paths are built up in a L{ConfigSpec<quickrelease.config.ConfigSpec>}
    with platform-specific path separtors in them.

    @param args: The directory components to join together.
    @type args: Array of C{str}

    @return: A string representing the joined paths, separated by the correct
    operating system path separator.
    @rtype: C{str}
    """
    return os.path.normpath(os.path.join(*args))

def WriteMemo(memoFileName, content, appendOk=False):
    if not appendOk and os.path.exists(memoFileName):
        raise ValueError("Memo file %s exists" % (memoFileName))

    if appendOk:
        handleMode = 'ab'
    else:
        handleMode = 'wb'

    try:
        memoHandle = open(memoFileName, handleMode)
    except IOError, ex:
        raise ValueError(ex)

    try:
        if type(content) in (list, tuple):
            for i in content:
                print >> memoHandle, i
        else:
            print >> memoHandle, content
    finally:
        memoHandle.close()

def ReadMemo(memoFileName, returnType=str): 
    if returnType not in (str, list, tuple):
        raise ValueError("ReadMemo() can only return str, list, tuple")

    try:
        memoHandle = open(memoFileName, 'rb')
    except (IOError, OSError), ex:
        raise ValueError(ex)

    try:
        content = None
        if returnType is str:
            content = memoHandle.read()
        elif returnType in (list, tuple):
            content = []
            for l in memoHandle:
                content.append(l.rstrip(os.linesep))

            content = returnType(content)
        else:
            assert False, "Unhandled return type: %s" % (returnType)
    finally:
        memoHandle.close()

    assert type(content) is returnType, ("content (type %s) is not "
     "requested returnType (%s)" % (type(content), returnType))
    return content

class ExceptionURLopener(FancyURLopener):
    """
    A thin wrapper around L{FancyURLopener} which raises an L{IOError} if
    an HTTP 403 (permission denied) or 404 (URI target not found) is
    encountered.

    This is useful for doing quick verifications to see that published
    deliverables are available at the expected URL.

    @raise IOError: If an HTTP 403/404 are encountered while retrieving the 
    specified URL. FancyURLopener also uses L{IOError}s for communicating errors
    it encounters.
    """
    def http_error_default(self, url, fp, errcode, errmsg, headers, data=None):
        if errcode == 403 or errcode == 404:
            raise IOError("HTTP %d error on %s" % (errcode, url))

        return FancyURLopener.http_error_default(self, url, fp, errcode, errmsg,
         headers, data)

def ImportModule(moduleName):
    """
    A convenience method for importing the given module name.
    @param moduleName: the name of the module to attempt to import
    @type moduleName: C{str}

    @return: A reference to the module object that can be queried, introspected,
    or instantiated.
    @rtype: C{module}

    @raise ImportError: Any standard ImportErrors are raised, per 
    C{__import__}'s normal behavior.
    """
    module = __import__(moduleName)
    moduleComponents = moduleName.split('.')
    for comp in moduleComponents[1:]:
        module = getattr(module, comp)

    return module

def ImportFunction(functionName):
    """
    A convenience method for importing a specific function out of a particular
    module and returning it for use.
    @param functionName: the fully qualified name, including package, of the 
    function to attempt to import
    @type functionName: C{str}

    @return: A function object which can be called.
    @rtype: C{function}

    @raise ImportError: Any standard ImportErrors are raised, per 
    C{__import__}'s normal behavior.
    """
    moduleNameParts = functionName.split('.')
    moduleName = '.'.join(moduleNameParts[:-1])
    function = getattr(ImportModule(moduleName), moduleNameParts[-1])
    return function
