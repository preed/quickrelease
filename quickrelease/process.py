
from glob import glob
import inspect
import os
import re
import sys

from quickrelease.step import Step
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.utils import GetActivePartnerList, ImportModule

QUICKRELEASE_PROCESSES_DIR = 'processes'
QUICKRELEASE_STEPS_DIR = 'steps'

QUICKRELEASE_MODULES_DIR = os.getenv('QUICKRELEASE_MODULES_DIR')
if QUICKRELEASE_MODULES_DIR is None:
   #QUICKRELEASE_MODULES_DIR = os.path.dirname(os.path.abspath(os.path.join(os.path.abspath(__file__), '..')))
   QUICKRELEASE_MODULES_DIR = os.path.dirname(os.path.abspath(__file__))
#else:
#   print "Overriding default quickrelease modules dir: " + QUICKRELEASE_MODULES_DIR

if not os.path.isabs(QUICKRELEASE_MODULES_DIR):
   QUICKRELEASE_MODULES_DIR = os.path.abspath(QUICKRELEASE_MODULES_DIR)

for d in (QUICKRELEASE_PROCESSES_DIR, QUICKRELEASE_STEPS_DIR):
   checkDir = os.path.join(QUICKRELEASE_MODULES_DIR, d)
   if not os.path.isdir(checkDir):
      raise RuntimeWarning("The specified QUICKRELEASE_MODULES_DIR %s is "
       "missing the '%s' directory; bailing." % (QUICKRELEASE_MODULES_DIR, d))

#print "Adding %s" % (QUICKRELEASE_MODULES_DIR)
#sys.path.append(QUICKRELEASE_MODULES_DIR)

class Process(object):
   RECOGNIZED_CONSTRUCTOR_ARGS = ('config', 'executeSteps', 'verifySteps',
    'ignoreErrors')

   _gAvailableProcessList = None

   def __init__(self, *args, **kwargs):
      object.__init__(self)

      # initialize these if the subclass didn't
      if 'stepNames' not in dir(self):
         self.stepNames = None
      if 'steps' not in dir(self):
         self.steps = ()

      # default attributes
      self.config = None
      self.executeSteps = True
      self.verifySteps = True
      self.ignoreErrors = False
      self.enableNotifications = False

      for arg in Process.RECOGNIZED_CONSTRUCTOR_ARGS:
         if kwargs.has_key(arg):
            setattr(self, arg, kwargs[arg])

      assert self.executeSteps is True or self.verifySteps is True, (
       "Neither executeSteps, nor verifySteps was requested; NOTHING TO DO!")

   # The default string representation for process steps is the name
   # of the class... but feel free to override.
   def __str__(self):
      return self.__class__.__name__

   def __cmp__(self, other):
      return cmp(str(self), str(other))

   def GetConfig(self):
      return self.config

   def GetProcessStepNames(self):
      if self.stepNames is None:
         self.stepNames = []

         for s in self.steps:
            assert issubclass(s.__class__, Step.__class__), ("Process steps "
             "must be derived from the Step class (step %s is not)" %
             (s.__name__))
            self.stepNames.append(s.__name__)

      return tuple(self.stepNames)

   def GetProcessSteps(self):
      steps = []
      for s in self.steps:
         stepInstance = s(process=self)
         assert isinstance(stepInstance, Step), ("Process steps must be "
          "derived from the Step class (step %s is not)" % (str(stepInstance)))
         steps.append(stepInstance)

      return tuple(steps)

   def RunProcess(self, startingStepName=None, stepsToRun=None):
      processSteps = self.GetProcessSteps()

      startNdx = 0

      if startingStepName is not None:
         foundStep = False
         for i in range(len(processSteps)):
            if str(processSteps[i]) == startingStepName:
               startNdx = i
               foundStep = True
               break

         if not foundStep:
            raise ValueError("Invalid step name '%s' given for process %s" %
             (startingStepName, str(self)))

      if stepsToRun is None:
         endNdx = len(processSteps)
      else:
         endNdx = startNdx + stepsToRun

      for step in processSteps[startNdx:endNdx]:
         os.chdir(self.GetConfig().GetRootDir())
         self.GetConfig().SetSection(self.GetConfig().GetDefaultSection())
         self.PerformStep(step)

   def PerformStep(self, stepObj):
      rootDir = self.GetConfig().GetRootDir()

      partnerList = [ None ]
      if stepObj.IsPartnerStep():
         partnerList = GetActivePartnerList(self.GetConfig())

      try:
         if self.executeSteps:
            for p in partnerList:
               os.chdir(rootDir)
               stepObj.SetActivePartner(p)
               stepObj.Preflight()
               os.chdir(rootDir)
               stepObj.SetActivePartner(p)
               stepObj.Execute()

         if self.verifySteps:
            for p in partnerList:
               os.chdir(rootDir)
               stepObj.SetActivePartner(p)
               stepObj.Verify()

         if self.enableNotifications:
            for p in partnerList:
               os.chdir(rootDir)
               stepObj.SetActivePartner(p)
               stepObj.Notify()

      except ReleaseFrameworkError, ex:
         if self.ignoreErrors:
            # warn?
            pass
         else:
            raise ex

