#!/usr/bin/env python
# encoding: utf-8
"""
XMDS2Parser.py

Created by Graham Dennis on 2007-12-29.
Copyright (c) 2007 __MyCompanyName__. All rights reserved.
"""

import re
from xpdeint.ScriptParser import ScriptParser
from xpdeint.ParserException import ParserException, parserWarning
from xpdeint.ParsedEntity import ParsedEntity
from xml.dom import minidom
from xpdeint import RegularExpressionStrings

from xpdeint._ScriptElement import _ScriptElement

from xpdeint.SimulationElement import SimulationElement as SimulationElementTemplate
from xpdeint.Geometry.GeometryElement import GeometryElement as GeometryElementTemplate
from xpdeint.Geometry.FieldElement import FieldElement as FieldElementTemplate
from xpdeint.Geometry._Dimension import _Dimension as Dimension
from xpdeint.Geometry.UniformDimensionRepresentation import UniformDimensionRepresentation
from xpdeint.Geometry.NonUniformDimensionRepresentation import NonUniformDimensionRepresentation

from xpdeint.Vectors.VectorElement import VectorElement as VectorElementTemplate
from xpdeint.Vectors.ComputedVector import ComputedVector as ComputedVectorTemplate
from xpdeint.Vectors.VectorInitialisation import VectorInitialisation as VectorInitialisationZeroTemplate
from xpdeint.Vectors.VectorInitialisationFromCDATA import VectorInitialisationFromCDATA as VectorInitialisationFromCDATATemplate
from xpdeint.Vectors.VectorInitialisationFromXSIL import VectorInitialisationFromXSIL as VectorInitialisationFromXSILTemplate


from xpdeint.Segments.TopLevelSequenceElement import TopLevelSequenceElement as TopLevelSequenceElementTemplate
from xpdeint.SimulationDrivers.DefaultDriver import DefaultDriver as DefaultDriverTemplate
from xpdeint.SimulationDrivers.MultiPathDriver import MultiPathDriver as MultiPathDriverTemplate
from xpdeint.SimulationDrivers.MPIMultiPathDriver import MPIMultiPathDriver as MPIMultiPathDriverTemplate
from xpdeint.SimulationDrivers.DistributedMPIDriver import DistributedMPIDriver as DistributedMPIDriverTemplate

from xpdeint.Segments import Integrators
from xpdeint.Segments.FilterSegment import FilterSegment as FilterSegmentTemplate
from xpdeint.Segments.BreakpointSegment import BreakpointSegment as BreakpointSegmentTemplate
from xpdeint.Segments.SequenceSegment import SequenceSegment as SequenceSegmentTemplate

from xpdeint.Operators.OperatorContainer import OperatorContainer as OperatorContainerTemplate

from xpdeint.Operators.DeltaAOperator import DeltaAOperator as DeltaAOperatorTemplate
from xpdeint.Operators.ConstantIPOperator import ConstantIPOperator as ConstantIPOperatorTemplate
from xpdeint.Operators.NonConstantIPOperator import NonConstantIPOperator as NonConstantIPOperatorTemplate
from xpdeint.Operators.ConstantEXOperator import ConstantEXOperator as ConstantEXOperatorTemplate
from xpdeint.Operators.NonConstantEXOperator import NonConstantEXOperator as NonConstantEXOperatorTemplate
from xpdeint.Operators.FilterOperator import FilterOperator as FilterOperatorTemplate
from xpdeint.Operators.CrossPropagationOperator import CrossPropagationOperator as CrossPropagationOperatorTemplate
from xpdeint.Operators.FunctionsOperator import FunctionsOperator as FunctionsOperatorTemplate


from xpdeint.Features.BinaryOutput import BinaryOutput as BinaryOutputTemplate
from xpdeint.Features.AsciiOutput import AsciiOutput as AsciiOutputTemplate
from xpdeint.MomentGroupElement import MomentGroupElement as MomentGroupTemplate

from xpdeint.Features import Transforms

from xpdeint import Features

from xpdeint.Features.Noises.POSIX.GaussianPOSIXNoise import GaussianPOSIXNoise
from xpdeint.Features.Noises.POSIX.UniformPOSIXNoise import UniformPOSIXNoise
from xpdeint.Features.Noises.POSIX.PoissonianPOSIXNoise import PoissonianPOSIXNoise
from xpdeint.Features.Noises.MKL.GaussianMKLNoise import GaussianMKLNoise
from xpdeint.Features.Noises.MKL.UniformMKLNoise import UniformMKLNoise
from xpdeint.Features.Noises.DSFMT.GaussianDSFMTNoise import GaussianDSFMTNoise
from xpdeint.Features.Noises.DSFMT.UniformDSFMTNoise import UniformDSFMTNoise
from xpdeint.Features.Noises.DSFMT.PoissonianDSFMTNoise import PoissonianDSFMTNoise

# TODO: Must check that we are never sampling a temporary vector when it doesn't exist.
# The way to do this is after the template tree has been built to iterate over all elements that can sample
# and verifying that it isn't sampling a temporary vector that it didn't create (or is a child of the creator).


