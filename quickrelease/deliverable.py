# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""
Provides high-level modeling of release deliverables, including a way to define,
find, filter, and manage them.

Deliverables are defined in L{ConfigSpec<quickrelease.config.ConfigSpec>}s 
using C{deliverable} definitions. The definition must include either a name
or regular expression that the final deliverable file will match against.

"Attributes" can also be added to the definition to annotate information
about the deliverable. Deliverables may also be filtered by attribute.

There are three types of attributes which may be defined and used to filter:

  1. B{Callback attributes}: this callback function is called with the L{Deliverable<quickrelease.deliverable.Deliverable>} object to match against; if the function returns the string being filtered for, the deliverable is considered to match.
  2. B{Regular expression attributes}: the file name is evaluated against the given regular expression; usually, this regular expression contains a (singular) backreference that is used to match against.
  3. B{Value attributes}: these are static values that are simply matched against verbatim.

A deliverable is defined like so:

  1. In the config file, create a section called C{[deliverable:B{name}]}. When querying to find all deliverables that meet this definition, refer to it by this name. This name, along with any additional filter attributes, is called the "deliverable class."
  2. Define an item in that config section that is either the deliverable file's name (C{name}) or a regular expression (C{regex}) matching the deliverable file, B{but not both}
  3. To define deliverable attributes, create an C{attributes} item, and list the attributes by name.
  4. To filter deliverables using these attributes, create a C{filter_attributes} item, and list all attributes available to filter by. All C{filter_attributes} must be listed in the C{attributes} list. Filter attributes are evaluated in the order they are defined.
  5. For each attribute, create an item named: C{attrib_B{NAME}_B{TYPE}}, where name is name of the attribute you've listed above, and TYPE is one of C{regex}, C{callback}, or C{value}.

After the build's deliverables are defined, the L{FindDeliverables<quickrelease.deliverable.FindDeliverables>}
method may be used to recursively traverse the given directory to find all
the deliverables.

To manipulate them, call L{GetDeliverables<quickrelease.deliverable.GetDeliverables>}
to return a set of L{Deliverable<quickrelease.deliverable.Deliverable>} objects,
which have methods which can be used to work with the underlying deliverable
in an opaque manner.

Notes
=====

 1. For performance reasons, the L{Deliverable<quickrelease.deliverable>} system uses a cache of deliverables; if the state of the directories you're searching for deliverables in changes over time, you may need to L{flush this cache<quickrelease.deliverable.FlushDeliverableCache>} and call L{FindDeliverables<quickrelease.deliverable.FindDeliverables>} again.
 2. Deliverables may be defined in a way that I{appears} to employ filter attributes when they, in fact, do not. This can be used to maintain the "filter pattern" in code, without requiring the complexity of defining a callback function or regular expression. For example, if there are two platform-specific installers, they may be defined thusly::

   [deliverable:installer:windows]
   name=MyInstaller.exe

   [deliverable:installer:mac]
   name=MyInstaller.dmg

Calls to C{GetDeliverable('installer:mac')} and C{GetDeliverable('installer:windows')} will behave as expected.

Example
=======

Two deliverable definitions follow; one for an installer and the other for a 
set of language packs related to an application.

The installer has a 32-bit and 64-bit version; for illustration purposes,
assume that for historical reasons, the installer names for the two types
are the same, but reside in different directories. (This comes from a real-
world example, but from a release engineering best-practices standpoint,
the installer should have a unique name)::

 [deliverable:installer]
 name=MyApplication.exe
 attributes=bits
 filter_attributes=bits
 attrib_arch_callback=mycompany.utils.InstallerBitsFilterCallback

 [deliverable:langpack]
 regex=langpack\-\w+.zip
 attributes=locale
 filter_attributes=locale
 attrib_locale_regex=langpack\-(\w+).zip

These files all reside in a directory called C{dist} in the source tree after
a build finishes, which has a directory structure like:

  - dist/installer/32bit/MyApplication.exe
  - dist/installer/64bit/MyApplication.exe
  - dist/langpacks/langpack-en.zip
  - dist/langpacks/langpack-es.zip
  - dist/langpacks/langpack-de.zip
  - dist/langpacks/langpack-fr.zip

