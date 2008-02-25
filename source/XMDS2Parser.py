#!/usr/bin/env python
# encoding: utf-8
"""
XMDS2Parser.py

Created by Graham Dennis on 2007-12-29.
Copyright (c) 2007 __MyCompanyName__. All rights reserved.
"""

import re
from ScriptParser import ScriptParser
from ParserException import ParserException
from ParsedEntity import ParsedEntity
from xml.dom import minidom
import RegularExpressionStrings

from SimulationElement import SimulationElement as SimulationElementTemplate
from GeometryElement import GeometryElement as GeometryElementTemplate
from FieldElement import FieldElement as FieldElementTemplate
from Dimension import Dimension

from VectorElement import VectorElement as VectorElementTemplate
from VectorInitialisation import VectorInitialisation as VectorInitialisationZeroTemplate
from VectorInitialisationCDATA import VectorInitialisationCDATA as VectorInitialisationCDATATemplate


from TopLevelSequenceElement import TopLevelSequenceElement as TopLevelSequenceElementTemplate
from DefaultDriver import DefaultDriver as DefaultDriverTemplate
from MultiPathDriver import MultiPathDriver as MultiPathDriverTemplate

from FixedStepIntegrator import FixedStepIntegrator
from AdaptiveStepIntegrator import AdaptiveStepIntegrator

from RK4Integrator import RK4Integrator as RK4IntegratorTemplate
from RK9Integrator import RK9Integrator as RK9IntegratorTemplate
from ARK45Integrator import ARK45Integrator as ARK45IntegratorTemplate
from ARK89Integrator import ARK89Integrator as ARK89IntegratorTemplate

from DeltaAOperator import DeltaAOperator as DeltaAOperatorTemplate
from ConstantIPOperator import ConstantIPOperator as ConstantIPOperatorTemplate
from AdaptiveStepIPOperator import AdaptiveStepIPOperator as AdaptiveStepIPOperatorTemplate
from ConstantEXOperator import ConstantEXOperator as ConstantEXOperatorTemplate
from NonConstantEXOperator import NonConstantEXOperator as NonConstantEXOperatorTemplate
from FilterOperator import FilterOperator as FilterOperatorTemplate


from BinaryOutput import BinaryOutput as BinaryOutputTemplate
from AsciiOutput import AsciiOutput as AsciiOutputTemplate
from MomentGroupElement import MomentGroupElement as MomentGroupTemplate


from AutoVectoriseFeature import AutoVectoriseFeature
from BenchmarkFeature import BenchmarkFeature
from ErrorCheckFeature import ErrorCheckFeature
from BingFeature import BingFeature
from OpenMPFeature import OpenMPFeature
from GlobalsFeature import GlobalsFeature
from ArgvFeature import ArgvFeature

from StochasticFeature import StochasticFeature
from GaussianPOSIXNoise import GaussianPOSIXNoise
from SlowGaussianPOSIXNoise import SlowGaussianPOSIXNoise
from UniformPOSIXNoise import UniformPOSIXNoise
from PoissonianPOSIXNoise import PoissonianPOSIXNoise
from GaussianMKLNoise import GaussianMKLNoise
from UniformMKLNoise import UniformMKLNoise

