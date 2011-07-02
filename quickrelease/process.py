# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

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
INIT_PY = '__init__.py'

gProcessAndStepDefnPath = []

QUICKRELEASE_DEFINITIONS_PATH = os.getenv('QUICKRELEASE_DEFINITIONS_PATH')

if QUICKRELEASE_DEFINITIONS_PATH is not None:
    for path in QUICKRELEASE_DEFINITIONS_PATH.split(os.path.pathsep):
        absPath = os.path.abspath(path)
        gProcessAndStepDefnPath.append(absPath)
        sys.path.append(os.path.dirname(absPath))

if os.getenv('QUICKRELEASE_OVERRIDE_DEFAULT_DEFINITIONS') is None:
    gProcessAndStepDefnPath.append(os.path.dirname(os.path.abspath(__file__)))

for path in gProcessAndStepDefnPath:
    if not os.path.isfile(os.path.join(path, INIT_PY)):
        raise RuntimeWarning("The specified directory %s in "
         "QUICKRELEASE_DEFINITIONS_PATH is missing an __init__.py file; "
         "please add one." % (path))
    for d in (QUICKRELEASE_PROCESSES_DIR, QUICKRELEASE_STEPS_DIR):
        checkDir = os.path.join(path, d)
        if not os.path.isdir(checkDir):
            raise RuntimeWarning("The specified directory %s in "
             "QUICKRELEASE_DEFINITIONS_PATH is missing the %s directory; "
             "bailing." % (path, d))
        elif not os.path.isfile(os.path.join(checkDir, INIT_PY)):
            raise RuntimeWarning("The specified directory %s in "
             "QUICKRELEASE_DEFINITIONS_PATH is missing an __init__.py file; "
             "please add one." % (path, d))

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
                assert issubclass(s, Step), ("Process steps "
                 "must be derived from the Step class (step %s is not)" %
                 (s.__name__))
                self.stepNames.append(s.__name__)

        return tuple(self.stepNames)

    def GetProcessSteps(self):
        steps = []
        for s in self.steps:
            stepInstance = s(process=self)
            assert isinstance(stepInstance, Step), ("Process steps must be "
             "derived from the Step class (step %s is not)" % (
             str(stepInstance)))

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

def GetAvailableProcesses():
    if Process._gAvailableProcessList is None:
        Process._gAvailableProcessList = []

        for path in gProcessAndStepDefnPath:
            #print "Checking process/step definition path: %s" % (path)
            cwd = os.getcwd()
            processModuleFiles = []

            try:
                os.chdir(os.path.join(path, QUICKRELEASE_PROCESSES_DIR))
                processModuleFiles = glob('*.py')
            finally:
                os.chdir(cwd)

            processModuleFiles.remove('__init__.py')

            if len(processModuleFiles) <= 0:
                continue

            filenameToModuleName = lambda f: '.'.join([os.path.basename(path),
             QUICKRELEASE_PROCESSES_DIR, os.path.splitext(f)[0]])
            moduleFiles = map(filenameToModuleName, processModuleFiles)
            processList = []

            for f in moduleFiles:
                #print "Importing process module: " + f

                try:
                    mod = ImportModule(f)
                except NameError, ex:
                    nameErrorRegex = "name '(\w+)' is not defined"
                    nameErrorMatch = re.match(nameErrorRegex, str(ex))
                    if nameErrorMatch:
                        raise ReleaseFrameworkError("Step %s is specified as "
                         "part of process %s, but is not defined" %
                         (nameErrorMatch.group(1), f.split('.')[-1]))
                    else:
                        raise ex
                except ImportError, ex:
                    importErrorRegex = "No module named (.+)"
                    importErrorMatch = re.match(importErrorRegex, str(ex))
                    if importErrorMatch:
                        raise ReleaseFrameworkError("Process %s is trying to "
                         "import undefined module %s" % (f,
                         importErrorMatch.group(1)))
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
    
                    raise ReleaseFrameworkError("Syntax error in %s "
                     "definition %s%s, line %d:\n%s" % (definitionType,
                     os.path.basename(ex.filename), processDetailStr, ex.lineno,
                     ex.text))
    
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if inspect.isclass(obj):
                        if obj.__module__ == f and issubclass(obj, Process):
                            #print "Process class found: %s" % (obj.__name__)
                            processList.append(obj)
    
            Process._gAvailableProcessList += processList

        Process._gAvailableProcessList = tuple(Process._gAvailableProcessList)
    
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
