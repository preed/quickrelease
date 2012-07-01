# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""A class for handling the launching, logging, handling, and termination of
external programs.

A minor historical note: 

The L{RunShellCommand<quickrelease.command.RunShellCommand>} class may, at first
glance, seem a bit weird.

This is mostly because it was originally a Python function that was later
converted to a class.

Additionally, an important initial design goal was to be 
API-compatible with a U{RunShellCommand()<http://mxr.mozilla.org/mozilla/source/tools/release/MozBuild/Util.pm#25>}-function
found in U{Mozilla<http://www.mozilla.org/>}'s (now legacy) Perl-based release 
framework, and ported. Over the years, additionally functionality was added.

It may seem odd that this class uses threading (and the old adage--"if you
solve a problem with threads, now you have I{two} problems"--may come to mind),
but this solution was based on the fact that the standard C{poll()}/C{select()}
model doesn't work on Win32, and RunShellCommand was required to support that
use-case.

Suffice it to say, while this class works well for its intended purposes,
it is also likely ripe for refactoring, including possible conversion to 
something such as U{MozProcess<https://github.com/mozautomation/mozmill/tree/b8eab24394d040bfadb25f041260cc39dcadd776/mozprocess>}.
"""

import errno
import os
import pickle
import re
from subprocess import PIPE
import sys
from tempfile import NamedTemporaryFile
from threading import Thread
import time
from Queue import Queue, Empty

from quickrelease.config import ConfigSpec, ConfigSpecError
from quickrelease.exception import ReleaseFrameworkError

gUsingKillableProcess = True
"""On Win32, the L{killableprocess<quickrelease.killableprocess>} class uses
process groups. There is a limitation that only one process may own the handle
to the process group. Some other tools (most notably, 
U{buildbot<http://buildbot.net/>}) use this same method for reliably killing
processes, and thus conflicts with QuickRelease.

You can use QuickRelease under such systems by defining 
C{DISABLE_KILLABLEPROCESS_PY} in the environment.
"""

try:
    if bool(ConfigSpec.GetConstant('DISABLE_KILLABLEPROCESS_PY')):
        gUsingKillableProcess = False
except ConfigSpecError:
    pass

if gUsingKillableProcess:
    from quickrelease.killableprocess import Popen
else:
    from subprocess import Popen

PIPE_STDOUT = 1
PIPE_STDERR = 2

# We used to use os.linesep here, but it turns out that doesn't work on
# MSYS, where the Win32 tools output os.linesep, but the ported Unix tools 
# only output \n
REMOVE_LINE_ENDING = lambda x: re.sub('\r?\n?$', '', x)

# Threading implementation inspired by: http://stackoverflow.com/a/4896288
class _OutputQueueReader(Thread):
    def __init__(self, queue=None,
                       monitoredStreams=2,
                       logHandleDescriptors=(),
                       storeBigOutput=True,
                       printOutput=False, bufferedOutput=False):
        Thread.__init__(self)
        self.printOutput = printOutput
        self.bufferedOutput = bufferedOutput

        self._storeBigOutput = storeBigOutput
        self._monitoredStreams = monitoredStreams
        self._queue = queue
        self._logHandleDescriptors = logHandleDescriptors
        self._collectedOutput = {}

        self._collectedOutput[PIPE_STDOUT] = []
        self._collectedOutput[PIPE_STDERR] = []

        self._bigOutputFileHandle = None
        self._maxInMemLines = ConfigSpec.GetConstant(
         'RUN_SHELL_COMMAND_IN_MEM_LINES')

    def _GetBackedByFile(self): return self._bigOutputFileHandle is not None
    backedByFile = property(_GetBackedByFile)

    def run(self):
        try:
            streamDeathCount = 0

            while True:
                try:
                    lineDesc = self._queue.get()
                except Empty:
                    continue

                if lineDesc.content is None:
                    #print "line content on type %s is none" % (lineObj['type'])

                    # Flush the last of our output to any big output files in
                    # use.
                    self._FlushBigOutputToFile(lineDesc.type)

                    self._queue.task_done()
                    streamDeathCount += 1
                    assert (streamDeathCount >= 0 and streamDeathCount <= 
                     self._monitoredStreams), ("Stream monitor/death count "
                     "mismatch!")
                    if streamDeathCount == self._monitoredStreams:
                        break
                    else:
                        continue
    
                if self.printOutput:
                    try:
                        print REMOVE_LINE_ENDING(lineDesc.content)
                        if not self.bufferedOutput:
                            sys.stdout.flush()
                    except IOError, ex:
                        if ex.errno != errno.EPIPE:
                            raise ex
    
                for h in self._logHandleDescriptors:
                    if h.handle is not None and h.type == lineDesc.type:
                        h.handle.write(lineDesc.content)
    
                self._collectedOutput[lineDesc.type].append(lineDesc)
    
                if (len(self._collectedOutput[lineDesc.type]) >
                 self._maxInMemLines):
                    self._FlushBigOutputToFile(lineDesc.type)
    
                self._queue.task_done()
    
            for h in self._logHandleDescriptors:
                if h.handle is not None:
                    h.handle.flush()

        finally:
            if self.backedByFile:
                self._bigOutputFileHandle.close()

    def __del__(self):
        if self.backedByFile:
            try:
                self._bigOutputFileHandle.close()
                os.unlink(self._bigOutputFileHandle.name)
            except OSError:
                pass

    # To simplify the logic in the caller, this function MAY BE A NO-OP
    def _FlushBigOutputToFile(self, outputType):
        if self._storeBigOutput:
            if self._bigOutputFileHandle is None:
                self._bigOutputFileHandle = NamedTemporaryFile(delete=False)

            # Make sure someone else didn't accidentally close() the handle
            assert not self._bigOutputFileHandle.closed, ("bigOutputFileHandle "
             "is closed?")
            pickle.dump( { 'type': outputType,
                           'contents': self._collectedOutput[outputType]
            }, self._bigOutputFileHandle)
            #self._bigOutputFileHandle.flush()

            self._collectedOutput[outputType] = []

    def GetOutput(self, outputType=PIPE_STDOUT, raw=False):
        if not self._collectedOutput.has_key(outputType):
            raise ValueError("No output type %s processed by this output "
             "monitor" % (outputType))

        if self._bigOutputFileHandle is not None:
            # At this point, the handle should always be closed.
            assert self._bigOutputFileHandle.closed, ("bigOutputFileHandle "
             "still open?")
            ## print >> sys.stderr, "In GetOutput(): %d" % (time.time())
            handle = open(self._bigOutputFileHandle.name, 'rb')
            ret = []
            if raw:
                ret = ''

            try:
                while True:
                    try:
                        data = pickle.load(handle)
                    except EOFError:
                        break

                    if data['type'] == outputType:
                        if raw:
                            ret += ''.join(list(x.content for x in 
                             data['contents']))

                        else:
                            ret += list(REMOVE_LINE_ENDING(x.content) for x in
                             data['contents'])
            finally:
                handle.close()

            ## print >> sys.stderr, "Leaving GetOutput(): %d" % (time.time())
            return ret

        else:
            if raw:
                return ''.join(list(x.content for x in
                 self._collectedOutput[outputType]))
            else:
                return list(REMOVE_LINE_ENDING(x.content) for x in
                 self._collectedOutput[outputType])

class RunShellCommandError(ReleaseFrameworkError):
    """
    An exception class representing various errors that can occur while
    setting up, executing, or cleaning up an instance of L{RunShellCommand}.

    The default implementation attempts to provide a detailed explanation to 
    the user regarding the failure.
    """

    STDERR_DISPLAY_CONTEXT = 5

    def __init__(self, rscObj):
        explanation = "RunShellCommand(): "
        if rscObj.processtimedout:
            explanation += "command %s timed out" % (rscObj)
        elif rscObj.processkilled:
            explanation += "command %s killed; exit value: %d" % (rscObj,
             rscObj.returncode)
        else:
            explanation += ("command %s failed; exit value: %d, partial "
             "stderr: %s" % (rscObj, rscObj.returncode, ' '.join(rscObj.stderr[
             -self.STDERR_DISPLAY_CONTEXT:])))

        ReleaseFrameworkError.__init__(self, explanation, rscObj)

    def _GetCommandObj(self): return self.details

    command = property(_GetCommandObj)
    """The full original L{RunShellCommand} object which generated the error.
    @type:  L{RunShellCommand} instance
    """

RUN_SHELL_COMMAND_DEFAULT_ARGS = { 
 'appendLogfile': True,
 'appendErrorLogfile': True,
 'autoRun': True,
 'command': (),
 'combineOutput': True,
 'errorLogfile': None,
 'logfile': None,
 'printOutput': None,
 'timeout': (ConfigSpec.GetConstant('RUN_SHELL_COMMAND_DEFAULT_TIMEOUT') *
     ConfigSpec.GetConstant('RUN_SHELL_COMMAND_TIMEOUT_FACTOR')),
 'raiseErrors': True,
 'verbose': False,
 'workdir': None,
 'input': None,
 'storeBigOutput': True,
}

# RunShellCommand may seem a bit weird, but that's because it was originally a
# function, and later converted to a class.

# TODO: output (both stdout/stderr together), rawstdout, and rawstderr
# properties; change "partial stderr" message in RunShellCommandError to use
# new "output" property

class RunShellCommand(object):
    """
    A class representing an externally-executed command, as well as various
    properties of that command, its input and output, and its final state
    (success/error/etc.)
    """
    def __init__(self, *args, **kwargs):
        """
        Create a RunShellCommand object to execute an external command.

        The constructor can be called in one of two ways:
            1. If an array is specified, all the default options below are 
            accepted and the command is run, with each argument of the array 
            considered arguments. (See U{the Python documentation<http://docs.python.org/library/subprocess.html#converting-argument-sequence>} for further rules regarding argument tolkenization on Windows.)
            2. Various keyword-style arguments can be passed, as documented
            below.

        @param command: The external command to run. First element is the
        external program name; subsequent elements are command arguments.
        @type  command: C{list}

        @param appendLogfile: Should the logfile specified for C{STDOUT} output
        already exist, should it be appended to or overwritten.
        Default: appended to (C{True})
        @type  appendLogfile: C{bool}

        @param appendErrorLogfile: Should the logfile specified for STDERR
        output already exist, should it be appended to or overwritten.
        Default: appended to (C{True})
        @type  appendErrorLogfile: C{bool}

        @param autoRun: Should the command be automatically launched or 
        should the caller manage when the program is launched by calling the 
        L{Run<quickrelease.command.RunShellCommand.Run>} method.
        Default: run automatically (C{True})
        @type autoRun: C{bool}

        @param combineOutput: Should C{STDOUT} and C{STDERR} output be combined.
        Default: yes, combine them (C{True})
        @type combineOutput: C{bool}

        @param logFile: Path to a logfile to use for C{STDOUT} output (C{STDERR}
        as well if C{combineOutput} is true).
        @type logFile: C{str}

        @param errorLogfile: Path to a logfile to use for C{STDERR} output 
        (ignored if C{combineOutput} is true).
        @type errorLogfile: C{str}

        @param printOutput: Print C{STDOUT} and C{STDERR} output to the screen.
        Default: if unset, output will take the value of the C{verbose}
        parameter
        @type  printOutput: C{bool}

        @param timeout: Timeout, in seconds, to wait for the process to complete
        Default: The 
        C{RUN_SHELL_COMMAND_DEFAULT_TIMEOUT} in L{QUICKRELEASE_CONSTANTS<quickrelease.constants.QUICKRELEASE_CONSTANTS>}
        controls this default value; since it is a ConfigSpec constant, it may 
        be modified from the environment.
        @type timeout: C{int}

        @param raiseErrors: If the 
        L{RunShellCommand<quickrelease.command.RunShellCommand>} class 
        encounters any errors, including execution failure of the underlying 
        program, should it automatically raise a 
        L{RunShellCommandError<quickrelease.command.RunShellCommandError>} or 
        let the user query the state of the shell command after the command 
        has completed.
        Default: raise the error (C{True})
        @type raiseErrors: C{bool}

        @param verbose: Print to the screen more verbose information about 
        when the program is being executed, in what working directory, and 
        whether it completed successfully.
        Also, if the C{printOutput} parameter is not specified, this argument 
        will set it.
        Default: be less verbose (C{False})
        @type verbose: C{bool}

        @param workdir: The working directory to C{chdir()} to before executing
        the program.
        Default: the current working directory.
        @type workdir: C{str}

        @param input: A file name or input stream to provide to the program as 
        C{STDIN}. If a file name (C{str}) is provided, it will be opened and 
        closed. An open input stream may also be provided.
        Default: No input stream is provided (C{None}); C{STDIN} is closed 
        when the command is executed.
        @type input: C{str} or C{file}

        @param storeBigOutput: Store output from programs over a set amount
        in a temporary file, instead of memory. This is useful for long-running
        build processes which generate a lot of output that you don't want to
        waste memory in the Python process storing.
        Default: store large output in temporary files (C{True})
        @type storeBigOutput: C{bool}

        @raise ValueError: when invalid argument values or initialization 
        formats (keyword vs. singular array) are mixed, a ValueError will be 
        raised.

        @raise RunShellCommandError: if C{autoRun} is specified, and the 
        command fails for some reason, a 
        L{RunShellCommandError<quickrelease.command.RunShellCommandError>} 
        will be raised.
        """

        object.__init__(self)

        if len(args) > 0:
             if len(kwargs.keys()) > 0:
                 raise ValueError("RunShellCommand(): Can't mix initialization "
                  "styles.")

             kwargs['command'] = args

        for arg in RUN_SHELL_COMMAND_DEFAULT_ARGS.keys():
            argValue = RUN_SHELL_COMMAND_DEFAULT_ARGS[arg]
            if kwargs.has_key(arg):
                argValue = kwargs[arg]

            setattr(self, "_" + arg, argValue)

        if type(self._command) not in (list, tuple):
            raise ValueError("RunShellCommand: command must be list/tuple.")
        elif len(self._command) <= 0:
            raise ValueError("RunShellCommand: Empty command.")

        self._processWasKilled = False
        self._processTimedOut = False
        self._startTime = None
        self._endTime = None
        self._returncode = None

        self._stdout = None
        self._rawstdout = None
        self._stderr = None
        self._outputMonitor = None
        self._stdin = None

        if self._input is not None:
            if type(self._input) is str:
                try:
                    self._stdin = open(self._input, 'r')
                except IOError, ex:
                    if ex.errno == errno.ENOENT:
                        raise ValueError("Invalid input stream file: %s" %
                         (self._input))
                    else:
                        raise ex
            else:
                self._stdin = self._input

        # This makes it so we can pass int, longs, and other types to our
        # RunShellCommand that are easily convertable to strings, but which 
        # Popen() will barf on if they're not strings.

        self._execArray = []

        for ndx in range(len(self._command)):
            listNdx = None
            try:
                _CheckRunShellCommandArg(type(self._command[ndx]))
                commandPart = None

                if type(self._command[ndx]) is list:
                    for lstNdx in range(len(self._command[ndx])):
                        _CheckRunShellCommandArg(type(
                         self._command[ndx][lstNdx]))
                        commandPart = str(self._command[ndx][lstNdx])
                else:
                    commandPart = str(self._command[ndx])

                if self.DEFAULT__STR__SEPARATOR in commandPart:
                    self.__str__separator = '|'

                self._execArray.append(commandPart)

            except TypeError, ex:
                errorStr = str(ex) + ": index %s" % (ndx)

                if listNdx is not None:
                    errorStr += ", sub index: %s" % (listNdx)

                raise ValueError(errorStr)

        if self._workdir is None:
            self._workdir = os.getcwd()

        if not os.path.isdir(self.workdir):
            raise ReleaseFrameworkError("RunShellCommand(): Invalid working "
             "directory: %s" % (self.workdir))

        if self._printOutput is None:
            self._printOutput = self._verbose

        try:
            if self._timeout is not None:
                self._timeout = int(self._timeout)
        except ValueError:
            raise ValueError("RunShellCommand(): Invalid timeout value '%s'"
             % self.timeout)

        if self._autoRun:
            self.Run()

    def _GetCommand(self): return self._command
    def _GetStdout(self): return self._GetOutputFromMonitor(PIPE_STDOUT)
    def _GetRawStdout(self): return self._GetOutputFromMonitor(PIPE_STDOUT,
     True)
    def _GetStderr(self): return self._GetOutputFromMonitor(PIPE_STDERR)
    def _GetRawStderr(self): return self._GetOutputFromMonitor(PIPE_STDERR,
     True)
    def _GetStartTime(self): return self._startTime
    def _GetEndTime(self): return self._endTime
    def _GetReturnCode(self): return self._returncode
    def _GetProcessKilled(self): return self._processWasKilled
    def _GetProcessTimedOut(self): return self._processTimedOut
    def _GetWorkDir(self): return self._workdir
    def _GetTimeout(self): return self._timeout

    def _GetOutputFromMonitor(self, outputType, raw=False):
        if self._outputMonitor is None:
            return None
        return self._outputMonitor.GetOutput(outputType, raw)

    def _GetOutputBackedByFile(self): 
        if self._outputMonitor is None:
            return False
        return self._outputMonitor.backedByFile

    def _GetRunningTime(self):
        if self._startTime is None or self._endTime is None:
            return None
        return self._endTime - self._startTime

    command = property(_GetCommand)
    """The external command to execute. Read-only.
    @type: C{list}"""

    stdout = property(_GetStdout)
    """A list of the C{STDOUT} stream from the external command with 
    line-endings removed. Read-only.
    @type: C{list}"""

    rawstdout = property(_GetRawStdout)
    """A string blob of the C{STDOUT} stream without any modification.
    Read-only.
    @type: C{str}"""

    stderr = property(_GetStderr)
    """A list of the C{STDERR} stream from the external command with 
    line-endings removed. Read-only.
    @type: C{list}"""

    runningtime = property(_GetRunningTime)
    """The running time of the command. C{None} if it hasn't been started yet.
    Read-only.
    @type: C{int} or C{None}"""

    starttime = property(_GetStartTime)
    """The epoch time when the command was started. C{None} if it hasn't been 
    started yet. Read-only.
    @type: C{int} or C{None}"""

    endtime = property(_GetEndTime)
    """The epoch time when the command completed. C{None} if it hasn't been 
    started yet. Read-only.
    @type: C{int} or C{None}"""

    returncode = property(_GetReturnCode)
    """The return value of the external command. C{None} if it hasn't been 
    started yet. Read-only.
    @type: C{int} or C{None}"""

    processkilled = property(_GetProcessKilled)
    """Whether the process was killed. Read-only.
    @type: C{bool}"""

    processtimedout = property(_GetProcessTimedOut)
    """Whether the process timeout value was exceeded. Read-only.
    @type: C{bool}"""

    workdir = property(_GetWorkDir)
    """The directory the command was executed in. Read-only.
    @type: C{str}"""

    timeout = property(_GetTimeout)
    """The timeout value the command was executed with. Read-only.
    @type: C{int}"""
    
    outputBackedByFile = property(_GetOutputBackedByFile)
    """Whether any output from this RunShellCommand object uses a file-based backing-store. Read-only.
    @type: C{bool}"""

    DEFAULT__STR__SEPARATOR = ','
    str__separator = DEFAULT__STR__SEPARATOR
    str__decorate = True

    def __str__(self):
        strRep = self.str__separator.join(self._execArray)
        if self.str__decorate:
            return "[" + strRep + "]"
        else:
            return strRep

    def __int__(self):
        return self.returncode

    def __bool__(self):
        return self.returncode == 0

    def SetStrOpts(self, separator=DEFAULT__STR__SEPARATOR, decorate=True):
        """
        Sets options for the representation of the command string for its
        __str__ method.

        @param separator: separator character to use to separate command 
        arguments; it may be useful to change this if your commands tend
        to involve a lot of the default separator. Default: "%s"
        @type  separator: C(str)

        @param decorate: Should the string be "decorated"; default: C(true) 
        @type  decorate: C(bool)
        """ % (RunShellCommand.DEFAULT__STR__SEPARATOR)

        self.str__separator = separator
        self.str__decorate = decorate 

    def Run(self):
        """
        Launch the external command specified by this 
        L{RunShellCommand<quickrelease.command.RunShellCommand>} object.

        @raise RunShellCommandError: if C{raiseErrors} was set in the 
        constructor and the external command either returns with a failure
        value or times out, a RunShellCommandError will be raised.
        """

        if self._verbose:
            timeoutStr = ""
            if self.timeout is not None and gUsingKillableProcess:
                secondsStr = "seconds"
                if self.timeout == 1:
                    secondsStr = "second"
                timeoutStr = " with timeout %d %s" % (self.timeout, secondsStr)

            print >> sys.stderr, ("RunShellCommand(): Running %s in directory "
             "%s%s." % (str(self), self.workdir, timeoutStr))

            # Make sure all the output streams are flushed before we start; this
            # really only ever seems to have caused a problem on Win32
            sys.stderr.flush()
            sys.stdout.flush()

        commandLaunched = False
        try:
            logDescs = []

            if self._logfile:
                if self._appendLogfile:
                    logHandle = open(self._logfile, 'a')
                else:
                    logHandle = open(self._logfile, 'w') 

                logDescs.append(_LogHandleDesc(logHandle, PIPE_STDOUT))

                if self._combineOutput:
                    logDescs.append(_LogHandleDesc(logHandle, PIPE_STDERR))

            if not self._combineOutput and self._errorLogfile is not None:
                if self._appendErrorLogfile:
                    errorLogHandle = open(self._errorLogfile, 'a')
                else:
                    errorLogHandle = open(self._errorLogfile, 'w')

                logDescs.append(_LogHandleDesc(errorLogHandle, PIPE_STDERR))

            outputQueue = Queue()

            stdinArg = None
            if self._input is not None:
                stdinArg = PIPE

            self._startTime = time.time()
            process = Popen(self._execArray, stdin=stdinArg, stdout=PIPE,
             stderr=PIPE, cwd=self.workdir, bufsize=0)
            commandLaunched = True

            stdinWriter = None
            if self._stdin is not None:
                #print >> sys.stderr, "Starting stdinWriter"
                stdinWriter = Thread(target=_WriteInput,
                 name="RunShellCommand() stdin writer",
                 args=(self._stdin, process.stdin))
                stdinWriter.start()

            stdoutReader = Thread(target=_EnqueueOutput,
             name="RunShellCommand() stdout reader",
             args=(process.stdout, outputQueue, PIPE_STDOUT))
            stderrReader = Thread(target=_EnqueueOutput,
             name="RunShellCommand() stderr reader",
             args=(process.stderr, outputQueue, PIPE_STDERR))
            self._outputMonitor = _OutputQueueReader(queue=outputQueue,
             logHandleDescriptors=logDescs, printOutput=self._printOutput)

            stdoutReader.start()
            stderrReader.start()
            self._outputMonitor.start()

            try:
                # If you're not using killable process, you theoretically have 
                # something else (buildbot) that's implementing a timeout for
                # you; so, all timeouts here are ignored... ...
                if self.timeout is not None and gUsingKillableProcess:
                    process.wait(self.timeout)
                else:
                    process.wait()

            except KeyboardInterrupt, ex:
                process.kill()
                self._processWasKilled = True
                raise ex
        except OSError, ex:
            if ex.errno == errno.ENOENT:
                raise ReleaseFrameworkError("Invalid command or working dir")
            raise ReleaseFrameworkError("OSError: %s" % str(ex), details=ex)
        #except Exception, ex:
        #    print "EX: %s" % (ex)
        #    raise ex
        finally:
            if commandLaunched:
                procEndTime = time.time()

                #print >> sys.stderr, "Joining stderrReader"
                stderrReader.join()
                #print >> sys.stderr, "Joining stdoutReader"
                stdoutReader.join()
                #print >> sys.stderr, "Joining outputMonitor"
                self._outputMonitor.join()
                #print >> sys.stderr, "Joining q"
                outputQueue.join()
                if stdinWriter is not None:
                    #print >> sys.stderr, "Joining stdinWriter"
                    stdinWriter.join()

                for h in logDescs:
                    h.handle.close()

                # Assume if the runtime was up to/beyond the timeout, that it 
                # was killed, due to timeout.
                if commandLaunched and self.runningtime >= self.timeout:
                    self._processWasKilled = True
                    self._processTimedOut = True

                #om = outputMonitor.collectedOutput[PIPE_STDOUT]
                #for i in range(om):
                #    print "STDOUT line %d (%d): %s" % (i, om[i].time,
                #     om[i].content)
                #
                #om = outputMonitor.collectedOutput[PIPE_STDERR]
                # for i in range(om):
                #     print "STDERR line %d (%d): %s" % (i, om[i].time,
                #      om[i].content)

                #self._stdout = outputMonitor.GetOutput(PIPE_STDOUT)
                #self._rawstdout = outputMonitor.GetOutput(PIPE_STDOUT,
                # raw=True)
                #self._stderr = outputMonitor.GetOutput(PIPE_STDERR)
                self._endTime = procEndTime
                self._returncode = process.returncode

                if self._input is not None and type(self._input) is str:
                    #print >> sys.stderr, "Closing stdin file."
                    self._stdin.close()

        if self._raiseErrors and self.returncode:
            raise RunShellCommandError(self)

def _CheckRunShellCommandArg(argType):
    if argType not in (str, unicode, int, float, list, long):
        raise TypeError("RunShellCommand(): unexpected argument type %s" % 
         (argType))

class _OutputLineDesc(object):
    def __init__(self, outputType=None, content=None):
        self.time = time.time()
        object.__init__(self)
        self.type = outputType
        self.content = content

class _LogHandleDesc(object):
    def __init__(self, handle, outputType=None):
        object.__init__(self)
        self.type = outputType
        self.handle = handle

def _WriteInput(inputStream, procStdinPipe):
    for line in iter(inputStream.readline, ''):
        assert line is not None, "Line was None"
        procStdinPipe.write(line)

    procStdinPipe.close()

def _EnqueueOutput(outputPipe, outputQueue, pipeType):
    for line in iter(outputPipe.readline, ''):
        assert line is not None, "Line was None"
        outputQueue.put(_OutputLineDesc(pipeType, line))

    outputPipe.close()
    outputQueue.put(_OutputLineDesc(pipeType))
