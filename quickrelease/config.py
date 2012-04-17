# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

import ConfigParser
import os
import re

from quickrelease import constants
from quickrelease.exception import ReleaseFrameworkError

class ConfigSpecError(ReleaseFrameworkError):
    NO_OPTION_ERROR = 0
    INTERPOLATION_MISSING_OPTION_ERROR = 1
    INTERPOLATION_SYNTAX_ERROR = 2
    COERCION_TYPE_ERROR = 3
    NO_SECTION_ERROR = 4
    PARSE_ERROR = 5

    def __init__(self, errorStr, details=None):
         ReleaseFrameworkError.__init__(self, errorStr, details)

    def __str__(self):
         return "ConfigSpec Error: " + ReleaseFrameworkError.__str__(self)

OVERRIDES_DISABLED_ERR_STR = ("Commandline variable overrides are not enabled "
 "in config file %s; enable them by setting 'allow_config_overrides' in the "
 "default section.")

class ConfigSpec(object):
    DEFAULT_SECTION = 'DEFAULT'
    CONFIG_SECTION_DELIMETER = ':'
    DELIV_SECTION_PREFIX = 'deliverable'
    PARTNER_SECTION_PREFIX = 'partner'

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
     section=DEFAULT_SECTION, overrides=()):

        if configFile is None:
            raise ConfigSpecError("No config file specified.")
        elif not os.path.isfile(configFile):
            raise ConfigSpecError("Invalid config file specified.")

        self._configFile = configFile
        self._configSpec = ConfigParser.SafeConfigParser()
        self._rootDir = rootDir
        self._currentSection = section

        # By default, overrides are not allowed.
        self._allowOverrides = False

        # Override hash given from the commandline (i.e. -D)
        self._clOverrides = {}

        try:
            self._configSpec.read(configFile)
        except ConfigParser.Error, ex:
            raise ConfigSpec._ConvertToConfigParserError(ex)

        if section != ConfigSpec.DEFAULT_SECTION:
            if self.section not in self.sectionList:
                raise ConfigSpecError("Invalid initial section '%s'" %
                 (section))

        self._ResetPartnerDefaultSectionVars()
  
        try:
            self._allowOverrides = self.SectionGet(ConfigSpec.DEFAULT_SECTION,
             'allow_config_overrides', bool)
        except ConfigSpecError, ex:
            if ConfigSpecError.NO_OPTION_ERROR != ex.details:
                raise ex

        if len(overrides) != 0:
            if not self._allowOverrides:
                raise ConfigSpecError(OVERRIDES_DISABLED_ERR_STR % (configFile))

            for o in overrides:
                try:
                    if not re.match('^(\w[\w\-_]*:)*[\w\-_]+=[\w\-_\.]+$', o):
                        raise ValueError()

                    (overrideKey, overrideVal) = o.split('=')
                except ValueError:
                    raise ConfigSpecError("Invalid commandline override: %s"
                     % (o))

                overrideSection = overrideName = None
                keyParts = overrideKey.split(
                 ConfigSpec.CONFIG_SECTION_DELIMETER)

                if 1 == len(keyParts):
                    overrideSection = ConfigSpec.DEFAULT_SECTION
                    overrideName = overrideKey
                else:
                    overrideName = keyParts.pop()
                    overrideSection = ConfigSpec.CONFIG_SECTION_DELIMETER.join(
                     keyParts)

                overrideSection.strip()
                overrideName.strip()

                #print "overrideSection: %s" % (overrideSection)
                #print "overrideName: %s" % (overrideName)
                #print "overrideValue: %s" % (overrideVal)

                if not self._clOverrides.has_key(overrideSection):
                    self._clOverrides[overrideSection] = {}

                self._clOverrides[overrideSection][overrideName] = overrideVal

        # DBUG
        #print "Commandline overrides: "
        #pprint.pprint(self._clOverrides)
        #print "Initial defaults: "
        #pprint.pprint(self.GetRawConfig().defaults())

    def _GetRootDir(self): return self._rootDir
    def _GetRawConfig(self): return self._configSpec
    def _GetConfigFile(self): return self._configFile
    def _GetSection(self): return self._currentSection
    def _GetSectionList(self): return self.rawConfig.sections()

    def _SetSection(self, newSection):
        newSection = newSection.strip()
        if self.section == newSection:
            return

        if (newSection.lower() != ConfigSpec.DEFAULT_SECTION.lower() and
         (not self.rawConfig.has_section(newSection))):
            raise ConfigSpecError("Non-existent config spec section: %s" %
             (newSection), ConfigSpecError.NO_SECTION_ERROR)
        self._currentSection = newSection

    def GetSectionItems(self, sectionName=None):
        if sectionName is None:
            sectionName = self.section

        # TODO: include overrides
        try:
            return list(x[0] for x in self.rawConfig.items(sectionName))
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

    def GetSectionElements(self, sectionName=None):
        if sectionName is None:
            sectionName = self.section

        # TODO: include overrides
        try:
            return self.rawConfig.items(sectionName)
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)
                             
    rootDir = property(_GetRootDir)
    configFile = property(_GetConfigFile)
    rawConfig = property(_GetRawConfig)
    section = property(_GetSection, _SetSection)
    sectionList = property(_GetSectionList)
    sectionItems = property(GetSectionItems)
    sectionElements = property(GetSectionElements)

    def _ResetPartnerDefaultSectionVars(self):
        for key in self.rawConfig.defaults().keys():
            if re.match('^PARTNER_', key, re.I):
                self.rawConfig.remove_option(ConfigSpec.DEFAULT_SECTION, key)

        # DBUG
        # pprint.pprint(self.rawConfig.defaults())

    def SetPartnerSection(self, partner):
        if not self.ValidPartner(partner):
            raise ConfigSpecError("Invalid/unknown partner: %s" % (partner))

        partnerSectionName = self._GetPartnerSectionName(partner)
        self.section = partnerSectionName

        # We do this so different variables from other partner sections don't
        # pollute the default variable namespace
        self._ResetPartnerDefaultSectionVars()

        for item in self.sectionElements:
            self.rawConfig.set(ConfigSpec.DEFAULT_SECTION,
             "PARTNER_%s" % (item[0]), item[1])

        if self._clOverrides.has_key(partnerSectionName):
            for overrideKey in self._clOverrides[partnerSectionName]:
                self.rawConfig.set(ConfigSpec.DEFAULT_SECTION,
                 "PARTNER_%s" % (overrideKey),
                 self._clOverrides[partnerSectionName][overrideKey])

    @staticmethod
    def _GetPartnerSectionName(partnerName):
        return (ConfigSpec.PARTNER_SECTION_PREFIX +
         ConfigSpec.CONFIG_SECTION_DELIMETER + partnerName)

    @staticmethod
    def _IsPartnerSection(sectionName):
       return (re.match('^%s%s' % (ConfigSpec.PARTNER_SECTION_PREFIX,
        ConfigSpec.CONFIG_SECTION_DELIMETER), sectionName) is not None)

    @staticmethod
    def _GetDeliverableSectionName(delivName):
        return (ConfigSpec.DELIV_SECTION_PREFIX + 
         ConfigSpec.CONFIG_SECTION_DELIMETER + delivName)

    def ValidDeliverable(self, deliverable):
        return (self._GetDeliverableSectionName(deliverable) in
         self.sectionList)

    def ValidPartner(self, partner):
        return self._GetPartnerSectionName(partner) in self.sectionList

    def PartnerGet(self, partner, name, coercion=None, interpolation={}):
        return self.SectionGet(self._GetPartnerSectionName(partner),
                                      name,
                                      coercion,
                                      interpolation)

    def SectionGet(self, section, name, coercion=None, interpOverrides={}):
        origSection = self.section

        try:
            self.section = section
            value = self.Get(name, coercion, interpOverrides)
        finally:
            self.section = origSection

        return value

    def Get(self, name, coercion=None, interpOverrides={}):
        getRawValues = interpOverrides is None
        overrides = None

        if coercion not in (bool, str, int, float, list, dict, None):
            raise ConfigSpecError("Invalid coercion type specified: %s" %
             (coercion), ConfigSpecError.COERCION_TYPE_ERROR)

        # Overrides/raw values aren't supported by the underlying
        # ConfigParser class, so skip all the override stuff and fast-track
        # coercions of this type
        if coercion in (bool, int, float):
            if getRawValues or len(interpOverrides.keys()) != 0:
                raise ConfigSpecError("Raw values and overrides are not "
                 "compatible with type coercions for bool, int, or float.")

            try:
                if coercion is bool:
                    return self.rawConfig.getboolean(self.section, name)
                elif coercion is int:
                    return self.rawConfig.getint(self.section, name)
                elif coercion is float:
                    return self.rawConfig.getfloat(self.section, name)
            except ConfigParser.Error, ex:
                raise self._ConvertToConfigParserError(ex)

        if (not getRawValues and len(interpOverrides.keys()) != 0 and
         not self._allowOverrides):
            raise ConfigSpecError(OVERRIDES_DISABLED_ERR_STR % 
             (self.configFile))

        # _And_ we have to do this here so variables that consist of other
        # (interpolated) variables correctly pick up the overrides specified
        # in the environment.
        envCurrentSectionOverrides = {}
        envDefaultSectionOverrides = {}
        
        try:
            envCurrentSectionOverrides = self._clOverrides[self.section]
        except KeyError:
            pass

        try:
            envDefaultSectionOverrides = self._clOverrides[
             ConfigSpec.DEFAULT_SECTION]
        except KeyError:
            pass

        try:
            # ORDER MATTERS HERE: 
            # the dict() conversion takes the last item if there
            # is any overlap, so we want the overrides in the following 
            # order:
            # -- Passed in to the function
            # -- Specified as a section override
            # -- specified as a default section override
            overrides = dict(envDefaultSectionOverrides.items() +
                             envCurrentSectionOverrides.items() +
                             interpOverrides.items())
        except TypeError:
            raise ConfigSpecError("Invalid interpolation overrides "
             "specified; must be convertable a dictionary.",
             ConfigSpecError.COERCION_TYPE_ERROR)

        if not self._allowOverrides:
            assert 0 == len(overrides.keys()), ("ConfigSpec variable overrides "
             "disabled, but slipped in anyway.")

        # We handle these above, but assert it, just in case:
        assert coercion not in (bool, int, float), ("bool, int, or float "
         "coercion slipped through?")

        try:
            confVal = self.rawConfig.get(self.section, name, getRawValues,
             overrides)
            if coercion is list:
                return confVal.split()
            elif coercion is dict:
                return self._ConfStringToDict(confVal)
            elif coercion is None or coercion is str:
                return confVal
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

        assert False, "Unreachable (or should be...)"

    def _ConvertToConfigParserError(self, err):
        errType = type(err)
        errCode = None

        if errType is ConfigParser.NoSectionError:
            errCode = ConfigSpecError.NO_SECTION_ERROR
        elif errType is ConfigParser.NoOptionError:
            errCode = ConfigSpecError.NO_OPTION_ERROR
        elif errType is ConfigParser.InterpolationMissingOptionError:
            errCode = ConfigSpecError.INTERPOLATION_MISSING_OPTION_ERROR
        elif errType is ConfigParser.InterpolationSyntaxError:
            errCode = ConfigSpecError.INTERPOLATION_SYNTAX_ERROR
        elif errType is ConfigParser.ParsingError:
            errCode = ConfigSpecError.PARSE_ERROR

        if errCode is None:
            return err
        else:
            return ConfigSpecError(err.message, errCode)

    # This method may seem a little convoluted, but to get the type of error
    # reporting we wanted, we decided to parse the string manually, in two 
    # phases. A couple of initial impl's were done using regular expressions,
    # but they didn't provide the information we wanted to be able to report 
    # to the user about the format error in their config file.
    def _ConfStringToDict(confStr):
        retDict = {}

        dictParts = []
        i = 0

        confStr = confStr.strip()
        while i < len(confStr):
            part = confStr[i:]
            #print part
            partStart = part.find('[')

            if partStart == -1:
                raise ConfigSpecError("Malformed dictionary element: %s" %
                 (part))
      
            partEnd = part.find(']', partStart)

            if partEnd == -1:
                raise ConfigSpecError("Malformed dictionary element2: %s" %
                 (part))
     
            # without brackets
            #   keyValuePair = dictStr[i + partStart + 1:i + partEnd]
            # with brackets
            keyValuePair = confStr[i + partStart:i + partEnd + 1]

            # Ignore empty key/value pairs
            if len(keyValuePair[1:len(keyValuePair) - 1].strip()) > 0:
                dictParts.append(keyValuePair)
            i += partEnd + 1

        for fullKey in dictParts:
            keyPart = fullKey[1:len(fullKey) - 1]
            keyPart = keyPart.lstrip()

            keyPartSplit = re.split('\s+', keyPart, 1)
            keyName = keyPartSplit[0]
            if len(keyPartSplit) != 2:
                raise ConfigSpecError("Missing dictionary value for key %s: %s"
                 % (keyName, fullKey))

            keyValue = keyPartSplit[1].lstrip()
            if 0 == len(keyValue):
                raise ConfigSpecError("Missing dictionary value for key %s: %s"
                 % (keyName, fullKey))

            retDict[keyName] = keyValue

        return retDict

