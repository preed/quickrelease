
from quickrelease.process import Process
from quickrelease.steps.TestSteps import *

class TestProcess(Process):
    steps = [ TestStepOne,
              TestPartnerStepTwo,
              TestStepThree,
            ]

