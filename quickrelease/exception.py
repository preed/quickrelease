class ReleaseFrameworkError(Exception):
   def __init__(self, explanation, details=None):
      self.explanation = explanation
      self.details = details
      Exception.__init__(self)

   def __str__(self):
      return str(self.explanation)

   def GetDetails(self):
      return self.details
