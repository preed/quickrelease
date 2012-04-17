# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import os

from quickrelease.exception import ReleaseFrameworkError, ReleaseFrameworkErrorCollection
from quickrelease.utils import GetActivePartners, PrintReleaseFrameworkError

class StepError(ReleaseFrameworkError):
    def __init__(self, stepObj, errStr, *args, **kwargs):
        ReleaseFrameworkError.__init__(self, errStr)

        assert isinstance(stepObj, Step), 'StepErrors require a Step object'
        self.erroredStep = stepObj

        self._partnerStr = ""
        if isinstance(stepObj, PartnerStep):
            self._partnerStr = " (partner: %s)" % (
             stepObj.GetActivePartner())

    def __str__(self):
        return "Error in step %s%s: %s" % (str(self.erroredStep),
         self._partnerStr, ReleaseFrameworkError.__str__(self))

class StandardStepRunner(object):
    def __init__(self, *args, **kwargs):
        object.__init__(self)

    def DoPreflight(self, stepObj):
        stepObj.Preflight()

    def DoExecute(self, stepObj):
        stepObj.Execute()

    def DoVerify(self, stepObj):
        stepObj.Verify()

    def DoNotify(self, stepObj):
        stepObj.Notify()

class Step(object):
    def __init__(self, *args, **kwargs):
        object.__init__(self)
        self._parentProcess = None
        self._runner = StandardStepRunner()

        if kwargs.has_key('process'):
            self._parentProcess =  kwargs['process']

        if kwargs.has_key('runner'):
            self._runner = kwargs['runner']

    def __str__(self):
        return self.__class__.__name__ 

    def _GetRunner(self): return self._runner
    def _GetParentProcess(self): return self._parentProcess
    def _GetConfig(self):
        if self.process is None:
            return None
        return self.process.config

    runner = property(_GetRunner)
    config = property(_GetConfig)
    process = property(_GetParentProcess) 

    def Preflight(self):
        pass

    def Execute(self):
        raise NotImplementedError("Need implementation for %s::Execute()" % 
         (str(self)))

    def Verify(self):
        raise NotImplementedError("Need implementation for %s::Verify()" % 
         (str(self)))
  
    def Notify(self):
        pass

    # We're kinda cheating here; when using it, it looks like SimpleStepError
    # is an exception type, not a function; it's mostly a convenience function
    # for creating a StepError Exception with a simple message, so we don't
    # have to pass the step object the StepError expects explicitly.
    def SimpleStepError(self, errStr, details=None):
        return StepError(self, errStr, details=details)

class PartnerStepRunner(object):
    def __init__(self, *args, **kwargs):
        object.__init__(self)

    def _RunPartnerStepMethod(self, stepObj, methodName):
        conf = stepObj.config
        rootDir = conf.rootDir
        errors = []

        for p in GetActivePartnerList(conf):
            try:
                os.chdir(rootDir)
                stepObj.activePartner = p
                stepMethod = getattr(stepObj, methodName)
                stepMethod()
            except ReleaseFrameworkError, ex:
                if stepObj.haltOnFirstError:
                    raise ex
                else:
                    # Unless we're in quiet mode...
                    PrintReleaseFrameworkError(ex)
                    errors.append(ex)

        if len(errors) != 0:
            raise ReleaseFrameworkErrorCollection(errors)

    def DoPreflight(self, stepObj):
        self._RunPartnerStepMethod(stepObj, "Preflight")

    def DoExecute(self, stepObj):
        self._RunPartnerStepMethod(stepObj, "Execute")

    def DoVerify(self, stepObj):
        self._RunPartnerStepMethod(stepObj, "Verify")

    def DoNotify(self, stepObj):
        self._RunPartnerStepMethod(stepObj, "Notify")

class PartnerStep(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)
        self._runner = PartnerStepRunner()
        self._activePartner = None
        self._partnerData = {}

        self.autoSetPartnerConfig = True
        self.haltOnFirstError = False

        if kwargs.has_key('auto_set_partner_config'):
            self.autoSetPartnerConfig = kwargs['auto_set_partner_config']

        if kwargs.has_key('halt_on_first_error'):
            self.haltOnFirstError = kwargs['halt_on_first_error']

    def _GetActivePartner(self): return self._activePartner

    def _SetActivePartner(self, partner):
        if partner not in GetActivePartnerList(self.config):
            raise self.SimpleStepError("Unknown partner '%s'" % (partner))

        self._activePartner = partner

        if self.autoSetPartnerConfig:
            self.config.SetPartnerSection(partner)

        if partner not in self._partnerData.keys():
            self._partnerData[partner] = {}

    activePartner = property(_GetActivePartner, _SetActivePartner)

    def Save(self, key, data):
        self._partnerData[self.activePartner][key] = data

    def Load(self, key):
        return self._partnerData[self.activePartner][key]

