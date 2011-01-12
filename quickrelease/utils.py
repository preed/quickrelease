
import hashlib
import os
import re
from threading import Thread
import types
from urllib import FancyURLopener

from quickrelease.config import ConfigSpec

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
   assert os.path.isfile(path), ("GetSHA1FileHash(): path is not a file: %s" %
    (path))
   sha1 = hashlib.sha1()
   f = open(path, 'rb')
   sha1.update(f.read())
   f.close()
   return sha1.hexdigest()

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

def RunShellCommand(command=(),
                    timeout=ConfigSpec.GetConstant(
                     'RUN_SHELL_COMMAND_DEFAULT_TIMEOUT'),
                    dir=None,
                    logfile=None, appendLogfile=True,
                    errorLogfile=None, appendErrorLogfile=True,
                    combineOutput=True,
                    printOutput=False, background=False,
                    verbose=False,
                    raiseErrors=True):

   assert len(command) > 0, "No empty commands"
   assert background is False, "Background not implemented yet"

   processWasKilled = False
   processTimedOut = False

   # This makes it so we can pass int, longs, and other types to our
   # RunShellCommand that are easily convertable to strings, but which Popen()
   # will barf on if they're not strings.
   #
   # There are certain python types that have interested effects if you call
   # str() on them, so we don't handle all Python types.
   #
   # TODO: handle array types correctly; that would be easy to do.
   # Also, are we doing the right thing for StringTypes?

   execArray = []
   for ndx in range(0, len(command)):
      argType = type(command[ndx])
      if (argType not in (types.IntType, types.FloatType, types.ListType,
                          types.LongType, types.StringType, types.StringTypes)):
         raise TypeError, ("RunShellCommand(): unexpected argument type %s" %
          (argType))

      execArray.append(str(command[ndx]))

   commandStr = ' '.join(execArray)

   if verbose or os.getenv('SB_VERBOSE') != None:
      if dir != None:
         print >> sys.stderr, ('Running command: %s in directory %s with '
          ' timeout %ss' % (commandStr, dir, timeout))
      else:
         print >> sys.stderr, ('Running command: %s with timeout %ss' % 
          (commandStr, timeout))

   if os.getenv('SB_SUPER_VERBOSE') != None:
      printOutput = True

   logHandle = None
   if logfile:
      if appendLogfile:
         logHandle = open(logfile, 'a')
      else:
         logHandle = open(logfile, 'w') 

   if combineOutput:
      errorLogHandle = logHandle
   elif errorLogfile is not None:
      if appendErrorLogfile:
         errorLogHandle = open(errorLogfile, 'a')
      else:
         errorLogHandle = open(errorLogfile, 'w')
   else:
      errorLogHandle = None

   procStartTime = int(time.time())
   process = Popen(execArray, stdout=PIPE, stderr=PIPE, cwd=dir)

   stdoutReader = NonBlockingPipeReader(pipe=process.stdout,
                                        printOutput=printOutput,
                                        logHandle=logHandle)

   stderrReader = NonBlockingPipeReader(pipe=process.stderr,
                                        printOutput=printOutput,
                                        logHandle=errorLogHandle)

   stdoutReader.start()
   stderrReader.start()

   try:
      # If you're not using killable process, you theoretically have something
      # else (buildbot) that's implementing a timeout for you; so, all
      # timeouts here are ignored... ...
      if gUsingKillableProcess:
         process.wait(timeout)
      else:
         process.wait()

   except KeyboardInterrupt:
      process.kill()
      processWasKilled = True

   procEndTime = int(time.time())

   stderrReader.join()
   stdoutReader.join()

   if logfile:
      logHandle.close()

   if errorLogfile and not combineOutput:
      errorLogHandle.close()

   procRunTime = procEndTime - procStartTime

   # Assume if the runtime was up to/beyond the timeout, that it was killed,
   # due to timeout.
   if procRunTime >= timeout:
      processWasKilled = True
      processTimedOut = True

   ret = {}

   ret['command'] = execArray
   ret['stdout'] = "".join(stdoutReader.GetOutput())
   ret['stderr'] = "".join(stderrReader.GetOutput())
   ret['startTime'] = procStartTime
   ret['endTime'] = procEndTime
   ret['runTime'] = procRunTime
   ret['timeout'] = timeout
   ret['processWasKilled'] = processWasKilled
   ret['processTimedOut'] = processTimedOut
   ret['exitValue'] = process.returncode

   if raiseErrors and process.returncode:
      raise RunShellCommandError(ret)

   return ret
