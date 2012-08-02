# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""
Logging class.
"""

import logging
import os
import re
import sys

from quickrelease.constants import _PIPE_STDOUT, _PIPE_STDERR
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

_COMMAND_LOGFILE_PREFIX = 'ShellCommand_'
_STEP_LOG_FILE = 'log.txt'

_TIME_FORMAT_STR = "%Y-%m-%d %H:%M:%S"

_QR_LOG_PREFIX = 'quickrelease'
_QR_COMMAND_LOG_PREFIX = '%s.command' % (_QR_LOG_PREFIX)
_QR_COMMAND_STDOUT_LOG_PREFIX = '%s.stdout' % (_QR_COMMAND_LOG_PREFIX)
_QR_COMMAND_STDERR_LOG_PREFIX = '%s.stderr' % (_QR_COMMAND_LOG_PREFIX)

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
        self._currentStepLogDir = None

        self._currentCommandLogHandler = None
        #self._currentCommandStdoutLogHandler = None
        #self._currentCommandStderrLogHandler = None

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
                ch = logging.StreamHandler(sys.stdout)
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
        #self._commandCount = 0

        self.logHandle.setLevel(min(self._loggingConfig.values()))
        _gAppLogger = self


    def _GetRawLogHandle(self): return logging.getLogger(_QR_LOG_PREFIX)
    def _GetLogDir(self): return self._logDirectory
    def _GetConfigString(self): return self._config
    def _GetCommandStdoutHandle(self): return _ShellCommandLoggerHandle(
     _PIPE_STDOUT)
    def _GetCommandStderrHandle(self): return _ShellCommandLoggerHandle(
     _PIPE_STDERR)
    def _GetStepLogDir(self, step):
        return os.path.join(self.logDirectory, str(step.process), str(step))
    def _GetCurrentStepLogDir(self):
        return self._currentStepLogDir

    logHandle = property(_GetRawLogHandle)
    logDirectory = property(_GetLogDir)
    stepLogDirectory = property(_GetCurrentStepLogDir)
    config = property(_GetConfigString)
    commandOutHandle = property(_GetCommandStdoutHandle)
    commandErrHandle = property(_GetCommandStderrHandle)

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

        self._currentStepLogDir = self._GetStepLogDir(step)
        if not os.path.exists(stepLogDir):
            Makedirs(stepLogDir)

        stepLogFile = os.path.join(self._currentStepLogDir, _STEP_LOG_FILE)

        fh = None
        try:
            fh = logging.FileHandler(stepLogFile, mode='w')
            fh.setLevel(self._loggingConfig[_DIR_OUTPUT])
            fh.setFormatter(self._formatter)
            fh.addFilter(NoCommandOutputFilter())
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

    # Right now, we only support a single LoggedShellCommand being run/logged
    # at a time anyway. So, to simplify the initial implementation, an open()
    # call to either the stdout/stderr log handles will open both, and neither
    # of them will actually close until they're both marked as closed.
    #
    # It will then be the caller's problem (in command.py) to synchronize this
    # so output from multiple commands don't get interleaved. This is a crappy
    # solution (and will likely be rewritten at some point), but it should
    # do for now, since we don't expect client users to ever have to futz
    # with this code (famous last words).
    #
    # (This is also why the parameter/state checking results in assert()ions,
    # not catchable exceptions.)
    #
    def InitializeCommandLog(self, commandLogger):
        if commandLogger == _QR_COMMAND_STDERR_LOG_PREFIX:
            return

        assert self._currentCommandLogHandler is None, ("InitializeCommandLog()"
         ": called on already-initalized command logger?")

        #assert (self._currentCommandStdoutLogHandler is None and
        # self._currentCommandStderrLogHandler is None), ("Command log is still "
        # "in use: stdout %s, stderr %s" % (self._currentCommandStdoutLogHandler,
        # self._currentCommandStderrLogHandler)

        if _DIR_OUTPUT not in self._loggingConfig.keys():
            return

        #if (self._currentCommandStdoutLogHandler is not None and
        # self._currentCommandStderrLogHandler is not None):
        #    return

        logOutput = "%s.txt" % (self._GetNextStepCommandLogfileName())

        fh = logging.FileHandler(logOutput, mode='a')
        fh.setLevel(logging.ERROR)
        fh.setFormatter(self._formatter)
        fh.addFilter(CommandOutputFilter())
        self.logHandle.addHandler(fh)
        self._currentCommandLogHandler = fh
        print "in init: %s" % (self._currentCommandLogHandler)

    def CloseCommandLog(self, commandLogger):
        if _DIR_OUTPUT not in self._loggingConfig.keys():
            return
        #print "CloseCommandLog(%s)" % (commandLogger)
        #print "%s" % (self._currentCommandLogHandler)
        if commandLogger == _QR_COMMAND_STDERR_LOG_PREFIX:
            return

        assert self._currentCommandLogHandler is not None, ("CloseCommandLog() "
         "called on non-existent command logger?")


        self.logHandle.removeHandler(self._currentCommandLogHandler)
        self._currentCommandLogHandler.close()
        self._currentCommandLogHandler = None

    def _GetNextStepCommandLogfileName(self):
        stepLogDir = GetAppLogger().stepLogDirectory

        if stepLogDir is None:
            raise RuntimeError("BLAH")

        runShellCommandLogs = []
        for entry in os.listdir(stepLogDir):
            if os.path.isfile(entry) and re.match('^%s\d+' %
             (_COMMAND_LOGFILE_PREFIX), entry):
                runShellCommandLogs.append(entry)

        return os.path.join(self.logDirectory,
         '%s%d' % (_COMMAND_LOGFILE_PREFIX, len(runShellCommandLogs) + 1))

class QuickReleaseFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith(_QR_LOG_PREFIX)

class CommandStdoutFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith(_QR_COMMAND_STDOUT_LOG_PREFIX)

class CommandStderrFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith(_QR_COMMAND_STDERR_LOG_PREFIX)

class NoCommandOutputFilter(logging.Filter):
    def filter(self, record):
        return not record.name.startswith(_QR_COMMAND_LOG_PREFIX)

class CommandOutputFilter(logging.Filter):
    def filter(self, record):
        return record.name.startswith(_QR_COMMAND_LOG_PREFIX)

_gCommandCount = 0

#def _GetCommandNumber():
#    global _gCommandCount
#    oldCount = _gCommandCount
#    _gCommandCount += 1
#    return oldCount

#class ShellCommandLogger(object):
#    def __init__(self):
#        object.__init__()
#
#        self._commandNum = _GetCommandNumber()
#
#    def _GetStdOutHandle: return _ShellCommandLoggerHandle(self._commandNum,
#     _PIPE_OUT)
#    def _GetStdErrHandle: return _ShellCommandLoggerHandle(self._commandNum,
#     _PIPE_ERR)
#
#    stdoutHandle = property(_GetStdOutHandle)
#    stderrHandle = property(_GetStdErrHandle)

class _ShellCommandLoggerHandle(object):
    def __init__(self, outputType):
        object.__init__(self)

        if _PIPE_STDOUT == outputType:
            self._loggerName = _QR_COMMAND_STDOUT_LOG_PREFIX
        elif _PIPE_STDERR == outputType:
            self._loggerName = _QR_COMMAND_STDERR_LOG_PREFIX
        else:
            raise ValueError("Invalid output type '%s'" % (outputType))

        self._logger = logging.getLogger(self._loggerName)
        self._openHandle = False

    def open(self):
        assert self._openHandle is False, ("Invalid _ShellCommandLoggleHandle.")
        # attach logger
        GetAppLogger().InitializeCommandLog(self._loggerName)
        self._openHandle = True
        return self

    def write(self, content):
        # TODO: allow user to configure what level this is logged at
        assert self._openHandle, "Invalid _ShellCommandLoggleHandle."
        self._logger.warning(content)

    def flush(self):
        assert self._openHandle, "Invalid _ShellCommandLoggleHandle."
        pass

    def close(self):
        # detach logger
        GetAppLogger().CloseCommandLog(self._loggerName)
        self._openHandle = False
        pass

