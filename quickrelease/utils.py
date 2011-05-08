
import hashlib
import os
import re
from subprocess import PIPE
import sys
from threading import Thread
import time
import types
from urllib import FancyURLopener

from quickrelease.config import ConfigSpec, ConfigSpecError

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
   f = open(path, 'rb')
   sha1.update(f.read())
   f.close()
   return sha1.hexdigest()

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

class NonBlockingPipeReader(Thread):
   def __init__(self, pipe=None,
                      logHandle=None, printOutput=False, bufferedOutput=False):
      Thread.__init__(self)
      self.pipe = pipe
      self.printOutput = printOutput
      self.bufferedOutput = bufferedOutput
      self.logHandle = logHandle
      self.collectedOutput = []

   def run(self):
      while True: 
         output = self.pipe.readline()

         if output == '':
            break

         if self.printOutput:
            # ... but don't add a newline, since it already contains one...
            print re.sub('\r?\n?$', '', output)
            if not self.bufferedOutput:
               sys.stdout.flush()

         if self.logHandle is not None:
            self.logHandle.write(output)

         self.collectedOutput.append(output)

      if self.logHandle is not None:
         self.logHandle.flush()

   def GetOutput(self):
      return self.collectedOutput

class RunShellCommandError(Exception):
   def __init__(self, returnObj):
      self.runShellCmdObj = returnObj
      Exception.__init__(self)

   def __str__(self):
      if (self.runShellCmdObj['processTimedOut']):
         return ("RunShellCommand(): command '%s' timed out; exit value: %d"
          % (self.GetCommandString(), self.GetExitValue()))
      elif (self.runShellCmdObj['processWasKilled']):
         return ("RunShellCommand(): command '%s' was killed; exit value: %d"
          % (self.GetCommandString(), self.GetExitValue()))

      return ("RunShellCommand(): command '%s' failed; exit value: %d, "
       "partial stderr: %s" % (self.GetCommandString(), self.GetExitValue(),
       ' '.join((re.split('[\r\n]+', self.GetStderr()))[-5:])))

   def GetCommand(self):
      return self.runShellCmdObj['command']

   def GetCommandString(self):
      return ' '.join(self.runShellCmdObj['command'])

   def GetExitValue(self):
      return self.runShellCmdObj['exitValue']

   def GetStdout(self):
      return self.runShellCmdObj['stdout']

   def GetStderr(self):
      return self.runShellCmdObj['stderr']

   def GetRunShellCommandObject(self):
      return self.runShellCmdObj

# https://github.com/buildbot/buildbot/blob/master/slave/buildslave/runprocess.py

# http://twistedmatrix.com/trac/browser/tags/releases/twisted-8.2.0/twisted/internet/process.py

# TODO convert this to args/kargs.

RUN_SHELL_COMMAND_DEFAULT_ARGS = { 
 'command': (),
 'timeout': ConfigSpec.GetConstant('RUN_SHELL_COMMAND_DEFAULT_TIMEOUT'),
 'workDir': None,
 'logfile': None,
 'appendLogfile': True,
 'errorLogfile': None,
 'appendErrorLogfile': True,
 'combineOutput': True,
 'printOutput': None,
 'verbose': False,
 'raiseErrors': True,
 'background': False,
 'autoRun': True
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

         setattr(self, arg, argValue)

      if type(self.command) not in (list, tuple):
         raise ValueError("RunShellCommand: command must be list/tuple.")
      elif len(self.command) <= 0:
         raise ValueError("RunShellCommand: Empty command.")

      if self.background:
         raise NotImplementedError("RunShellCommand: background not "
          "implemented yet.")

      self.processWasKilled = False
      self.processTimedOut = False
      self.stdout = None
      self.stderr = None
      self.startTime = None
      self.endTime = None
      self.returncode = None

      # This makes it so we can pass int, longs, and other types to our
      # RunShellCommand that are easily convertable to strings, but which 
      # Popen() will barf on if they're not strings.

      self.execArray = []

      for ndx in range(len(self.command)):
         listNdx = None
         try:
            self._CheckRunShellCommandArg(type(self.command[ndx]))

            if type(self.command[ndx]) is list:
               for lstNdx in range(len(self.command[ndx])):
                  self._CheckRunShellCommandArg(type(self.command[ndx][lstNdx]))
                  self.execArray.append(str(self.command[ndx][lstNdx]))
            else:
               self.execArray.append(str(self.command[ndx]))
         except TypeError, ex:
            errorStr = str(ex) + ": index %s" % (ndx)

            if listNdx is not None:
               errorStr += ", sub index: %s" % (listNdx)

            raise ValueError(errorStr)

      if self.workDir is None:
         self.workDir = os.getcwd()

      if self.printOutput is None:
         self.printOutput = self.verbose

      try:
         if self.timeout is not None:
            self.timeout = int(self.timeout)
      except ValueError:
         raise ValueError("RunShellCommand(): Invalid timeout value '%s'"
          % self.timeout)

      if self.autoRun:
         self.Run()

   def __str__(self):
      return ' '.join(self.execArray)

   def __int__(self):
      return self.returncode

   def Run(self):
      if self.verbose:
         timeoutStr = ""
         if self.timeout is not None and gUsingKillableProcess:
            timeoutStr = " with timeout %d seconds" % (self.timeout)

         print >> sys.stderr, ("RunShellCommand(): Running [%s] in directory "
          "%s%s." % (','.join(self.execArray), self.workDir, timeoutStr))

      try:
         logHandle = None
         if self.logfile:
            if self.appendLogfile:
               logHandle = open(self.logfile, 'a')
            else:
               logHandle = open(self.logfile, 'w') 

         if self.combineOutput:
            errorLogHandle = logHandle
         elif self.errorLogfile is not None:
            if self.appendErrorLogfile:
               errorLogHandle = open(self.errorLogfile, 'a')
            else:
               errorLogHandle = open(self.errorLogfile, 'w')
         else:
            errorLogHandle = None

         procStartTime = time.time()
         process = Popen(self.execArray, stdout=PIPE, stderr=PIPE,
          cwd=self.workDir)

         stdoutReader = NonBlockingPipeReader(pipe=process.stdout,
                                              printOutput=self.printOutput,
                                              logHandle=logHandle)
   
         stderrReader = NonBlockingPipeReader(pipe=process.stderr,
                                              printOutput=self.printOutput,
                                              logHandle=errorLogHandle)

         stdoutReader.start()
         stderrReader.start()

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
            processWasKilled = True

      finally:
         procEndTime = time.time()

         stderrReader.join()
         stdoutReader.join()

         if self.logfile:
            logHandle.close()

         if self.errorLogfile and not self.combineOutput:
            errorLogHandle.close()
  
         procRunTime = procEndTime - procStartTime
   
         # Assume if the runtime was up to/beyond the timeout, that it was 
         # killed, due to timeout.
         if procRunTime >= self.timeout:
            self.processWasKilled = True
            self.processTimedOut = True
   
         self.stdout = "".join(stdoutReader.GetOutput())
         self.stderr = "".join(stderrReader.GetOutput())
         self.startTime = procStartTime
         self.endTime = procEndTime
         self.returncode = process.returncode

         if self.raiseErrors and self.returncode:
            raise RunShellCommandError(self)

   #TODO:
   def GetRunningTime(self):
      pass 

   def _CheckRunShellCommandArg(self, argType):
      if argType not in (str, unicode, int, float, list, long):
         raise TypeError("RunShellCommand(): unexpected argument type %s" % 
          (argType))
