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

class ReleaseFrameworkErrorCollection(ReleaseFrameworkError):
    def __init__(self, group):
        # copy?
        self._errorGroup = list(group)
        ReleaseFrameworkError.__init__(self, None, group)

        self._explanation = str(self)

    def __str__(self):
        errorStrs = list(str(x) for x in self._errorGroup)
        return "Release Framework Errors:\n\t%s" % '\n\t'.join(errorStrs)

    def append(self, releaseFrameworkError):
        self._errorGroup.append(releaseFrameworkError)
        self._explanation = str(self)
