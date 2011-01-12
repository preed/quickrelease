
QUICKRELEASE_CONSTANTS = {
   'MV' : 'mv',
   'PERL' : 'perl',
   'S3CURL' : 's3curl.pl',
   'SVN' : 'svn',
   'RSYNC' : 'rsync',
   'UNZIP' : 'unzip',
   'WGET' : 'wget',
   
   'SB_BUILD_PLATFORMS': ('windows-i686-msvc8',
                          'macosx-i686',
                          'linux-i686',
                          'linux-x86_64'),

   'SB_BUILD_PLATFORM_EXTENSIONS': { 'windows-i686-msvc8': 'exe',
                                     'macosx-i686': 'dmg',
                                     'linux-i686': 'tar.gz',
                                     'linux-x86_64': 'tar.gz' },

   # in seconds, so five minutes
   'RUN_SHELL_COMMAND_DEFAULT_TIMEOUT': 60 * 5,

   # in seconds, so 10 mintues.
   'SB_S3_PUSH_TIMEOUT': 60 * 10,

   'SB_S3_MIME_TYPES': { 'asc' : 'text/plain',
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

CONSTANTS_FROM_ENV_HANDLERS = {
   'SB_BUILD_PLATFORMS': lambda val: tuple(val.split()),
   'SB_BUILD_PLATFORM_EXTENSIONS': lambda val: NotImplementedError("Need to turn SB_BUILD_PLATFORM_EXTENSIONS overloads into a dict!"), 
   'SB_BUILD_S3_MIME_TYPES': lambda val: NotImplementedError("Need to turn SB_BUILD_S3_MIME_TYPES overloads into a dict!"), 
}

