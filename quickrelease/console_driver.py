#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (c) 2010-2011 Pioneers of the Inevitable/Songbird
# Copyright (c) 2011      J. Paul Reed
# Copyright (c) 2011-2012 Release Engineering Approaches
#
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

r"""QuickRelease's command-line driver.

Allows users to set options, get information about the defined processes/steps,
run specific processes, and wraps various exceptions so as to present a 
nicer interface.

This driver will normally get installed to your python installation's binary 
directory as "quickrelease" when installing QuickRelease with setuptools.
"""

from optparse import OptionParser
import os
import sys

from quickrelease.config import ConfigSpec, ConfigSpecError, ConfSpecErrorIsMissingError
from quickrelease.exception import ReleaseFrameworkError
from quickrelease.log import Logger
from quickrelease.process import GetAvailableProcessesList, GetProcessByName
from quickrelease.utils import PrintReleaseFrameworkError

QUICK_RELEASE_VERSION = '0.15.0pre'

gRootDir = None
gUserDefinedConstants = None

def main():
    global gRootDir

    o = OptionParser(usage="%s [ -l [-p ProcessName ] | "
                     "-c config.cfg -p ProcessName [options] ]" % (sys.argv[0]),
                     version="%prog version " + QUICK_RELEASE_VERSION)
    o.add_option('-1', '--onestep', dest='runOneStep', default=False,
                 action='store_true',
                 help="Run only a single step of the specified process; "
                 "useful with --start-at.")
    o.add_option('-C', '--user-constants', dest='userConstants', default=None,
                 help="Package path to user-defined constants."
                 "See documentation for more information.")
    o.add_option('-c', '--config', dest='configSpecFile', default=None,
                 help="Harness configuration specification file to use. "
                 "Required.")
    o.add_option('-D', '--define', dest='variableRedefs', default=[],
                 action='append',
                 help="Specify config file variable overrides on the "
                 "commandline. Must be enabled in the configuration file "
                 "specified by --config. "
                 "Use: -D[section:]variable_name=override_value")
    o.add_option('-i', '--ignore-errors', dest='ignoreErrors', default=False,
                 action='store_true',
                 help="Ignore any errors encountered while running; continue "
                 "on with the next steps")
    o.add_option('-L', '--logDir ', dest='logDir', default=None,
                 help="Directory to store log files for a process in."
                 "Default: the root directory; if any logs are requested (see "
                 "the --verbose argument),they will be dumped in the specifed "
                 "root directory (see the --root argument)")
    o.add_option('-l', '--list', dest='showList', default=False,
                 action='store_true',
                 help="List all available processes or, if with -p, "
                 "all steps that constitute a prcoess.")
    o.add_option('-p', '--process', dest='process', default=None,
                 help="Process to run/list steps of.")
    o.add_option('-r', '--root', dest='rootDir', default=os.getcwd(),
                 help="Root directory to use; default: cwd")
    o.add_option('-s', '--start-at', dest='startAt', default=None,
                 help="Step Name to start at")
    o.add_option('-V', '--verify-only', dest='verifyOnly', default=False,
                 action='store_true',
                 help="Only run the Verify portion of the specified steps.")
    o.add_option('-v', '--verbose', dest='verbose', default=None,
                 help="Set the verbosity level using a string of "
                 "'level:output', pairs separated by commas. may be specifed "
                 "to the same destination. Possible levels are: 0 (only error "
                 "messages and exceptions), 1 (log messages from "
                 "steps/processes), 2 (debug messages from steps/processes), "
                 "and 3 (internal QuickRelease debugging messages). Higher "
                 "levels include all the levels below them. Output can be one "
                 "of 'dir' (see --logDir), console (stderr for errors, stdout "
                 "for all else); or a path to a file to dump all output of "
                 "that type to. Defult: '1:console', i.e. all error messages, "
                 "exceptions, and log messgaes from steps/processes logged to "
                 "the console. If --logDir is specified, the default becomes: "
                 "'1:console,2:dir'. NOTE: this option can also set in the "
                 "config file; if this is done, all commandline parameters "
                 "will be added to it.")
    o.add_option('-X', '--execute-only', dest='executeOnly', default=False,
                 action='store_true',
                 help="Only run the Execute portion of the specified steps.")

    if len(sys.argv[1:]) == 0:
        o.print_help(file=sys.stderr)
        return 0

    (options, args) = o.parse_args()

    #if (options.mode is None):
    #    o.print_help(file=sys.stderr)
    #    return -1

    if options.showList:
        try:
            if options.process:
                process = GetProcessByName(options.process)
                if process is None:
                    print >> sys.stderr, "Unknown process: %s" % (
                     options.process)
                    return -1

                processStepNames = process.processStepNames

                print "Steps for the %s process:" % (str(process))
                for i in range(len(processStepNames)):
                    print "%3d. %s" % (i + 1, processStepNames[i])

            else:
                # Do this first, so if we have an import error, we error out
                # before printing anything
                procs = GetAvailableProcessesList()

                print "Available processes: ",
                if len(procs) == 0:
                    print "None."
                else:
                    print
                    for p in procs:
                        print "    * " + str(p)
        except ReleaseFrameworkError, ex:
            PrintReleaseFrameworkError(ex)
            return -1
        except AssertionError, ex:
            print >> sys.stderr, "Failed assertion: %s" % (ex)
            return -1

        return 0

    gRootDir = os.path.abspath(options.rootDir)

    if not os.path.isdir(gRootDir):
        print >> sys.stderr, "Invalid root dir: %s" % (gRootDir)
        o.print_help(file=sys.stderr)
        return -1

    if options.userConstants is not None:
        try:
            ConfigSpec.GetUserDefinedConstantsDict(options.userConstants,
             ConfigSpec.QR_CONSTANTS_DICT_NAME)
            os.environ[ConfigSpec.USER_DEFINED_CONSTANTS_ENV_VAR] = (
             options.userConstants)
        except ConfigSpecError, ex:
            print >> sys.stderr, str(ex)
            o.print_help(file=sys.stderr)
            return -1

    try:
        configSpec = ConfigSpec(options.configSpecFile,
         overrides=options.variableRedefs)
    except ConfigSpecError, ex:
        print >> sys.stderr, str(ex)
        return -1

    if options.verbose is None:
        try:
            options.verbose = configSpec.SectionGet('quickrelease', 'verbose')
        except ConfigSpecError, ex:
            if not ConfSpecErrorIsMissingError(ex.details):
                raise ex

    if options.runOneStep:
        stepsToRun = 1
    else:
        stepsToRun = None

    if options.process is None:
        o.print_help(file=sys.stderr)
        return -1

    if options.executeOnly and options.verifyOnly:
        print >> sys.stderr, "Must either execute or verify the process steps."
        return 1

    processHadErrors = False
    try:
        try:
            processToRun = GetProcessByName(options.process,
             config=configSpec, verifySteps=not options.executeOnly,
             executeSteps=not options.verifyOnly,
             ignoreErrors=options.ignoreErrors,
             logger=Logger(config=options.verbose, logDirectory=options.logDir))

            if processToRun is None:
                raise ValueError("Unknown process: %s" % (options.process))

            processToRun.Run(startingStepName=options.startAt,
             stepsToRun=stepsToRun)

            processHadErrors = processToRun.errored
        except (ValueError, NotImplementedError), ex:
            print >> sys.stderr, ex
            return -1
        except ReleaseFrameworkError, ex:
            PrintReleaseFrameworkError(ex)
            return -1
    except KeyboardInterrupt:
        print >> sys.stderr, "Interrupted."
        return 0
    except AssertionError, ex:
        print >> sys.stderr, "Failed assertion: %s" % (ex)
        return -1

    if processHadErrors:
       return -1 

    print >> sys.stderr, "Process %s completed successfully." % (
     options.process)
    return 0

if (sys.version_info[0] != 2 
 or sys.version_info[1] <= 4):
     print >> sys.stderr, ("%s has only been tested with Python 2.5.x - "
      "2.7.x; please use one of these versions." % (sys.argv[0]))
     sys.exit(-1)

if __name__ == '__main__':
     sys.exit(main())
