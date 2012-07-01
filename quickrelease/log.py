# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""
Logging class.
"""

import logging
import os
import re
import sys

from quickrelease.config import ConfigSpec
from quickrelease.utils import Makedirs

_LEVEL_MAP = [
                        logging.ERROR,
                        logging.WARNING,
                        logging.INFO,
                        logging.DEBUG 
                      ]

_CONSOLE_OUTPUT = 'console'
_DIR_OUTPUT = 'dir'

_DEFAULT_CONFIG = '1:%s' % (_CONSOLE_OUTPUT)
_DEFAULT_CONFIG_WITH_LOGDIR = '1:%s,2:%s' % (_CONSOLE_OUTPUT, _DIR_OUTPUT)

_COMMAND_LOGFILE_PREFIX = 'RunShellCommand_'

_gAppLogger = None

def GetAppLogger():
    if _gAppLogger is None:
        raise RuntimeError("No logger configured for this application run.")
    return _gAppLogger

class Logger(object):
    """
    An object representing a handle to a QuickRelease Logger, which is, in turn,
    a wrapper around Python's own L{logging} module.
    """
    RECOGNIZED_CONSTRUCTOR_ARGS = ('config', 'logDirectory', 'prefixMessages',
     'timestampMessages')

    def _ParseConfigString(self):
        configParts = self._config.split(',')

        for part in configParts:
            if part.strip() == '':
                continue

            try:
                (level, output) = part.split(':')
                level = int(level)
                output = output.strip()
            except ValueError:
                # Handle int()s that fail and non-string objects that can't
                # strip()
                raise ValueError("Invalid logging config part: %s" % (part))

            levelRange = range(len(_LEVEL_MAP))
            if not level in levelRange:
                raise ValueError("Invalid logging level '%d'; must be %d-%d" %
                 (level, min(levelRange), max(levelRange)))
       
            if output not in (_CONSOLE_OUTPUT, _DIR_OUTPUT):
                if not os.path.isabs(output):
                    raise ValueError("When specifying files to log to, "
                     "absolute paths must be used.")
                elif os.path.exists(output):
                     raise ValueError("Cannot log to an exisiting path; "
                      "please remove %s first." % (output))
        
            self._loggingConfig[output] = _LEVEL_MAP[level]

    def __init__(self, *args, **kwargs):
        """
        Construct a L{Logger} object.

        @param config: A configuration string to configure this logger.
        @type config: C{str}

        @param logDirectory: The root directory to place log files in, organized by process and step. {Process}.
        @type executeSteps: C{str}

        @param prefixMessages: Whether to prefix each message with its message type (error, warning, info, or debug). (Note: QuickRelease uses a slightly different definition for these terms than most syslog-style applications; refer to the documentation for details.
        @type prefixMessages: C{bool} (Default: false)

        @param timestampMessages: Whether to prefix each message with a timestamp.
        @type timestampMessages: C{bool} (Default: false)
        """
        object.__init__(self)
        
        # default attributes
        self._logDirectory = None

        # prefix each message with data-type (info, debug, error, etc.)
        self._prefixMessages = False
        self._timestampMessages = False

        self._loggingConfig = {}

        self._config = None

        # levels:
        # 0 - errors: only exceptions
        # 1 - warning: user important messages
        # 2 - info: user debugging
        # 3 - debug: quickrelease debug messages

        # logdir -> console
        # logdir: logdir/process/step/log.txt
        #         log.info, log.out, log.err
        #         log.info, log.out, log.err
        # output is "dir", "stepfile", "file", "console"
        #
        # status mode (prints what quickrelease is doing)

        for arg in Logger.RECOGNIZED_CONSTRUCTOR_ARGS:
            if kwargs.has_key(arg):
                setattr(self, '_' + arg, kwargs[arg])

        if self._config is None:
            self._config = _DEFAULT_CONFIG

        if self._logDirectory is not None:
            self._config = _DEFAULT_CONFIG_WITH_LOGDIR

        self._ParseConfigString()

        for logOutput in self._loggingConfig.keys():
            if (logOutput == _DIR_OUTPUT and self._logDirectory is None):
                raise ValueError("Log level(s) %s set to output to a "
                 "directory, but no log directory was specified; see the "
                 "-L option." % (', '.join(self._loggingConfig[logOutput])))

        if (self._logDirectory is not None and
         not os.path.exists(self._logDirectory)):
            Makedirs(self._logDirectory)

        self._formatStr = '%(message)s'

        if self._prefixMessages:
            self._formatStr = '%(levelname)s: %(message)s'
        if self._timestampMessages:
            self._formatStr = '%(acstime)s: %(message)s'
        if self._prefixMessages and self._timestampMessages:
            self._formatStr = '%(acstime)s %(levelname)s: %(message)s'

        self._formatter = logging.Formatter(self._formatStr)

        for logOutput in self._loggingConfig.keys():
            if logOutput == _DIR_OUTPUT:
                # Dir is handled below, since the file name changes at every
                # step...
                pass 
            elif logOutput == _CONSOLE_OUTPUT:
                #ch = logging.StreamHandler(stream=sys.stdout)
                ch = logging.StreamHandler(sys.stdout)
                #print self._loggingConfig[logOutput]
                ch.setLevel(self._loggingConfig[logOutput])
                self.logHandle.addHandler(ch)
            else:
                fh = logging.FileHandler(logOutput, mode='a')
                fh.setLevel(self._loggingConfig[logOutput])
                self.logHandle.addHandler(fh)

        self._currentStepName = None
        self._currentStepHandler = None

        _gAppLogger = self


    def _GetRawLogHandle(self): return logging.getLogger('quickrelease')
    def _GetLogDir(self): return self._logDirectory
    def _GetConfigString(self): return self._config

    logHandle = property(_GetRawLogHandle)
    logDirectory = property(_GetLogDir)
    config = property(_GetConfigString)

    def _GetStepLogfileName(self, step):
        return os.path.join(self._logDirectory, step.process, str(step))

    def _GetNextStepCommandLogfileName(self, step):
        stepLogDir = self._GetStepLogfileName()

        runShellCommandLogs = []
        for entry in os.listdirs(stepLogDir):
            if os.path.isfile(entry) and re.match('^%s\d+' %
             (_COMMAND_LOGFILE_PREFIX), entry):
                runShellCommandLogs.append(entry)

        return os.path.join(self._logDirectory, step.process, str(step),
         '%s%d' % (_COMMAND_LOGFILE_PREFIX, len(runShellCommandLogs) + 1))

    def _HandleStepLogHandler(self, givenKwargs):
        if _DIR_OUTPUT not in self._loggingConfig.keys():
            return

        if 'step' not in givenKwargs:
            raise RuntimeError("Need a step!")


        step = givenKwargs['step']

        if step.name == self._currentStepName:
            return

        self.logHandle.removeHandler(self._currentStepLogHandler)
        self._currentStepName = step.name
        self._currentStepLogHandler = None
        fh = logging.FileHandler(self._GetStepLogfileName(step), mode='w')
        fh.setLevel(_LEVEL_MAP[self._loggingConfig['dir']])
        self.logHandle.addHandler(fh)
        self._currentStepLogHandler = fg

    def Log(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.warning(msg, kwargs)

    def LogErr(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.error(msg, kwargs)

    def LogDebug(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.info(msg, kwargs)

    def LogInternalDebug(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.debug(msg, kwargs)
