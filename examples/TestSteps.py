
from quickrelease.step import Step, PartnerStep

class TestStepOne(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)

    def Execute(self):
        print "EXECUTE TestStepOne."
        print "    Release version: %s" % (self.GetConfig().Get('version'))

    def Verify(self):
        print "VERIFY TestStepOne."
        print

class TestPartnerStepTwo(PartnerStep):
    def __init__(self, *args, **kwargs):
        PartnerStep.__init__(self, *args, **kwargs)
    
    def Preflight(self):
        print "PREFLIGHT TestPartnerStepTwo with partner %s." % (
         self.GetActivePartner())

    def Execute(self):
        print "EXECUTE TestPartnerStepTwo."
        print "    Partner: %s" % (self.GetActivePartner())
        print "    Version: %s" % (self.GetConfig().Get('version'))
        print "    Partner build number: %s" % (
         self.GetConfig().SectionGet('common', 'partner_build_number'))

    def Verify(self):
        print "VERIFY TestPartnerStepTwo."


class TestStepThree(Step):
    def __init__(self, *args, **kwargs):
        Step.__init__(self, *args, **kwargs)
    
    def Execute(self):
        print
        print "EXECUTE TestStepThree."

    def Verify(self):
        print "VERIFY TestStepThree:"
        print "    Verifying version still: %s" % (
         self.GetConfig().Get('version'))
        print