C{mycompany.utils.InstallerBitsFilterCallback} might look like::

    def InstallerBitsFilterCallback(deliverableObject):
        # the fileName property contains the full path; get the directory:
        deliverableDir = os.path.dirname(deliverableObject.fileName)
        if deliverableDir.find("32bit") != -1:
            return "32"
        elif deliverableDir.find("64bit") != -1:
            return "64"

        raise ReleaseFrameworkError("Not a 32- or 64-bit installer?")

Before being able to query for any found deliverables, the cache must be primed::

    deliverableDir = os.path.join(GetDeliverableRootPath(), "dist")
    n = FindDeliverables(deliverableDir, config)
    if n is None:
        print "%s directory already scanned for deliverables." % (deliverableDir)
    else:
        print "%d deliverables found!" % (n)

To find/manipulate the installers::

    # Make sure there are two installers:
    installers = GetDeliverables('installer')
    if len(installers) != 2:
        print "Missing installer? Only %d installer(s) found." % (len(installers))

    installer32 = GetDeliverable('installer:32')
    # code to upload 32-bit installer to 32-bit directory

    installer64 = GetDeliverable('installer:64')
    # code to upload 64-bit installer to 64-bit directory

To find the French language pack, the code might read::

    frenchLangpack = GetDeliverable('langpack:fr')

To get all language packs::

    allLangpacks = GetDeliverables('langpack')
    for pack in allLangpacks:
        print "Langpack found: %s" % (pack.fileName)

To copy all the language packs for a partner that wants all language packs, except German::

    for pack in GetDeliverables('langpack'):
        if pack.GetAttribute('locale') != 'de':
            shutil.copy(pack.fileName, partnerDirectory)

This, however, will blow up with a L{ConfigSpecError<quickrelease.config.ConfigSpecError>}, since more than one deliverable matches::

    oneLangpackIHope = GetDeliverable('langpack')

Subclasses
==========

The L{Deliverable<quickrelease.config.Deliverable>} object can be subclassed.

This is particularly useful if you have a commonly used deliverable that has a large number of attributes or extra information you'd like to store about the deliverable and make accessible to callers.

This can be done by creating an object that is a subclass of L{Deliverable<quickrelease.config.Deliverable>}, and adding an item in the deliverable description in the config file named C{subclass}, and the fully-scoped reference to the object, like so::

  [deliverable:big_deliverable_object]
  name=MyThing.exe
  subclass=mycompany.companydeliverables.BigDeliverableDescriptor

Then, in companydeliverables.py, you'd have::

    class AddonDescriptor(Deliverable):
        def __init__(self, bigDelivFile="", *args, **kwargs):
            Deliverable.__init__(self, bigDelivFile, *args, **kwargs)

            self._bigDelivExtraInfo = None
            self._bigDelivMoreExtraInfo = None

        def CustomBigDeliverableMethod(self):
            return self._bigDelivExtraInfo


