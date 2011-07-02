# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

class ReleaseFrameworkError(Exception):
    def __init__(self, explanation, details=None):
        self._explanation = explanation
        self._details = details
        Exception.__init__(self, explanation)

    def _GetExplanation(self): return self._explanation
    def _GetDetails(self): return self._details

    explanation = property(_GetExplanation)
    details = property(_GetDetails)

    def __str__(self):
        return str(self.explanation)
