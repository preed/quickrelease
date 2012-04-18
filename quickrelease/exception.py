# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""Various exception/error types used by both QuickRelease and available for 
QuickRelease users to use in their own code.
"""

## TODO: separate out QuickRelease-specific errors from ones for users.

class ReleaseFrameworkError(Exception):
    """
    A standard error class to indicate a error with the release framework.
    """
    def __init__(self, explanation, details=None):
        """
        Construct the ReleaseFrameworkError.

        @param explanation: A summary of the exception.
        @type explanation: C{str} (or covertable to)

        @param details: Further details regarding the exception.
        """
        self._explanation = explanation
        self._details = details
        Exception.__init__(self, explanation)

    def _GetExplanation(self): return self._explanation
    def _GetDetails(self): return self._details

    explanation = property(_GetExplanation)
    """A short summary of the exception. Read-only.
    @type: C{str}"""
    details = property(_GetDetails)
    """Extended details, if provided, regarding the exception. Read-only."""

    def __str__(self):
        return str(self.explanation)

## TODO: provide an __iter__ method for this
class ReleaseFrameworkErrorCollection(ReleaseFrameworkError):
    """
    A collection class to collect multiple ReleaseFrameworkErrors and handle
    them as a group. This class is useful when you've got a repeated process
    (e.g. partner processes), but want to attempt all the process with all the
    partners before halting.
    """
    def __init__(self, group=()):
        """
        Create the ReleaseFrameworkErrorCollection.

        @param group: An existing C{list} of r{ReleaseFrameworkError}s.
        @type group: C{list}
        """
        # TODO: deepcopy these
        self._errorGroup = list(group)
        ReleaseFrameworkError.__init__(self, None, group)

        self._explanation = str(self)

    def __str__(self):
        errorStrs = list(str(x) for x in self._errorGroup)
        return "Release Framework Errors:\n\t%s" % '\n\t'.join(errorStrs)

    def append(self, releaseFrameworkError):
        """Attach the specific L{ReleaseFrameworkError} to the collection.

        @param releaseFrameworkError: The L{ReleaseFrameworkError} to be added 
        to the collection.
        @type releaseFrameworkError: L{ReleaseFrameworkError}
        """
        self._errorGroup.append(releaseFrameworkError)
        self._explanation = str(self)
