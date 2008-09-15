#!/usr/bin/env python
# encoding: utf-8
"""
_MomentGroupElement.py

This contains all the pure-python code for MomentGroupElement.tmpl

Created by Graham Dennis on 2007-10-18.
Copyright (c) 2007 __MyCompanyName__. All rights reserved.
"""

from xpdeint.ScriptElement import ScriptElement
from xpdeint.ParserException import ParserException

from xpdeint.Function import Function
from xpdeint.Utilities import lazyproperty

class _MomentGroupElement (ScriptElement):
  def __init__(self, number, *args, **KWs):
    self.number = number
    self.name = 'mg' + str(self.number)
    
    ScriptElement.__init__(self, *args, **KWs)
    
    # Set default variables
    self.requiresInitialSample = False
    self.getVar('momentGroups').append(self)
    self.computedVectors = set()
    self.operatorContainers = []
    
    scriptElements = self.getVar('scriptElements')
    if not self in scriptElements:
      scriptElements.append(self)
    
    
    sampleFunctionName = ''.join(['_', self.id, '_sample'])
    sampleFunction = Function(name = sampleFunctionName,
                              args = [],
                              implementation = self.sampleFunctionContents)
    self.functions['sample'] = sampleFunction
    
    processFunctionName = ''.join(['_', self.id, '_process'])
    processFunction = Function(name = processFunctionName,
                               args = [],
                               implementation = self.processFunctionContents)
    self.functions['process'] = processFunction
    
    writeOutFunctionName = ''.join(['_', self.id, '_write_out'])
    writeOutFunction = Function(name = writeOutFunctionName,
                                args = [('FILE*', '_outfile')],
                                implementation = self.writeOutFunctionContents)
    self.functions['writeOut'] = writeOutFunction
  
  @lazyproperty
  def children(self):
    result = set()
    result.update(self.computedVectors)
    result.update(self.operatorContainers)
    return result
  
  # Do we actually need to allocate the moment group vector?
  # We may not need to allocate the raw vector if there is no
  # processing of the raw vector to be done before it is written.
  @lazyproperty
  def rawVectorNeedsToBeAllocated(self):
    # If we have processing code, then we definitely need a raw vector
    if self.hasattr('processingCode') and self.processingCode:
      return True
    
    dict = {'returnValue': False, 'MomentGroup': self}
    featureOrdering = ['Driver']
    
    # This function allows the features to determine whether or not the raw vector
    # needs to be allocated by changing the value of the 'returnValue' key in dict.
    # The features should only change the value to true if they need the raw vector
    # allocated. Otherwise, they shouldn't touch the value.
    self.insertCodeForFeatures('rawVectorNeedsToBeAllocated', featureOrdering, dict)
    
    return dict['returnValue']
  
  def bindNamedVectors(self):
    super(_MomentGroupElement, self).bindNamedVectors()
    
    for dependency in self.dependencies:
      if self.hasPostProcessing and dependency.type == 'complex':
        self.rawVector.type = 'complex'
      
    if not self.rawVectorNeedsToBeAllocated:
      self.outputField.managedVectors.remove(self.processedVector)
      self.processedVector.remove()
      self.processedVector = self.rawVector
    
  
  def preflight(self):
    super(_MomentGroupElement, self).preflight()
    
    # Throw out the propagation dimension if it only contains a single sample
    if self.outputField.hasDimensionName(self.propagationDimension):
      if self.outputField.dimensionWithName(self.propagationDimension).inSpace(0).lattice == 1:
        singlePointDimension = self.outputField.dimensionWithName(self.propagationDimension)
        self.outputField.dimensions.remove(singlePointDimension)
        singlePointDimension.remove()
    
  
  


