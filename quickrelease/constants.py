
QUICKRELEASE_CONSTANTS = {
    'BZIP_PROG': 'bzip2',
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

    'BUILD_PLATFORMS_MAP': {'Windows-i686': 'win32',
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

QUICKRELEASE_CONSTANTS['BUILD_PLATFORMS'] = QUICKRELEASE_CONSTANTS['BUILD_PLATFORMS_MAP'].values()

CONSTANTS_FROM_ENV_HANDLERS = {
    'BUILD_PLATFORMS': lambda val: tuple(val.split()),
    'BUILD_PLATFORM_EXTENSIONS': lambda val: NotImplementedError("Need to turn BUILD_PLATFORM_EXTENSIONS overloads into a dict!"), 
    'S3_MIME_TYPES': lambda val: NotImplementedError("Need to turn S3_MIME_TYPES overloads into a dict!"), 
}

