
from glob import glob
import inspect
import os
import re

from quickrelease.step import Step
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.utils import GetActivePartnerList

PROCESS_MODULES_HOME = ('quickrelease', 'processes')
PROCESS_MODULES_PYTHON_PATH = '.'.join(PROCESS_MODULES_HOME)
PROCESS_MODULES_PATH = None

if PROCESS_MODULES_PATH is None:
   PROCESS_MODULES_PATH = ''
   for _p in PROCESS_MODULES_HOME:
      PROCESS_MODULES_PATH = os.path.join(PROCESS_MODULES_PATH, _p)

#print "path is: " + PROCESS_MODULES_PATH
#print "pypath is: " + PROCESS_MODULES_PYTHON_PATH

class Process(object):
   RECOGNIZED_CONSTRUCTOR_ARGS = ('config', 'executeSteps', 'verifySteps',
    'ignoreErrors')

   AVAILABLE_PROCESS_LIST = None

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
   @staticmethod
   def GetAvailableProcesses():
      if Process.AVAILABLE_PROCESS_LIST is None:
         cwd = os.getcwd()
         # XXX TODO: search PYTHON_PATH
         os.chdir(PROCESS_MODULES_PATH)
         pyFiles = glob('*.py')
         os.chdir(cwd)
         processModuleFiles = []
         for f in pyFiles:
            if f != '__init__.py':
               processModuleFiles.append(f)

         filenameToModuleName = lambda f: PROCESS_MODULES_PYTHON_PATH + '.' + os.path.splitext(f)[0]
         moduleFiles = map(filenameToModuleName, processModuleFiles)
         #for f in moduleFiles:
         #   print "Found module files: " + f

         try:
            processModules = map(__import__, moduleFiles)
         except NameError, ex:
            importErrorRegex = "name '(\w+)' is not defined"
            importErrorMatch = re.match(importErrorRegex, str(ex))
            if importErrorMatch:
               raise ReleaseFrameworkError("%s is specified in a Process, "
                "but not defined as a Step" % (importErrorMatch.group(1)))
            else:
               raise ex

         if len(processModules) <= 0:
            return ()

         processList = []

         #for i in processModules:
         #   print "pm is %s" % (str(i))
         for attr in dir(processModules[0].processes):
            possibleModule = getattr(processModules[0].processes, attr)
            if inspect.ismodule(possibleModule):
               for name in dir(possibleModule):
                  obj = getattr(possibleModule, name)
                  if inspect.isclass(obj):
                     # only add modules in the right path
                     # TODO: actually, do this as an isinstance check
                     if ('.'.join(obj.__module__.split('.')[:-1]) ==
                      PROCESS_MODULES_PYTHON_PATH):
                        #print "Class found: %s, %s" % (obj.__name__, name)
                        processList.append(obj)

         
         Process.AVAILABLE_PROCESS_LIST = tuple(processList)

      return Process.AVAILABLE_PROCESS_LIST

   @staticmethod
   def GetAvailableProcessesList():
      ret = []

      for proc in Process.GetAvailableProcesses():
         ret.append(proc.__name__)

      return tuple(ret)

   @staticmethod
   def GetProcessByName(procName=None, config=None, *args, **kwargs):
      if procName is None:
         return None

      for proc in Process.GetAvailableProcesses():
         if proc.__name__ == procName:
            kwargs['config'] = config
            return proc(*args, **kwargs)

      return None
