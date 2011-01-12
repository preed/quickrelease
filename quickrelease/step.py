
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.utils import GetActivePartnerList

class StepError(ReleaseFrameworkError):
   def __init__(self, stepObj, errStr, *args, **kwargs):
      ReleaseFrameworkError.__init__(self, errStr)

      assert isinstance(stepObj, Step), ('StepErrors require a Step '
       'object')

      self.erroredStep = stepObj

   def __str__(self):
      return "Error in step %s: %s" % (str(self.erroredStep),
       ReleaseFrameworkError.__str__(self))

class Step(object):
   def __init__(self, *args, **kwargs):
      object.__init__(self)
      self.parentProcess = None

      if kwargs.has_key('process'):
         self.parentProcess =  kwargs['process']

      # Partner-related varibles
      self.partnerStep = False
      self.activePartner = None
      self.autoSetPartnerConfig = True

      if kwargs.has_key('partner_step'):
         self.partnerStep = kwargs['partner_step']

      if kwargs.has_key('auto_set_partner_config'):
         self.autoSetPartnerConfig = kwargs['auto_set_partner_config']

   def __str__(self):
      return self.__class__.__name__ 

   def GetConfig(self):
      if self.GetParentProcess() is None:
         return None
      return self.GetParentProcess().GetConfig()

   def IsPartnerStep(self):
      return self.partnerStep

   def AutoInitPartnerConfig(self):
      return self.IsPartnerStep() and self.autoSetPartnerConfig

   def GetActivePartner(self):
      return self.activePartner

   def SetActivePartner(self, partner):
      if not self.IsPartnerStep():
         if partner is None:
            return
         else:
            assert False, "Cannot set an active partner for non-partner steps"

      assert partner in GetActivePartnerList(self.GetConfig()), ("Unknown "
       " partner '%s'" % (partner))
      self.activePartner = partner

   def GetParentProcess(self):
      return self.parentProcess

   def Preflight(self):
      pass

   def Execute(self):
      raise NotImplementedError("Step::Execute()")

   def Verify(self):
      raise NotImplementedError("Step::Verify()")
  
   def Notify(self):
      pass

   # We're kinda cheating here; when using it, it looks like SimpleStepError
   # is an exception type, not a function; it's mostly a convenience function
   # for creating a StepError Exception with a simple message, so we don't
   # have to pass the step object the StepError expects explicitly.
   def SimpleStepError(self, errStr, details=None):
      return StepError(self, errStr, details=details)
