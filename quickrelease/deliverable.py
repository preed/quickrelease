
import copy
import os
import re
import types

from config import ConfigSpecError, ConfigSpec

#from quickrelease.steps.TestSteps import ParseAddonName

class Deliverable(object):
   DELIVERABLE_SECTION_CLASS = 'deliverable'
   DELIVERABLE_CONFIG_PREFIX = (DELIVERABLE_SECTION_CLASS +
    ConfigSpec.CONFIG_SECTION_DELIMETER)

   ERROR_STR_NEED_NAME_OR_REGEX = ("Deliverable class '%s' must define a name "
    "or a regex for the deliverable.")

   gDeliverablesCache = None

   def __init__(self, config, deliverableClass, deliverableFile, 
    *args, **kwargs):
      object.__init__(self, *args, **kwargs)

      if not os.path.isabs(deliverableFile):
         raise ValueError("Must provide absolute path to Deliverable "
          "constructor")
      elif not os.path.isfile(deliverableFile):
         raise ValueError("Non-existent file passed to Deliverable constructor")
      elif not Deliverable.IsDeliverableSection(config, deliverableClass):
         raise ValueError("Non-existent deliverable class passed to "
          "Deliverable constructor: %s" % deliverableClass)

      self.configSection = self.DeliverableSectionNameFromClass(
       deliverableClass)
      self.deliverableClass = deliverableClass
      self.file = deliverableFile
      self.regex = None
      self.name = None
      self.filterAttributes = None
      self.attributes = []
      self.attributeHandlers = {}

      try:
         self.name = config.SectionGet(self.configSection, 'name').strip()
      except ConfigSpecError, ex:
         if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
            raise ex
         pass

      try:
         self.regex = config.SectionGet(self.configSection, 'regex').strip()
      except ConfigSpecError, ex:
         if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
            raise ex
         pass

      if self.regex is None and self.name is None:
         raise ConfigSpecError(self.ERROR_STR_NEED_NAME_OR_REGEX %
          (deliverableClass))

      try:
         self.attributes = config.SectionGet(self.configSection, 'attributes',
          list)
      except ConfigSpecError, ex:
         if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
            raise ex
         pass

      for attr in self.attributes:
         attributeRegex = None
         attributeHandler = None

         try:
            attributeHandler = config.SectionGet(self.configSection,
             'attrib_%s_handler' % (attr))
         except ConfigSpecError, ex:
            if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
               raise ex

            try:
               attributeRegex = config.SectionGet(self.configSection,
                'attrib_%s_regex' % (attr))
            except ConfigSpecError:
               if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
                  raise ex
               pass

         if attributeRegex is None and attributeHandler is None:
            raise ConfigSpecError("Deliverable class '%s' defines "
             "attribute '%s', but doesn't define a regex or handler for it." %
             (deliverableClass, attr))
 
         if attributeHandler is not None:
            try:
               attributeHandlerModParts = attributeHandler.split('.')
               mod = __import__('.'.join(attributeHandlerModParts[:-1]))
               components = attributeHandler.split('.')
               for comp in attributeHandlerModParts[1:]:
                  mod = getattr(mod, comp)

               self.attributeHandlers[attr] = mod
            except NameError, ex:
               raise ConfigSpecError("Deliverable class '%s' defines an "
                "attribute handler for attribute '%s', but the handler is "
                "undefined: %s" % (self.deliverableClass, attr, str(ex)))
         elif attributeRegex is not None:
            self.attributeHandlers[attr] = attributeRegex
         else:
            assert False, "Shouldn't reach this"

      try:
         self.filterAttributes = config.SectionGet(self.configSection,
          'filter_attributes', list)
      except ConfigSpecError, ex:
         if ex.GetDetails() != ConfigSpecError.NO_OPTION_ERROR:
            raise ex
         pass

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

      handlerType = type(self.attributeHandlers[attribute])

      if handlerType is str:
         attribMatch = re.search(self.attributeHandlers[attribute],
          self.GetFileName())

         if attribMatch is None:
            return None
         elif len(attribMatch.groups()) == 1:
            return attribMatch.group(1)
         else:
            return attribMatch.groups()

      elif handlerType is types.FunctionType:
         return self.attributeHandlers[attribute](self)
      else:
         assert False, "Non-str, non-function attribute handler: %s" % (
          handlerType)


   @staticmethod
   def FindDeliverables(config, deliverableDir, useCache=True, flushCache=True):
      if not os.path.isdir(deliverableDir):
         raise ValueError("Invalid deliverable directory: %s" % 
          (deliverableDir))

      if (Deliverable.gDeliverablesCache is not None and
       (useCache and not flushCache)):
         return Deliverable.gDeliverablesCache

      deliverables = []
      deliverableSections = Deliverable.GetDeliverableSections(config)

      ignoreUndefinedDeliverables = True 
      try:
         ignoreUndefinedDeliverables = config.Get(
          'ignore_undefined_deliverables', bool)
      except ConfigSpecError:
         pass

      for root, dirs, files in os.walk(deliverableDir):
         for f in files:
            #print "Looking at: %s" % (os.path.join(root, f))
            deliverableDescList = []
            for section in deliverableSections:
               delivRegex = None
               delivName = None
               matchType = None

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
                         Deliverable.DeliverableClassFromSectionName(section))
                     else:
                        raise ex

               if ((delivName is not None and f == delivName) or 
                (delivRegex is not None and re.search(delivRegex, f))):
                  delivClassDescription = { 'type': matchType,
                                            'class' : 
                    Deliverable.DeliverableClassFromSectionName(section),
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
               deliverables.append(Deliverable(config, delivDesc['class'],
                delivDesc['file']))
            else:
               matchedClassList = []
               fileLoc = deliverableDescList[0]['file']
               for delivDesc in deliverableDescList:
                  assert fileLoc == delivDesc['file'], ("Deliverable file name "
                   "mismatch (%s vs %s)?" % (fileLoc, delivDesc['file']))

                  matchedClassList.append("%s (matched via %s)" % (
                   delivDesc['class'], delivDesc['type']))

               raise ConfigSpecError("More than one deliverable class for "
                "the file '%s': %s" % (matchType, ', '.join(matchedClassList)))

      if flushCache: 
         Deliverable.gDeliverablesCache = tuple(deliverables)

      return tuple(deliverables)

   @staticmethod
   def GetAllDeliverables(useCache=True, config=None, deliverableDir=None):
      if Deliverable.gDeliverablesCache is None or not useCache:
         if config is None or deliverableDir is None:
            if useCache:
               raise ValueError("Must call FindDeliverables() before "
                "GetAllDeliverables()")
            else:
               raise ValueError("When not using the deliverable cache, a "
                "ConfigSpec and deliverable directory must be provided")
     
         return Deliverable.FindDeliverables(config, deliverableDir, useCache,
          False)
      
      # check if copy is necessary; may be ok if immutable
      return Deliverable.gDeliverablesCache

   @staticmethod
   def GetDeliverable(deliverableName, useCache=True, config=None,
    deliverableDir=None):

      filterValues = deliverableName.split(':')
      possibleDelivs = []

      for deliv in Deliverable.GetAllDeliverables(useCache, config,
       deliverableDir):
         ## TODO deliverable mask in config, i.e. installer:platform, but make
         ## platform defineable
         if filterValues[0] == deliv.GetName():
            if len(filterValues) == 1:
               return deliv
            else:
               possibleDelivs.append(deliv)

      filteredDeliverableList = []
      for pd in possibleDelivs:
         filterNames = pd.GetFilterAttributes()
         skipThisDeliv = False
         for ndx in range(len(filterValues))[1:]:
            if pd.GetAttribute(filterNames[ndx]) != filterValues[ndx]:
               skipThisDeliv = True
               break

         if skipThisDeliv:
            continue

         filteredDeliverableList.append(pd)

      if len(filteredDeliverableList) == 1:
         return filteredDeliverableList[0]
      else:
         raise ConfigSpecError("More than one deliverable matched for "
          "deliverable name '%s': %s" % (deliverableName,
          ', '.join(filteredDeliverableList)))

   @staticmethod
   def GetDeliverableSections(config):
      retSections = []

      for section in config.GetSectionList():
         if Deliverable.IsDeliverableSectionName(section):
            retSections.append(section)

      return tuple(retSections)

   @staticmethod
   def DeliverableClassFromSectionName(sectionName):
      return re.sub('^%s' % (Deliverable.DELIVERABLE_CONFIG_PREFIX), '',
       sectionName)

   @staticmethod
   def DeliverableSectionNameFromClass(delivClass):
      return Deliverable.DELIVERABLE_CONFIG_PREFIX + delivClass

   @staticmethod
   def IsDeliverableSectionName(sectionName):
      return sectionName.startswith(Deliverable.DELIVERABLE_CONFIG_PREFIX)

   @staticmethod
   def IsDeliverableSection(config, delivClass):
      try:
         config.SectionGet(Deliverable.DeliverableSectionNameFromClass(
          delivClass), 'name')
      except ConfigSpecError:
         try:
            config.SectionGet(Deliverable.DeliverableSectionNameFromClass(
             delivClass), 'regex')
         except ConfigSpecError:
            return False

      return True

