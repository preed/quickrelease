# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

r"""quickrelease.config - A representation of a key/value configuration 
specification, selected by the user at runtime.

This module is wrapper around the builtin ConfigParser module. It removes the 
ability to modify the configuration at runtime, and adds some 
quickrelease-specific functionality (definition of "partners" and
"deliverables.")

It also provides methods for retriving defined constants, which may be
overridden in various ways.

The format of the configuration specification is described in the blah blah 
module documentation.
"""

import ConfigParser
import os
import re

from quickrelease import constants
from quickrelease.exception import ReleaseFrameworkError

class ConfigSpecError(ReleaseFrameworkError):
    """
    An exception class representing various errors that can occur with 
    L{ConfigSpec}s.

    It also re-expresses many of 
    L{SafeConfigParser<ConfigParser.SafeConfigParser>}'s exceptions as 
    constants which can be tested for by querying the C{details} property of 
    the exception.
    """

    NO_OPTION_ERROR = 0
    """See L{ConfigParser.NoOptionError}"""
    INTERPOLATION_MISSING_OPTION_ERROR = 1
    """See L{ConfigParser.InterpolationMissingOptionError}"""
    INTERPOLATION_SYNTAX_ERROR = 2
    """See L{ConfigParser.InterpolationSyntaxError}"""
    COERCION_TYPE_ERROR = 3
    """The type requested for a coercion was a non-supported type."""
    NO_SECTION_ERROR = 4
    """See L{ConfigParser.NoSectionError}"""
    PARSE_ERROR = 5
    """See L{ConfigParser.ParsingError}"""

    def __init__(self, errorStr, details=None):
         ReleaseFrameworkError.__init__(self, errorStr, details)

    def __str__(self):
         return "ConfigSpec Error: " + ReleaseFrameworkError.__str__(self)

OVERRIDES_DISABLED_ERR_STR = ("Commandline variable overrides are not enabled "
 "in config file %s; enable them by setting 'allow_config_overrides' in the "
 "default section.")