class XMDS2Parser(ScriptParser):
  @staticmethod
  def canParseXMLDocument(xmlDocument):
    simulationElement = xmlDocument.getChildElementByTagName("simulation")
    if not simulationElement.hasAttribute('xmds-version') or simulationElement.getAttribute('xmds-version') != '2':
      return False
    return True
  
  def domainPairFromString(self, domainString, element):
    """
    Parse a string of the form ``(someNumber1, someNumber2)`` and return the two
    strings corresponding to the numbers ``someNumber1`` and ``someNumber2`` 
    """
    
    regex = re.compile(RegularExpressionStrings.domainPair)
    result = regex.match(domainString)
    if not result:
      raise ParserException(element, "Could not understand '%(domainString)s' as a domain"
                                     " of the form ( +/-someNumber, +/-someNumber)" % locals())
    
    minimumString = result.group(1)
    maximumString = result.group(2)
    
    return minimumString, maximumString
  
  def parseXMLDocument(self, xmlDocument, globalNameSpace, filterClass):
    self.argumentsToTemplateConstructors = {'searchList':[globalNameSpace], 'filter': filterClass}
    self.globalNameSpace = globalNameSpace
    
    _ScriptElement.argumentsToTemplateConstructors = self.argumentsToTemplateConstructors
    
    simulationElement = xmlDocument.getChildElementByTagName("simulation")
    
    nameElement = simulationElement.getChildElementByTagName('name')
    self.globalNameSpace['simulationName'] = nameElement.innerText()
    
    authorElement = simulationElement.getChildElementByTagName('author')
    self.globalNameSpace['author'] = authorElement.innerText()
    
    descriptionElement = simulationElement.getChildElementByTagName('description')
    self.globalNameSpace['simulationDescription'] = descriptionElement.innerText()
    
    self.simulation = self.globalNameSpace['simulation']
    
    simulationElementTemplate = SimulationElementTemplate(parent = self.simulation, **self.argumentsToTemplateConstructors)
    
    self.parseDriverElement(simulationElement)
    
    self.parseFeatures(simulationElement)
    
    self.parseGeometryElement(simulationElement)
    
    self.parseVectorElements(simulationElement)
    
    self.parseComputedVectorElements(simulationElement, None)
    
    self.parseTopLevelSequenceElement(simulationElement)
    
    self.parseOutputElement(simulationElement)
    
  
  def parseDependencies(self, element, optional = False):
    dependenciesElement = element.getChildElementByTagName('dependencies', optional)
    dependencyVectorNames = []
    if dependenciesElement:
      dependencyVectorNames = RegularExpressionStrings.symbolsInString(dependenciesElement.innerText())
      return ParsedEntity(dependenciesElement, dependencyVectorNames)
    else:
      return None
    
  
  def parseDriverElement(self, simulationElement):
    driverClass = DefaultDriverTemplate
    
    driverAttributeDictionary = dict()
    
    driverElement = simulationElement.getChildElementByTagName('driver', optional=True)
    if driverElement:
      
      driverName = driverElement.getAttribute('name').strip().lower()
      
      class UnknownDriverException(Exception):
        pass
      
      try:
        if 'multi-path' in driverName:
          if driverName == 'multi-path':
            driverClass = MultiPathDriverTemplate
          elif driverName == 'mpi-multi-path':
            driverClass = MPIMultiPathDriverTemplate
          else:
            raise UnknownDriverException()
          
          if not driverElement.hasAttribute('paths'):
            raise ParserException(driverElement, "Missing 'paths' attribute for multi-path driver.")
          pathCount = RegularExpressionStrings.integerInString(driverElement.getAttribute('paths'))
          driverAttributeDictionary['pathCount'] = pathCount
        elif driverName == 'none':
          pass
        elif driverName == 'distributed-mpi':
          driverClass = DistributedMPIDriverTemplate
        else:
          raise UnknownDriverException()
      except UnknownDriverException, err:
        raise ParserException(driverElement, "Unknown driver type '%(driverName)s'. "
                                             "The options are 'none' (default), 'multi-path', 'mpi-multi-path' or 'distributed-mpi'." % locals())
      
      if driverClass == MultiPathDriverTemplate:
        kindString = None
        if driverElement.hasAttribute('kind'):
          kindString = driverElement.getAttribute('kind').strip().lower()
        if kindString in (None, 'single'):
          pass
        elif kindString == 'mpi':
          driverClass = MPIMultiPathDriverTemplate
        else:
          raise ParserException(driverElement,
                                "Unknown multi-path kind '%(kindString)s'. "
                                "The options are 'single' (default), or 'mpi'." % locals())
    
    simulationDriver = driverClass(parent = self.simulation, xmlElement = driverElement,
                                   **self.argumentsToTemplateConstructors)
    self.applyAttributeDictionaryToObject(driverAttributeDictionary, simulationDriver)
    return simulationDriver
  
  
  def parseFeatures(self, simulationElement):
    featuresParentElement = simulationElement.getChildElementByTagName('features', optional=True)
    if not featuresParentElement:
      featuresParentElement = simulationElement
    
    def parseSimpleFeature(tagName, featureClass):
      featureElement = featuresParentElement.getChildElementByTagName(tagName, optional=True)
      feature = None
      if featureElement:
        if len(featureElement.innerText()) == 0 or featureElement.innerText().lower() == 'yes':
          feature = featureClass(parent = self.simulation,
                                 **self.argumentsToTemplateConstructors)
          feature.xmlElement = featureElement
      return featureElement, feature
    
    
    parseSimpleFeature('auto_vectorise', Features.AutoVectorise.AutoVectorise)
    parseSimpleFeature('benchmark', Features.Benchmark.Benchmark)
    parseSimpleFeature('error_check', Features.ErrorCheck.ErrorCheck)
    parseSimpleFeature('bing', Features.Bing.Bing)
    parseSimpleFeature('openmp', Features.OpenMP.OpenMP)
    parseSimpleFeature('halt_non_finite', Features.HaltNonFinite.HaltNonFinite)
    parseSimpleFeature('diagnostics', Features.Diagnostics.Diagnostics)
    
    
    validationFeatureElement = featuresParentElement.getChildElementByTagName('validation', optional=True)
    if validationFeatureElement and validationFeatureElement.hasAttribute('kind'):
      kindString = validationFeatureElement.getAttribute('kind').strip().lower()
      
      if kindString in ('run-time', 'none'):
        validationFeature = Features.Validation.Validation(parent = self.simulation,
                                                           runValidationChecks = kindString == 'run-time',
                                                           **self.argumentsToTemplateConstructors)
      elif kindString == 'compile-time':
        pass
      else:
        raise ParserException(validationFeatureElement, "The 'kind' attribute of the <validation> tag must be one of\n"
                                                        "'compile-time', 'run-time' or 'none'.")
      
    
    argumentsFeatureElement = featuresParentElement.getChildElementByTagName('arguments', optional=True)
    
    if argumentsFeatureElement:
      argumentsFeature = Features.Arguments.Arguments(parent = self.simulation,
                                                      **self.argumentsToTemplateConstructors)
      argumentsFeature.xmlElement = argumentsFeatureElement
      
      argumentElements = argumentsFeatureElement.getChildElementsByTagName('argument')
      
      argumentsFeature.postArgumentsCodeEntity = ParsedEntity(argumentsFeatureElement, argumentsFeatureElement.cdataContents())
      
      argumentList = []
      # Note that "h" is already taken as the "help" option 
      shortOptionNames = set(['h'])
      
      for argumentElement in argumentElements:
        name = argumentElement.getAttribute('name').strip()
        type = argumentElement.getAttribute('type').strip().lower()
        defaultValue = argumentElement.getAttribute('default_value').strip()
        
        # Determine the short name (i.e. single character) of the full option name
        shortName = ""
        for character in name:
          if character not in shortOptionNames:
            shortName = character
            shortOptionNames.add(character)
            break
        
        if shortName == "":
          raise ParserException(argumentElement, "Unable to find a short (single character) name for command line option")        
        
        if type == 'real':
          type = 'double'
        
        if not type in ('int', 'long', 'double', 'string'):
          raise ParserException(argumentElement, "Invalid type name '%(type)s'.\n"
                                                 "Valid options are 'int', 'long', 'double' or 'string'." % locals())
        
        argumentAttributeDictionary = dict()
        
        argumentAttributeDictionary['name'] = name
        argumentAttributeDictionary['shortName'] = shortName
        argumentAttributeDictionary['type'] = type
        argumentAttributeDictionary['defaultValue'] = defaultValue
        
        argumentList.append(argumentAttributeDictionary)
      
      argumentsFeature.argumentList = argumentList
    
    
    globalsElement = featuresParentElement.getChildElementByTagName('globals', optional=True)
    if globalsElement:
      globalsTemplate = Features.Globals.Globals(parent = self.simulation,
                                                 **self.argumentsToTemplateConstructors)
      globalsTemplate.globalsCodeEntity = ParsedEntity(globalsElement, globalsElement.cdataContents())
    
    cflagsElement = featuresParentElement.getChildElementByTagName('cflags', optional=True)
    if cflagsElement:
      cflagsTemplate = Features.CFlags.CFlags(parent = self.simulation,
                                              **self.argumentsToTemplateConstructors)
      cflagsTemplate.cflagsString = cflagsElement.innerText().strip()
    
    stochasticFeatureElement, stochasticFeature = parseSimpleFeature('stochastic', Features.Stochastic.Stochastic)
    
    if stochasticFeature:
      stochasticFeature.xmlElement = stochasticFeatureElement
      noiseElements = stochasticFeatureElement.getChildElementsByTagName('noise')
      stochasticFeature.noises = []
      for noiseElement in noiseElements:
        prefix = noiseElement.getAttribute('prefix').strip()
        kind = noiseElement.getAttribute('kind').strip().lower()
        noiseClass = None
        noiseAttributeDictionary = dict()
        if kind in ('gauss', 'gaussian', 'gaussian-posix'):
          noiseClass = GaussianPOSIXNoise
        elif kind in ('uniform', 'uniform-posix'):
          noiseClass = UniformPOSIXNoise
        elif kind in ('poissonian', 'poissonian-posix', 'poissonian-dsfmt'):
          if kind.endswith('dsfmt'):
            noiseClass = PoissonianDSFMTNoise
          else:
            noiseClass = PoissonianPOSIXNoise
          
          if not noiseElement.hasAttribute('mean-rate'):
            raise ParserException(noiseElement, "Poissonian noise must specify a 'mean-rate' attribute.")
          
          meanRateString = noiseElement.getAttribute('mean-rate')
          try:
            meanRate = float(meanRateString) # Is it a simple number?
            if meanRate < 0.0:               # Was the number positive?
              raise ParserException(noiseElement, "Mean-rate for Poissonian noises must be positive.")
          except ValueError, err:
            # We could just barf now, but it could be valid code, and there's no way we can know.
            # But we only accept code for this value when we have a validation element with a 
            # run-time kind of validation check
            if 'Validation' in self.globalNameSpace['features']:
              validationFeature = self.globalNameSpace['features']['Validation']
              validationFeature.validationChecks.append("""
              if (%(meanRateString)s < 0.0)
                _LOG(_ERROR_LOG_LEVEL, "ERROR: The mean-rate for Poissonian noise %(prefix)s is not positive!\\n"
                                       "Mean-rate = %%e\\n", %(meanRateString)s);""" % locals())
            else:
              raise ParserException(noiseElement, "Unable to understand '%(meanRateString)s' as a positive real value.\nUse the feature <validation/> to allow for arbitrary code." % locals())
          noiseAttributeDictionary['noiseMeanRate'] = meanRateString
        elif kind in ('gaussian-mkl'):
          noiseClass = GaussianMKLNoise
        elif kind in ('uniform-mkl'):
          noiseClass = UniformMKLNoise
        elif kind in ('gaussian-dsfmt'):
          noiseClass = GaussianDSFMTNoise
        elif kind in ('uniform-dsfmt'):
          noiseClass = UniformDSFMTNoise
        else:
          raise ParserException(noiseElement, "Unknown noise kind '%(kind)s'." % locals())
        noise = noiseClass(parent = stochasticFeature,
                           **self.argumentsToTemplateConstructors)
        
        self.applyAttributeDictionaryToObject(noiseAttributeDictionary, noise)
        
        noise.prefix = prefix
        
        noiseCountString = noiseElement.getAttribute('num').strip()
        try:
          noiseCount = int(noiseCountString)
        except ValueError, err:
          raise ParserException(noiseElement, "Cannot understand '%(noiseCountString)s' as an "
                                              "integer number of noises." % locals())
        noise.noiseCount = noiseCount
        
        noise.seedArray = []
        if noiseElement.hasAttribute('seed'):
          seedStringList = noiseElement.getAttribute('seed').split()
          for seedString in seedStringList:
            try:
              seedInt = int(seedString)
              if seedInt < 0:
                raise ParserException(noiseElement, "Seeds must be positive integers." % locals())
            except ValueError, err:
              if 'Validation' in self.globalNameSpace['features']:
                validationFeature = self.globalNameSpace['features']['Validation']
                validationFeature.validationChecks.append("""
                if (%(seedString)s < 0)
                  _LOG(_ERROR_LOG_LEVEL, "ERROR: The seed for random noise %(prefix)s is not positive!\\n"
                  "Seed = %%d\\n", %(seedString)s);""" % locals())
              else:
                raise ParserException(noiseElement, "Unable to understand seed '%(seedString)s' as a positive integer.\nUse the feature <validation/> to allow for arbitrary code." % locals())
          
          noise.seedArray = seedStringList
        
        stochasticFeature.noises.append(noise)
    
    fftwElement = featuresParentElement.getChildElementByTagName('fftw', optional=True)
    
    fourierTransformClass = None
    
    fftAttributeDictionary = dict()
    
    if not fftwElement:
      fourierTransformClass = Transforms._NoTransform._NoTransform
    else:
      threadCount = 1
      if fftwElement.hasAttribute('threads'):
        try:
          threadCountString = fftwElement.getAttribute('threads')
          threadCount = int(threadCountString)
        except ValueError, err:
          raise ParserException(fftwElement, "Cannot understand '%(threadCountString)s' as an "
                                             "integer number of threads." % locals())
        
        if threadCount <= 0:
          raise ParserException(fftwElement, "The number of threads must be greater than 0.")
      
      if not fftwElement.hasAttribute('version'):
        # FIXME: We need to determine the default FFTW version based on what is available
        fourierTransformClass = Transforms.FourierTransformFFTW3.FourierTransformFFTW3
      elif fftwElement.getAttribute('version').strip() == '3':
        fourierTransformClass = Transforms.FourierTransformFFTW3.FourierTransformFFTW3
      elif fftwElement.getAttribute('version').strip().lower() == 'none':
        fourierTransformClass = Transforms._NoTransform._NoTransform
      else:
        raise ParserException(fftwElement, "The version attribute must be either 'none' or '3'.")
      
      planType = None
      if not fftwElement.hasAttribute('plan'):
        pass
      elif fftwElement.getAttribute('plan').strip().lower() == 'estimate':
        planType = 'FFTW_ESTIMATE'
      elif fftwElement.getAttribute('plan').strip().lower() == 'measure':
        planType = 'FFTW_MEASURE'
      elif fftwElement.getAttribute('plan').strip().lower() == 'patient':
        planType = 'FFTW_PATIENT'
      elif fftwElement.getAttribute('plan').strip().lower() == 'exhaustive':
        planType = 'FFTW_EXHAUSTIVE'
      else:
        raise ParserException(fftwElement, "The plan attribute must be one of 'estimate', 'measure', 'patient' or 'exhaustive'.")
      
      if planType:
        fftAttributeDictionary['planType'] = planType
      
      if threadCount > 1:
        if fourierTransformClass == Transforms.FourierTransformFFTW3.FourierTransformFFTW3:
          fourierTransformClass = Transforms.FourierTransformFFTW3Threads.FourierTransformFFTW3Threads
        elif fourierTransformClass == Transforms._NoTransform._NoTransform:
          raise ParserException(fftwElement, "Can't use threads with no fourier transforms.")
        else:
          # This shouldn't be reached because the fourierTransformClass should be one of the above options
          raise ParserException(fftwElement, "Internal consistency error.")
        
        fftAttributeDictionary['threadCount'] = threadCount
    
    fourierTransform = fourierTransformClass(parent = self.simulation, **self.argumentsToTemplateConstructors)
    
    self.applyAttributeDictionaryToObject(fftAttributeDictionary, fourierTransform)
  
  def parseFeatureAttributes(self, someElement, someTemplate):
    self.parseNoisesAttribute(someElement, someTemplate)
    self.parseMaxIterationsAttribute(someElement, someTemplate)
  
  def parseNoisesAttribute(self, someElement, someTemplate):
    if not (someElement.hasAttribute('noises') or someElement.hasAttribute('no_noises')):
      return
    
    if someElement.hasAttribute('noises') and someElement.hasAttribute('no_noises'):
      raise ParserException(someElement, "You cannot specify both a 'noises' attribute and a 'no_noises' attribute.")
    
    if someElement.hasAttribute('noises'):
      noises = RegularExpressionStrings.symbolsInString(someElement.getAttribute('noises'))
      someTemplate.noisesEntity = ParsedEntity(someElement, noises)
    
    if someElement.hasAttribute('no_noises'):
      if someElement.getAttribute('no_noises').strip().lower() in ('yes', 'true'):
        someTemplate.noisesEntity = ParsedEntity(someElement, [])
  
  def parseMaxIterationsAttribute(self, someElement, someTemplate):
    if not isinstance(someTemplate, Integrators.AdaptiveStep.AdaptiveStep):
      return
    
    if not someElement.hasAttribute('max_iterations'):
      return
    
    maxIterationsString = someElement.getAttribute('max_iterations').strip()
    try:
      maxIterations = int(maxIterationsString)
      if not maxIterations >= 1:
        raise ParserException(someElement, "max_iterations value must be a positive integer.")
    except ValueError, err:
      raise ParserException(someElement, "Unable to understand '%(maxIterationsString)s' as an integer for 'max_iterations'.")
    
    if not 'MaxIterations' in self.globalNameSpace['features']:
      maxIterationsFeature = Features.MaxIterations.MaxIterations(**self.argumentsToTemplateConstructors)
      maxIterationsFeature.maxIterationsDict = {}
    else:
      maxIterationsFeature = self.globalNameSpace['features']['MaxIterations']
    
    maxIterationsFeature.maxIterationsDict[someTemplate] = maxIterations
  
  def parseGeometryElement(self, simulationElement):
    geometryElement = simulationElement.getChildElementByTagName('geometry')
    
    geometryTemplate = GeometryElementTemplate(parent = self.simulation, **self.argumentsToTemplateConstructors)
    
    ## First grab the propagation dimension name
    
    propagationDimensionElement = geometryElement.getChildElementByTagName('propagation_dimension')
    if len(propagationDimensionElement.innerText()) == 0:
      raise ParserException(propagationDimensionElement, "The propagation_dimension element must not be empty")
    
    propagationDimensionName = propagationDimensionElement.innerText()
    self.globalNameSpace['globalPropagationDimension'] = propagationDimensionName
    self.globalNameSpace['symbolNames'].add(propagationDimensionName)
    
    if 'none' in self.globalNameSpace['transforms']:
      noTransform = self.globalNameSpace['transforms']['none']
    else:
      noTransform = Transforms._NoTransform._NoTransform(parent = self.simulation, **self.argumentsToTemplateConstructors)
    
    propagationDimension = Dimension(name = propagationDimensionName,
                                     transverse = False,
                                     transform = noTransform,
                                     parent = geometryTemplate,
                                     **self.argumentsToTemplateConstructors)
    
    propagationDimension.addRepresentation(NonUniformDimensionRepresentation(name = propagationDimensionName,
                                                                             type = 'double',
                                                                             parent = propagationDimension,
                                                                             xmlElement = propagationDimensionElement,
                                                                             **self.argumentsToTemplateConstructors))
    
    geometryTemplate.dimensions = [propagationDimension]
    
    ## Now grab and parse all of the transverse dimensions
    
    transverseDimensionsElement = geometryElement.getChildElementByTagName('transverse_dimensions', optional=True)
    if transverseDimensionsElement:
      dimensionElements = transverseDimensionsElement.getChildElementsByTagName('dimension', optional=True)
      
      for dimensionElement in dimensionElements:
        def parseAttribute(attrName):
          if not dimensionElement.hasAttribute(attrName) or len(dimensionElement.getAttribute(attrName)) == 0:
            raise ParserException(dimensionElement, "Each dimension element must have a non-empty"
                                                    " '%(attrName)s' attribute" % locals())
          
          return dimensionElement.getAttribute(attrName).strip()
        
        
        ## Grab the name of the dimension
        dimensionName = parseAttribute('name')
        
        try:
          dimensionName = RegularExpressionStrings.symbolInString(dimensionName)
        except ValueError, err:
          raise ParserException(dimensionElement, "'%(dimensionName)s is not a valid name for a dimension.\n"
                                                  "It must not start with a number, and can only contain "
                                                  "alphanumeric characters and underscores." % locals())
        ## Make sure the name is unique
        if dimensionName in self.globalNameSpace['symbolNames']:
          raise ParserException(dimensionElement, "Dimension name %(dimensionName)s conflicts with "
                                                  "previously-defined symbol of the same name." % locals())
        
        ## Now make sure no-one else steals it
        self.globalNameSpace['symbolNames'].add(dimensionName)
        
        ## Grab the number of lattice points and make sure it's a positive integer
        
        latticeString = parseAttribute('lattice')
        if not latticeString.isdigit():
          raise ParserException(dimensionElement, "Could not understand lattice value "
                                                  "'%(latticeString)s' as a positive integer." % locals())
        
        ## Grab the domain strings
        domainString = parseAttribute('domain')
        
        ## Returns two strings for the end points
        minimumString, maximumString = self.domainPairFromString(domainString, dimensionElement)
        
        ## Now we try make some sense of them
        try:
          minimumFloat = float(minimumString)
          maximumFloat = float(maximumString)
        except ValueError, err: # If not floats then we check the validation feature.
          if 'Validation' in self.globalNameSpace['features']:
            validationFeature = self.globalNameSpace['features']['Validation']
            validationFeature.validationChecks.append("""
            if (%(minimumString)s >= %(maximumString)s)
              _LOG(_ERROR_LOG_LEVEL, "ERROR: The end point of the dimension '%(maximumString)s' must be "
                                     "greater than the start point.\\n"
                                     "Start = %%e, End = %%e\\n", %(minimumString)s,%(maximumString)s);""" % locals())
          else:
            raise ParserException(dimensionElement, """Could not understand domain (%(minimumString)s, %(maximumString)s) as numbers.
Use feature <validation/> to allow for arbitrary code.""" % locals() )
        else: # In this case we were given numbers and should check that they in the correct order here
          if minimumFloat >= maximumFloat:
            raise ParserException(dimensionElement, "The end point of the dimension, '%(maximumString)s', must be "
                                           "greater than the start point, '%(minimumString)s'." % locals())
        
        transform = None
        transformName = 'none'
        
        if dimensionElement.hasAttribute('transform'):
          transformName = dimensionElement.getAttribute('transform').strip()
          if not transformName.lower() in self.globalNameSpace['transforms']:
            raise ParserException(dimensionElement, "Unknown transform of type '%(transformName)s'." % locals())
          transform = self.globalNameSpace['transforms'][transformName.lower()]
        
        if not transform:
          # default to 'dft'
          if 'dft' in self.globalNameSpace['transforms']:
            transform = self.globalNameSpace['transforms']['dft']
            transformName = 'dft'
          elif 'none' in self.globalNameSpace['transforms']:
            transform = self.globalNameSpace['transforms']['none']
          else:
            transform = Transforms._NoTransform._NoTransform(**self.argumentsToTemplateConstructors)
        
        dim = transform.newDimension(name = dimensionName, lattice = int(latticeString),
                                     minimum = minimumString, maximum = maximumString,
                                     parent = geometryTemplate, transformName = transformName,
                                     xmlElement = dimensionElement)
        
        geometryTemplate.dimensions.append(dim)
      
      # We have just finished looping over the normal dimensions in the transverse_dimensions element.
      # Now we need to grab any 'integer_valued' tags and parse those.
      self.parseIntegerValuedElements(transverseDimensionsElement, geometryTemplate)
    
    driver = self.globalNameSpace['features']['Driver']
    if isinstance(driver, DistributedMPIDriverTemplate):
      transverseDimensions = geometryTemplate.dimensions[1:]
      mpiTransform = transverseDimensions[0].transform
      if not mpiTransform.isMPICapable:
        raise ParserException(mpiTransform.xmlElement, "The '%s' transform cannot be used with the 'distributed-mpi' driver." % mpiTransform.featureName)
      mpiTransform.initialiseForMPIWithDimensions(transverseDimensions)
    
    return geometryTemplate
  
  def parseIntegerValuedElements(self, transverseDimensionsElement, geometryTemplate):
    integerValuedElements = transverseDimensionsElement.getChildElementsByTagName('integer_valued', optional=True)
    if not integerValuedElements:
      return
    
    firstIntegerValuedElement = None
    lastIntegerValuedElement = None
    
    for integerValuedElement in integerValuedElements:
      # If the integer_valued tag doesn't have a 'kind' attribute, default to 'last'
      if not integerValuedElement.hasAttribute('kind'):
        if lastIntegerValuedElement:
          # We already have an integer_valued tag of kind 'last'
          raise ParserException(integerValuedElement, "There is already an 'integer_valued' element of kind 'last'.")
        else:
          # Everything is OK
          lastIntegerValuedElement = integerValuedElement
      else:
        # We have an integer_valued tag
        kindString = integerValuedElement.getAttribute('kind').strip().lower()
        if kindString == 'last':
          if lastIntegerValuedElement:
            # We already have an integer_valued tag of kind 'last'
            raise ParserException(integerValuedElement, "There is already an 'integer_valued' element of kind 'last'.")
          else:
            # Everything is OK
            lastIntegerValuedElement = integerValuedElement
        elif kindString == 'first':
          if firstIntegerValuedElement:
            # We already have an integer_valued tag of kind 'first'
            raise ParserException(integerValuedElement, "There is already an 'integer_valued' element of kind 'first'.")
          else:
            # Everything is OK
            firstIntegerValuedElement = integerValuedElement
        else:
          raise ParserException(integerValuedElement, "Unknown kind '%(kindString)s' for an integer_valued element." % locals())
    
    # At this point we have at most one firstIntegerValuedElement
    # and one lastIntegerValuedElement
    
    if firstIntegerValuedElement:
      self.parseIntegerValuedElement(firstIntegerValuedElement, geometryTemplate)
    if lastIntegerValuedElement:
      self.parseIntegerValuedElement(lastIntegerValuedElement, geometryTemplate)
    
  
  def parseIntegerValuedElement(self, integerValuedElement, geometryTemplate):
    dimensionElements = integerValuedElement.getChildElementsByTagName('dimension')
    
    dimensionList = []
    
    for dimensionElement in dimensionElements:
      # Parse the namem
      if not dimensionElement.hasAttribute('name'):
        raise ParserException(dimensionElement, "Missing 'name' attribute.")
      
      dimensionName = dimensionElement.getAttribute('name').strip()
      
      try:
        dimensionName = RegularExpressionStrings.symbolInString(dimensionName)
      except ValueError, err:
        raise ParserException(dimensionElement, "'%(dimensionName)s is not a valid name for a dimension.\n"
                                                "It must not start with a number, and can only contain "
                                                "alphanumeric characters and underscores." % locals())
      ## Make sure the name is unique
      if dimensionName in self.globalNameSpace['symbolNames']:
        raise ParserException(dimensionElement, "Dimension name %(dimensionName)s conflicts with "
                                                "previously-defined symbol of the same name." % locals())
      
      
      # Parse the domain string
      if not dimensionElement.hasAttribute('domain'):
        raise ParserException(dimensionElement, "Missing 'domain' attribute.")
      
      domainString = dimensionElement.getAttribute('domain').strip()
      
      minimumString, maximumString = self.domainPairFromString(domainString, dimensionElement)
      # We are not guaranteed that these can be transformed into int's
      try:
        minimumValue = int(minimumString)
        maximumValue = int(maximumString)
      except ValueErr, err:
        raise ParserException(dimensionElement, "Integer dimension %(dimensionName)s has non-integer domain "
                                                "(%(minimumString)s, %(maximumString)s)" % locals())
     
      if minimumValue >= maximumValue:
        raise ParserException(dimensionElement, "Integer dimension %(dimensionName)s must have end greater "
                                                "than start. Domain = (%(minimumString)s, %(maximumString)s)" % locals())
      
      # If we have a lattice attribute, check that it agrees with the domain
      if dimensionElement.hasAttribute('lattice'):
        try:
          latticeString = dimensionElement.getAttribute('lattice').strip()
          lattice = RegularExpressionStrings.integerInString(latticeString)
        except ValueError, err:
          raise ParserException(dimensionElement, "Unable to understand '%(latticeString)s' as an integer." % locals())
        
        if (maximumValue - minimumValue + 1) != lattice:
          raise ParserException(dimensionElement, "The lattice value of '%(latticeString)s' doesn't match with the domain "
                                                  "'%(domainString)s'." % locals())
      else:
        lattice = maximumValue - minimumValue + 1
      
      if 'none' in self.globalNameSpace['transforms']:
        transform = self.globalNameSpace['transforms']['none']
      else:
        transform = Transforms._NoTransform._NoTransform(**self.argumentsToTemplateConstructors)
        
      dim = transform.newDimension(name = dimensionName, lattice = lattice, type = 'long',
                                   minimum = minimumString, maximum = maximumString,
                                   parent = geometryTemplate, indexable = True, transformName = 'none')
      
      dimensionList.append(dim)
    
    if not integerValuedElement.hasAttribute('kind') or integerValuedElement.getAttribute('kind').strip().lower() == 'last':
      geometryTemplate.dimensions.extend(dimensionList)
    else:
      dimensionList.reverse()
      for dim in dimensionList:
        geometryTemplate.dimensions.insert(1, dim)
    
    
  
  def parseVectorElements(self, parentElement):
    vectorElements = parentElement.getChildElementsByTagName('vector', optional=True)
    for vectorElement in vectorElements:
      vectorTemplate = self.parseVectorElement(vectorElement)
  
  def parseVectorElement(self, vectorElement):
    if not vectorElement.hasAttribute('dimensions'):
      dimensionNames = [dim.name for dim in self.globalNameSpace['geometry'].dimensions if dim.transverse]
    elif len(vectorElement.getAttribute('dimensions').strip()) == 0:
      # No dimensions
      dimensionNames = []
    else:
      dimensionsString = vectorElement.getAttribute('dimensions').strip()
      dimensionNames = RegularExpressionStrings.symbolsInString(dimensionsString)
      if not dimensionNames:
        raise ParserException(vectorElement, "Cannot understand '%(dimensionsString)s' as a "
                                            "list of dimensions" % locals())
        
    
    fieldTemplate = FieldElementTemplate.sortedFieldWithDimensionNames(dimensionNames, xmlElement = vectorElement)
    
    if not vectorElement.hasAttribute('name') or len(vectorElement.getAttribute('name')) == 0:
      raise ParserException(vectorElement, "Each vector element must have a non-empty 'name' attribute")
    
    vectorName = vectorElement.getAttribute('name')
    if not vectorName == RegularExpressionStrings.symbolInString(vectorName):
      raise ParserException(vectorElement, "'%(vectorName)s' is not a valid name for a vector.\n"
                                           "The name must not start with a number and can only contain letters, numbers and underscores." % locals())
    
    # Check that this vector name is unique
    for field in self.globalNameSpace['fields']:
      if len(filter(lambda x: x.name == vectorName, field.vectors)) > 0:
        raise ParserException(vectorElement, "Vector name '%(vectorName)s' conflicts with a "
                                             "previously defined vector of the same name" % locals())
    
    ## Check that the name isn't already taken
    if vectorName in self.globalNameSpace['symbolNames']:
      raise ParserException(vectorElement, "Vector name '%(vectorName)s' conflicts with previously "
                                          "defined symbol of the same name." % locals())
    
    ## Make sure no-one else takes the name
    self.globalNameSpace['symbolNames'].add(vectorName)
    
    vectorTemplate = VectorElementTemplate(name = vectorName, field = fieldTemplate,
                                           **self.argumentsToTemplateConstructors)
    
    self.globalNameSpace['vectors'].append(vectorTemplate)
    
    if not vectorElement.hasAttribute('initial_space'):
      vectorTemplate.initialSpace = 0
    else:
      vectorTemplate.initialSpace = fieldTemplate.spaceFromString(vectorElement.getAttribute('initial_space'),
                                                                  xmlElement = vectorElement)
    
    componentsElement = vectorElement.getChildElementByTagName('components')
    
    typeString = None
    if vectorElement.hasAttribute('type'):
      typeString = vectorElement.getAttribute('type').lower()
    
    if typeString in (None, 'complex'):
      vectorTemplate.type = 'complex'
    elif typeString in ('double', 'real'):
      vectorTemplate.type = 'double'
    else:
      raise ParserException(componentsElement, "Unknown type '%(typeString)s'. "
                                               "Options are 'complex' (default), "
                                               "or 'double' / 'real' (synonyms)" % locals())
    
    componentsString = componentsElement.innerText()
    if not componentsString:
      raise ParserException(componentsElement, "The components element must not be empty")
    
    results = RegularExpressionStrings.symbolsInString(componentsString)
    
    if not results:
      raise ParserException(componentsElement, "Could not extract component names from component string "
                                               "'%(componentsString)s'." % locals())
    
    for componentName in results:
      if componentName in self.globalNameSpace['symbolNames']:
        raise ParserException(componentsElement, "Component name '%(componentName)s' conflicts with "
                                                 "a previously-defined symbol of the same name." % locals())
      self.globalNameSpace['symbolNames'].add(componentName)
      
      vectorTemplate.components.append(componentName)
    
    initialisationElement = vectorElement.getChildElementByTagName('initialisation', optional=True)
    
    if initialisationElement:
      initialisationTemplate = vectorTemplate.initialiser
      kindString = None
      if initialisationElement.hasAttribute('kind'):
        kindString = initialisationElement.getAttribute('kind').lower()
      
      if kindString in (None, 'code'):
        initialisationTemplate = VectorInitialisationFromCDATATemplate(parent = vectorTemplate, xmlElement=initialisationElement,
                                                                       **self.argumentsToTemplateConstructors)
        initialisationTemplate.dependenciesEntity = self.parseDependencies(initialisationElement, optional=True)
        
        if len(initialisationElement.cdataContents()) == 0:
          raise ParserException(initialisationElement, "Empty initialisation code in 'code' initialisation element.")
        initialisationTemplate.initialisationCodeEntity = ParsedEntity(initialisationElement, initialisationElement.cdataContents())
      elif kindString == 'zero':
        initialisationTemplate = vectorTemplate.initialiser
      elif kindString == 'xsil':
        initialisationTemplate = VectorInitialisationFromXSILTemplate(parent = vectorTemplate, xmlElement=initialisationElement,
                                                                      **self.argumentsToTemplateConstructors)
        geometryMatchingMode = 'strict'
        if initialisationElement.hasAttribute('geometry_matching_mode'):
          geometryMatchingMode = initialisationElement.getAttribute('geometry_matching_mode').strip().lower()
          if not geometryMatchingMode in ('strict', 'loose'):
            raise ParserException(initialisationElement, "The geometry matching mode for XSIL import must either be 'strict' or 'loose'.")
        initialisationTemplate.geometryMatchingMode = geometryMatchingMode
        
        filenameElement = initialisationElement.getChildElementByTagName('filename')
        momentGroupName = 'NULL'
        if filenameElement.hasAttribute('moment_group'):
          momentGroupName = 'moment_group_' + filenameElement.getAttribute('moment_group').strip()
        
        initialisationTemplate.momentGroupName = momentGroupName
        
        initialisationTemplate.initialisationCodeEntity = ParsedEntity(initialisationElement, initialisationElement.cdataContents())
        
        filename = filenameElement.innerText()
        if filename.isspace():
          raise ParserException(filenameElement, "The contents of the filename tag must be non-empty.")
        
        initialisationTemplate.filename = filename
        
      else:
        raise ParserException(initialisationElement, "Initialisation kind '%(kindString)s' is unrecognised.\n"
                                                     "The options are 'code' (default), 'xsil', or 'zero' "
                                                     "(this is the same as having no initialisation element)." % locals())
      
      # Untie the old initialiser from the vector
      # Probably not strictly necessary
      if not vectorTemplate.initialiser == initialisationTemplate:
        vectorTemplate.initialiser.vector = None
        vectorTemplate.initialiser.remove()
      initialisationTemplate.vector = vectorTemplate
      vectorTemplate.initialiser = initialisationTemplate
      
      self.parseFeatureAttributes(initialisationElement, initialisationTemplate)
    
    return vectorTemplate
  
  def parseComputedVectorElements(self, parentElement, parentTemplate):
    results = []
    computedVectorElements = parentElement.getChildElementsByTagName('computed_vector', optional=True)
    for computedVectorElement in computedVectorElements:
      # Add the computed vector template to the results
      results.append(self.parseComputedVectorElement(computedVectorElement, parentTemplate))
    
    return results
  
  def parseComputedVectorElement(self, computedVectorElement, parentTemplate):
    if not computedVectorElement.hasAttribute('name') or len(computedVectorElement.getAttribute('name')) == 0:
      raise ParserException(computedVectorElement, "Each computed vector element must have a non-empty 'name' attribute")
    
    vectorName = computedVectorElement.getAttribute('name')
    
    # Check that this vector name is unique
    for field in self.globalNameSpace['fields']:
      if len(filter(lambda x: x.name == vectorName, field.vectors)) > 0:
        raise ParserException(computedVectorElement, "Computed vector name '%(vectorName)s' conflicts with a "
                                                     "previously defined vector of the same name" % locals())
    
    ## Check that the name isn't already taken
    if vectorName in self.globalNameSpace['symbolNames']:
      raise ParserException(computedVectorElement, "Computed vector name '%(vectorName)s' conflicts with previously "
                                                   "defined symbol of the same name." % locals())
    
    ## Make sure no-one else takes the name
    self.globalNameSpace['symbolNames'].add(vectorName)
    
    if not computedVectorElement.hasAttribute('dimensions'):
      dimensionNames = [dim.name for dim in self.globalNameSpace['geometry'].dimensions if dim.transverse]
    elif len(computedVectorElement.getAttribute('dimensions').strip()) == 0:
      # No dimensions
      dimensionNames = []
    else:
      dimensionsString = computedVectorElement.getAttribute('dimensions').strip()
      dimensionNames = RegularExpressionStrings.symbolsInString(dimensionsString)
      if not dimensionNames:
        raise ParserException(computedVectorElement, "Cannot understand '%(dimensionsString)s' as a "
                                                     "list of dimensions" % locals())
        
    
    fieldTemplate = FieldElementTemplate.sortedFieldWithDimensionNames(dimensionNames, xmlElement = computedVectorElement)
    
    if parentTemplate is None:
      parentTemplate = fieldTemplate
    # One way or another, we now have our fieldTemplate
    # So we can now construct the computed vector template
    vectorTemplate = ComputedVectorTemplate(name = vectorName, field = fieldTemplate,
                                            parent = parentTemplate,
                                            xmlElement = computedVectorElement,
                                            **self.argumentsToTemplateConstructors)
    
    self.globalNameSpace['vectors'].append(vectorTemplate)
    
    componentsElement = computedVectorElement.getChildElementByTagName('components')
    
    typeString = None
    if computedVectorElement.hasAttribute('type'):
      typeString = computedVectorElement.getAttribute('type').lower()
    
    if typeString in (None, 'complex'):
      vectorTemplate.type = 'complex'
    elif typeString in ('double', 'real'):
      vectorTemplate.type = 'double'
    else:
      raise ParserException(componentsElement, "Unknown type '%(typeString)s'. "
                                               "Options are 'complex' (default), "
                                               "or 'double' / 'real' (synonyms)" % locals())
    
    componentsString = componentsElement.innerText()
    if not componentsString:
      raise ParserException(componentsElement, "The components element must not be empty")
    
    results = RegularExpressionStrings.symbolsInString(componentsString)
    
    if not results:
      raise ParserException(componentsElement, "Could not extract component names from component string "
                                               "'%(componentsString)s'." % locals())
    
    for componentName in results:
      if componentName in self.globalNameSpace['symbolNames']:
        raise ParserException(componentsElement, "Component name '%(componentName)s' conflicts with "
                                                 "a previously-defined symbol of the same name." % locals())
      self.globalNameSpace['symbolNames'].add(componentName)
      
      vectorTemplate.components.append(componentName)
    
    evaluationElement = computedVectorElement.getChildElementByTagName('evaluation')
    vectorTemplate.evaluationCodeEntity = ParsedEntity(evaluationElement, evaluationElement.cdataContents())
    
    vectorTemplate.dependenciesEntity = self.parseDependencies(evaluationElement, optional=True)
    
    self.parseFeatureAttributes(evaluationElement, vectorTemplate)
    
    return vectorTemplate
  
  
  def parseTopLevelSequenceElement(self, simulationElement):
    topLevelSequenceElement = simulationElement.getChildElementByTagName('sequence')
    
    topLevelSequenceElementTemplate = TopLevelSequenceElementTemplate(**self.argumentsToTemplateConstructors)
    
    self.parseSequenceElement(topLevelSequenceElement, topLevelSequenceElementTemplate)
  
  def parseSequenceElement(self, sequenceElement, sequenceTemplate):
    if sequenceElement.hasAttribute('cycles'):
      cyclesString = sequenceElement.getAttribute('cycles')
      try:
        cycles = int(cyclesString)
      except ValueError, err:
        raise ParserException(sequenceElement, "Unable to understand '%(cyclesString)s' as an integer.")
      
      if cycles <= 0:
        raise ParserException(sequenceElement, "The number of cycles must be positive.")
      
      sequenceTemplate.localCycles = cycles
    
    for childNode in sequenceElement.childNodes:
      if not childNode.nodeType == minidom.Node.ELEMENT_NODE:
        continue
      
      tagName = childNode.tagName.lower()
      
      if tagName == 'integrate':
        integrateTemplate = self.parseIntegrateElement(childNode)
        sequenceTemplate.addSegment(integrateTemplate)
      elif tagName == 'filter':
        # Construct the filter segment
        filterSegmentTemplate = FilterSegmentTemplate(**self.argumentsToTemplateConstructors)
        # Add it to the sequence element as a child segment
        sequenceTemplate.addSegment(filterSegmentTemplate)
        # Create an operator container to house the filter operator
        operatorContainer = OperatorContainerTemplate(parent = filterSegmentTemplate,
                                                      **self.argumentsToTemplateConstructors)
        # Add the operator container to the filter segment
        filterSegmentTemplate.operatorContainers.append(operatorContainer)
        # parse the filter operator
        filterOperator = self.parseFilterOperator(childNode, operatorContainer)
      elif tagName == 'breakpoint':
        # Construct the breakpoint segment
        breakpointSegmentTemplate = BreakpointSegmentTemplate(**self.argumentsToTemplateConstructors)
        # Add it to the sequence element as a child segment
        sequenceTemplate.addSegment(breakpointSegmentTemplate)
        # parse a dependencies element
        breakpointSegmentTemplate.dependenciesEntity = self.parseDependencies(childNode)
        
        if childNode.hasAttribute('filename'):
          breakpointSegmentTemplate.filename = childNode.getAttribute('filename').strip()
        else:
          parserWarning(childNode, "Breakpoint names defaulting to the sequence 1.xsil, 2.xsil, etc.")
      elif tagName == 'sequence':
        # Construct the sequence segment
        sequenceSegmentTemplate = SequenceSegmentTemplate(**self.argumentsToTemplateConstructors)
        sequenceTemplate.addSegment(sequenceSegmentTemplate)
        
        self.parseSequenceElement(childNode, sequenceSegmentTemplate)
      else:
        raise ParserException(childNode, "Unknown child of sequence element. "
                                         "Possible children include 'sequence', 'integrate', 'filter' or 'breakpoint' elements.")
    
  
  def parseIntegrateElement(self, integrateElement):
    if not integrateElement.hasAttribute('algorithm'):
      raise ParserException(integrateElement, "Integration element must have an 'algorithm' attribute.")
    
    integratorTemplateClass = None
    algorithmSpecificOptionsDict = dict()
    
    algorithmString = integrateElement.getAttribute('algorithm')
    if algorithmString == 'RK4':
      integratorTemplateClass = Integrators.RK4.RK4
    elif algorithmString == 'RK9':
      integratorTemplateClass = Integrators.RK9.RK9
    elif algorithmString == 'ARK45':
      integratorTemplateClass = Integrators.ARK45.ARK45
    elif algorithmString == 'ARK89':
      integratorTemplateClass = Integrators.ARK89.ARK89
    elif algorithmString in ['SI','SIC']:
      if algorithmString == 'SI':
        integratorTemplateClass = Integrators.SI.SI
      else:
        integratorTemplateClass = Integrators.SIC.SIC
      
      if integrateElement.hasAttribute('iterations'):
        algorithmSpecificOptionsDict['iterations'] = RegularExpressionStrings.integerInString(integrateElement.getAttribute('iterations'))
        if algorithmSpecificOptionsDict['iterations']<1:
          raise ParserException(integrateElement, "Iterations element must be 1 or greater (default 3).")
    else:
      raise ParserException(integrateElement, "Unknown algorithm '%(algorithmString)s'. "
                                              "Options are 'SI', 'SIC', 'RK4', 'RK9', 'ARK45' or 'ARK89'." % locals())
    
    integratorTemplate = integratorTemplateClass(**self.argumentsToTemplateConstructors)
    self.applyAttributeDictionaryToObject(algorithmSpecificOptionsDict, integratorTemplate)      
    
    if integrateElement.hasAttribute('home_space'):
      attributeValue = integrateElement.getAttribute('home_space').strip().lower()
      if attributeValue == 'k':
        integratorTemplate.homeSpace = self.globalNameSpace['geometry'].spaceMask
      elif attributeValue == 'x':
        integratorTemplate.homeSpace = 0
      else:
        raise ParserException(integrateElement, "home_space must be either 'k' or 'x'.")
    
    if issubclass(integratorTemplateClass, Integrators.AdaptiveStep.AdaptiveStep):
      if not integrateElement.hasAttribute('tolerance'):
        raise ParserException(integrateElement, "Adaptive integrators need a 'tolerance' attribute.")
      else:
        toleranceString = integrateElement.getAttribute('tolerance').strip()
        try:
          tolerance = float(toleranceString)
          if tolerance <= 0.0:
            raise ParserException(integrateElement, "Tolerance must be positive.")
        except ValueError, err:
          raise ParserException(integrateElement, "Could not understand tolerance '%(toleranceString)s' "
                                                  "as a number." % locals())
        
        integratorTemplate.tolerance = tolerance
      
      # FIXME: The adaptive integrators need both an absolute and a relative cutoff
      if not integrateElement.hasAttribute('cutoff'):
        pass
      else:
        cutoffString = integrateElement.getAttribute('cutoff').strip()
        try:
          cutoff = float(cutoffString)
          if not 0.0 < cutoff <= 1.0:
            raise ParserException(integrateElement, "Cutoff must be in the range (0.0, 1.0].")
        except ValueError, err:
          raise ParserException(integrateElement, "Could not understand cutoff '%(cutoffString)s' "
                                                  "as a number." % locals())
        integratorTemplate.cutoff = cutoff
        
    
    if not integrateElement.hasAttribute('interval'):
      raise ParserException(integrateElement, "Integrator needs 'interval' attribute.")
    
    intervalString = integrateElement.getAttribute('interval')
    # Now check if the interval is a valid number or variable
    try:
      interval = float(intervalString) # Is it a simple number?
      if interval <= 0.0:              # Was the number positive?
        raise ParserException(integrateElement, "Interval must be positive.")
    except ValueError, err:
      # We could just barf now, but it could be valid code, and there's no way we can know.
      # But we only accept code for this value when we have a validation element with a 
      # run-time kind of validation check
      if 'Validation' in self.globalNameSpace['features']:
        validationFeature = self.globalNameSpace['features']['Validation']
        segmentNumber = integratorTemplate.segmentNumber
        validationFeature.validationChecks.append("""
        if (%(intervalString)s <= 0.0)
          _LOG(_ERROR_LOG_LEVEL, "ERROR: The interval for segment %(segmentNumber)i is not positive!\\n"
                                 "Interval = %%e\\n", %(intervalString)s);""" % locals())
      else:
        raise ParserException(integrateElement, "Could not understand interval '%(intervalString)s' "
                                                "as a number.\nUse the feature <validation/> to allow for arbitrary code." % locals())
    
    integratorTemplate.interval = intervalString
    
    if not integrateElement.hasAttribute('steps'):
      raise ParserException(integrateElement, "Integrator needs a 'steps' attribute.")
      
    stepsString = integrateElement.getAttribute('steps').strip()
    
    if not stepsString.isdigit():
      raise ParserException(integrateElement, "Could not understand steps '%(stepsString)s' "
                                              "as a positive integer." % locals())
    
    steps = int(stepsString)
    integratorTemplate.stepCount = steps
    
    samplesElement = integrateElement.getChildElementByTagName('samples')
    samplesString = samplesElement.innerText()
    
    results = RegularExpressionStrings.integersInString(samplesString)
    
    if not results:
      raise ParserException(samplesElement, "Could not understand '%(samplesString)s' "
                                            "as a list of integers" % locals())
    
    if filter(lambda x: x < 0, results):
      raise ParserException(samplesElement, "All sample counts must be greater than zero.")
    
    integratorTemplate.samplesEntity = ParsedEntity(samplesElement, results)
    
    integratorTemplate.computedVectors.update(self.parseComputedVectorElements(integrateElement, integratorTemplate))
    
    self.parseOperatorsElements(integrateElement, integratorTemplate)
    
    self.parseFiltersElements(integrateElement, integratorTemplate)
    
    self.parseFeatureAttributes(integrateElement, integratorTemplate)
    
    return integratorTemplate
  
  def parseFiltersElements(self, integrateElement, integratorTemplate):
    filtersElements = integrateElement.getChildElementsByTagName('filters', optional=True)
    
    for filtersElement in filtersElements:
      filterOperatorContainer = self.parseFilterElements(filtersElement, parent=integratorTemplate)
      
      whereString = None
      if filtersElement.hasAttribute('where'):
        whereString = filtersElement.getAttribute('where').strip().lower()
      if whereString in (None, 'step start'):
        integratorTemplate.stepStartOperatorContainers.append(filterOperatorContainer)
      elif whereString == 'step end':
        integratorTemplate.stepEndOperatorContainers.append(filterOperatorContainer)
      else:
        raise ParserException(filtersElement, "Unknown placement of filters in the 'where' tag of '%(whereString)s'.\n"
                                              "Valid options are: 'step start' (default) or 'step end'." % locals())
    
  
  def parseFilterElements(self, filtersElement, parent, optional = False):
    filterElements = filtersElement.getChildElementsByTagName('filter', optional = optional)
    
    if filterElements:
      operatorContainer = OperatorContainerTemplate(parent = parent,
                                                    **self.argumentsToTemplateConstructors)
    else:
      operatorContainer = None
    
    for filterElement in filterElements:
      filterTemplate = self.parseFilterOperator(filterElement, operatorContainer)
    
    return operatorContainer
  
  def parseFilterOperator(self, filterElement, operatorContainer):
    filterTemplate = FilterOperatorTemplate(parent = operatorContainer,
                                            xmlElement = filterElement,
                                            **self.argumentsToTemplateConstructors)
    
    filterTemplate.operatorDefinitionCodeEntity = ParsedEntity(filterElement, filterElement.cdataContents())
    
    filterTemplate.dependenciesEntity = self.parseDependencies(filterElement, optional=True)
    
    return filterTemplate
  
  def parseOperatorsElements(self, integrateElement, integratorTemplate):
    operatorsElements = integrateElement.getChildElementsByTagName('operators')
    
    fieldsUsed = set()
    validFieldNames = [field.name for field in self.globalNameSpace['fields']]
    
    for operatorsElement in operatorsElements:
      if not operatorsElement.hasAttribute('dimensions'):
        dimensionNames = [dim.name for dim in self.globalNameSpace['geometry'].dimensions if dim.transverse]
      else:
        dimensionNames = RegularExpressionStrings.symbolsInString(operatorsElement.getAttribute('dimensions'))
      
      fieldTemplate = FieldElementTemplate.sortedFieldWithDimensionNames(dimensionNames, createIfNeeded = False)
      
      if not fieldTemplate:
        raise ParserException(operatorsElement, "There are no vectors with this combination of dimensions.")
      
      if fieldTemplate in fieldsUsed:
        raise ParserException(operatorsElement, "There can only be one operators element per combination of dimensions.")
      
      fieldsUsed.add(fieldTemplate)
      
      self.parseOperatorsElement(operatorsElement, integratorTemplate, fieldTemplate)
    
  
  def parseOperatorsElement(self, operatorsElement, integratorTemplate, fieldTemplate):
    operatorContainer = OperatorContainerTemplate(field = fieldTemplate, xmlElement = operatorsElement,
                                                  name = fieldTemplate.name + '_operators',
                                                  parent = integratorTemplate,
                                                  **self.argumentsToTemplateConstructors)
    integratorTemplate.intraStepOperatorContainers.append(operatorContainer)
    
    self.parseOperatorElements(operatorsElement, operatorContainer, integratorTemplate)
  
  def parseOperatorElements(self, operatorsElement, operatorContainer, integratorTemplate):
    haveHitDeltaAOperator = False
    for childNode in operatorsElement.childNodes:
      if childNode.nodeType == minidom.Node.ELEMENT_NODE and childNode.tagName == 'operator':
        # We have an operator element
        operatorTemplate = self.parseOperatorElement(childNode, operatorContainer)
        
        if haveHitDeltaAOperator and not isinstance(operatorTemplate, (FunctionsOperatorTemplate)):
          # Currently all operators after the CDATA code will trigger this exception, but when we
          # implement 'functions' operators, they will need to be added to the above list so they don't
          # trigger this exception.
          raise ParserException(childNode, "You cannot have this kind of operator after the CDATA section\n"
                                           "of the <operators> element. The only operators that can be put\n"
                                           "after the CDATA section are 'functions' operators.")
      
      elif childNode.nodeType == minidom.Node.CDATA_SECTION_NODE:
        deltaAOperatorTemplate = self.parseDeltaAOperator(operatorsElement, operatorContainer)
    
  
  def parseDeltaAOperator(self, operatorsElement, operatorContainer):
    deltaAOperatorTemplate = DeltaAOperatorTemplate(parent = operatorContainer, xmlElement = operatorsElement,
                                                    **self.argumentsToTemplateConstructors)
    
    deltaAOperatorTemplate.propagationCodeEntity = ParsedEntity(operatorsElement, operatorsElement.cdataContents())
    
    self.parseFeatureAttributes(operatorsElement, deltaAOperatorTemplate)
    
    deltaAOperatorTemplate.dependenciesEntity = self.parseDependencies(operatorsElement, optional=True)
    
    integrationVectorsElement = operatorsElement.getChildElementByTagName('integration_vectors')
    integrationVectorsNames = RegularExpressionStrings.symbolsInString(integrationVectorsElement.innerText())
    
    if integrationVectorsElement.hasAttribute('fourier_space'):
      deltaAOperatorTemplate.operatorSpace = operatorContainer.field.spaceFromString(integrationVectorsElement.getAttribute('fourier_space'),
                                                                                     xmlElement = integrationVectorsElement)
    
    if not integrationVectorsNames:
      raise ParserException(integrationVectorsElement, "Element must be non-empty.")
    
    deltaAOperatorTemplate.integrationVectorsEntity = ParsedEntity(integrationVectorsElement, integrationVectorsNames)
    
    if integrationVectorsElement.hasAttribute('fourier_space'):
      deltaAOperatorTemplate.operatorSpace = \
        deltaAOperatorTemplate.field.spaceFromString(integrationVectorsElement.getAttribute('fourier_space'))
  
  def parseOperatorElement(self, operatorElement, operatorContainer):
    if not operatorElement.hasAttribute('kind'):
      raise ParserException(operatorElement, "Missing 'kind' attribute.")
    
    kindString = operatorElement.getAttribute('kind').strip().lower()
    
    constantString = None
    if operatorElement.hasAttribute('constant'):
      constantString = operatorElement.getAttribute('constant').strip().lower()
    
    parserMethod = None
    operatorTemplateClass = None
    
    if kindString == 'ip':
      integratorTemplate = operatorContainer.parent
      
      if isinstance(integratorTemplate, Integrators.FixedStep.FixedStep) and not constantString:
        raise ParserException(operatorElement, "Missing 'constant' attribute.")
      elif isinstance(integratorTemplate, Integrators.AdaptiveStep.AdaptiveStep):
        operatorTemplateClass = NonConstantIPOperatorTemplate
      elif constantString == 'yes':
        operatorTemplateClass = ConstantIPOperatorTemplate
      elif constantString == 'no':
        operatorTemplateClass = NonConstantIPOperatorTemplate
      else:
        raise ParserException(operatorElement, "The 'constant' attribute must be either 'yes' or 'no'.")
      
      parserMethod = self.parseIPOperatorElement
    elif kindString == 'ex':
      if not constantString:
        raise ParserException(operatorElement, "Missing 'constant' attribute.")
      
      parserMethod = self.parseEXOperatorElement
      if constantString == 'yes':
        operatorTemplateClass = ConstantEXOperatorTemplate
      elif constantString == 'no':
        operatorTemplateClass = NonConstantEXOperatorTemplate
      else:
        raise ParserException(operatorElement, "The constant attribute must be either 'yes' or 'no'.")
    elif kindString == 'cross_propagation':
      parserMethod = self.parseCrossPropagationOperatorElement
      operatorTemplateClass = CrossPropagationOperatorTemplate
    elif kindString == 'functions':
      parserMethod = None
      operatorTemplateClass = FunctionsOperatorTemplate
    else:
      raise ParserException(operatorElement, "Unknown operator kind '%(kindString)s'\n"
                                             "Valid options are: 'ip', 'ex', 'filter' or 'cross-propagation'." % locals())
    
    operatorTemplate = operatorTemplateClass(parent = operatorContainer,
                                             xmlElement = operatorElement,
                                             **self.argumentsToTemplateConstructors)
    
    operatorTemplate.operatorDefinitionCodeEntity = ParsedEntity(operatorElement, operatorElement.cdataContents())
    
    operatorTemplate.dependenciesEntity = self.parseDependencies(operatorElement, optional=True)
    
    if parserMethod:
      parserMethod(operatorTemplate, operatorElement)
    
    return operatorTemplate
  
  def parseIPOperatorElement(self, operatorTemplate, operatorElement):
    if operatorElement.hasAttribute('fourier_space'):
      operatorTemplate.operatorSpace = \
        operatorTemplate.field.spaceFromString(operatorElement.getAttribute('fourier_space'),
                                               xmlElement = operatorElement)
    
    operatorNamesElement = operatorElement.getChildElementByTagName('operator_names')
    operatorNames = RegularExpressionStrings.symbolsInString(operatorNamesElement.innerText())
    
    if not operatorNames:
      raise ParserException(operatorNamesElement, "operator_names must not be empty.")
    
    for operatorName in operatorNames:
      if operatorName in self.globalNameSpace['symbolNames']:
        raise ParserException(operatorNamesElement,
                "Operator name '%(operatorName)s' conflicts with previously-defined symbol." % locals())
      # self.globalNameSpace['symbolNames'].add(operatorName)
      
    operatorTemplate.operatorNames = operatorNames
    
    vectorName = operatorTemplate.id + "_field"
    
    operatorVectorTemplate = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                                   parent = operatorTemplate,
                                                   **self.argumentsToTemplateConstructors)
    operatorVectorTemplate.type = 'complex'
    if operatorElement.hasAttribute('type'):
      typeString = operatorElement.getAttribute('type').strip().lower()
      if not typeString in ['double', 'complex']:
        raise ParserException(operatorElement, "Unknown IP operator type '%(typeString)s'.\n"
                                               "The 'type' attribute must be either 'double' or 'complex'." % locals())
      operatorVectorTemplate.type = typeString
    
    operatorVectorTemplate.initialSpace = operatorTemplate.operatorSpace
    operatorVectorTemplate.needsInitialisation = False
    
    operatorContainer = operatorTemplate.parent
    integratorTemplate = operatorContainer.parent
    
    if not isinstance(operatorTemplate, NonConstantIPOperatorTemplate):
      operatorVectorTemplate.nComponents = len(integratorTemplate.ipPropagationStepFractions) * len(operatorNames)
    else:
      operatorVectorTemplate.nComponents = integratorTemplate.nonconstantIPFields * len(operatorNames)
    operatorTemplate.operatorVector = operatorVectorTemplate
    
    return operatorTemplate
  
  def parseEXOperatorElement(self, operatorTemplate, operatorElement):
    if operatorElement.hasAttribute('fourier_space'):
      operatorTemplate.operatorSpace = \
        operatorTemplate.field.spaceFromString(operatorElement.getAttribute('fourier_space'),
                                               xmlElement = operatorElement)
    
    operatorNamesElement = operatorElement.getChildElementByTagName('operator_names')
    
    operatorNames = RegularExpressionStrings.symbolsInString(operatorNamesElement.innerText())
    
    if not operatorNames:
      raise ParserException(operatorNamesElement, "operator_names must not be empty.")
    
    resultVectorComponentPrefix = "_" + operatorTemplate.id
    resultVectorComponents = []
    
    for operatorName in operatorNames:
      if operatorName in self.globalNameSpace['symbolNames']:
        raise ParserException(operatorNamesElement,
                "Operator name '%(operatorName)s' conflicts with previously-defined symbol." % locals())
      # I'm not sure that we should be protecting the operator names in an EX or IP operator (except within
      # an operators element)
      
      # self.globalNameSpace['symbolNames'].add(operatorName)
    
    operatorTemplate.operatorNames = operatorNames
    
    if isinstance(operatorTemplate, ConstantEXOperatorTemplate):
      vectorName = operatorTemplate.id + "_field"
      
      operatorVectorTemplate = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                                     parent = operatorTemplate,
                                                     **self.argumentsToTemplateConstructors)
      operatorVectorTemplate.type = 'double'
      
      operatorVectorTemplate.initialSpace = operatorTemplate.operatorSpace
      operatorVectorTemplate.needsInitialisation = False
      operatorVectorTemplate.components = operatorNames[:]
      operatorTemplate.operatorVector = operatorVectorTemplate
    
    
    vectorName = operatorTemplate.id + "_result"
    resultVector = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                         parent = operatorTemplate,
                                         **self.argumentsToTemplateConstructors)
    resultVector.type = 'double'
    
    resultVector.initialSpace = 0
    resultVector.needsInitialisation = False
    resultVector.components = resultVectorComponents
    operatorTemplate.resultVector = resultVector
    
    return operatorTemplate
  
  
  def parseCrossPropagationOperatorElement(self, operatorTemplate, operatorElement):
    if not operatorElement.hasAttribute('algorithm'):
      raise ParserException(operatorElement, "Missing 'algorithm' attribute.")
    
    algorithmString = operatorElement.getAttribute('algorithm').strip()
    
    crossIntegratorClass = None
    
    algorithmSpecificOptionsDict = {}
    
    if algorithmString == 'RK4':
      crossIntegratorClass = Integrators.RK4.RK4
    elif algorithmString == 'SI':
      crossIntegratorClass = Integrators.SI.SI
      if operatorElement.hasAttribute('iterations'):
        algorithmSpecificOptionsDict['iterations'] = RegularExpressionStrings.integerInString(operatorElement.getAttribute('iterations'))
        if algorithmSpecificOptionsDict['iterations']<1:
          raise ParserException(operatorElement, "Iterations element must be 1 or greater (default 3).")
      
    else:
      raise ParserException(operatorElement, "Unknown cross-propagation algorithm '%(algorithmString)s'.\n"
                                             "The options are 'SI' or 'RK4'." % locals())
    
    crossIntegratorTemplate = crossIntegratorClass(xmlElement = operatorElement,
                                                   parent = operatorTemplate,
                                                   **self.argumentsToTemplateConstructors)
    crossIntegratorTemplate.cross = True
    
    self.applyAttributeDictionaryToObject(algorithmSpecificOptionsDict, crossIntegratorTemplate)
    
    if not operatorElement.hasAttribute('propagation_dimension'):
      raise ParserException(operatorElement, "Missing 'propagation_dimension' attribute.")
    
    propagationDimensionName = operatorElement.getAttribute('propagation_dimension').strip()
    fullField = operatorTemplate.field
    if not fullField.hasDimensionName(propagationDimensionName):
      fullFieldName = fullField.name
      raise ParserException(operatorElement, "The '%(propagationDimensionName)s' dimension must be a dimension of the\n"
                                             "'%(fullFieldName)s' field in order to cross-propagate along this dimension."
                                             % locals())
    
    operatorTemplate.propagationDimension = propagationDimensionName
    
    propagationDimension = fullField.dimensionWithName(propagationDimensionName)
    
    propDimRep = propagationDimension.inSpace(0)
    
    if not propDimRep.type == 'double' or not isinstance(propagationDimension.inSpace(0), UniformDimensionRepresentation):
      raise ParserException(operatorElement, "Cannot integrate in the '%(propagationDimensionName)s' direction as it is an integer-valued dimension.\n"
                                             "Cross-propagators can only integrate along normal dimensions." % locals())
    
    fieldPropagationDimensionIndex = fullField.indexOfDimension(propagationDimension)
    # Set the stepCount -- this is the lattice for this dimension minus 1 because we know the value at the starting boundary
    crossIntegratorTemplate.stepCount = ''.join(['(', propDimRep.globalLattice, ' - 1)'])
    
    boundaryConditionElement = operatorElement.getChildElementByTagName('boundary_condition')
    
    if not boundaryConditionElement.hasAttribute('kind'):
      raise ParserException(boundaryConditionElement, "The 'boundary_condition' tag must have a kind='left' or kind='right' attribute.")
    
    kindString = boundaryConditionElement.getAttribute('kind').strip().lower()
    
    if kindString == 'left':
      operatorTemplate.propagationDirection = '+'
    elif kindString == 'right':
      operatorTemplate.propagationDirection = '-'
    else:
      raise ParserException(boundaryConditionElement, "Unknown boundary condition kind '%(kindString)s'. Options are 'left' or 'right'." % locals())
    
    # Set the step
    crossIntegratorTemplate.step = ''.join([operatorTemplate.propagationDirection, '_', fullField.name, '_d', propagationDimensionName])
    
    
    operatorTemplate.boundaryConditionDependenciesEntity = self.parseDependencies(boundaryConditionElement, optional=True)
    
    operatorTemplate.boundaryConditionCodeEntity = ParsedEntity(boundaryConditionElement, boundaryConditionElement.cdataContents())
    
    integrationVectorsElement = operatorElement.getChildElementByTagName('integration_vectors')
    integrationVectorNames = RegularExpressionStrings.symbolsInString(integrationVectorsElement.innerText())
    operatorTemplate.integrationVectorsEntity = ParsedEntity(integrationVectorsElement, integrationVectorNames)
    
    # We need to construct the field element for the reduced dimensions
    reducedField = operatorTemplate.reducedDimensionFieldForField(fullField)
    operatorTemplate.reducedField = reducedField
    
    operatorContainer = OperatorContainerTemplate(field = reducedField,
                                                  parent = crossIntegratorTemplate,
                                                  **self.argumentsToTemplateConstructors)
    crossIntegratorTemplate.intraStepOperatorContainers.append(operatorContainer)
    
    # Now we can construct the delta a operator for the cross-propagation integrator
    # When we parse our operator elements (if we have any), the delta a operator will also be constructed
    self.parseOperatorElements(operatorElement, operatorContainer, crossIntegratorTemplate)
    
    operatorTemplate.crossPropagationIntegrator = crossIntegratorTemplate
    operatorTemplate.crossPropagationIntegratorDeltaAOperator = operatorContainer.deltaAOperator
  
  
  def parseOutputElement(self, simulationElement):
    outputElement = simulationElement.getChildElementByTagName('output')
    if not outputElement.hasAttribute('format') or not outputElement.getAttribute('format').strip():
      raise ParserException(outputElement, "Missing format attribute.")
    
    formatString = outputElement.getAttribute('format').strip()
    
    outputTemplateClass = None
    
    if formatString.lower() == 'binary':
      outputTemplateClass = BinaryOutputTemplate
    elif formatString.lower() == 'ascii':
      outputTemplateClass = AsciiOutputTemplate
    else:
      raise ParserException(outputElement, "The format attribute must be either 'binary' or 'ascii'.")
    
    
    if not outputElement.hasAttribute('filename'):
      filename = self.globalNameSpace['simulationName']
    elif not outputElement.getAttribute('filename').strip():
      raise ParserException(outputElement, "Filename attribute is empty.")
    else:
      filename = outputElement.getAttribute('filename').strip()
    
    if filename.lower().endswith('.xsil'):
      index = filename.lower().rindex('.xsil')
      filename = filename[0:index]
    
    outputTemplate = outputTemplateClass(parent = self.simulation, **self.argumentsToTemplateConstructors)
    outputTemplate.precision = 'double'
    outputTemplate.filename = filename
    outputTemplate.xmlElement = outputElement
    
    geometryTemplate = self.globalNameSpace['geometry']
    
    momentGroupElements = outputElement.getChildElementsByTagName('group', optional=True)
    for momentGroupNumber, momentGroupElement in enumerate(momentGroupElements):
      samplingElement = momentGroupElement.getChildElementByTagName('sampling')
      
      momentGroupTemplate = MomentGroupTemplate(number = momentGroupNumber, xmlElement = momentGroupElement,
                                                parent = self.simulation,
                                                **self.argumentsToTemplateConstructors)
      
      samplingFieldTemplate = FieldElementTemplate(name = momentGroupTemplate.name + "_sampling", parent = self.simulation,
                                                   **self.argumentsToTemplateConstructors)
      momentGroupTemplate.samplingField = samplingFieldTemplate
      
      outputFieldTemplate = FieldElementTemplate(name = momentGroupTemplate.name + "_output", parent = self.simulation,
                                                 **self.argumentsToTemplateConstructors)
      momentGroupTemplate.outputField = outputFieldTemplate
      
      momentGroupTemplate.computedVectors.update(self.parseComputedVectorElements(samplingElement, momentGroupTemplate))
      
      sampleCount = 0
      
      if samplingElement.hasAttribute('initial_sample'):
        if samplingElement.getAttribute('initial_sample').strip().lower() == 'yes':
          momentGroupTemplate.requiresInitialSample = True
          sampleCount = 1
      
      momentGroupTemplate.sampleSpace = 0
      samplingDimension = Dimension(name = self.globalNameSpace['globalPropagationDimension'],
                                    transverse = False,
                                    transform = self.globalNameSpace['transforms']['none'],
                                    parent = momentGroupTemplate.outputField,
                                    **self.argumentsToTemplateConstructors)
      samplingDimension.addRepresentation(NonUniformDimensionRepresentation(name = self.globalNameSpace['globalPropagationDimension'],
                                                                            type = 'double',
                                                                            lattice = sampleCount,
                                                                            parent = samplingDimension,
                                                                            **self.argumentsToTemplateConstructors))
      
      momentGroupTemplate.outputField.dimensions = [samplingDimension]
      
      dimensionElements = samplingElement.getChildElementsByTagName('dimension', optional=True)
      
      for dimensionElement in dimensionElements:
        if not dimensionElement.hasAttribute('name') or not dimensionElement.getAttribute('name').strip():
          raise ParserException(dimensionElement, 
                  'Dimension element needs a name attribute corresponding to a dimension name')
        
        dimensionName = dimensionElement.getAttribute('name').strip()
        
        if not geometryTemplate.hasDimensionName(dimensionName):
          raise ParserException(dimensionElement, 
                  "Dimension name '%(dimensionName)s' doesn't correspond to a previously-defined dimension." % locals())
        
        geometryDimension = geometryTemplate.dimensions[geometryTemplate.indexOfDimensionName(dimensionName)]
        
        fourierSpace = False
        if dimensionElement.hasAttribute('fourier_space') and geometryDimension.isTransformable:
          spaceString = dimensionElement.getAttribute('fourier_space').strip().lower()
          fourierSpace = None
          if spaceString == 'yes':
            fourierSpace = True
          elif spaceString == 'no':
            fourierSpace = False
          else:
            if geometryDimension.inSpace(0).name == spaceString:
              fourierSpace = False
            elif geometryDimension.inSpace(-1).name == spaceString:
              fourierSpace = True
          if fourierSpace == None:
            raise ParserException(dimensionElement, "fourier_space attribute for dimension '%s' must be 'yes' / '%s' or 'no' / '%s'"
                                                    % (dimensionName, geometryDimension.inSpace(-1).name, geometryDimension.inSpace(0).name))
        
        dimensionRepresentation = geometryDimension.inSpace(0)
        if fourierSpace:
          momentGroupTemplate.sampleSpace |= geometryDimension.transformMask
          dimensionRepresentation = geometryDimension.inSpace(momentGroupTemplate.sampleSpace)
        
        lattice = dimensionRepresentation.lattice
        
        if dimensionElement.hasAttribute('lattice'):
          latticeString = dimensionElement.getAttribute('lattice').strip()
          if not latticeString:
            raise ParserException(dimensionElement, "If the lattice attribute is present, it must not be empty.")
          
          if not latticeString.isdigit():
            raise ParserException(dimensionElement,
                    "Unable to interpret '%(latticeString)s' as an integer" % locals())
          
          lattice = int(latticeString)
          geometryLattice = int(geometryDimension.inSpace(momentGroupTemplate.sampleSpace).lattice)
          
          if lattice > geometryLattice:
            raise ParserException(dimensionElement, 
                    "Can't sample more points than there are points in the original dimension.")
          
          if not fourierSpace:
            if lattice > 1 and not (geometryLattice % lattice) == 0:
              raise ParserException(dimensionElement,
                      "The number of sampling lattice points must divide the number "
                      "of lattice points on the simulation grid.")
          # If it is in fourier space, then all we require is that the number of points
          # is less than the total number of points, something that we have already checked.
          
        if lattice > 1:
          outputFieldDimension = geometryDimension.copy(parent = outputFieldTemplate)
          if not dimensionRepresentation.lattice == lattice:
            for rep in outputFieldDimension.representations:
              rep.lattice = lattice
          samplingFieldTemplate.dimensions.append(outputFieldDimension.copy(parent = samplingFieldTemplate))
          outputFieldTemplate.dimensions.append(outputFieldDimension)
          
        elif lattice == 1:
          # In this case, we don't want the dimension in either the moment group, or the sampling field
          pass
        elif lattice == 0:
          # In this case, the dimension only belongs to the sampling field because we are integrating over it.
          # Note that we previously set the lattice of the dimension to be the same as the number
          # of points in this dimension according to the geometry element.
          
          samplingFieldTemplate.dimensions.append(geometryDimension.copy(parent=samplingFieldTemplate))
      
      samplingFieldTemplate.sortDimensions()
      outputFieldTemplate.sortDimensions()
      
      for field in [samplingFieldTemplate, outputFieldTemplate]:
        field.sortDimensions()
        space = momentGroupTemplate.sampleSpace
        for dim in field.dimensions:
          if not dim.inSpace(space).lattice == geometryTemplate.dimensionWithName(dim.name).inSpace(space).lattice:
            dim.invalidateRepresentationsOtherThan(dim.inSpace(space))
      
      # end looping over dimension elements.  
      rawVectorTemplate = VectorElementTemplate(name = 'raw', field = momentGroupTemplate.outputField,
                                                **self.argumentsToTemplateConstructors)
      rawVectorTemplate.type = 'double'
      rawVectorTemplate.initialSpace = momentGroupTemplate.sampleSpace
      momentGroupTemplate.rawVector = rawVectorTemplate
      
      momentsElement = samplingElement.getChildElementByTagName('moments')
      momentNames = RegularExpressionStrings.symbolsInString(momentsElement.innerText())
      
      if not momentNames:
        raise ParserException(momentsElement, "Moments element should be a list of moment names")
      
      for momentName in momentNames:
        if momentName in self.globalNameSpace['symbolNames']:
          raise ParserException(momentsElement, 
                  "'%(momentName)s' cannot be used as a moment name because it clashes with "
                  "a previously-defined variable." % locals())
        
        ## We don't add the momentName to the symbol list because they can be used by other moment groups safely
        rawVectorTemplate.components.append(momentName)
      
      momentGroupTemplate.dependenciesEntity = self.parseDependencies(samplingElement)
      
      samplingCodeEntity = ParsedEntity(samplingElement, samplingElement.cdataContents())
      if not samplingCodeEntity.value:
        raise ParserException(samplingElement, "The CDATA section for the sampling code must not be empty.")
      
      momentGroupTemplate.samplingCodeEntity = samplingCodeEntity
      momentGroupTemplate.outputSpace = momentGroupTemplate.sampleSpace & momentGroupTemplate.outputField.spaceMask
      
      operatorContainer = self.parseFilterElements(samplingElement, parent=momentGroupTemplate, optional=True)
      if operatorContainer:
        momentGroupTemplate.operatorContainers.append(operatorContainer)
      
      operatorElements = samplingElement.getChildElementsByTagName('operator', optional=True)
      if operatorElements:
        operatorContainer = OperatorContainerTemplate(field = samplingFieldTemplate,
                                                      # Point the proxies for the shared code etc at
                                                      # the moment group object's sampling code, the sampling space, etc.
                                                      sharedCodeEntityKeyPath = 'parent.samplingCodeEntity',
                                                      sharedCodeSpaceKeyPath = 'parent.sampleSpace',
                                                      dependenciesKeyPath = 'parent.dependencies',
                                                      parent = momentGroupTemplate,
                                                      **self.argumentsToTemplateConstructors)
        
        momentGroupTemplate.operatorContainers.append(operatorContainer)
        for operatorElement in operatorElements:
          kindString = operatorElement.getAttribute('kind').strip().lower()
          if not kindString in ('functions', 'ex'):
            raise ParserException(operatorElement, "Unrecognised operator kind '%(kindString)s'. "
                                                   "The only valid operator kinds in sampling elements are 'functions' and 'ex'." % locals())
          operatorTemplate = self.parseOperatorElement(operatorElement, operatorContainer)
          if isinstance(operatorTemplate, ConstantEXOperatorTemplate):
            raise ParserException(operatorElement, "You cannot have a constant EX operator in moment group sampling. Try constant=\"no\".")
      
      
      
      # We have now dealt with the sampling element, and now need to deal with the processing element.
      # TODO: Implement processing element.
      processingElement = momentGroupElement.getChildElementByTagName('post_processing', optional=True)
      
      processedVectorTemplate = VectorElementTemplate(name = 'processed', field = outputFieldTemplate,
                                                      **self.argumentsToTemplateConstructors)
      processedVectorTemplate.type = 'double'
      processedVectorTemplate.initialSpace = momentGroupTemplate.outputSpace
      momentGroupTemplate.processedVector = processedVectorTemplate
      
      if not processingElement:
        momentGroupTemplate.hasPostProcessing = False
        processedVectorTemplate.components = rawVectorTemplate.components[:]
        rawVectorTemplate.type = 'double'
      else:
        momentGroupTemplate.hasPostProcessing = True
  

