#!/usr/bin/env python,
# encoding: utf-8
"""
_FourierTransform.py

Created by Graham Dennis on 2008-07-30.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.Features.Transforms._Transform import _Transform

from xpdeint.Geometry.DimensionRepresentation import DimensionRepresentation
from xpdeint.Geometry.UniformDimensionRepresentation import UniformDimensionRepresentation
from xpdeint.Geometry.SplitUniformDimensionRepresentation import SplitUniformDimensionRepresentation

from xpdeint.ParserException import ParserException

from xpdeint.Utilities import lazy_property, combinations

import math, operator

class _FourierTransformFFTW3 (_Transform):
  transformName = 'FourierTransform'
  fftwSuffix = ''
  
  coordinateSpaceTag = DimensionRepresentation.registerTag('FFTW coordinate space')
  fourierSpaceTag = DimensionRepresentation.registerTag('FFTW Fourier space')
  
  def __init__(self, *args, **KWs):
    _Transform.__init__(self, *args, **KWs)
    self.transformNameMap = {}
  
  @lazy_property
  def fftwPrefix(self):
    precision = self.getVar('precision')
    return {'double': 'fftw', 'single': 'fftwf'}[precision]
  
  @lazy_property
  def fftwLibVersionName(self):
      return {'fftw': 'fftw3', 'fftwf': 'fftw3f'}[self.fftwPrefix]
  
  @lazy_property
  def wisdomExtension(self):
    result = '.' + self.fftwLibVersionName
    if self.fftwSuffix:
      result += '_' + self.fftwSuffix
    return result
  
  @lazy_property
  def uselib(self):
    result = [self.fftwLibVersionName]
    if self.fftwSuffix:
      result.append(self.fftwLibVersionName + '_' + self.fftwSuffix)
    return result
  
  def newDimension(self, name, lattice, minimum, maximum,
                   parent, transformName, aliases = set(),
                   spectralLattice = None,
                   type = 'real', xmlElement = None):
    assert type == 'real'
    assert transformName in ['dft', 'dct', 'dst']
    dim = super(_FourierTransformFFTW3, self).newDimension(name, lattice, minimum, maximum,
                                                           parent, transformName, aliases,
                                                           type, xmlElement)
    self.transformNameMap[dim.name] = transformName
    if transformName == 'dft':
      # x-space representation
      xspace = UniformDimensionRepresentation(name = name, type = type, lattice = lattice,
                                              minimum = minimum, maximum = maximum, parent = dim,
                                              tag = self.coordinateSpaceTag,
                                              **self.argumentsToTemplateConstructors)
      # kspace representation
      kspace = SplitUniformDimensionRepresentation(name = 'k' + name, type = type, lattice = lattice,
                                                   range = '%s - %s' % (xspace.maximum, xspace.minimum),
                                                   parent = dim, tag = self.fourierSpaceTag,
                                                   **self.argumentsToTemplateConstructors)
    else:
      # x-space representation
      stepSize = '((real)%(maximum)s - %(minimum)s)/(%(lattice)s)' % locals()
      xspace = UniformDimensionRepresentation(name = name, type = type, lattice = lattice,
                                              minimum = None, maximum = None, stepSize = stepSize,
                                              tag = self.coordinateSpaceTag,
                                              parent = dim, **self.argumentsToTemplateConstructors)
      # Modify the minimum and maximum values to deal with the 0.5*stepSize offset
      xspace._minimum = '%s + 0.5*%s' % (minimum, xspace.stepSize)
      xspace._maximum = '%s + 0.5*%s' % (maximum, xspace.stepSize)
      if transformName == 'dct':
        # kspace representation
        kspace = UniformDimensionRepresentation(name = 'k' + name, type = type, lattice = lattice,
                                                minimum = '0.0', maximum = None,
                                                stepSize = '(M_PI/(%(maximum)s - %(minimum)s))' % locals(),
                                                tag = self.fourierSpaceTag,
                                                parent = dim, **self.argumentsToTemplateConstructors)
        kspace._maximum = '%s * %s' % (kspace.stepSize, kspace.globalLattice)
      else:
        kspace = UniformDimensionRepresentation(name = 'k' + name, type = type, lattice = lattice,
                                                minimum = None, maximum = None,
                                                stepSize = '(M_PI/(%(maximum)s - %(minimum)s))' % locals(),
                                                tag = self.fourierSpaceTag,
                                                parent = dim, **self.argumentsToTemplateConstructors)
        kspace._minimum = '%s' % kspace.stepSize
        kspace._maximum = '%s * (%s + 1)' % (kspace.stepSize, kspace.globalLattice)
    
    dim.addRepresentation(xspace)
    dim.addRepresentation(kspace)
    return dim
  
  def canTransformVectorInDimension(self, vector, dim):
    result = super(_FourierTransformFFTW3, self).canTransformVectorInDimension(vector, dim)
    if result:
      transformName = self.transformNameMap[dim.name]
      # We can only transform complex vectors with dft.
      # dct/dst can manage both complex and real
      if transformName == 'dft' and not vector.type == 'complex':
        result = False
    
    return result
  
  def r2rKindForDimensionAndDirection(self, dim, direction):
    transformName = self.transformNameMap[dim.name]
    return {'dct': {'forward': 'FFTW_REDFT10', 'backward': 'FFTW_REDFT01'},
            'dst': {'forward': 'FFTW_RODFT10', 'backward': 'FFTW_RODFT01'}}[transformName][direction]
  
  def initialiseForMPIWithDimensions(self, dimensions):
    # We can only upgrade to MPI support if both the first and second dimensions
    # are 'dft' or 'r2r' transforms. In the future, this restriction can be lifted
    if len(dimensions) < 2:
      raise ParserException(self._driver.xmlElement,
                            "There must be at least two dimensions to use the 'distributed-mpi' with the '%s' transform." % self.transformName[dimensions[0].name])
    if not (dimensions[0].transform == self and dimensions[1].transform == self) \
       or ((self.transformNameMap[dimensions[0].name] == 'dft') ^ (self.transformNameMap[dimensions[1].name] == 'dft')) \
       or ((self.transformNameMap[dimensions[0].name] in ['dct', 'dst']) ^ (self.transformNameMap[dimensions[1].name] in ['dct', 'dst'])):
      raise ParserException(self._driver.xmlElement,
                            "To use the 'distributed-mpi' driver with the 'dft', 'dct' or 'dst' transforms, both the first and second dimensions "
                            "must use one of these transforms with the additional restriction that if the 'dft' transform is used for one dimension "
                            "it must be used for the other.")
    super(_FourierTransformFFTW3, self).initialiseForMPIWithDimensions(dimensions)
  
  def fftCost(self, dimNames):
    geometry = self.getVar('geometry')
    untransformedDimReps = dict([(dimName, geometry.dimensionWithName(dimName).representations[0]) for dimName in dimNames])
    cost = sum([int(math.ceil(math.log(untransformedDimReps[dimName].lattice))) for dimName in dimNames], 0)
    cost *= reduce(operator.mul, [untransformedDimReps[dimName].lattice for dimName in dimNames], 1)
    return cost
  
  def availableTransformations(self):
    results = []
    geometry = self.getVar('geometry')
    sortedDimNames = [(geometry.indexOfDimensionName(dimName), dimName) for dimName in self.transformNameMap]
    sortedDimNames.sort()
    sortedDimNames = [o[1] for o in sortedDimNames]
    
    transformFunctions = dict(
      transformSpecifier = self.transformSpecifier,
      transformGlobals = self.transformGlobals,
      transformInitialise = self.transformInitialise,
      transformFinalise = self.transformFinalise
    )
    
    for dimName in sortedDimNames:
      # FIXME: The 0:2 slice in the following is to prevent double-up due to the current use of three representations
      # for distributed MPI dimensions. This won't be needed when we convert to bases internally in xpdeint.
      dimReps = geometry.dimensionWithName(dimName).representations[0:2]
      for basisReps in combinations(2, dimReps):
        results.append(dict(
          transformations = [frozenset(rep.name for rep in basisReps)],
          cost = self.fftCost([dimName]),
          requiresScaling = True,
          transformType = 'c2c' if self.transformNameMap[dimName] == 'dft' else 'r2r',
          **transformFunctions
        ))
    
    if self.hasattr('mpiDimensions'):
      for dim in self.mpiDimensions:
        sortedDimNames.remove(dim.name)
    
    c2cDimNames = [dimName for dimName in sortedDimNames if self.transformNameMap[dimName] == 'dft']
    r2rDimNames = [dimName for dimName in sortedDimNames if self.transformNameMap[dimName] in ['dct', 'dst']]
    
    untransformedDimReps = dict([(dimName, geometry.dimensionWithName(dimName).representations[0]) for dimName in sortedDimNames])
    transformedDimReps = dict([(dimName, geometry.dimensionWithName(dimName).representations[1]) for dimName in sortedDimNames])
    
    # Create optimised forward/backward transforms
    for dimNames, transformType in [(c2cDimNames, 'c2c'), (r2rDimNames, 'r2r')]:
      if len(dimNames) <= 1: continue
      cost = self.fftCost(dimNames)
      untransformedBasis = tuple([untransformedDimReps[dimName].name for dimName in dimNames])
      transformedBasis = tuple([transformedDimReps[dimName].name for dimName in dimNames])
      bases = frozenset([untransformedBasis, transformedBasis])
      results.append(dict(
        transformations = [bases],
        cost = cost,
        requiresScaling = True,
        transformType = transformType,
        **transformFunctions
      ))
    
    final_transforms = []
    for transform in results:
      final_transforms.append(transform.copy())
      transform['outOfPlace'] = True
      final_transforms.append(transform)
    
    return final_transforms
  
  def transformSpecifier(self, transformDict, vector, prefixBasis, postfixBasis, representationMap):
    mpiPrefix = [basisName for basisName in prefixBasis if not basisName in representationMap]
    mpiPrefix = mpiPrefix[0] if mpiPrefix else None
    
    prefixLattice = reduce(
      operator.mul,
      [representationMap[basisName].lattice
        for basisName in prefixBasis if basisName in representationMap],
      1
    )
    
    postfixLattice = reduce(
      operator.mul,
      [representationMap[basisName].lattice for basisName in postfixBasis],
      1
    )
    postfixLattice *= vector.nComponents
    
    print transformDict
    if transformDict['transformType'] is 'r2r' and vector.type == 'complex':
      postfixLattice *= 2
    
    return (mpiPrefix, prefixLattice, postfixLattice)
  