from FourierTransformNone import FourierTransformNone
from FourierTransformFFTW2 import FourierTransformFFTW2
from FourierTransformFFTW3 import FourierTransformFFTW3
from FourierTransformFFTW3Threads import FourierTransformFFTW3Threads

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
  
  def parseXMLDocument(self, xmlDocument, globalNameSpace, filterClass):
    self.argumentsToTemplateConstructors = {'searchList':[globalNameSpace], 'filter': filterClass}
    self.globalNameSpace = globalNameSpace
    
    simulationElement = xmlDocument.getChildElementByTagName("simulation")
    
    nameElement = simulationElement.getChildElementByTagName('name')
    self.globalNameSpace['simulationName'] = nameElement.innerText()
    
    authorElement = simulationElement.getChildElementByTagName('author')
    self.globalNameSpace['author'] = authorElement.innerText()
    
    descriptionElement = simulationElement.getChildElementByTagName('description')
    self.globalNameSpace['simulationDescription'] = descriptionElement.innerText()
    
    simulationElementTemplate = SimulationElementTemplate(**self.argumentsToTemplateConstructors)
    
    self.parseFeatures(simulationElement)
    
    self.parseGeometryElement(simulationElement)
    
    self.parseFieldElements(simulationElement)
    
    self.parseTopLevelSequenceElement(simulationElement)
    
    self.parseOutputElement(simulationElement)
    
    return simulationElementTemplate
  
  
  def parseFeatures(self, simulationElement):
    featuresParentElement = simulationElement.getChildElementByTagName('features', optional=True)
    if not featuresParentElement:
      featuresParentElement = simulationElement
    
    def parseSimpleFeature(tagName, featureClass):
      featureElement = featuresParentElement.getChildElementByTagName(tagName, optional=True)
      feature = None
      if featureElement:
        if len(featureElement.innerText()) == 0 or featureElement.innerText().lower() == 'yes':
          feature = featureClass(**self.argumentsToTemplateConstructors)
          feature.xmlElement = featureElement
      return featureElement, feature
    
    
    parseSimpleFeature('auto_vectorise', AutoVectoriseFeature)
    parseSimpleFeature('benchmark', BenchmarkFeature)
    parseSimpleFeature('error_check', ErrorCheckFeature)
    parseSimpleFeature('bing', BingFeature)
    parseSimpleFeature('openmp', OpenMPFeature)
    
    argvFeatureElement, argvFeature = parseSimpleFeature('argv', ArgvFeature)
    
    if argvFeatureElement:
      argElements = argvFeatureElement.getChildElementsByTagName('arg')
      
      argList = []
      # Note that "h" is already taken as the "help" option 
      shortOptionNames = set(['h'])
      
      for argElement in argElements:
        name = argElement.getAttribute('name').strip()
        type = argElement.getAttribute('type').strip().lower()
        defaultValue = argElement.getAttribute('default_value').strip()
        
        # Determine the short name (i.e. single character) of the full option name
        shortName = ""
        for character in name:
          if character not in shortOptionNames:
            shortName = character
            shortOptionNames.add(character)
            break
        
        if shortName == "":
          raise ParserException(argElement, "Unable to find a short (single character) name for command line option")        
        
        argAttributeDictionary = dict()
        
        argAttributeDictionary['name'] = name
        argAttributeDictionary['shortName'] = shortName
        argAttributeDictionary['type'] = type
        argAttributeDictionary['defaultValue'] = defaultValue
        
        argList.append(argAttributeDictionary)
      
      argvFeature.argList = argList
    
    
    globalsElement = featuresParentElement.getChildElementByTagName('globals', optional=True)
    if globalsElement:
      globalsTemplate = GlobalsFeature(**self.argumentsToTemplateConstructors)
      globalsTemplate.globalsCode = globalsElement.cdataContents()
    
    stochasticFeatureElement, stochasticFeature = parseSimpleFeature('stochastic', StochasticFeature)
    
    if stochasticFeature:
      stochasticFeature.xmlElement = stochasticFeatureElement
      noiseElements = stochasticFeatureElement.getChildElementsByTagName('noise')
      stochasticFeature.noises = []
      for noiseElement in noiseElements:
        kind = noiseElement.getAttribute('kind').strip().lower()
        noiseClass = None
        noiseAttributeDictionary = dict()
        if kind in ('gauss', 'gaussian', 'gaussian-posix'):
          noiseClass = GaussianPOSIXNoise
        elif kind in ('slow-gaussian', 'slow-gaussian-posix'):
          noiseClass = SlowGaussianPOSIXNoise
        elif kind in ('uniform', 'uniform-posix'):
          noiseClass = UniformPOSIXNoise
        elif kind in ('poissonian', 'poissonian-posix'):
          noiseClass = PoissonianPOSIXNoise
          if not noiseElement.hasAttribute('mean-rate'):
            raise ParserException(noiseElement, "Poissonian noise must specify a 'mean-rate' attribute.")
          
          meanRateString = noiseElement.getAttribute('mean-rate')
          try:
            meanRate = float(meanRateString)
          except ValueError, err:
            raise ParserException(noiseElement, "Unable to understand '%(meanRateString)s' as a real value." % locals())
          noiseAttributeDictionary['noiseMeanRate'] = meanRateString
        elif kind in ('gaussian-mkl'):
          noiseClass = GaussianMKLNoise
        elif kind in ('uniform-mkl'):
          noiseClass = UniformMKLNoise
        else:
          raise ParserException(noiseElement, "Unknown noise kind '%(kind)s'." % locals())
        noise = noiseClass(**self.argumentsToTemplateConstructors)
        
        self.applyAttributeDictionaryToObject(noiseAttributeDictionary, noise)
        
        prefix = noiseElement.getAttribute('prefix').strip()
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
          seedString = noiseElement.getAttribute('seed').strip()
          noise.seedArray = RegularExpressionStrings.integersInString(seedString)
        
        stochasticFeature.noises.append(noise)
    
    fftwElement = featuresParentElement.getChildElementByTagName('fftw', optional=True)
    
    fourierTransformClass = None
    
    fftAttributeDictionary = dict()
    
    if not fftwElement:
      fourierTransformClass = FourierTransformNone
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
        fourierTransformClass = FourierTransformFFTW3
      elif fftwElement.getAttribute('version').strip() == '3':
        fourierTransformClass = FourierTransformFFTW3
      elif fftwElement.getAttribute('version').strip() == '2':
        fourierTransformClass = FourierTransformFFTW2
      elif fftwElement.getAttribute('version').strip().lower() == 'none':
        fourierTransformClass = FourierTransformNone
      else:
        raise ParserException(fftwElement, "The version attribute must be one of 'None', '2', or '3'.")
      
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
        if fourierTransformClass == FourierTransformFFTW3:
          fourierTransformClass = FourierTransformFFTW3Threads
        elif fourierTransformClass == FourierTransformFFTW2:
          raise ParserException(fftwElement, "Can't use threads with FFTW2.")
        elif fourierTransformClass == FourierTransformNone:
          raise ParserException(fftwElement, "Can't use threads with no fourier transforms.")
        else:
          # This shouldn't be reached because the fourierTransformClass should be one of the above options
          raise ParserException(fftwElement, "Internal consistency error.")
        
        fftAttributeDictionary['threadCount'] = threadCount
    
    fourierTransform = fourierTransformClass(**self.argumentsToTemplateConstructors)
    
    self.applyAttributeDictionaryToObject(fftAttributeDictionary, fourierTransform)
  
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
  
  def parseGeometryElement(self, simulationElement):
    geometryElement = simulationElement.getChildElementByTagName('geometry')
    
    geometryTemplate = GeometryElementTemplate(**self.argumentsToTemplateConstructors)
    
    ## First grab the propagation dimension name
    
    propagationDimensionElement = geometryElement.getChildElementByTagName('prop_dim')
    if len(propagationDimensionElement.innerText()) == 0:
      raise ParserException(propagationDimensionElement, "The prop_dim element must not be empty")
    
    propagationDimensionName = propagationDimensionElement.innerText()
    self.globalNameSpace['propagationDimension'] = propagationDimensionName
    
    geometryTemplate.dimensions = [Dimension(name = propagationDimensionName, transverse = False)]
    
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
        
        minimumString, maximumString = self.domainPairFromString(domainString, float, dimensionElement)
        
        geometryTemplate.dimensions.append(Dimension(name = dimensionName, transverse = True, lattice = int(latticeString),
                                                     minimum = minimumString, maximum = maximumString))
      
      # We have just finished looping over the normal dimensions in the transverse_dimensions element.
      # Now we need to grab any 'integer_valued' tags and parse those.
      self.parseIntegerValuedElements(transverseDimensionsElement, geometryTemplate)
    
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
      
      minimumString, maximumString = self.domainPairFromString(domainString, int, dimensionElement)
      # We are guaranteed that these can be transformed into int's
      minimumValue = int(minimumString)
      maximumValue = int(maximumString)
      
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
      
      dimensionList.append(Dimension(name = dimensionName, transverse = True, type = 'long', lattice = lattice,
                                     minimum = minimumString, maximum = maximumString))
    
    if not dimensionElement.hasAttribute('kind') or dimensionElement.getAttribute('kind').strip().lower() == 'last':
      geometryTemplate.dimensions.extend(dimensionList)
    else:
      dimensionList.reverse()
      for dim in dimensionList:
        geometryTemplate.dimensions.insert(0, dim)
    
    
  
  def parseFieldElements(self, simulationElement):
    fieldElements = simulationElement.getChildElementsByTagName('field')
    for fieldElement in fieldElements:
      self.parseFieldElement(fieldElement)
  
  def parseFieldElement(self, fieldElement):
    if not fieldElement.hasAttribute('name') or len(fieldElement.getAttribute('name')) == 0:
      raise ParserException(fieldElement, "Each field element must have a non-empty 'name' attribute")
    
    fieldName = fieldElement.getAttribute('name').strip()
    try:
      fieldName = RegularExpressionStrings.symbolInString(fieldName)
    except ValueError, err:
      raise ParserException(fieldElement, "Cannot accept '%(fieldName)s as the name of a field." % locals())
    
    ## Check that the name isn't already taken
    if fieldName in self.globalNameSpace['symbolNames']:
      raise ParserException(fieldElement, "Field name '%(fieldName)s' conflicts with previously "
                                          "defined symbol of the same name." % locals())
    ## Make sure no-one else takes the name
    self.globalNameSpace['symbolNames'].add(fieldName)
    
    fieldTemplate = FieldElementTemplate(name = fieldName, **self.argumentsToTemplateConstructors)
    fieldTemplate.xmlElement = fieldElement
    
    if not fieldElement.hasAttribute('dimensions'):
      fieldTemplate.dimensions = filter(lambda x: x.transverse, self.globalNameSpace['geometry'].dimensions)
    elif len(fieldElement.getAttribute('dimensions').strip()) == 0:
      # No dimensions
      pass
    else:
      dimensionsString = fieldElement.getAttribute('dimensions').strip()
      results = RegularExpressionStrings.symbolsInString(dimensionsString)
      if not results:
        raise ParserException(fieldElement, "Cannot understand '%(dimensionsString)s' as a "
                                            "list of dimensions" % locals())
      
      geometryTemplate = self.globalNameSpace['geometry']
      
      for dimensionName in results:
        if not geometryTemplate.hasDimensionName(dimensionName):
          raise ParserException(fieldElement, "Don't recognise '%(dimensionName)s' as one of "
                                              "the dimensions defined in the geometry element." % locals())
        
        fieldTemplate.dimensions.append(geometryTemplate.dimensions[geometryTemplate.indexOfDimensionName(dimensionName)])
    
    fieldTemplate.sortDimensions()
    
    for field in self.globalNameSpace['fields']:
      if (not field == fieldTemplate) and fieldTemplate.isSubsetOfField(field) and field.isSubsetOfField(fieldTemplate):
        raise ParserException(fieldElement, "Cannot have two fields with the same dimensions."
                                            " Conflict between '%s' and '%s'." % (field.name, fieldTemplate.name))
    
    self.parseVectorElements(fieldElement, fieldTemplate)
    
    return fieldTemplate
  
  
  def parseVectorElements(self, fieldElement, fieldTemplate):
    vectorElements = fieldElement.getChildElementsByTagName('vector')
    for vectorElement in vectorElements:
      vectorTemplate = self.parseVectorElement(vectorElement, fieldTemplate)
      fieldTemplate.managedVectors.add(vectorTemplate)
    
  
  def parseVectorElement(self, vectorElement, fieldTemplate):
    if not vectorElement.hasAttribute('name') or len(vectorElement.getAttribute('name')) == 0:
      raise ParserException(vectorElement, "Each vector element must have a non-empty 'name' attribute")
    
    vectorName = vectorElement.getAttribute('name')
    
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
      vectorTemplate.initialSpace = fieldTemplate.spaceFromString(vectorElement.getAttribute('initial_space'))
    
    componentsElement = vectorElement.getChildElementByTagName('components')
    
    typeString = None
    if componentsElement.hasAttribute('type'):
      typeString = componentsElement.getAttribute('type').lower()
    
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
        initialisationTemplate = VectorInitialisationCDATATemplate(**self.argumentsToTemplateConstructors)
        if len(initialisationElement.cdataContents()) == 0:
          raise ParserException(initialisationElement, "Empty initialisation code in 'code' initialisation element.")
        initialisationTemplate.initialisationCode = initialisationElement.cdataContents()
      elif kindString == 'zero':
        initialisationTemplate = vectorTemplate.initialiser
      else:
        raise ParserException(initialisationElement, "Initialisation kind '%(kindString)s' is unrecognised. "
                                                     "The options are 'code' (default), or 'zero' "
                                                     "(this is the same as having no initialisation element)." % locals())
      
      # Untie the old initialiser from the vector
      # Probably not strictly necessary
      if not vectorTemplate.initialiser == initialisationTemplate:
        vectorTemplate.initialiser.vector = None
        vectorTemplate.initialiser.remove()
      initialisationTemplate.vector = vectorTemplate
      vectorTemplate.initialiser = initialisationTemplate
      
      self.parseNoisesAttribute(initialisationElement, initialisationTemplate)
    
    return vectorTemplate
  
  
  def parseTopLevelSequenceElement(self, simulationElement):
    topLevelSequenceElement = simulationElement.getChildElementByTagName('sequence')
    
    driverClass = DefaultDriverTemplate
    
    driverAttributeDictionary = dict()
    
    if topLevelSequenceElement.hasAttribute('driver'):
      driverName = topLevelSequenceElement.getAttribute('driver').strip()
      if driverName == 'multi-path':
        driverClass = MultiPathDriverTemplate
        if not topLevelSequenceElement.hasAttribute('paths'):
          raise ParserException(topLevelSequenceElement, "Missing 'paths' attribute for multi-path driver.")
        pathCount = RegularExpressionStrings.integerInString(topLevelSequenceElement.getAttribute('paths'))
        driverAttributeDictionary['pathCount'] = pathCount
      elif driverName == 'none':
        pass
      else:
        raise ParserException(topLevelSequenceElement, "Unknown driver type '%(driverName)s'. "
                                                       "The options are 'none' (default), or 'multi-path'." % locals())
    
    topLevelSimulationElementTemplate = driverClass(**self.argumentsToTemplateConstructors)
    
    self.applyAttributeDictionaryToObject(driverAttributeDictionary, topLevelSimulationElementTemplate)
    
    for childNode in topLevelSequenceElement.childNodes:
      if not childNode.nodeType == minidom.Node.ELEMENT_NODE:
        continue
      
      if childNode.tagName.lower() == 'integrate':
        integrateTemplate = self.parseIntegrateElement(childNode)
        topLevelSimulationElementTemplate.childSegments.append(integrateTemplate)
      else:
        raise ParserException(childNode, "Unknown child of sequence element. "
                                         "Possible children include 'integrate' elements.")
      
    return topLevelSimulationElementTemplate
  
  
  def parseIntegrateElement(self, integrateElement):
    if not integrateElement.hasAttribute('algorithm'):
      raise ParserException(integrateElement, "Integration element must have an 'algorithm' attribute.")
    
    integratorTemplateClass = None
    
    algorithmString = integrateElement.getAttribute('algorithm')
    if algorithmString == 'RK4':
      integratorTemplateClass = RK4IntegratorTemplate
    elif algorithmString == 'RK9':
      integratorTemplateClass = RK9IntegratorTemplate
    elif algorithmString == 'ARK45':
      integratorTemplateClass = ARK45IntegratorTemplate
    elif algorithmString == 'ARK89':
      integratorTemplateClass = ARK89IntegratorTemplate
    else:
      raise ParserException(integrateElement, "Unknown algorithm '%(algorithmString)s'. "
                                              "Options are 'RK4', 'RK9', 'ARK45' or 'ARK89'." % locals())
    
    integratorTemplate = integratorTemplateClass(**self.argumentsToTemplateConstructors)
    
    if integrateElement.hasAttribute('home_space'):
      attributeValue = integrateElement.getAttribute('home_space').strip().lower()
      if attributeValue == 'k':
        integratorTemplate.homeSpace = globalNameSpace['geometry'].spaceMask
      elif attributeValue == 'x':
        integratorTemplate.homeSpace = 0
      else:
        raise ParserException(integrateElement, "home_space must be either 'k' or 'x'.")
    
    if issubclass(integratorTemplateClass, AdaptiveStepIntegrator):
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
    try:
      interval = float(intervalString)
      if interval <= 0.0:
        raise ParserException(integrateElement, "Interval must be positive.")
    except ValueError, err:
      raise ParserException(integrateElement, "Could not understand interval '%(intervalString)s' "
                                              "as a number." % locals())
    
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
    
    self.parseOperatorsElements(integrateElement, integratorTemplate)
    
    return integratorTemplate
  
  
  def parseOperatorsElements(self, integrateElement, integratorTemplate):
    operatorsElements = integrateElement.getChildElementsByTagName('operators')
    
    fieldNamesUsed = set()
    validFieldNames = [field.name for field in self.globalNameSpace['fields']]
    
    for operatorsElement in operatorsElements:
      if not operatorsElement.hasAttribute('field'):
        raise ParserException(operatorsElement, "Missing 'field' attribute.")
      fieldName = operatorsElement.getAttribute('field').strip()
      
      if fieldName in fieldNamesUsed:
        raise ParserException(operatorsElement, "There can only be one operators element per field.")
      
      if not fieldName in validFieldNames:
        raise ParserException(operatorsElement, "'%(fieldName)s' isn't the name of a field." % locals())
      
      fieldNamesUsed.add(fieldName)
      fieldTemplate = filter(lambda x: x.name == fieldName, self.globalNameSpace['fields'])[0]
      
      self.parseOperatorsElement(operatorsElement, integratorTemplate, fieldTemplate)
    
  
  def parseOperatorsElement(self, operatorsElement, integratorTemplate, fieldTemplate):
    deltaAOperatorTemplate = DeltaAOperatorTemplate(field = fieldTemplate, integrator = integratorTemplate,
                                                    **self.argumentsToTemplateConstructors)
    deltaAOperatorTemplate.propagationCode = operatorsElement.cdataContents()
    deltaAOperatorTemplate.xmlElement = operatorsElement
    
    self.parseNoisesAttribute(operatorsElement, deltaAOperatorTemplate)
    
    dependenciesElement = operatorsElement.getChildElementByTagName('dependencies', optional=True)
    dependencyVectorNames = []
    if dependenciesElement:
      dependencyVectorNames = RegularExpressionStrings.symbolsInString(dependenciesElement.innerText())
      deltaAOperatorTemplate.dependenciesEntity = ParsedEntity(dependenciesElement, dependencyVectorNames)
    
    
    integrationVectorsElement = operatorsElement.getChildElementByTagName('integration_vectors')
    integrationVectorsNames = RegularExpressionStrings.symbolsInString(integrationVectorsElement.innerText())
    
    if not integrationVectorsNames:
      raise ParserException(integrationVectorsElement, "Element must be non-empty.")
    
    deltaAOperatorTemplate.integrationVectorsEntity = ParsedEntity(integrationVectorsElement, integrationVectorsNames)
    
    if integrationVectorsElement.hasAttribute('fourier_space'):
      deltaAOperatorTemplate.operatorSpace = \
        deltaAOperatorTemplate.field.spaceFromString(integrationVectorsElement.getAttribute('fourier_space'))
    
    
    self.parseOperatorElements(operatorsElement, integratorTemplate, deltaAOperatorTemplate)
    
    self.xmlElement = operatorsElement
    
    return deltaAOperatorTemplate
  
  def parseOperatorElements(self, operatorsElement, integratorTemplate, deltaAOperatorTemplate):
    operatorElements = operatorsElement.getChildElementsByTagName('operator', optional=True)
    for operatorElement in operatorElements:
      operatorTemplate = self.parseOperatorElement(operatorElement, integratorTemplate, deltaAOperatorTemplate)
  
  def parseOperatorElement(self, operatorElement, integratorTemplate, deltaAOperatorTemplate):
    if not operatorElement.hasAttribute('kind'):
      raise ParserException(operatorElement, "Missing 'kind' attribute.")
    
    kindString = operatorElement.getAttribute('kind').strip()
    
    constantString = None
    if operatorElement.hasAttribute('constant'):
      constantString = operatorElement.getAttribute('constant').strip()
    
    parserMethod = None
    operatorTemplateClass = None
    
    if kindString.lower() == 'ip':
      if not constantString:
        raise ParserException(operatorElement, "Missing 'constant' attribute.")
        
      if not constantString.lower() == 'yes':
        raise ParserException(operatorElement, "There isn't a non-constant IP operator.")
      
      if not isinstance(integratorTemplate, AdaptiveStepIntegrator):
        operatorTemplateClass = ConstantIPOperatorTemplate
      else:
        operatorTemplateClass = AdaptiveStepIPOperatorTemplate
      
      parserMethod = self.parseIPOperatorElement
    elif kindString.lower() == 'ex':
      if not constantString:
        raise ParserException(operatorElement, "Missing 'constant' attribute.")
      
      parserMethod = self.parseEXOperatorElement
      if constantString.lower() == 'yes':
        operatorTemplateClass = ConstantEXOperatorTemplate
      elif constantString.lower() == 'no':
        operatorTemplateClass = NonConstantEXOperatorTemplate
      else:
        raise ParserException(operatorElement, "The constant attribute must be either 'yes' or 'no'.")
    elif kindString.lower() == 'filter':
      parserMethod = self.parseFilterOperatorElement
      operatorTemplateClass = FilterOperatorTemplate
    else:
      raise ParserException(operatorElement, "Unknown operator kind '%(kindString)'s\n"
                                             "Valid options are: 'ip', 'ex' or 'filter'." % locals())
    
    operatorTemplate = operatorTemplateClass(field = deltaAOperatorTemplate.field, integrator = integratorTemplate,
                                             **self.argumentsToTemplateConstructors)
    operatorTemplate.xmlElement = operatorElement
    operatorTemplate.operatorDefinitionCode = operatorElement.cdataContents()
    if operatorElement.hasAttribute('fourier_space'):
      operatorTemplate.operatorSpace = \
        operatorTemplate.field.spaceFromString(operatorElement.getAttribute('fourier_space'))
    
    dependenciesElement = operatorElement.getChildElementByTagName('dependencies', optional=True)
    dependencyVectorNames = []
    if dependenciesElement:
      dependencyVectorNames = RegularExpressionStrings.symbolsInString(dependenciesElement.innerText())
      operatorTemplate.dependenciesEntity = ParsedEntity(dependenciesElement, dependencyVectorNames)
    
    parserMethod(operatorTemplate, operatorElement, deltaAOperatorTemplate)
    
    return operatorTemplate
  
  def parseIPOperatorElement(self, operatorTemplate, operatorElement, deltaAOperatorTemplate):
    operatorNamesElement = operatorElement.getChildElementByTagName('operator_names')
    operatorNames = RegularExpressionStrings.symbolsInString(operatorNamesElement.innerText())
    
    if not operatorNames:
      raise ParserException(operatorNamesElement, "operator_names must not be empty.")
    
    for operatorName in operatorNames:
      if operatorName in self.globalNameSpace['symbolNames']:
        raise ParserException(operatorNamesElement,
                "Operator name '%(operatorName)s' conflicts with previously-defined symbol." % locals())
      self.globalNameSpace['symbolNames'].add(operatorName)
      
    operatorTemplate.deltaAOperator = deltaAOperatorTemplate
    operatorTemplate.operatorNames = operatorNames
    
    operatorTargetPairs = self.targetComponentsForOperatorsInString(operatorNames, deltaAOperatorTemplate.propagationCode)
    
    operatorTemplate.operatorComponentsEntity = ParsedEntity(operatorElement, operatorTargetPairs)
    
    segmentName = operatorTemplate.integrator.name
    operatorName = operatorTemplate.name
    vectorName = "%(segmentName)s_%(operatorName)s_field" % locals()
    
    operatorVectorTemplate = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                                   **self.argumentsToTemplateConstructors)
    operatorVectorTemplate.type = 'complex'
    
    operatorVectorTemplate.initialSpace = operatorTemplate.operatorSpace
    operatorVectorTemplate.needsInitialisation = False
    operatorVectorTemplate.field.temporaryVectors.add(operatorVectorTemplate)
    if not isinstance(operatorTemplate, AdaptiveStepIPOperatorTemplate):
      operatorVectorTemplate.nComponents = len(operatorTemplate.integrator.ipPropagationStepFractions) * len(operatorNames)
    else:
      operatorVectorTemplate.nComponents = operatorTemplate.integrator.nonconstantIPFields * len(operatorNames)
    operatorTemplate.operatorVector = operatorVectorTemplate
    
    return operatorTemplate
  
  def parseEXOperatorElement(self, operatorTemplate, operatorElement, deltaAOperatorTemplate):
    operatorNamesElement = operatorElement.getChildElementByTagName('operator_names')
    
    operatorNames = RegularExpressionStrings.symbolsInString(operatorNamesElement.innerText())
    
    if not operatorNames:
      raise ParserException(operatorNamesElement, "operator_names must not be empty.")
    
    segmentName = operatorTemplate.integrator.name
    operatorName = operatorTemplate.name
    resultVectorComponentPrefix = "_%(segmentName)s_%(operatorName)s" % locals()
    resultVectorComponents = []
    
    for operatorName in operatorNames:
      if operatorName in self.globalNameSpace['symbolNames']:
        raise ParserException(operatorNamesElement,
                "Operator name '%(operatorName)s' conflicts with previously-defined symbol." % locals())
      self.globalNameSpace['symbolNames'].add(operatorName)
    
    operatorTemplate.deltaAOperator = deltaAOperatorTemplate
    operatorTemplate.operatorNames = operatorNames
    
    operatorTargetPairs = self.targetComponentsForOperatorsInString(operatorNames, deltaAOperatorTemplate.propagationCode)
    
    operatorTemplate.operatorComponentsEntity = ParsedEntity(operatorElement, operatorTargetPairs)
    
    if isinstance(operatorTemplate, ConstantEXOperatorTemplate):
      segmentName = operatorTemplate.integrator.name
      operatorNumber = len(operatorTemplate.integrator.operators)
      vectorName = "%(segmentName)s_operator%(operatorNumber)i_field" % locals()
      
      operatorVectorTemplate = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                                     **self.argumentsToTemplateConstructors)
      operatorVectorTemplate.type = 'complex'
      
      operatorVectorTemplate.initialSpace = operatorTemplate.operatorSpace
      operatorVectorTemplate.needsInitialisation = False
      operatorVectorTemplate.field.temporaryVectors.add(operatorVectorTemplate)
      operatorVectorTemplate.components = operatorNames[:]
      operatorTemplate.operatorVector = operatorVectorTemplate
    
    
    vectorName = "%(segmentName)s_operator%(operatorNumber)i_result" % locals()
    resultVector = VectorElementTemplate(name = vectorName, field = operatorTemplate.field,
                                         **self.argumentsToTemplateConstructors)
    resultVector.type = 'complex'
    
    resultVector.initialSpace = 0
    resultVector.needsInitialisation = False
    resultVector.field.temporaryVectors.add(resultVector)
    resultVector.components = resultVectorComponents
    operatorTemplate.resultVector = resultVector
    deltaAOperatorTemplate.dependencies.add(resultVector)
    
    return operatorTemplate
  
  def parseFilterOperatorElement(self, operatorTemplate, operatorElement, deltaAOperatorTemplate):
    targetField = None
    momentsVectorName = None
    geometryTemplate = self.globalNameSpace['geometry']
    
    integratorName = operatorTemplate.integrator.name
    operatorName = operatorTemplate.name
    
    if not operatorTemplate.dependenciesEntity:
      raise ParserException(operatorElement,
              "Filter operators must have a dependencies element.")
    
    momentsElement = operatorElement.getChildElementByTagName('moments', optional=True)
    if momentsElement:
      if momentsElement.hasAttribute('target_field') and momentsElement.hasAttribute('dimensions'):
        raise ParserException(momentsElement,
                "Filter operators must have only one of the attributes 'dimensions' and 'target_field'")
      elif momentsElement.hasAttribute('target_field'):
        targetFieldName = momentsElement.getAttribute('target_field').strip()
        fieldsWithName = filter(lambda x: x.name == targetFieldName, self.globalNameSpace['fields'])
        assert len(fieldsWithName) <= 1
        if len(fieldsWithName) == 0:
          raise ParserException(momentsElement, "target_field '%(targetFieldName)s' does not exist." % locals())
        targetField = fieldsWithName[0]
        
        if not targetField.isSubsetOfField(operatorTemplate.field):
          raise ParserException(momentsElement,
                  "target_field must only contain dimensions that are in the integration field.")
        
        momentsVectorName = "%(integratorName)s_%(operatorName)s_moments" % locals()
      elif momentsElement.hasAttribute('dimensions'):
        targetField = FieldElementTemplate(name = "%(integratorName)s_%(operatorName)s_field" % locals(),
                                           **self.argumentsToTemplateConstructors)
        momentsVectorName = 'moments'
        
        dimensionNames = RegularExpressionStrings.symbolsInString(momentsElement.getAttribute('dimensions'))
        for dimensionName in dimensionNames:
          if not geometryTemplate.hasDimensionName(dimensionName):
            raise ParserException(momentsElement, "Dimension name '%(dimensionName)s' does not exist." % locals())
          if not operatorTemplate.field.hasDimensionName(dimensionName):
            raise ParserException(momentsElement, 
                    "Filter moments cannot have dimensions that aren't in the integration field. "
                    "The offending dimension is '%(dimensionName)s'." % locals())
          
          targetField.dimensions.append(geometryTemplate.dimensions[geometryTemplate.indexOfDimensionName(dimensionName)])
        targetField.sortDimensions()
      else:
        raise ParserException(momentsElement,
                "Moments in filter operators must have either the 'dimensions' attribute "
                "or the 'target_field' attribute set.")
      
      if momentsElement.hasAttribute('name'):
        filterName = momentsElement.getAttribute('name').strip()
        if filterName in self.globalNameSpace['symbolNames']:
          raise ParserException(momentsElement, 
                  "Filter moments name '%(filterName)s' conflicts with previously defined symbol." % locals())
        self.globalNameSpace['symbolNames'].add(filterName)
        momentsVectorName = filterName
            
      momentsVector = VectorElementTemplate(name = momentsVectorName, field = targetField,
                                            **self.argumentsToTemplateConstructors)
      
      targetField.temporaryVectors.add(momentsVector)
      
      if not momentsElement.hasAttribute('type'):
        ## By default, the type will be complex
        pass
      else:
        momentsVectorType = momentsElement.getAttribute('type').strip().lower()
        if momentsVectorType == 'complex':
          momentsVector.type = 'complex'
        elif momentsVectorType in ('double', 'real'):
          momentsVector.type = 'double'
        else:
          raise ParserException(momentsElement,
                "Unknown type '%(momentsVectorType)s'. "
                "Options are 'complex' (default), or 'double' / 'real' (synonyms)." % locals())
      
      momentNames = RegularExpressionStrings.symbolsInString(momentsElement.innerText())
      
      for momentName in momentNames:
        momentsVector.components.append(momentName)
      
      deltaAOperatorTemplate.dependencies.add(momentsVector)
      operatorTemplate.dependencies.add(momentsVector)
      operatorTemplate.resultVector = momentsVector
      
      if momentsElement.hasAttribute('name'):
        self.globalNameSpace['vectors'].append(momentsVector)
    
    return operatorTemplate
  
  
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
    
    outputTemplate = outputTemplateClass(**self.argumentsToTemplateConstructors)
    outputTemplate.precision = 'double'
    outputTemplate.filename = filename
    
    momentGroupElements = outputElement.getChildElementsByTagName('group')
    for momentGroupNumber, momentGroupElement in enumerate(momentGroupElements):
      samplingElement = momentGroupElement.getChildElementByTagName('sampling')
      
      momentGroupTemplate = MomentGroupTemplate(number = momentGroupNumber, **self.argumentsToTemplateConstructors)
      
      samplingFieldTemplate = FieldElementTemplate(name = momentGroupTemplate.name + "_sampling",
                                                   **self.argumentsToTemplateConstructors)
      momentGroupTemplate.samplingField = samplingFieldTemplate
      
      outputFieldTemplate = FieldElementTemplate(name = momentGroupTemplate.name + "_output",
                                                 **self.argumentsToTemplateConstructors)
      outputFieldTemplate.isOutputField = True
      momentGroupTemplate.outputField = outputFieldTemplate
      
      sampleCount = 0
      
      if samplingElement.hasAttribute('initial_sample'):
        if samplingElement.getAttribute('initial_sample').strip().lower() == 'yes':
          momentGroupTemplate.requiresInitialSample = True
          sampleCount = 1
      
      momentGroupTemplate.sampleSpace = 0
      momentGroupTemplate.dimensions = [Dimension(name = self.globalNameSpace['propagationDimension'],
                                                  transverse = False,
                                                  lattice = sampleCount,
                                                  override = momentGroupTemplate)]
      
      dimensionElements = samplingElement.getChildElementsByTagName('dimension', optional=True)
      
      for dimensionElement in dimensionElements:
        if not dimensionElement.hasAttribute('name') or not dimensionElement.getAttribute('name').strip():
          raise ParserException(dimensionElement, 
                  'Dimension element needs a name attribute corresponding to a dimension name')
        
        dimensionName = dimensionElement.getAttribute('name').strip()
        geometryTemplate = self.globalNameSpace['geometry']
        
        if not geometryTemplate.hasDimensionName(dimensionName):
          raise ParserException(dimensionElement, 
                  "Dimension name '%(dimensionName)s' doesn't correspond to a previously-defined dimension." % locals())
        
        geometryDimension = geometryTemplate.dimensions[geometryTemplate.indexOfDimensionName(dimensionName)]
        dimension = geometryDimension.copy()
        
        fourierSpace = False
        if dimensionElement.hasAttribute('fourier_space') and dimension.fourier:
          spaceString = dimensionElement.getAttribute('fourier_space').strip().lower()
          if spaceString in ('yes', 'k' + dimensionName):
            fourierSpace = True
          elif spaceString in ('no', dimensionName):
            fourierSpace = False
          else:
            raise ParserException(dimensionElement, "fourier_space attribute for dimension '%s' must be 'yes' / '%s' or 'no' / '%s'"
                                                    % (dimensionName, 'k' + dimensionName, dimensionName))
        
        if fourierSpace:
          momentGroupTemplate.sampleSpace |= 1 << geometryTemplate.indexOfDimensionName(dimensionName)
        
        lattice = dimension.lattice
        
        if dimensionElement.hasAttribute('lattice'):
          latticeString = dimensionElement.getAttribute('lattice').strip()
          if not latticeString:
            raise ParserException(dimensionElement, "If the lattice attribute is present, it must not be empty.")
          
          if not latticeString.isdigit():
            raise ParserException(dimensionElement,
                    "Unable to interpret '%(latticeString)s' as an integer" % locals())
          
          lattice = int(latticeString)
          geometryLattice = int(geometryDimension.lattice)
          
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
          dimension.lattice = lattice
          momentGroupTemplate.dimensions.append(dimension)
          samplingFieldTemplate.dimensions.append(dimension)
        elif lattice == 1:
          # In this case, we don't want the dimension in either the moment group, or the sampling field
          pass
        elif lattice == 0:
          # In this case, the dimension only belongs to the sampling field because we are integrating over it.
          # Note that we previously set the lattice of the dimension to be the same as the number
          # of points in this dimension according to the geometry element.
          samplingFieldTemplate.dimensions.append(dimension)
      
      samplingFieldTemplate.sortDimensions()
      momentGroupTemplate.sortDimensions()
      
      # end looping over dimension elements.  
      rawVectorTemplate = VectorElementTemplate(name = 'raw', field = momentGroupTemplate,
                                                **self.argumentsToTemplateConstructors)
      rawVectorTemplate.type = 'double'
      rawVectorTemplate.initialSpace = momentGroupTemplate.sampleSpace
      momentGroupTemplate.managedVectors.add(rawVectorTemplate)
      momentGroupTemplate.rawVector = rawVectorTemplate
      outputFieldTemplate.dimensions = momentGroupTemplate.dimensions
      
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
      
      dependenciesElement = samplingElement.getChildElementByTagName('dependencies')
      dependencyVectorNames = RegularExpressionStrings.symbolsInString(dependenciesElement.innerText())
      momentGroupTemplate.dependenciesEntity = ParsedEntity(dependenciesElement, dependencyVectorNames)
      
      samplingCode = samplingElement.cdataContents()
      if not samplingCode:
        raise ParserException(samplingElement, "The CDATA section for the sampling code must not be empty.")
      
      momentGroupTemplate.samplingCode = samplingCode
      momentGroupTemplate.outputSpace = momentGroupTemplate.sampleSpace
      
      # We have now dealt with the sampling element, and now need to deal with the processing element.
      # TODO: Implement processing element.
      processingElement = momentGroupElement.getChildElementByTagName('post_processing', optional=True)
      
      processedVectorTemplate = VectorElementTemplate(name = 'processed', field = outputFieldTemplate,
                                                      **self.argumentsToTemplateConstructors)
      processedVectorTemplate.type = 'double'
      processedVectorTemplate.initialSpace = momentGroupTemplate.outputSpace
      outputFieldTemplate.managedVectors.add(processedVectorTemplate)
      momentGroupTemplate.processedVector = processedVectorTemplate
      
      if not processingElement:
        momentGroupTemplate.hasPostProcessing = False
        processedVectorTemplate.components = rawVectorTemplate.components[:]
        rawVectorTemplate.type = 'double'
      else:
        momentGroupTemplate.hasPostProcessing = True
  

