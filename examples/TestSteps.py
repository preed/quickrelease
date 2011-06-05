
from quickrelease.step import Step

class TestStepOne(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Execute(self):
        print
        print "Execute TestStepOne."
        print "    Release version: %s" % (self.GetConfig().Get('version'))

    def Verify(self):
        print "Verify TestStepOne."
        print

class TestStepTwo(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)
    
    def Preflight(self):
        print "Preflight TestStepTwo."

    def Execute(self):
        print "Execute TestStepTwo."
        print "    Release version still: %s" % (self.GetConfig().Get('version'))

    def Verify(self):
        print "Verify TestStepTwo."
        print


class TestStepThree(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)
    
    def Execute(self):
        print "Execute TestStepThree.\n"

    def Verify(self):
        print "Verify TestStepThree."
        print "    Verifying version still: %s" % (self.GetConfig().Get('version'))
