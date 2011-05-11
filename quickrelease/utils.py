
import errno
import hashlib
import os
import platform
import re
from subprocess import PIPE
import sys
from threading import Thread
import time
import types
from urllib import FancyURLopener
from Queue import Queue, Empty

from quickrelease.config import ConfigSpec, ConfigSpecError
from quickrelease.exception import ReleaseFrameworkError

gUsingKillableProcess = True

try:
   if bool(ConfigSpec.GetConstant('DISABLE_KILLABLEPROCESS_PY')):
      gUsingKillableProcess = False
except ConfigSpecError:
   pass

if gUsingKillableProcess:
   from quickrelease.killableprocess import Popen
else:
   from subprocess import Popen

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
   os.makedirs(path)

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

PIPE_STDOUT = 1
PIPE_STDERR = 2

class _OutputQueueReader(Thread):
   def __init__(self, queue=None,
                      monitoredStreams=2,
                      logHandleDescriptors=(),
                      printOutput=False, bufferedOutput=False):
      Thread.__init__(self)
      self.queue = queue
      self.printOutput = printOutput
      self.bufferedOutput = bufferedOutput
      self.logHandleDescriptors = logHandleDescriptors
      self.monitoredStreams = monitoredStreams

      self.collectedOutput = {}

      self.collectedOutput[PIPE_STDOUT] = []
      self.collectedOutput[PIPE_STDERR] = []

   def run(self):
      streamDeathCount = 0

      while True:
         try:
            lineDesc = self.queue.get()
         except Empty:
            continue

         if lineDesc.content is None:
            #print "line content on type %s is none" % (lineObj['type'])
            self.queue.task_done()
            streamDeathCount += 1
            assert (streamDeathCount >= 0 and streamDeathCount <= 
             self.monitoredStreams), "Stream monitor/death count mismatch!"
            if streamDeathCount == self.monitoredStreams:
               break
            else:
               continue

         if self.printOutput:
            # ... but don't add a newline, since it already contains one...
            print re.sub('\r?\n?$', '', lineDesc.content)
            if not self.bufferedOutput:
               sys.stdout.flush()

         for h in self.logHandleDescriptors:
            if h.handle is not None and h.type == lineDesc.type:
               h.handle.write(lineDesc.content)

         ## TODO: if collectedOutput is too big, dump to file
         self.collectedOutput[lineDesc.type].append(lineDesc)

         self.queue.task_done()

      for h in self.logHandleDescriptors:
         if h.handle is not None:
            h.handle.flush()

   def GetOutput(self, outputType=PIPE_STDOUT):
      if not self.collectedOutput.has_key(outputType):
         raise ValueError("No output type %s processed by this output monitor" %
          (outputType))

      return list(x.content for x in self.collectedOutput[outputType])

class RunShellCommandError(ReleaseFrameworkError):
   def __init__(self, rscObj):
      if rscObj.processtimedout:
         explanation = "RunShellCommand(): command %s timed out." % (rcsObj)
      elif rscObj.processkilled:
         explanation = ("RunShellCommand(): command %s killed; exit value: %d"
          % (rcsOobj, rcsObj.returncode))
      else:
         explanation = ("RunShellCommand(): command %s failed; exit value: %d, "
          "partial stderr: %s" % (rcsObj, rcsObj.returncode,
          ' '.join((re.split('[\r\n]+', rscObj.stderr()))[-5:])))

      ReleaseFrameworkError.__init__(explanation, rscObj)

   def _GetCommandObj(self): return self.details
   command = property(_GetCommandObj)

RUN_SHELL_COMMAND_DEFAULT_ARGS = { 
 'appendLogfile': True,
 'appendErrorLogfile': True,
 'autoRun': True,
 'command': (),
 'combineOutput': True,
 'errorLogfile': None,
 'logfile': None,
 'printOutput': None,
 'timeout': ConfigSpec.GetConstant('RUN_SHELL_COMMAND_DEFAULT_TIMEOUT'),
 'raiseErrors': True,
 'verbose': False,
 'workdir': None,
}

