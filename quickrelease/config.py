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

class ConfigSpec:
    DEFAULT_STARTING_SECTION = 'DEFAULT'
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
     section=DEFAULT_STARTING_SECTION, overrides=()):

        if configFile is None:
            raise ConfigSpecError("No config file specified.")
        elif not os.path.isfile(configFile):
            raise ConfigSpecError("Invalid config file specified.")

        self.configFile = configFile
        self.configSpec = ConfigParser.SafeConfigParser()
        self.rootDirectory = rootDir
        self.currentSection = section
        self.defaultSection = section

        # Overrides are not allowed by default.
        self.allowOverrides = False

        # Override hash given from the commandline (i.e. -D)
        self._clOverrides = {}

        try:
            self.configSpec.read(configFile)
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

        if section != ConfigSpec.DEFAULT_STARTING_SECTION:
            if self.GetSection() not in self.GetSectionList():
                raise ConfigSpecError("Invalid initial section '%s'" %
                 (self.GetSection()))

        # Need to prefill these in, so they don't blow up, but since
        # SetActivePartner hasn't been called yet, they're all blank
        self._ResetPartnerDefaultSectionVars()
  
        try:
            self.allowOverrides = self.Get('allow_config_overrides', bool)
        except ConfigSpecError, ex:
            if ConfigSpecError.NO_OPTION_ERROR != ex.details:
                raise ex

        if len(overrides) != 0:
            if not self.allowOverrides:
                raise ConfigSpecError(OVERRIDES_DISABLED_ERR_STR % (configFile))

            for o in overrides:
                try:
                    if not re.match('^(\w.+:)?[\w\-_]+=[\w\-_\.]+$', o):
                        raise ValueError()

                    (overrideKey, overrideVal) = o.split('=')
                except ValueError:
                    raise ConfigSpecError("Invalid commandline override: %s"
                     % (o))

                overrideSection = overrideName = None
                try:
                    (overrideSection, overrideName) = overrideKey.split(":")
                except ValueError:
                    overrideSection = self.defaultSection
                    overrideName = overrideKey

                overrideSection.strip()
                overrideName.strip()

                if not self._clOverrides.has_key(overrideSection):
                    self._clOverrides[overrideSection] = {}

                self._clOverrides[overrideSection][overrideName] = overrideVal

    def GetRootDir(self):
        return self.rootDirectory

    def GetRawConfig(self):
        return self.configSpec
    
    def GetSectionList(self):
        return self.configSpec.sections()

    def GetSection(self):
        return self.currentSection

    def GetSectionItems(self, sectionName=None):
        if sectionName is None:
            sectionName = self.currentSection

        # TODO: include overrides
        try:
            return list(x[0] for x in self.GetRawConfig().items(sectionName))
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

    def GetAll(self, sectionName=None):
        if sectionName is None:
            sectionName = self.currentSection

        # TODO: include overrides
        try:
            return self.GetRawConfig().items(sectionName)
        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

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

    def _ResetPartnerDefaultSectionVars(self):
        for sect in self.GetSectionList():
            if ConfigSpec._IsPartnerSection(sect):
                for opt in self.GetRawConfig().options(sect):
                    #print "Option in %s: %s" % (sect, o)
                    self.GetRawConfig().set(self.GetDefaultSection(),
                     "PARTNER_%s" % (opt), "")
    
    def SetPartnerSection(self, partner):
        if not self.ValidPartner(partner):
            raise ConfigSpecError("Invalid/unknown partner: %s" % (partner))

        self.SetSection(self._GetPartnerSectionName(partner))

        # We do this so different variables from other partner sections don't
        # polute the default variable namespace
        self._ResetPartnerDefaultSectionVars()

        for item in self.GetAll():
            self.GetRawConfig().set(self.GetDefaultSection(),
             "PARTNER_%s" % (item[0]), item[1])

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
         self.GetSectionList())

    def ValidPartner(self, partner):
        return self._GetPartnerSectionName(partner) in self.GetSectionList()

    def PartnerGet(self, partner, name, coercion=None, interpolation={}):
        return self.SectionGet(self._GetPartnerSectionName(partner),
                                      name,
                                      coercion,
                                      interpolation)

    def SectionGet(self, section, name, coercion=None, interpOverrides={}):
        origSection = self.GetSection()

        try:
            self.SetSection(section)
            value = self.Get(name, coercion, interpOverrides)
        finally:
            self.SetSection(origSection)

        return value

    def Get(self, name, coercion=None, interpOverrides={}):
        getRawValues = False
        overrides = None

        if coercion not in (bool, str, int, float, list, None):
            raise ConfigSpecError("Invalid coercion type specified: %s" %
             (coercion), ConfigSpecError.COERCION_TYPE_ERROR)

        if self.allowOverrides:
            # It would be nice to just use ConfigParser's built in ability
            # to handle overrides; unfortunately, if a type-conversion is
            # requested, getboolean/getfloat/etc. don't support such overrides

            override = None
            try:
                override = self._clOverrides[self.currentSection][name]
            except KeyError:
                # Check the default section too...
                try:
                    override = self._clOverrides[self.defaultSection][name]
                except KeyError:
                    pass

            if override is not None:
                if coercion is None:
                    return override
                else:
                    return coercion(override)

        if interpOverrides is None:
            getRawValues = True
        else:
            if not self.allowOverrides and len(interpOverrides.keys()) != 0:
                raise ConfigSpecError(OVERRIDES_DISABLED_ERR_STR % 
                 (self.configFile))

            # _And_ we have to do this here so variables that consist of other
            # (interpolated) variables correctly pick up the overrides specified
            # in the environment.
            envCurrentSectionOverrides = {}
            envDefaultSectionOverrides = {}
        
            try:
                envCurrentSectionOverrides = self._clOverrides[
                 self.currentSection]
            except KeyError:
                pass
            try:
                envDefaultSectionOverrides = self._clOverrides[
                 self.defaultSection]
            except KeyError:
                pass

            try:
                # ORDER MATTERS HERE: 
                overrides = dict(interpOverrides.items() +
                                 envDefaultSectionOverrides.items() +
                                 envCurrentSectionOverrides.items())
            except TypeError:
                raise ConfigSpecError("Invalid interpolation overrides "
                 "specified; must be convertable a dictionary.",
                 ConfigSpecError.COERCION_TYPE_ERROR)

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
            elif coercion is None or coercion is str:
                return self.configSpec.get(self.currentSection, name,
                 getRawValues, overrides)

        except ConfigParser.Error, ex:
            raise self._ConvertToConfigParserError(ex)

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
