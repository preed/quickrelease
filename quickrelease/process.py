# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""
The base class for QuickRelease processes, along with utility functions to 
find, load, manipulate, and run L{Process}es.

L{Process}es are usually searched for in the C{quickrelease/processes} directory. This behavior can be modified by setting the B{C{QUICKRELEASE_DEFINITIONS_PATH}} to the name of a directory containing both a "processes" and "steps" directory.

To exclude the inclusion of any L{Process}es or L{Step<quickrelease.step.Step>}s in the standard QuickRelease directories, set B{C{QUICKRELEASE_OVERRIDE_DEFAULT_DEFINITIONS}} in the environment.
"""

from glob import glob
import inspect
import os
import re
import sys

from quickrelease.config import ConfigSpec
from quickrelease.step import Step
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.utils import ImportModule, PrintReleaseFrameworkError

QUICKRELEASE_PROCESSES_DIR = 'processes'
QUICKRELEASE_STEPS_DIR = 'steps'
INIT_PY = '__init__.py'

gProcessAndStepDefnPath = []

QUICKRELEASE_DEFINITIONS_PATH = os.getenv('QUICKRELEASE_DEFINITIONS_PATH')

if QUICKRELEASE_DEFINITIONS_PATH is not None:
    for path in QUICKRELEASE_DEFINITIONS_PATH.split(os.path.pathsep):
        if re.search('\-', path):
            raise RuntimeWarning("Dashes (-) are not allowed in the "
             "QUICKRELEASE_DEFINITIONS_PATH (currently set to: %s), due to "
             "Python's import-statement limitations." % 
             (QUICKRELEASE_DEFINITIONS_PATH))
        absPath = os.path.abspath(path)
        gProcessAndStepDefnPath.append(absPath)
        sys.path.append(os.path.dirname(absPath))

if os.getenv('QUICKRELEASE_OVERRIDE_DEFAULT_DEFINITIONS') is None:
    gProcessAndStepDefnPath.append(os.path.dirname(os.path.abspath(__file__)))

INIT_PY_MISSING_ERR_STR = ("The specified directory '%s' in "
 "QUICKRELEASE_DEFINITIONS_PATH is missing an __init__.py file; please add "
 "one.")

for path in gProcessAndStepDefnPath:
    if not os.path.isfile(os.path.join(path, INIT_PY)):
        raise RuntimeWarning(INIT_PY_MISSING_ERR_STR % (path))
    for d in (QUICKRELEASE_PROCESSES_DIR, QUICKRELEASE_STEPS_DIR):
        checkDir = os.path.join(path, d)
        if not os.path.isdir(checkDir):
            raise RuntimeWarning("The specified directory '%s' in "
             "QUICKRELEASE_DEFINITIONS_PATH is missing the '%s' directory; "
             "bailing." % (path, d))
        elif not os.path.isfile(os.path.join(checkDir, INIT_PY)):
            raise RuntimeWarning(INIT_PY_MISSING_ERR_STR % (checkDir))

class Process(object):
    """
    An object representing an automated process.

    L{Process}es consist of an ordered list of defined L{Step<quickrelease.step.Step>} objects.
    """
    RECOGNIZED_CONSTRUCTOR_ARGS = ('config', 'executeSteps', 'verifySteps',
     'ignoreErrors', 'logger')

    _gAvailableProcessList = None

    def __init__(self, *args, **kwargs):
        """
        Construct a L{Process} object.

        @param config: A configuration specification to associate with this L{Process}
        @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>}

        @param executeSteps: Run the C{Execute} method of the L{Step<quickrelease.step.Step>}s comprising this L{Process}.
        @type executeSteps: C{bool}

        @param verifySteps: Run the C{Verify} method of the L{Step<quickrelease.step.Step>}s comprising this L{Process}.
        @type verifySteps: C{bool}

        @param ignoreErrors: Print any L{ReleaseFrameworkError<quickrelease.exception.ReleaseFrameworkError>}s that occur during the running of the given L{Process}, but continue execution.
        @type ignoreErrors: C{bool}
        """

        object.__init__(self)

        # initialize these if the subclass didn't
        #if 'stepNames' not in dir(self):
        if 'steps' not in dir(self):
            self.steps = ()

        # default attributes
        self._config = None
        self._executeSteps = True
        self._verifySteps = True
        self._ignoreErrors = False
        self._everHadErrors = False
        self._enableNotifications = False
        self._stepNames = None
        self._logger = None

        for arg in Process.RECOGNIZED_CONSTRUCTOR_ARGS:
            if kwargs.has_key(arg):
                setattr(self, '_' + arg, kwargs[arg])

        assert self._executeSteps is True or self._verifySteps is True, (
         "Neither executeSteps, nor verifySteps was requested; NOTHING TO DO!")

    def __str__(self):
        """@note: The default string representation for process steps is the name of the class... but feel free to override."""
        return self.__class__.__name__

    def __cmp__(self, other):
        return cmp(str(self), str(other))

    def _GetConfig(self): return self._config
    def _GetLogger(self): return self._logger
    def _HadErrors(self): return self._everHadErrors

    def _GetProcessStepNames(self):
        if self._stepNames is None:
            self._stepNames = []

            for s in self.steps:
                assert issubclass(s, Step), ("Process steps "
                 "must be derived from the Step class (step %s is not)" %
                 (s.__name__))
                self._stepNames.append(s.__name__)

        return tuple(self._stepNames)

    def _GetProcessSteps(self):
        steps = []
        for s in self.steps:
            stepInstance = s(process=self)
            assert isinstance(stepInstance, Step), ("Process steps must be "
             "derived from the Step class (step %s is not)" % (
             str(stepInstance)))

            steps.append(stepInstance)

        return tuple(steps)

    config = property(_GetConfig)
    """The L{ConfigSpec<quickrelease.config.ConfigSpec>} associated with this process when it was created. Read-only.
    @type: L{ConfigSpec<quickrelease.config.ConfigSpec>}"""

    errored = property(_HadErrors)
    """Has this process ever encountered an error. Useful for when warnings are ignored or in L{PartnerStep<quickrelease.step.PartnerStep>}s. Read-only.
    @type: C{bool}"""

    processStepNames = property(_GetProcessStepNames)
    """Names of the L{Step<quickrelease.step.Step>}s comprising this L{Process}. Read-only.
    @type: C{list} of C{str}"""

    processSteps = property(_GetProcessSteps)
    """Instantiated L{Step<quickrelease.step.Step>} objects comprising this L{Process}. Read-only.
    @type: C{list} of L{Step<quickrelease.step.Step>}"""

    logger = property(_GetLogger)

    def Run(self, startingStepName=None, stepsToRun=None):
        """
        Run this L{Step<quickrelease.step.Step>}s comprising this process.

        @param startingStepName: The name of the step to start at. Default: the first step.
        @type startingStepName: C{str}

        @param stepsToRun: The number of steps of the process to run. Default: all.
        @type stepsToRun: C{int}

        @raise ValueError: If C{startingStepName} refers to a non-existant L{Step<quickrelease.step.Step>}.
        """

        processSteps = self.processSteps

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
            os.chdir(self.config.rootDir)
            self.config.section = ConfigSpec.DEFAULT_SECTION
            self._PerformStep(step)

    def _PerformStep(self, stepObj):
        try:
            rootDir = self.config.rootDir
            stepRunner = stepObj.runner

            os.chdir(rootDir)
            stepRunner.DoPreflight(stepObj)

            if self._executeSteps:
                os.chdir(rootDir)
                stepRunner.DoExecute(stepObj)

            if self._verifySteps:
                os.chdir(rootDir)
                stepRunner.DoVerify(stepObj)

            if self._enableNotifications:
                os.chdir(rootDir)
                stepRunner.DoNotify(stepObj)

        except ReleaseFrameworkError, ex:
            self._everHadErrors = True
            if self._ignoreErrors:
                PrintReleaseFrameworkError(ex)
            else:
                raise ex

def GetAvailableProcesses():
    """
    Search for and instantiate all of the defined QuickRelease L{Process}es.

    B{Note}: for performance reasons, a cache is used to store these L{Process}es after the first call to C{GetAvailableProcesses()}. There is currently no way to clear this cache.

    @return: A tuple of references to all defined QuickRelease L{Process}es in the provided "processes" directories.
    @rtype: C{tuple} of L{Process}

    @raise ReleaseFrameworkError: A L{ReleaseFrameworkError<quickrelease.exception.ReleaseFrameworkError>} is raised in the following circumstances:
      1. A L{Process} lists a L{Step<quickrelease.step.Step>}, but that Step is not defined.
      2. A L{Process} is attempting to import a module which has not been defined.
      3. A L{Process} is attempting to import a L{Step<quickrelease.step.Step>}, but that Step contains a syntax error.
      4. Other problems may cause L{NameError}s, L{ImportError}s, or L{SyntaxError}s to be recast into L{ReleaseFrameworkError<quickrelease.exception.ReleaseFrameworkError>}s with the original error message.
    """
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

            processModuleFiles.remove(INIT_PY)

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
                        raise ReleaseFrameworkError("%s: NameError: %s" % (f,
                         ex), ex)
                except ImportError, ex:
                    importErrorRegex = "No module named (.+)"
                    importErrorMatch = re.match(importErrorRegex, str(ex))
                    if importErrorMatch:
                        raise ReleaseFrameworkError("Process %s is trying to "
                         "import undefined module %s" % (f,
                         importErrorMatch.group(1)))
                    else:
                        raise ReleaseFrameworkError("%s: ImportError: %s" % (f,
                         ex), ex)
                except SyntaxError, ex:
                    definitionType = None
                    parentDir = os.path.basename(os.path.dirname(ex.filename))
                    processDetailStr = ""
                    if parentDir == QUICKRELEASE_PROCESSES_DIR:
                        definitionType = "process"
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
    """
    Get a list of all the available QuickRelease processes.

    @return: all available, defined L{Process}es
    @rtype: C{tuple} of L{Process}
    """
    ret = []

    for proc in GetAvailableProcesses():
        ret.append(proc.__name__)

    ret.sort()
    return tuple(ret)

def GetProcessByName(procName=None, config=None, *args, **kwargs):
    """
    Look for provided process by name and instantiate it.

    @param procName: The L{Process} name to search for and instantiate 
    @type procName: C{str}
    
    @param config: A configuration specification to associate the given process with when it is executed.
    @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @param args: Positional arguments to pass to the constructor of the given L{Process}
    @type args: C{list}

    @param kwargs: Keyword arguments to pass to the constructor of the given L{Process}. Preferred over positional arguments.
    @type kwargs: C{dict}

    @return: instantiated L{Process} object
    @rtype: L{Process} or C{None} if no process by that name exists.
    """

    if procName is None:
        return None

    for proc in GetAvailableProcesses():
        if proc.__name__ == procName:
            kwargs['config'] = config
            return proc(*args, **kwargs)

    return None
