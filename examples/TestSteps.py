
from quickrelease.step import Step, PartnerStep

class TestStepOne(Step):
    def Execute(self):
        print "EXECUTE %s." % (self)
        print "    Release version: %s" % (self.config.Get('version'))
        print "    Release build number: %s" % (
         self.config.Get('build_number'))

    def Verify(self):
        print "VERIFY %s." % (self)
        print

class TestPartnerStepTwo(PartnerStep):
    def Preflight(self):
        print "PREFLIGHT %s with partner %s." % (self, self.activePartner)

    def Execute(self):
        print "EXECUTE %s." % (self)
        print "    Partner: %s" % (self.activePartner)
        print "    Version: %s" % (self.config.Get('version'))
        print "    Partner build number: %s" % (
         self.config.SectionGet('common', 'partner_build_number'))

    def Verify(self):
        print "VERIFY %s." % (self)
        print

class TestStepThree(Step):
    def Execute(self):
        print "EXECUTE %s." % (self)
        print

    def Verify(self):
        print "VERIFY %s:" % (self)
        print "    Verifying version still: %s" % (
         self.config.Get('version'))
        print