The constructor for your subclassed object will be called, in order, with the following arguments:
  1. The full path of the deliverable's location
  2. The name of the deliverable class (C{big_deliverable_thing} above
  3. A L{ConfigSpec<quickrelease.config.ConfigSpec>} reference

"""

import copy
import os
import re

from quickrelease.config import ConfigSpecError, ConfigSpec
from quickrelease.utils import ImportModule, ImportFunction

class Deliverable(object):
    """
    Represents a single deliverable on the file system.
    """
    DELIVERABLE_CONFIG_PREFIX = (ConfigSpec.DELIV_SECTION_PREFIX +
     ConfigSpec.CONFIG_SECTION_DELIMETER)

    ERROR_STR_NEED_NAME_OR_REGEX = ("Deliverable class '%s' must define a name "
     "or a regex for the deliverable.")

    _gDeliverablesCache = {}
    _gAttributeCallbackCache = {}

    ATTRIB_TYPE_CALLBACK = 0
    ATTRIB_TYPE_REGEX = 1
    ATTRIB_TYPE_VALUE = 2

    def __init__(self, deliverableFile, deliverableClass, config, *args,
     **kwargs):
        """
        Construct a deliverable object.

        @param deliverableFile: the full path of the deliverable on the file system. 
        @type deliverableFile: C{str} 

        @param deliverableClass: the deliverable class name matching this deliverable, e.g. C{name} in C{[deliverable:name]}.
        @type deliverableClass: C{str}

        @param config: A L{ConfigSpec<quickrelease.config.ConfigSpec>} reference.
        @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>}

        @raise ValueError: A ValueError is raised when:
          1. The provided C{deliverableFile} isn't a full path.
          2. The provided C{deliverableFile} doesn't exist.
          3. The provided C{deliverableClass} is not a valid deliverable defined in the config file passed.
        @raise ConfigSpecError: A ConfigSpecError is raised when:
          1. The deliverable definition does not include a C{name} or C{regex} item.
          2. The deliverable defines an attribute, but not a handler (regex, callback, or value) for that attribute.
          3. The deliverable defines a filter attribute which is not a valid attribute.
        """
        object.__init__(self, *args, **kwargs)

        if not os.path.isabs(deliverableFile):
            raise ValueError("Must provide absolute path to Deliverable "
             "constructor")
        elif not os.path.isfile(deliverableFile):
            raise ValueError("Non-existent file passed to Deliverable "
             "constructor")
        elif not IsValidDeliverableClass(config, deliverableClass):
            raise ValueError("Non-existent deliverable class passed to "
             "Deliverable constructor: %s" % deliverableClass)

        self._configSection = DeliverableSectionNameFromClass(deliverableClass)
        self._deliverableClass = deliverableClass
        self._queriedDeliverableClass = None
        self._file = deliverableFile
        self._regex = None
        self._name = None
        self._filterAttributes = None
        self._attributes = []
        self._attributeHandlers = {}

        deliverableSectionItems = config.GetSectionItems(self._configSection)

        if 'name' in deliverableSectionItems:
            self._name = config.SectionGet(self._configSection, 'name').strip()

        if 'regex' in deliverableSectionItems:
            self._regex = config.SectionGet(self._configSection,
             'regex').strip()

        if self.regex is None and self.name is None:
            raise ConfigSpecError(self.ERROR_STR_NEED_NAME_OR_REGEX %
             (self._deliverableClass))

        if 'attributes' in deliverableSectionItems:
            self._attributes = config.SectionGet(self._configSection,
             'attributes', list)

        for attr in self._attributes:
            attributeValue = None
            attributeType = None

            if ('attrib_%s_handler' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_CALLBACK
                attributeValue = config.SectionGet(self._configSection,
                 'attrib_%s_handler' % (attr))
            elif ('attrib_%s_regex' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_REGEX
                attributeValue = config.SectionGet(self._configSection,
                 'attrib_%s_regex' % (attr))
            elif ('attrib_%s_value' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_VALUE
                attributeValue = config.SectionGet(self._configSection,
                 'attrib_%s_value' % (attr))
            else:
                raise ConfigSpecError("Deliverable class '%s' defines "
                 "attribute '%s', but doesn't define handler for it." %
                 (deliverableClass, attr))

            attributeHandlerDescriptor = {}
            attributeHandlerDescriptor['type'] = attributeType

            if attributeType == Deliverable.ATTRIB_TYPE_CALLBACK:
                if Deliverable._gAttributeCallbackCache.has_key(attributeValue):
                    attributeHandlerDescriptor['handler'] = (
                     Deliverable._gAttributeCallbackCache[attributeValue])
                else:
                    try:
                        handlerFunction = ImportFunction(attributeValue)
                        attributeHandlerDescriptor['handler'] = handlerFunction
                        Deliverable._gAttributeCallbackCache[attributeValue] = (
                         handlerFunction)
                    except NameError, ex:
                        raise ConfigSpecError("Deliverable class '%s' defines "
                         "an attribute callback handler for attribute '%s', "
                         "but the callback is undefined: %s" % (
                         self._deliverableClass, attr, str(ex)))

            elif (attributeType == Deliverable.ATTRIB_TYPE_REGEX or
             attributeType == Deliverable.ATTRIB_TYPE_VALUE):
                attributeHandlerDescriptor['handler'] = attributeValue

                # Hacky
                if attributeType == Deliverable.ATTRIB_TYPE_REGEX:
                    regexFlags = 0
                    try:
                        regexFlagsStr = config.SectionGet(self._configSection,
                         'regexflags').strip()
                        regexFlags = eval(regexFlagsStr) 
                    except ConfigSpecError, ex:
                        if ex.details != ConfigSpecError.NO_OPTION_ERROR:
                            raise ex

                    attributeHandlerDescriptor['regexFlags'] = regexFlags
            else:
                assert False, "Unknown attribute handler type: %s" % (
                 attributeType)

            self._attributeHandlers[attr] = attributeHandlerDescriptor

        if 'filter_attributes' in deliverableSectionItems:
            self.filterAttributes = config.SectionGet(self._configSection,
             'filter_attributes', list)

        if self.filterAttributes is not None:
            for fa in self.filterAttributes:
                if fa not in self.attributes:
                    raise ConfigSpecError("Deliverable class '%s' defines "
                     "invalid filter attribute '%s'" % (deliverableClass, fa))

    def __rep__(self):
        return "<class %s: %s (%s)>" % (self.__class__, self.name,
         self.fileName)

    def __str__(self):
        """The full path to the deliverable."""
        return self.fileName

    def _GetName(self): return self._deliverableClass
    def _GetQueriedName(self): return self._queriedDeliverableClass
    def _GetLocation(self): return self._file
    def _GetFileName(self): return os.path.basename(self.fileName)
    def _GetRegex(self): return self._regex
    def _GetAttributes(self): return tuple(self._attributes)

    def _GetFilterAttributes(self):
        if self.filterAttributes is None:
            return None
        else:
            return tuple(self._filterAttributes)

    name = property(_GetName)
    """The name of the deliverable class. Read-only.
    @type: C{str}"""

    queriedName = property(_GetQueriedName)
    """The name of the deliverable class, including any filter attributes used. Read-only.
    @type: C{str}"""

    fileName = property(_GetLocation)
    """The full path to the deliverable. Read-only.
    @type: C{str}"""

    file = property(_GetFileName)
    """The name of the file, without its path. Read-only.
    @type: C{str}"""

    regex = property(_GetRegex)
    """If the deliverable is defined to match against a regular expression, that regular expression; if the deliverable is defined to match against a name, C{None}. Read-only.
    @type: C{str} or None"""

    attributes = property(_GetAttributes)
    """A list of the deliverable's attributes. Read-only.
    @type: C{list}"""

    filterAttributes = property(_GetFilterAttributes)
    """A list of attributes which may be used to filter deliverables of this type. Read-only.
    @type: C{list}"""

    def GetAttribute(self, attribute):
        """
        Get the named attribute from the deliverable.

        Depending on the type of the attribute, this may involve matching
        a regular expression, calling a callback function, or merely fetching
        a local, static attribute (a string).

        @param attribute: The name of the deliverable's attribute to get.
        @type attribute: C{str}

        @return: The deliverable's attribute.
        @rtype: Variable. Usually a C{str}.

        @raise ValueError: When an attribute is requested which the deliverable does not define.
        """

        if attribute not in self.attributes:
            raise ValueError("Deliverable class '%s' has no attribute '%s" % (self.name, attribute))

        handlerType = self._attributeHandlers[attribute]['type']
  
        if handlerType == Deliverable.ATTRIB_TYPE_VALUE:
            return self._attributeHandlers[attribute]['handler']
        elif handlerType == Deliverable.ATTRIB_TYPE_REGEX:
            attribMatch = re.search(
             self._attributeHandlers[attribute]['handler'], self.fileName,
             self._attributeHandlers[attribute]['regexFlags'])

            if attribMatch is None:
                return None
            elif len(attribMatch.groups()) == 1:
                return attribMatch.group(1)
            else:
                return attribMatch.groups()
        elif handlerType == Deliverable.ATTRIB_TYPE_CALLBACK:
            return self._attributeHandlers[attribute]['handler'](self)
        else:
            assert False, "Unknown attribute handler type: %s" % (handlerType)

def FindDeliverables(deliverableDir, config):
    """
    Prime the L{Deliverable<quickrelease.deliverable.Deliverable>} cache by recursively traversing the given directory and searching for all deliverables defined in the given L{ConfigSpec<quickrelease.config.ConfigSpec>} file.

    @param deliverableDir: A directory to recursively search through for deliverables.
    @type deliverableDir: C{str}

    @param config: A reference to a L{ConfigSpec<quickrelease.config.ConfigSpec>} containing definitions deliverable definitions.
    @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @return: The number of deliverable found in the given directory. If the
    given directory already exists in the deliverables cache, B{None}.
    @rtype: C{int} or C{None}

    @raise ValueError: If an invalid directory is provided.
    @raise ConfigSpecError: in a number of cases:
      1. If a deliverable section in the config file does not specify a C{name} or a C{regex} item.
      2. If a deliverable file matches two different deliverable classes. This means the deliverable definitions in the config file need to be made more unique.
      3. If a subclass is specified, and the module loader can't find and/or load it (due to syntax errors, etc.)

    """
    if not os.path.isdir(deliverableDir):
        raise ValueError("Invalid deliverable directory: %s" % (deliverableDir))

    if Deliverable._gDeliverablesCache.has_key(deliverableDir):
        return None

    deliverables = []
    deliverableSections = GetDeliverableSections(config)

    ignoreUndefinedDeliverables = True 
    try:
        ignoreUndefinedDeliverables = config.Get(
         'ignore_undefined_deliverables', bool)
    except ConfigSpecError, ex:
        if ex.details != ConfigSpecError.NO_OPTION_ERROR:
            raise ex

    for root, dirs, files in os.walk(deliverableDir):
        for f in files:
            #print "Looking at: %s" % (os.path.join(root, f))
            deliverableDescList = []
            for section in deliverableSections:
                delivRegex = None
                delivName = None
                matchType = None
                subclassType = None

                sectionItems = config.GetSectionItems(section)

                regexFlags = 0
                if 'name' in sectionItems:
                    delivName = config.SectionGet(section, 'name').strip()
                    matchType = 'name'
                elif 'regex' in sectionItems:
                    delivRegex = config.SectionGet(section, 'regex').strip()
                    matchType = 'regex'
               
                    try:
                        regexFlagsStr = config.SectionGet(section,
                         'regexflags').strip()
                        regexFlags = eval(regexFlagsStr)
                    except ConfigSpecError, ex:
                        if ex.details != ConfigSpecError.NO_OPTION_ERROR:
                            raise ex

                else:
                    raise ConfigSpecError(
                     Deliverable.ERROR_STR_NEED_NAME_OR_REGEX %
                     DeliverableClassFromSectionName(section))

                #print "f is %s, name is %s, regex is %s" % (f, delivName, delivRegex)          
                if ((delivName is not None and f == delivName) or 
                 (delivRegex is not None and re.search(delivRegex, f,
                 regexFlags))):
                    if 'subclass' in sectionItems:
                        subclassType = config.SectionGet(section,
                         'subclass').strip()

                    delivClassDescription = { 
                     'type': matchType,
                     'subclass' : subclassType,
                     'class' : DeliverableClassFromSectionName(section),
                     'file' : os.path.join(root, f),
                    }


                    deliverableDescList.append(delivClassDescription)

            if len(deliverableDescList) == 0:
                if not ignoreUndefinedDeliverables:
                    assert False, "Should be a release framework error."
                else:
                    continue

            if len(deliverableDescList) == 1:
                delivDesc = deliverableDescList[0]

                if delivDesc['subclass'] is not None:
                    try:
                        subclassModule = ImportFunction(delivDesc['subclass'])
                        newDelivObj = subclassModule(delivDesc['file'],
                         delivDesc['class'], config)
                    except NameError, ex:
                        raise ConfigSpecError("subclass error %s" % (ex)) 
                else:
                    newDelivObj = Deliverable(delivDesc['file'], 
                     delivDesc['class'], config)

                deliverables.append(newDelivObj)

            else:
                matchedClassList = []
                fileLoc = deliverableDescList[0]['file']
                for delivDesc in deliverableDescList:
                    assert fileLoc == delivDesc['file'], ("Deliverable file "
                     "name mismatch (%s vs %s)?" % (fileLoc, delivDesc['file']))

                    matchedClassList.append("%s (matched via %s)" % (
                     delivDesc['class'], delivDesc['type']))

                raise ConfigSpecError("More than one deliverable class for "
                 "the file %s: %s" % (fileLoc, ', '.join(matchedClassList)))

    Deliverable._gDeliverablesCache[deliverableDir] = tuple(deliverables)
    return len(tuple(deliverables))

def GetAllDeliverables(deliverableDir=None):
    """
    Return the list of known deliverables in the deliverable cache. 

    @param deliverableDir: Return only deliverables found in this directory. This directory must have been scanned for deliverables with L{FindDeliverables}. The default (C{None}) is to return all deliverables from all scanned directories.
    @type deliverableDir: C{str} or C{None}

    @return: All deliverables found in the given directory, or all directories if C{deliverableDir} was C{None} (the default).
    @rtype: C{tuple} of L{Deliverable<quickrelease.deliverable.Deliverable>}

    @raise ValueError: When either L{FindDeliverables} has not been called yet, or the specified L{deliverableDir} has not yet been scanned with L{FindDeliverables}. 
    """

    if deliverableDir is not None:
        if not Deliverable._gDeliverablesCache.has_key(deliverableDir):
            raise ValueError("Directory %s has not been scanned for "
             "deliverables yet; use FindDeliverables()" % (deliverableDir))

        return tuple(Deliverable._gDeliverablesCache[deliverableDir])
    else:
        cacheKeys = Deliverable._gDeliverablesCache.keys()
        if len(cacheKeys) == 0:
            raise ValueError("No deliverables found yet; prime cache with "
             "FindDeliverables()")

        allDeliverables = []

        for dDirs in cacheKeys:
            for deliv in Deliverable._gDeliverablesCache[dDirs]:
                allDeliverables.append(deliv)

        return tuple(allDeliverables)

def GetDeliverables(deliverableClass, deliverableDir=None):
    """
    Get all deliverables matching the given deliverable class (including filter attributes).

    @param deliverableClass: The class of deliverable to return.
    @type deliverableClass: C{str}

    @param deliverableDir: Only return deliverables found in this directory. 
    Default: all directories scanned with L{FindDeliverables}. 
    @type deliverableDir: C{str}

    @return: All deliverables matching the given class in the given directory.
    @rtype: C{list} of L{Deliverable}

    @raise ValueError: ValueErrors are raised in the followin cases:
       1. If filter attributes are provided for a deliverable that defines no filter attributes.
       2. If more filter attributes were provided in the query than than are defined in the deliverable definition.
    """
    filterArgs = deliverableClass.split(':')
    filterArgsLen = len(filterArgs)
    filteredDeliverableList = []

    # Process the static filters, given in the config file
    for deliv in GetAllDeliverables(deliverableDir):
        staticFilters = deliv.GetName().split(':')
        staticFilterLen = len(staticFilters)

        filterNdx = 0

        skipThisDeliv = False
        while filterNdx < filterArgsLen and filterNdx < staticFilterLen:
            if filterArgs[filterNdx] != staticFilters[filterNdx]:
                skipThisDeliv = True
                break

            filterNdx += 1

        if skipThisDeliv:
            continue

        # If we've parsed all of the filter arguments, we're done
        if filterNdx == filterArgsLen:
            retDeliv = copy.deepcopy(deliv)
            retDeliv.queriedDeliverableClass = deliverableClass
            filteredDeliverableList.append(retDeliv)
            continue

        dynamicFilters = deliv.GetFilterAttributes()

        if dynamicFilters is None and filterNdx < filterArgsLen:
            raise ValueError("GetDeliverables passed filter '%s' for a "
             "deliverable class that defines no filter attributes" %
             ':'.join(filterArgs[filterNdx:]))

        dynamicFilterLen = len(dynamicFilters)

        while filterNdx < filterArgsLen:
            dynNdx = filterNdx - staticFilterLen
            assert dynNdx >= 0, "Invalid (negative) dynamic filter index."
            if dynNdx >= dynamicFilterLen:
                availableFilters = staticFilters[1:] + list(dynamicFilters)
                availableFiltersStr = ', '.join(availableFilters)
                filterCount = len(availableFilters)
                if filterCount > 1:
                    pluralFilters = "s"
                else:
                    pluralFilters = ""

                raise ValueError("GetDeliverables passed extra filter '%s' "
                 "for deliverable %s; %s defines %d filter%s: %s." % (
                 ':'.join(filterArgs[filterNdx:]), deliv.GetName(),
                 deliv.GetName(), filterCount, pluralFilters,
                 availableFiltersStr))

            if (deliv.GetAttribute(dynamicFilters[dynNdx]) != 
             filterArgs[filterNdx]):
                skipThisDeliv = True
                break

            filterNdx += 1

        if skipThisDeliv:
            continue

        retDeliv = copy.deepcopy(deliv)
        retDeliv.queriedDeliverableClass = deliverableClass
        filteredDeliverableList.append(retDeliv)

    return filteredDeliverableList

def GetDeliverable(deliverableClass, deliverableDir=None):
    """
    Similar to L{GetDeliverables}, but returns a single deliverable, or raises an error if multiple deliverables match. This is a convenience method to avoid patterns like::
        
        oneDeliverable = GetDeliverables('only_one')
        DoSomethingWithOnlyOneDeliverable(oneDeliverable[0])

    @return: If no deliverables match, C{None}; otherwise, the deliverable that matches.
    @rtype: L{Deliverable} or C{None}

    @see: Documentation for L{GetDeliverables}

    @raise ConfigSpecError: if more than a single deliverable matches the query
    """

    possibleDelivs = GetDeliverables(deliverableClass, deliverableDir)

    if len(possibleDelivs) == 0:
        return None
    elif len(possibleDelivs) > 1:
        raise ConfigSpecError("More than one deliverable matched for "
         "deliverable class %s: %s" % (deliverableClass,
         ', '.join(list(x.GetLocation() for x in possibleDelivs))))
    else:
        return possibleDelivs[0]

def FlushDeliverableCache(deliverableDir=None):
    """
    Flush the deliverable cache of all L{Deliverable} entries.

    @param deliverableDir: a specific directory to flush the cache of. Default: all the known directories.
    @type deliverableDir: C{str} or C{None}

    @raise ValueError: If a C{deliverableDir} is specified that is not in the cache.

    """
    if deliverableDir is None:
        Deliverable._gDeliverablesCache.clear()
    else:
        try:
            del Deliverable._gDeliverablesCache[deliverableDir]
        except KeyError:
            raise ValueError("Deliverable directory %s not in cache" %
             (deliverableDir))

def GetDeliverableSections(config):
    """
    Get a list of all section names representing in the given config defining deliverables.
    @param config: A reference to a L{ConfigSpec<quickrelease.config.ConfigSpec>} containing definitions deliverable definitions.
    @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>}

    @return: A list of strings representing the sections in the given config defining deliverables.
    @rtype: C{list} of C{str}
    """

    retSections = []

    for section in config.sectionList:
        if IsDeliverableSectionName(section):
            retSections.append(section)

    return retSections

def DeliverableClassFromSectionName(sectionName):
    """
    Given a L{ConfigSpec<quickrelease.config.ConfigSpec>} deliverable section name, return the deliverable class it is describing.

    @param sectionName: the L{ConfigSpec<quickrelease.config.ConfigSpec>} section.
    @type sectionName: C{str}

    @return: The deliverable class name
    @rtype: C{str}
    """

    return re.sub('^%s' % (Deliverable.DELIVERABLE_CONFIG_PREFIX), '',
     sectionName)

def DeliverableSectionNameFromClass(delivClass):
    """
    Given a L{Deliverable} class name, return the L{ConfigSpec<quickrelease.config.ConfigSpec>} section that would define it.

    @param delivClass: the deliverable class name
    @type delivClass: C{str}

    @return: The L{ConfigSpec<quickrelease.config.ConfigSpec>} section that would define it. B{Note}: No checks are done to see if this section actually exists in a given config file; see L{IsValidDeliverableClass}.
    @rtype: C{str}
    """
    return Deliverable.DELIVERABLE_CONFIG_PREFIX + delivClass

def IsDeliverableSectionName(sectionName):
    """
    Given a L{ConfigSpec<quickrelease.config.ConfigSpec>} section name, return whether it is a deliverable section name.

    @param sectionName: the L{ConfigSpec<quickrelease.config.ConfigSpec>} section.
    @type sectionName: C{str}

    @return: Whether the section name is a defines a deliverable
    @rtype: C{bool}
    """
    return sectionName.startswith(Deliverable.DELIVERABLE_CONFIG_PREFIX)

def IsValidDeliverableClass(config, delivClass):
    """
    Given a L{Deliverable} class name, determine whether the L{ConfigSpec<quickrelease.config.ConfigSpec>} section that would define exists and is propery formed.
    
    @param config: The config file to check for the given deliverable section in
    @type config: L{ConfigSpec<quickrelease.config.ConfigSpec>} reference

    @param delivClass: The deliverable class name
    @type delivClass: C{str}

    @return: Does the given L{ConfigSpec<quickrelease.config.ConfigSpec>} contain a validly-formed L{Deliverable} definition for the given deliverable class name.
    @rtype: C{bool}
    """
    try:
        sectionItems = config.GetSectionItems(DeliverableSectionNameFromClass(
         delivClass))
    except ValueError:
        return False

    return 'name' in sectionItems or 'regex' in sectionItems
