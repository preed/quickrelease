
from quickrelease.process import Process
from quickrelease.steps.TestSteps import *

class TestProcess(Process):
    steps = [ TestStepOne,
              TestPartnerStepTwo,
              TestStepThree,
            ]

    def __init__(self, *args, **kwargs):
        Process.__init__(self, *args, **kwargs)
