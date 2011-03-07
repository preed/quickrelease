
import copy
import os
import re
import types

from quickrelease.config import ConfigSpecError, ConfigSpec

class Deliverable(object):
   DELIVERABLE_SECTION_PREFIX = 'deliverable'
   DELIVERABLE_CONFIG_PREFIX = (DELIVERABLE_SECTION_PREFIX +
    ConfigSpec.CONFIG_SECTION_DELIMETER)

   ERROR_STR_NEED_NAME_OR_REGEX = ("Deliverable class '%s' must define a name "
    "or a regex for the deliverable.")

   _gDeliverablesCache = {}

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
         raise ValueError("Non-existent file passed to Deliverable constructor")
      elif not IsDeliverableSection(config, deliverableClass):
         raise ValueError("Non-existent deliverable class passed to "
          "Deliverable constructor: %s" % deliverableClass)

      self.configSection = DeliverableSectionNameFromClass(deliverableClass)
      self.deliverableClass = deliverableClass
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
         self.attributes = config.SectionGet(self.configSection, 'attributes',
          list)

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
            try:
               attributeHandlerModParts = attributeValue.split('.')
               mod = __import__('.'.join(attributeHandlerModParts[:-1]))
               for comp in attributeHandlerModParts[1:]:
                  mod = getattr(mod, comp)

               attributeHandlerDescriptor['handler'] = mod
            except NameError, ex:
               raise ConfigSpecError("Deliverable class '%s' defines an "
                "attribute callback handler for attribute '%s', but the "
                "callback is undefined: %s" % (self.deliverableClass, attr,
                str(ex)))
         elif (attributeType == Deliverable.ATTRIB_TYPE_REGEX or
          attributeType == Deliverable.ATTRIB_TYPE_VALUE):
            attributeHandlerDescriptor['handler'] = attributeValue
         else:
            assert False, "Unknown attribute handler type: %s" % (attributeType)

         self.attributeHandlers[attr] = attributeHandlerDescriptor

      if 'filter_attributes' in deliverableSectionItems:
         self.filterAttributes = config.SectionGet(self.configSection,
          'filter_attributes', list)

      if self.filterAttributes is not None:
         for fa in self.filterAttributes:
            if fa not in self.attributes:
               raise ConfigSpecError("Deliverable class '%s' defines invalid "
                "filter attribute '%s'" % (deliverableClass, fa))

   def __str__(self):
      return self.GetLocation()

   def GetName(self):
      return self.deliverableClass

   def GetLocation(self):
      return self.file

   def GetFileName(self):
      return os.path.basename(self.GetLocation())

   def GetRegex(self):
      return self.regex

   def GetFilterAttributes(self):
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
         attribMatch = re.search(self.attributeHandlers[attribute]['handler'],
          self.GetFileName())

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
      ignoreUndefinedDeliverables = config.Get('ignore_undefined_deliverables',
       bool)
   except ConfigSpecError, ex:
      if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
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

            try: 
               delivName = config.SectionGet(section, 'name').strip()
               matchType = 'name'
            except ConfigSpecError, ex:
               if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
                  raise ex

               try: 
                  delivRegex = config.SectionGet(section, 'regex').strip()
                  matchType = 'regex'
               except ConfigSpecError, ex:
                  if ex.GetDetails() == ConfigSpecError.NO_OPTION_ERROR:
                     raise ConfigSpecError(
                      Deliverable.ERROR_STR_NEED_NAME_OR_REGEX %
                      DeliverableClassFromSectionName(section))
                  else:
                     raise ex

            #print "f is %s, name is %s, regex is %s" % (f, delivName, delivRegex)          
            if ((delivName is not None and f == delivName) or 
             (delivRegex is not None and re.search(delivRegex, f))):
               try:
                 subclassType = config.SectionGet(section,
                  'subclass').strip()
               except ConfigSpecError, ex:
                  if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
                     raise ex
                  pass

               delivClassDescription = { 'type': matchType,
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
                  subclassParts = delivDesc['subclass'].split('.')
                  mod = __import__('.'.join(subclassParts[:-1]))
                  for comp in subclassParts[1:]:
                     mod = getattr(mod, comp)

                  newDelivObj = mod(delivDesc['file'], delivDesc['class'],
                   config)
              
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
               assert fileLoc == delivDesc['file'], ("Deliverable file name "
                "mismatch (%s vs %s)?" % (fileLoc, delivDesc['file']))

               matchedClassList.append("%s (matched via %s)" % (
                delivDesc['class'], delivDesc['type']))

            raise ConfigSpecError("More than one deliverable class for "
             "the file %s: %s" % (fileLoc, ', '.join(matchedClassList)))

   Deliverable._gDeliverablesCache[deliverableDir] = tuple(deliverables)
   return len(tuple(deliverables))

def GetAllDeliverables(deliverableDir=None):
   if deliverableDir is not None:
      if not Deliverable._gDeliverablesCache.has_key(deliverableDir):
         raise ValueError("Directory %d has not been scanned for deliverables "
          "yet; use FindDeliverables()" % (deliverableDir))

      return tuple(Deliverable._gDeliverablesCache[deliverableDir])
   else:
      cacheKeys = Deliverable._gDeliverablesCache.keys()
      if len(cacheKeys) == 0:
         raise ValueError("No deliverables found yet; prime cache with
          FindDeliverables()" % (deliverableDir))

      allDeliverables = []

      for dDirs in cacheKeys:
         for deliv in Deliverable._gDeliverablesCache[dDirs]:
            allDeliverables.append(deliv)

      return tuple(allDeliverables)

def GetDeliverables(deliverableClass, deliverableDir=None):
   filterValues = deliverableClass.split(':')
   possibleDelivs = []

   for deliv in GetAllDeliverables(deliverableDir):
      if filterValues[0] == deliv.GetName():
         possibleDelivs.append(deliv)

   filteredDeliverableList = []
   for pd in possibleDelivs:
      filterNames = pd.GetFilterAttributes()
   
      if filterNames is None and len(filterValues) > 1:
         raise ValueError("GetDeliverables passed filter '%s' for a "
          "deliverable class that defines no filter attributes" %
          ':'.join(filterValues[1:]))

      skipThisDeliv = False
      for ndx in range(len(filterValues))[1:]:
         if pd.GetAttribute(filterNames[ndx]) != filterValues[ndx]:
            skipThisDeliv = True
            break

      if skipThisDeliv:
         continue

      filteredDeliverableList.append(pd)

   return filteredDeliverableList

def GetDeliverable(deliverableClass, deliverableDir=None):
   possibleDelivs = GetDeliverables(deliverableClass, deliverableDir)

   if len(possibleDelivs) == 0:
      return None
   elif len(possibleDelivs) > 1:
      raise ConfigSpecError("More than one deliverable matched for "
       "deliverable class %s: %s" % (deliverableClass,
       ', '.join(possibleDelivs)))
   else:
      return possibleDelivs[0]

def FlushDeliverableCache(deliverableDir=None):
   if deliverableDir is None:
      Deliverable._gDeliverablesCache.clear()
   else:
      try:
         del Deliverable._gDeliverablesCache[deliverableDir]
      except KeyError:
         raise ValueError("Deliverable directory %d not in cache" %
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

def IsDeliverableSection(config, delivClass):
   sectionItems = config.GetSectionItems(DeliverableSectionNameFromClass(
    delivClass))
   return 'name' in sectionItems or 'regex' in sectionItems