class ConfigSpec(object):
    """
    A class representing a QuickRelease runtime-specified configuration 
    specification for a process.
    """
    DEFAULT_SECTION = 'DEFAULT'
    CONFIG_SECTION_DELIMETER = ':'
    DELIV_SECTION_PREFIX = 'deliverable'
    PARTNER_SECTION_PREFIX = 'partner'

    @staticmethod
    def GetConstant(name):
        """
        Retrive the named constant from the environment, if it's defined there,
        or from L{quickrelease.constants}. The return type can be a complex
        Python type.

        This provides a way to retrieve some configuration values without
        having direct access to a L{ConfigSpec} handle.

        It also allows those values to be overridden by setting environment
        variables.

        For this reason, it is generally preferable to use instantiated 
        L{ConfigSpec} handles instead of this method. However, this method can
        be (and is) used in places where it's not convenient to obtain one.

        @param  name: The name of the constant to retrieve.
        @type   name: C{str}

        @returns: The value of the requested constant.
        @rtype:   Mixed, depending on how the variable was defined in 
                  L{quickrelease.constants}, or whether a converter was 
                  specified for the variable when obtaining it from the 
                  environment.
        """

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
        """
        @returns: A list of all defined constants. (Does not include constants 
                  available via the environment.)
        @rtype:   C{list}
        """
        return constants.QUICKRELEASE_CONSTANTS.keys()

    def __init__(self, configFile, rootDir=os.getcwd(),
     section=DEFAULT_SECTION, overrides=()):
        """
        Create a handle to a QuickRelease configuration specification
        ("C{ConfigSpec}") for use.

        @param configFile: The ConfigPaser .ini-style file to parse
        @type  configFile: C{str}

        @param rootDir: The "root directory" to use for this config;
        defaults to the current working directory at the time the ConfigSpec is 
        initialized. Is generally used to specify a directory 
        @type  rootDir: C{str}

        @param section: Section to start in. Defaults to the ini file's
        "default" section.
        @type  section: C{str}

        @param overrides: A list of strings representing overrides to apply
        to the given config specification. The expected format for each string
        is: "section:key=value" Section may be omitted, and in this case, the 
        override is added to the default section.

        B{Note}: the allow_config_overrides item B{must} be set in the config 
        file, or an exception will be raised if any are provided. 
        @type  overrides: C{list} of C{str}

        @return:  C{ConfigSpec} reference

        @raise ConfigSpecError: raises C{ConfigSpecError}s exceptions in the
        following cases:
            1. The specified config file to parse is missing or an invalid value
            was specified.
            2. The initial section specifed doesn't exist in the config
            3. Overriding of values is not allowed by the config, but overrides
            were provided.
            4. L{SafeConfigParser<ConfigParser.SafeConfigParser>} errors 
            encountered while parsing the config file may be raised as 
            converted L{ConfigSpecError<quickrelease.config.ConfigSpecError>}s.
        """

        # We have to error check this ourselves because the ConfigParser class
        # doesn't (this is a feature!)
        try:
            if not os.path.isfile(configFile):
                raise ConfigSpecError("Specified config file '%s' missing." %
                 (configFile))
        except TypeError:
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
        """
        @param sectionName: the section to return the list of defined items for;
        defaults to the currently-selected section.
        @type  sectionName: C{str}

        @return:  A list of defined items ("options") in the specified section.
        @rtype:   C{list} of C{str}

        @raise ConfigSpecError: L{SafeConfigParser<ConfigParser.SafeConfigParser>} errors are converted 
        to L{ConfigSpecError<quickrelease.config.ConfigSpecError>} s as 
        appropriate.
        """
        if sectionName is None:
            sectionName = self.section

        # TODO: include overrides
        try:
            return list(x[0] for x in self.rawConfig.items(sectionName))
        except ConfigParser.Error, ex:
            raise ConfigSpec._ConvertToConfigParserError(ex)

    def GetSectionElements(self, sectionName=None):
        """
        @param sectionName: the section to return the list of defined elements
        for; defaults to the currently-selected section.
        @type  sectionName: C{str}

        @return:  A list of defined items ("options") in the specified section.
        @rtype:   C{list} of two-element C{list}: (C{item}, C{value})

        @raise ConfigSpecError: L{SafeConfigParser<ConfigParser.SafeConfigParser>} errors are converted 
        to L{ConfigSpecError<quickrelease.config.ConfigSpecError>}s as 
        appropriate.
        """

        if sectionName is None:
            sectionName = self.section

        # TODO: include overrides
        try:
            return self.rawConfig.items(sectionName)
        except ConfigParser.Error, ex:
            raise ConfigSpec._ConvertToConfigParserError(ex)

    rootDir = property(_GetRootDir)
    """ The root directory set when the configuration specification object was
    created. Read-only.
    @type: C{str}"""

    configFile = property(_GetConfigFile)
    """ The name of the config file loaded when the configuration specification
    object was created. Read-only.
    @type: C{str}"""

    rawConfig = property(_GetRawConfig)
    """The underlying L{SafeConfigParser<ConfigParser.SafeConfigParser>}
    handle. Read-only.
    @type: L{SafeConfigParser<ConfigParser.SafeConfigParser>}"""

    section = property(_GetSection, _SetSection)
    """The current section name.
    @type: C{str}"""

    sectionList = property(_GetSectionList)
    """A C{list} of all defined sections in the configuration specification.
    Read-only.
    @type: C{list}"""
    sectionItems = property(GetSectionItems)
    """A C{list} of all defined items ("options") in the current section.
    Read-only.
    @type: C{list}"""
    sectionElements = property(GetSectionElements)
    """A C{list} of (option, value) lists defined in the current section.
    Read-only.
    @type: C{list}"""

    def _ResetPartnerDefaultSectionVars(self):
        for key in self.rawConfig.defaults().keys():
            if re.match('^PARTNER_', key, re.I):
                self.rawConfig.remove_option(ConfigSpec.DEFAULT_SECTION, key)

        # DBUG
        # pprint.pprint(self.rawConfig.defaults())

    def SetPartnerSection(self, partner):
        """
        Set the C{ConfigSpec}'s current section to that of the named partner.

        This method will also update the default section so all 
        partner-specific variables may be used in other sections by prefacing
        them with C{PARTNER_}.
        
        Example: a section on version numbers includes different suffixes
        for partners. Each partner defines its unique C{version_number_suffix} 
        in its own section. Then, any common section can reference 
        C{PARTNER_version_number_suffix} and the appropriate values will be 
        substituted.

        @param partner: The name of the partner's partner-specific section 
        to switch to.
        @type  partner: C{str}
        """

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
        """
        Determine whether the given deliverable name is "valid," e.g.
        defined in the L{ConfigSpec} provided by the user.

        @type  deliverable: C{str}
        @param deliverable: The name of the deliverable to validate.

        @rtype:   C{bool}
        @return:  Does the given string represent a validly defined
        "deliverable" for the current configuration specification.
        """
        return (self._GetDeliverableSectionName(deliverable) in
         self.sectionList)

    def ValidPartner(self, partner):
        """
        Determine whether the given partner name is "valid," e.g. defined in the
        L{ConfigSpec} provided by the user.

        @param partner: The name of the partner to validate.
        @type  partner: C{str}

        @rtype:   C{bool}
        @return:  Does the given string represent a validly defined "partner"
        for the current configuration specification.
        """
        return self._GetPartnerSectionName(partner) in self.sectionList

    def PartnerGet(self, partner, name, coercion=None, interpolation={}):
        """
        Retrieve the value for the given item name in the specified-partner's
        section.

        Care is taken to ensure that the C{ConfigSpec} handle state is left as
        it was.

        @param partner: The partner to query the partner-section for the
        requested item. 
        @type  partner: C{str}

        @see: L{ConfigSpec.Get()<quickrelease.config.ConfigSpec.Get>} for a 
        comprehensive explanation of this method's other arguments and 
        possible exceptions.
        """
        # TODO: this really needs to call SetPartnerSection() for fully-correct
        # behavior.
        return self.SectionGet(self._GetPartnerSectionName(partner),
                                      name,
                                      coercion,
                                      interpolation)

    def SectionGet(self, section, name, coercion=None, interpOverrides={}):
        """
        Retrieve the value for the given item name in the specified-section.
        Care is taken to ensure that the C{ConfigSpec} handle state is left as
        it was.

        @param section: The name of the section to obtain the requested item
        from.
        @type  section: C{str}

        @see: L{ConfigSpec.Get()<quickrelease.config.ConfigSpec.Get>} for a 
        comprehensive explanation of this method's other arguments and 
        possible exceptions.
        """
        origSection = self.section

        try:
            self.section = section
            value = self.Get(name, coercion, interpOverrides)
        finally:
            self.section = origSection

        return value

    # TODO: when the default section is specified, restrict access to just
    # what defaults() returns
    def Get(self, name, coercion=None, interpOverrides={}):
        """
        Retrieve the value for the given item name in the current section.

        @param name: Name of the option to retrieve.
        @type  name: C{str}

        @param coercion: A Python type instance to coerce the return into.
        Defined coercions exist for C{bool}, C{str}, C{int}, C{float}, C{list},
        and C{dict}; by default, a C{str} is returned.
        @type  coercion: C{type}

        @param interOverrides: If overrides are allowed, a dictionary of 
        key/value pairs to override values for for the current request. If set i
        to None, no L{SafeConfigParser<ConfigParser.SafeConfigParser>}
        interpolation will take place, and the raw values specified in the 
        configuration specification will be returned.
        @type  interpOverrides: C{dict} of key-value pairs to override or 
        C{None}

        @rtype:  C{str}, unless a coercion is specified.
        @return: The option specified in the config specification for the 
        given name in the current section.

        @raise ConfigSpecError: 
        L{SafeConfigParser<ConfigParser.SafeConfigParser>} errors are converted 
        to L{ConfigSpecError<quickrelease.config.ConfigSpecError>}s as 
        appropriate.
        """
       

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
                raise ConfigSpec._ConvertToConfigParserError(ex)

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
                return ConfigSpec._ConfStringToDict(confVal)
            elif coercion is None or coercion is str:
                return confVal
        except ConfigParser.Error, ex:
            raise ConfigSpec._ConvertToConfigParserError(ex)

        assert False, "Unreachable (or should be...)"

    @staticmethod
    def _ConvertToConfigParserError(err):
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
    @staticmethod
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

