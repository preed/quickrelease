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
from quickrelease.exception import _QuickReleaseError
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
_STEP_LOG_FILE = 'log.txt'

_TIME_FORMAT_STR = "%Y-%m-%d %H:%M:%S"

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
            except (ValueError, AttributeError):
                # Handle int()s that fail and non-string objects that can't
                # strip()
                raise ValueError("Invalid logging config part: %s" % (part))

            levelRange = range(len(_LEVEL_MAP))
            if level not in levelRange:
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
        global _gAppLogger

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
        self._prefixMessages = False
        self._timestampMessages = False
        self._config = None

        # Internal stuff
        self._loggingConfig = {}
        self._currentStepLogHandler = None

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
            if self._logDirectory is not None:
                self._config = _DEFAULT_CONFIG_WITH_LOGDIR
            else:
                self._config = _DEFAULT_CONFIG
        
        self._ParseConfigString()
        
        if self._logDirectory is not None:
            self._logDirectory = os.path.abspath(self._logDirectory)

        for logOutput in self._loggingConfig.keys():
            if (logOutput == _DIR_OUTPUT and self._logDirectory is None):
                raise ValueError("Log level(s) %s set to output to a "
                 "directory, but no log directory was specified; see the "
                 "-L option." % (', '.join(self._loggingConfig[logOutput])))

        if self._logDirectory is not None:
            if os.path.exists(self._logDirectory):
                if not os.path.isdir(self._logDirectory):
                    raise ValueError("The specified log directory %s exists, "
                     "but is not a directory." % (self._logDirectory))
            else:
                Makedirs(self._logDirectory)

        self._formatStr = '%(message)s'

        if self._prefixMessages:
            self._formatStr = '%(levelname)s: %(message)s'
        if self._timestampMessages:
            self._formatStr = '%(asctime)s: %(message)s'
        if self._prefixMessages and self._timestampMessages:
            self._formatStr = '%(asctime)s %(levelname)s: %(message)s'

        self._formatter = logging.Formatter(self._formatStr, _TIME_FORMAT_STR)

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
                ch.setFormatter(self._formatter)
                self.logHandle.addHandler(ch)
            else:
                fh = logging.FileHandler(logOutput, mode='a')
                fh.setLevel(self._loggingConfig[logOutput])
                fh.setFormatter(self._formatter)
                self.logHandle.addHandler(fh)

        self._currentStepName = None
        self._currentStepHandler = None

        self.logHandle.setLevel(min(self._loggingConfig.values()))
        _gAppLogger = self


    def _GetRawLogHandle(self): return logging.getLogger('quickrelease')
    def _GetLogDir(self): return self._logDirectory
    def _GetConfigString(self): return self._config

    logHandle = property(_GetRawLogHandle)
    logDirectory = property(_GetLogDir)
    config = property(_GetConfigString)

    def _GetStepLogDir(self, step):
        return os.path.join(self.logDirectory, str(step.process), str(step))

    def _GetNextStepCommandLogfileName(self, step):
        stepLogDir = self._GetStepLogDir(step)

        runShellCommandLogs = []
        for entry in os.listdir(stepLogDir):
            if os.path.isfile(entry) and re.match('^%s\d+' %
             (_COMMAND_LOGFILE_PREFIX), entry):
                runShellCommandLogs.append(entry)

        return os.path.join(self.logDirectory,
         '%s%d' % (_COMMAND_LOGFILE_PREFIX, len(runShellCommandLogs) + 1))

    def _HandleStepLogHandler(self, givenKwargs):
        if _DIR_OUTPUT not in self._loggingConfig.keys():
            return

        # Handles the case where someone grabbed the logger from GetAppLogger(),
        # and wants to print an error message; in this case (for now), we'll
        # print the log message to wherever the other log output is going,
        # which seems reasonable, but may also bury log output.
        #
        # Hrm...

        if 'step' not in givenKwargs:
            return

        step = givenKwargs['step']

        if step.name == self._currentStepName:
            return

        if self._currentStepLogHandler is not None:
            self.logHandle.removeHandler(self._currentStepLogHandler)
            self._currentStepLogHandler.close()
        self._currentStepLogHandler = None

        self._currentStepName = step.name

        stepLogDir = self._GetStepLogDir(step)
        if not os.path.exists(stepLogDir):
            Makedirs(stepLogDir)

        stepLogFile = os.path.join(stepLogDir, _STEP_LOG_FILE)

        fh = None
        try:
            fh = logging.FileHandler(stepLogFile, mode='w')
            fh.setLevel(self._loggingConfig[_DIR_OUTPUT])
            fh.setFormatter(self._formatter)
        except IOError, ex:
            raise _QuickReleaseError(ex)
            
        self.logHandle.addHandler(fh)
        self._currentStepLogHandler = fh

    def Log(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.warning(msg, kwargs)

    def LogErr(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.error(msg, kwargs)

    def LogDebug(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.info(msg, kwargs)

    def _LogQR(self, msg, **kwargs):
        self._HandleStepLogHandler(kwargs)
        return self.logHandle.debug(msg, kwargs)