class RunShellCommand(object):
   def __init__(self, *args, **kwargs):
      object.__init__(self)

      if len(args) > 0:
          if len(kwargs.keys()) > 0:
             raise ValueError("Can't mix initialization styles.")

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
      self._stdout = None
      self._stderr = None
      self._startTime = None
      self._endTime = None
      self._returncode = None

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
                  _CheckRunShellCommandArg(type(self._command[ndx][lstNdx]))
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
   def _GetStdout(self): return self._stdout
   def _GetStderr(self): return self._stderr
   def _GetStartTime(self): return self._startTime
   def _GetEndTime(self): return self._endTime
   def _GetReturnCode(self): return self._returncode
   def _GetProcessKilled(self): return self._processWasKilled
   def _GetProcessTimedOut(self): return self._processTimedOut
   def _GetWorkDir(self): return self._workdir
   def _GetTimeout(self): return self._timeout

   def _GetRunningTime(self):
      if self._startTime is None or self._endTime is None:
         return None
      return self._endTime - self._startTime

   command = property(_GetCommand)
   stdout = property(_GetStdout)
   stderr = property(_GetStderr)
   runningtime = property(_GetRunningTime)
   starttime = property(_GetStartTime)
   endtime = property(_GetEndTime)
   returncode = property(_GetReturnCode)
   processkilled = property(_GetProcessKilled)
   processtimedout = property(_GetProcessTimedOut)
   workdir = property(_GetWorkDir)
   timeout = property(_GetTimeout)

   DEFAULT__STR__SEPARATOR = ','
   __str__separator = DEFAULT__STR__SEPARATOR
   __str__decorate = True

   def __str__(self):
      strRep = self.__str__separator.join(self._execArray)
      if self.__str__decorate:
         return "[" + strRep + "]"
      else:
         return strRep

   def SetStrOpts(self, separator=DEFAULT__STR__SEPARATOR, decorate=True):
      self.__str__separator = separator
      self.__str__decorate = decorate 

   def __int__(self):
      return self.returncode

   def Run(self):
      if self._verbose:
         timeoutStr = ""
         if self.timeout is not None and gUsingKillableProcess:
            timeoutStr = " with timeout %d seconds" % (self.timeout)

         print >> sys.stderr, ("RunShellCommand(): Running %s in directory "
          "%s%s." % (str(self), self.workdir, timeoutStr))

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
         elif self._errorLogfile is not None:
            if self._appendErrorLogfile:
               errorLogHandle = open(self._errorLogfile, 'a')
            else:
               errorLogHandle = open(self._errorLogfile, 'w')

            logDescs.append(_LogHandleDesc(errorLogHandle, PIPE_STDERR))

         outputQueue = Queue()

         self._startTime = time.time()
         process = Popen(self._execArray, stdout=PIPE, stderr=PIPE,
          cwd=self.workdir, bufsize=0)
         commandLaunched = True

         stdoutReader = Thread(target=_EnqueueOutput,
          args=(process.stdout, outputQueue, PIPE_STDOUT))
         stderrReader = Thread(target=_EnqueueOutput,
          args=(process.stderr, outputQueue, PIPE_STDERR))
         outputMonitor = _OutputQueueReader(queue=outputQueue,
          logHandleDescriptors=logDescs, printOutput=self._printOutput)

         stdoutReader.start()
         stderrReader.start()
         outputMonitor.start()

         try:
            # If you're not using killable process, you theoretically have 
            # something else (buildbot) that's implementing a timeout for you;
            # so, all timeouts here are ignored... ...
            if self.timeout is not None and gUsingKillableProcess:
               process.wait(self.timeout)
            else:
               process.wait()

         except KeyboardInterrupt:
            process.kill()
            self._processWasKilled = True
      except OSError, ex:
         if ex.errno == errno.ENOENT:
            raise ReleaseFrameworkError("Invalid command or working dir")
         raise ex
      #except Exception, ex:
      #   print "EX: %s" % (ex)
      finally:
         if commandLaunched:
            procEndTime = time.time()

            #print >> sys.stderr, "Joining stderrReader"
            stderrReader.join()
            #print >> sys.stderr, "Joining stdoutReader"
            stdoutReader.join()
            #print >> sys.stderr, "Joining outputMonitor"
            outputMonitor.join()
            #print >> sys.stderr, "Joining q"
            outputQueue.join()

            for h in logDescs:
               h.handle.close()

            # Assume if the runtime was up to/beyond the timeout, that it was 
            # killed, due to timeout.
            if commandLaunched and self.runningtime >= self.timeout:
               self._processWasKilled = True
               self._processTimedOut = True
 
            #for i in range(len(outputMonitor.collectedOutput)):
            #   print "Line %d content: %s" % (i, outputMonitor.collectedOutput[i]['content'])
            #   print "Line %d time: %s" % (i, outputMonitor.collectedOutput[i]['time'])

            self._stdout = outputMonitor.GetOutput(PIPE_STDOUT)
            self._stderr = outputMonitor.GetOutput(PIPE_STDERR)
            self._endTime = procEndTime
            self._returncode = process.returncode

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

def _EnqueueOutput(outputPipe, outputQueue, pipeType):
   for line in iter(outputPipe.readline, ''):
      assert line is not None, "Line was None"
      outputQueue.put(_OutputLineDesc(pipeType, line))

   outputPipe.close()
   outputQueue.put(_OutputLineDesc(pipeType))
