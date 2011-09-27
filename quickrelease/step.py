# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import os

from quickrelease.exception import ReleaseFrameworkError
from quickrelease.utils import GetActivePartnerList

class StepError(ReleaseFrameworkError):
    def __init__(self, stepObj, errStr, *args, **kwargs):
        ReleaseFrameworkError.__init__(self, errStr)

        assert isinstance(stepObj, Step), 'StepErrors require a Step object'
        self.erroredStep = stepObj

    def __str__(self):
        return "Error in step %s: %s" % (str(self.erroredStep),
         ReleaseFrameworkError.__str__(self))

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
        self.parentProcess = None
        self._runner = StandardStepRunner()

        if kwargs.has_key('process'):
            self.parentProcess =  kwargs['process']

        if kwargs.has_key('runner'):
            self._runner = kwargs['runner']

    def _GetRunner(self): return self._runner
    runner = property(_GetRunner)

    def __str__(self):
        return self.__class__.__name__ 

    def GetConfig(self):
        if self.GetParentProcess() is None:
            return None
        return self.GetParentProcess().GetConfig()

    def GetParentProcess(self):
        return self.parentProcess

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

    def DoPreflight(self, stepObj):
        conf = stepObj.GetConfig()
        rootDir = conf.GetRootDir()
        for p in GetActivePartnerList(conf):
            os.chdir(rootDir)
            stepObj.SetActivePartner(p)
            stepObj.Preflight()

    def DoExecute(self, stepObj):
        conf = stepObj.GetConfig()
        rootDir = conf.GetRootDir()
        for p in GetActivePartnerList(conf):
            os.chdir(rootDir)
            stepObj.SetActivePartner(p)
            stepObj.Execute()

    def DoVerify(self, stepObj):
        conf = stepObj.GetConfig()
        rootDir = conf.GetRootDir()
        for p in GetActivePartnerList(conf):
            os.chdir(rootDir)
            stepObj.SetActivePartner(p)
            stepObj.Verify()

    def DoNotify(self, stepObj):
        conf = stepObj.GetConfig()
        rootDir = conf.GetRootDir()
        for p in GetActivePartnerList(conf):
            os.chdir(rootDir)
            stepObj.SetActivePartner(p)
            stepObj.Notify()

class PartnerStep(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)
        self._runner = PartnerStepRunner()
        self.activePartner = None
        self.autoSetPartnerConfig = False

        if kwargs.has_key('auto_set_partner_config'):
            self.autoSetPartnerConfig = kwargs['auto_set_partner_config']
        
    def AutoInitPartnerConfig(self):
        return self.autoSetPartnerConfig

    def GetActivePartner(self):
        return self.activePartner

    def SetActivePartner(self, partner):
        if partner not in GetActivePartnerList(self.GetConfig()):
            raise self.SimpleStepError("Unknown  partner '%s'" % (partner))

        self.activePartner = partner

        if self.AutoInitPartnerConfig():
            self.GetConfig().SetPartnerSection(partner)
