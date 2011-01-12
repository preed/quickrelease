
import ConfigParser
import os

from quickrelease import constants
from quickrelease.exception import ReleaseFrameworkError

class ConfigSpecError(ReleaseFrameworkError):
   def __init__(self, errorStr, details=None):
      ReleaseFrameworkError.__init__(self, errorStr, details)

   def __str__(self):
      return "ConfigSpec Error: " + ReleaseFrameworkError.__str__(self)

class ConfigSpec:
   DEFAULT_STARTING_SECTION = 'DEFAULT'
   CONFIG_SECTION_DELIMETER = ':'

   @staticmethod
   def GetConstant(name):
      value = os.getenv(name)

      if value is not None:
         if name in constants.CONSTANTS_FROM_ENV_HANDLERS:
            return constants.CONSTANTS_FROM_ENV_HANDLERS[name](value)
         else:
            return value

      if name in constants.QUICKRELEASE_CONSTANTS:
         return constants.QUICKRELEASE_CONSTANTS[name]

      raise ConfigSpecError("Undefined constant '%s'" % (name))

   @staticmethod
   def GetDefinedConstants():
      return constants.QUICKRELEASE_CONSTANTS.keys()

   def __init__(self, configFile, rootDir=os.getcwd(),
    section=DEFAULT_STARTING_SECTION):

      if configFile is None:
         raise ConfigSpecError("No config file specified.")
      elif not os.path.isfile(configFile):
         raise ConfigSpecError("Invalid config file specified.")

      self.configSpec = ConfigParser.SafeConfigParser()
      self.rootDirectory = rootDir
      self.currentSection = section
      self.defaultSection = section

      try:
         self.configSpec.read(configFile)
      except ConfigParser.ParsingError, ex:
         raise ConfigSpecError(str(ex))

      if section != ConfigSpec.DEFAULT_STARTING_SECTION:
         if self.GetSection() not in self.GetSectionList():
            raise ConfigSpecError("Invalid initial section '%s'" %
             (self.GetSection()))
   
   def GetRootDir(self):
      return self.rootDirectory

   def GetRawConfig(self):
      return self.configSpec
   
   def GetSectionList(self):
      return self.configSpec.sections()

   def GetSection(self):
      return self.currentSection

   def GetDefaultSection(self):
      return self.defaultSection

   def SetSection(self, newSection):
      if self.GetSection() == newSection:
         return

      if (newSection.lower() != 'default' and
       (not self.configSpec.has_section(newSection))):
         raise ConfigSpecError("Non-existent config spec section: %s" %
          (newSection), 'INVALID_SECTION')
      self.currentSection = newSection

   def SetPartnerSection(self, partner):
      if not self.ValidPartner(partner):
         raise ConfigSpecError("Invalid/unknown partner: %s" % (partner))

      self.SetSection(self._GetPartnerSectionName(partner))

   @staticmethod
   def _GetPartnerSectionName(partnerName):
      return 'partner' + ConfigSpec.CONFIG_SECTION_DELIMETER + partnerName
  
   @staticmethod
   def _GetDeliverableSectionName(delivName):
      return 'deliverable' + ConfigSpec.CONFIG_SECTION_DELIMETER + delivName

   def ValidDeliverable(self, deliverable):
      return (self._GetDeliverableSectionName(deliverable) in
       self.GetSectionList())

   def ValidPartner(self, partner):
      return self._GetPartnerSectionName(partner) in self.GetSectionList()

   def PartnerGet(self, partner, name, coercion=None, interpolation=()):
      return self.SectionGet(self._GetPartnerSectionName(partner),
                             name,
                             coercion,
                             interpolation)

   def SectionGet(self, section, name, coercion=None, interpOverrides=()):
      origSection = self.GetSection()
      self.SetSection(section)

      try:
         value = self.Get(name, coercion, interpOverrides)
      except ConfigSpecError, ex:
         raise ex
      finally:
         self.SetSection(origSection)

      return value

   def Get(self, name, coercion=None, interpOverrides=()):
      getRawValues = False
      overrides = None

      if interpOverrides is None:
         getRawValues = True
      else:
         try:
            # Attempt to convert our argument to a tuple for type-checking
            # purposes.
            overrides = tuple(interpOverrides)
         except TypeError:
            raise ConfigSpecError("Invalid interpolation overrides "
             "specified; must be convertable to a tuple.")

      try:
         if coercion is bool:
            return self.configSpec.getboolean(self.currentSection, name)
         elif coercion is int:
            return self.configSpec.getint(self.currentSection, name)
         elif coercion is float:
            return self.configSpec.getfloat(self.currentSection, name)
         elif coercion is list:
            return self.configSpec.get(self.currentSection, name,
             getRawValues, overrides).split()
         elif coercion is None:
            return self.configSpec.get(self.currentSection, name,
             getRawValues, overrides)

         raise ConfigSpecError("Invalid coercion type specified: %s" %
          (coercion))
      except ConfigParser.NoOptionError, ex:
         raise ConfigSpecError("Undefined config variable '%s' requested "
          "from section %s" % (name, self.currentSection), ex)
      except ConfigParser.InterpolationSyntaxError, ex:
         raise ConfigSpecError(str(ex), ex)

   def GetAll(self):
      return self.configSpec.items(self.currentSection)
