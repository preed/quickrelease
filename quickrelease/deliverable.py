# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import copy
import os
import re

from quickrelease.config import ConfigSpecError, ConfigSpec
from quickrelease.utils import ImportModule, ImportFunction

class Deliverable(object):
    DELIVERABLE_SECTION_PREFIX = 'deliverable'
    DELIVERABLE_CONFIG_PREFIX = (DELIVERABLE_SECTION_PREFIX +
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

        self.configSection = DeliverableSectionNameFromClass(deliverableClass)
        self.deliverableClass = deliverableClass
        self.queriedDeliverableClass = None
        self.file = deliverableFile
        self.regex = None
        self.name = None
        self.filterAttributes = None
        self.attributes = []
        self.attributeHandlers = {}

        deliverableSectionItems = config.GetSectionItems(self.configSection)

        if 'name' in deliverableSectionItems:
            self.name = config.SectionGet(self.configSection, 'name').strip()

        if 'regex' in deliverableSectionItems:
            self.regex = config.SectionGet(self.configSection, 'regex').strip()

        if self.regex is None and self.name is None:
            raise ConfigSpecError(self.ERROR_STR_NEED_NAME_OR_REGEX %
             (deliverableClass))

        if 'attributes' in deliverableSectionItems:
            self.attributes = config.SectionGet(self.configSection,
             'attributes', list)

        for attr in self.attributes:
            attributeValue = None
            attributeType = None

            if ('attrib_%s_handler' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_CALLBACK
                attributeValue = config.SectionGet(self.configSection,
                 'attrib_%s_handler' % (attr))
            elif ('attrib_%s_regex' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_REGEX
                attributeValue = config.SectionGet(self.configSection,
                 'attrib_%s_regex' % (attr))
            elif ('attrib_%s_value' % (attr)) in deliverableSectionItems:
                attributeType = Deliverable.ATTRIB_TYPE_VALUE
                attributeValue = config.SectionGet(self.configSection,
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
                         self.deliverableClass, attr, str(ex)))

            elif (attributeType == Deliverable.ATTRIB_TYPE_REGEX or
             attributeType == Deliverable.ATTRIB_TYPE_VALUE):
                attributeHandlerDescriptor['handler'] = attributeValue

                # Hacky
                if attributeType == Deliverable.ATTRIB_TYPE_REGEX:
                    regexFlags = 0
                    try:
                        regexFlagsStr = config.SectionGet(self.configSection,
                         'regexflags').strip()
                        regexFlags = eval(regexFlagsStr) 
                    except ConfigSpecError:
                        if ex.details != ConfigSpecError.NO_OPTION_ERROR:
                            raise ex

                    attributeHandlerDescriptor['regexFlags'] = regexFlags
            else:
                assert False, "Unknown attribute handler type: %s" % (
                 attributeType)

            self.attributeHandlers[attr] = attributeHandlerDescriptor

        if 'filter_attributes' in deliverableSectionItems:
            self.filterAttributes = config.SectionGet(self.configSection,
             'filter_attributes', list)

        if self.filterAttributes is not None:
            for fa in self.filterAttributes:
                if fa not in self.attributes:
                    raise ConfigSpecError("Deliverable class '%s' defines "
                     "invalid filter attribute '%s'" % (deliverableClass, fa))

    def __rep__(self):
        return "<class %s: %s (%s)>" % (self.__class__, self.GetName(),
         self.GetLocation())

    def __str__(self):
        return self.GetLocation()

    def GetName(self):
        return self.deliverableClass

    def GetQueriedName(self):
        return self.queriedDeliverableClass

    def GetLocation(self):
        return self.file

    def GetFileName(self):
        return os.path.basename(self.GetLocation())

    def GetRegex(self):
        return self.regex

    def GetFilterAttributes(self):
        if self.filterAttributes is None:
            return None
        else:
            return tuple(self.filterAttributes)

    def GetAttributes(self):
        return tuple(self.attributes)

    def GetAttribute(self, attribute):
        if attribute not in self.attributes:
            raise ValueError("Deliverable class '%s' has no attribute '%s" %
             (self.GetName(), attribute))

        handlerType = self.attributeHandlers[attribute]['type']
  
        if handlerType == Deliverable.ATTRIB_TYPE_VALUE:
            return self.attributeHandlers[attribute]['handler']
        elif handlerType == Deliverable.ATTRIB_TYPE_REGEX:
            attribMatch = re.search(
             self.attributeHandlers[attribute]['handler'], self.GetFileName(),
             self.attributeHandlers[attribute]['regexFlags'])

             if attribMatch is None:
                 return None
             elif len(attribMatch.groups()) == 1:
                 return attribMatch.group(1)
             else:
                 return attribMatch.groups()
        elif handlerType == Deliverable.ATTRIB_TYPE_CALLBACK:
            return self.attributeHandlers[attribute]['handler'](self)
        else:
            assert False, "Unknown attribute handler type: %s" % (handlerType)

def FindDeliverables(deliverableDir, config):
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
                    except ConfigSpecError:
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
    if deliverableDir is None:
        Deliverable._gDeliverablesCache.clear()
    else:
        try:
            del Deliverable._gDeliverablesCache[deliverableDir]
        except KeyError:
            raise ValueError("Deliverable directory %s not in cache" %
             (deliverableDir))

def GetDeliverableSections(config):
    retSections = []

    for section in config.GetSectionList():
        if IsDeliverableSectionName(section):
            retSections.append(section)

    return retSections

def DeliverableClassFromSectionName(sectionName):
    return re.sub('^%s' % (Deliverable.DELIVERABLE_CONFIG_PREFIX), '',
     sectionName)

def DeliverableSectionNameFromClass(delivClass):
    return Deliverable.DELIVERABLE_CONFIG_PREFIX + delivClass

def IsDeliverableSectionName(sectionName):
    return sectionName.startswith(Deliverable.DELIVERABLE_CONFIG_PREFIX)

def IsValidDeliverableClass(config, delivClass):
    try:
        sectionItems = config.GetSectionItems(DeliverableSectionNameFromClass(
         delivClass))
    except ValueError:
        return False

    return 'name' in sectionItems or 'regex' in sectionItems
