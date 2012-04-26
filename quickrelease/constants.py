# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""A defined list of constants available to QuickRelease users.

The are some important difference between QuickRelease's L{config items<quickrelease.config>} and C{constants}:

  1. C{constants} may be accessed without a L{ConfigSpec<quickrelease.config.ConfigSpec>} reference. This makes them useful in places where it may be difficult to obtain such a reference.
  2. C{constants} can be overriden by the environment. This can be useful, but should be used sparingly, since the override is not yet logged anywhere. It's mostly intended to redefine paths to executables in different situations.  For instance, if you have a debug version of the C{unzip} utility that you would like to have a L{Process<quickrelease.process.Process>} use. You can set the C{UNZIP} environment variable, and if your process is using a constant, it will be picked up. (This is similar to L{ConfigSpec<quickrelease.config.ConfigSpec>}'s overrides, but cannot currently be disabled.)
  3. C{constant} can return complex Python types (lists, dictionaries, etc.)
"""

QUICKRELEASE_CONSTANTS = {
    'BZIP_PROG': 'bzip2',
    'GPG' : 'gpg',
    'MAKE' : 'make',
    'MD5SUM' : 'md5sum',
    'MV' : 'mv',
    'PERL' : 'perl',
    'S3CURL' : 's3curl.pl',
    'SVN' : 'svn',
    'RSYNC' : 'rsync',
    'TAR' : 'tar',
    'UNZIP' : 'unzip',
    'WGET' : 'wget',

    'BUILD_PLATFORMS_MAP': { 'Windows-i686': 'win32',
                             'Darwin-i686': 'mac',
                             'Linux-i686': 'linux',
                             'Linux-x86_64': 'linux-x64',
                           },

    'BUILD_PLATFORM_EXTENSIONS': { 'win32': 'exe',
                                   'mac': 'dmg',
                                   'linux': 'tar.gz',
                                   'linux-x64': 'tar.gz',
                                 },

    # in seconds, so five minutes
    'RUN_SHELL_COMMAND_DEFAULT_TIMEOUT': 60 * 5,

    # in seconds, so 10 mintues.
    'S3_PUSH_TIMEOUT': 60 * 10,

    'S3_MIME_TYPES': { 'asc' : 'text/plain',
                       'bz2' : 'application/x-bzip2',
                       'dmg' : 'application/x-apple-diskimage',
                       'exe' : 'application/octet-stream',
                       'mar' : 'application/octet-stream',
                       'md5' : 'text/plain',
                       'tar.gz' : 'application/x-gzip',
                       'txt': 'text/plain',
                       'zip': 'application/zip',
                     },
}
"""
Various constants that can be useful for QuickRelease L{Process<quickrelease.process.Process>}es.
"""

QUICKRELEASE_CONSTANTS['BUILD_PLATFORMS'] = QUICKRELEASE_CONSTANTS['BUILD_PLATFORMS_MAP'].values()

CONSTANTS_FROM_ENV_HANDLERS = {
    'BUILD_PLATFORMS': lambda val: tuple(val.split()),
    'BUILD_PLATFORM_EXTENSIONS': lambda val: NotImplementedError("Need to turn BUILD_PLATFORM_EXTENSIONS overloads into a dict!"), 
    'S3_MIME_TYPES': lambda val: NotImplementedError("Need to turn S3_MIME_TYPES overloads into a dict!"), 
}
"""A dictionary of named constants -> handlers to convert an environment 
variable string into the expected Python type. The type should match
what the named constant in L{QUICKRELEASE_CONSTANTS<quickrelease.constants.QUICKRELEASE_CONSTANTS>} returns.
"""