# investigate load_module()/find_module()
def GetAvailableProcesses():
   if Process._gAvailableProcessList is None:
      cwd = os.getcwd()
      processModuleFiles = []

      try:
         os.chdir(os.path.join(QUICKRELEASE_MODULES_DIR, 
          QUICKRELEASE_PROCESSES_DIR))
         processModuleFiles = glob('*.py')
      finally:
         os.chdir(cwd)

      processModuleFiles.remove('__init__.py')

      #print "PYTHONPATH: " + ':'.join(sys.path)

      if len(processModuleFiles) <= 0:
         return ()

      filenameToModuleName = lambda f: '.'.join([os.path.basename(QUICKRELEASE_MODULES_DIR),
       QUICKRELEASE_PROCESSES_DIR, os.path.splitext(f)[0]])
      moduleFiles = map(filenameToModuleName, processModuleFiles)
      processList = []

      for f in moduleFiles:
         #print "Importing: " + f

         try:
            mod = ImportModule(f)
         except NameError, ex:
            importErrorRegex = "name '(\w+)' is not defined"
            importErrorMatch = re.match(importErrorRegex, str(ex))
            if importErrorMatch:
               raise ReleaseFrameworkError("Step %s is specified as part of "
                "process %s, but is not defined" % (importErrorMatch.group(1), 
                f.split('.')[-1]))
            else:
               raise ex
         except SyntaxError, ex:
            definitionType = None
            parentDir = os.path.basename(os.path.dirname(ex.filename))
            if parentDir == QUICKRELEASE_PROCESSES_DIR:
               definitionType = "process"
               processDetailStr = ""
            elif parentDir == QUICKRELEASE_STEPS_DIR:
               definitionType = "step"
               processDetailStr = " (part of process %s)" % (
                f.split('.')[-1])

            raise ReleaseFrameworkError("Syntax error in %s definition %s%s, "
             "line %d:\n%s" % (definitionType, os.path.basename(ex.filename),
             processDetailStr, ex.lineno, ex.text))

         for attr in dir(mod):
            obj = getattr(mod, attr)
            if inspect.isclass(obj):
               if obj.__module__ == f and issubclass(obj, Process):
                  #print "Class found: %s" % (obj.__name__)
                  processList.append(obj)

      Process._gAvailableProcessList = tuple(processList)

   return Process._gAvailableProcessList

def GetAvailableProcessesList():
   ret = []

   for proc in GetAvailableProcesses():
      ret.append(proc.__name__)

   ret.sort()
   return tuple(ret)

def GetProcessByName(procName=None, config=None, *args, **kwargs):
   if procName is None:
      return None

   for proc in GetAvailableProcesses():
      if proc.__name__ == procName:
         kwargs['config'] = config
         return proc(*args, **kwargs)

   return None
