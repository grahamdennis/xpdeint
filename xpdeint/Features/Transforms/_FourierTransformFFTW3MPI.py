#!/usr/bin/env python
# encoding: utf-8
"""
_FourierTransformFFTW3MPI.py

Created by Graham Dennis on 2008-06-08.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.Features.Transforms.FourierTransformFFTW3 import FourierTransformFFTW3

from xpdeint.ParserException import ParserException
from xpdeint.Utilities import permutations

import operator, math

class _FourierTransformFFTW3MPI (FourierTransformFFTW3):
  def preflight(self):
    super(_FourierTransformFFTW3MPI, self).preflight()
    
    fields = self.getVar('fields')
    geometry = self.getVar('geometry')
    driver = self._driver
    
    # Check that all vectors that are distributed and need fourier transforms
    # contain all the points in the MPI dimensions. Otherwise we can't fourier
    # transform them.
    for field in filter(driver.isFieldDistributed, fields):
      # If all the distributed dimensions are the same in this field as in the geometry, then everything is OK
      if all([field.dimensionWithName(name) == geometry.dimensionWithName(name) for name in driver.distributedDimensionNames]):
        continue
      for vector in [v for v in self.vectorsNeedingThisTransform if v.field == field]:
        raise ParserException(vector.xmlElement, "Vector '%s' cannot be fourier transformed because it would be distributed with MPI "
                                                 "and it doesn't have the same number of points as the geometry for the distributed dimensions." % vector)
    
    for field in [field for field in fields if not field.isDistributed]:
      for dim in [dim for dim in field.dimensions if dim.transform == self]:
        for rep in [rep for rep in dim.representations if rep and rep.hasLocalOffset]:
          dim.invalidateRepresentation(rep)
  
  def vectorNeedsPartialTransforms(self, vector):
    if not self._driver.isFieldDistributed(vector.field):
      return False
    if not vector.needsTransforms:
      return False
    # If any of the spaces in which this vector is needed are not full spaces, then we need partial transforms
    tm = self.transformMask
    if any([(space & tm) != 0 and (space & tm) != (vector.field.spaceMask & tm) for space in vector.spacesNeeded]):
      return True
    return False
  
  def initialiseForMPIWithDimensions(self, dimensions):
    # It has already been checked by _FourierTransformFFTW3 that we can handle these dimensions
    # but let's just run a couple of assert's to make sure
    assert not ((self.transformNameMap[dimensions[0].name] == 'dft') ^ (self.transformNameMap[dimensions[1].name] == 'dft'))
    assert not ((self.transformNameMap[dimensions[0].name] in ['dct', 'dst']) ^ (self.transformNameMap[dimensions[1].name] in ['dct', 'dst']))
    for dim in dimensions[0:2]:
      assert self.transformNameMap[dim.name] in ['dft', 'dct', 'dst']
      # Check that the dimension doesn't have any mapping rules yet
      assert not dim._mappingRules
    
    self._driver.distributedDimensionNames = [dim.name for dim in dimensions[0:2]]
    self.mpiDimensions = dimensions[0:2]
    self.swappedSpace = reduce(operator.__or__, [dim.transformMask for dim in self.mpiDimensions])
    
    firstMPIDimension = dimensions[0]
    secondMPIDimension = dimensions[1]
    # Add additional transformed representations for the swapped case.
    for rep in firstMPIDimension.representations[:]:
      distributedRep = rep.copy(parent = firstMPIDimension)
      distributedRep.setHasLocalOffset('unswapped')
      firstMPIDimension.addRepresentation(distributedRep)
    
    for rep in secondMPIDimension.representations[1:]:
      distributedRep = rep.copy(parent = secondMPIDimension)
      distributedRep.setHasLocalOffset('swapped')
      secondMPIDimension.addRepresentation(distributedRep)
    
    self.distributedMPIKinds = set([self.transformNameMap[firstMPIDimension.name]])
    if self.distributedMPIKinds.intersection(['dct', 'dst']):
      self.distributedMPIKinds.update(['dct', 'dst'])
    
  
  def mappingRulesForDimensionInField(self, dim, field):
    """
    Return default mapping rules. Each rule is a ``(mask, index)`` pair.
    A mapping rule matches a space if ``mask & space`` is nonzero. The rules
    are tried in order until one matches, and the representation correponding
    to the index in the rule is the result.
    """
    if self.isFieldDistributed(field) and dim.name in self._driver.distributedDimensionNames:
      if dim.name == self._driver.distributedDimensionNames[1]:
        return [(self.swappedSpace, 2), (dim.transformMask, 1), (None, 0)]
      else:
        return [(self.swappedSpace, 1), (dim.transformMask, 3), (None, 2)]
    return super(_FourierTransformFFTW3MPI, self).mappingRulesForDimensionInField(dim, field)
  
  
  def isFieldDistributed(self, field):
    if not field:
      return False
    return field.hasDimension(self.mpiDimensions[0]) and field.hasDimension(self.mpiDimensions[1])
  
  def sizeOfFieldInSpace(self, field, space):
    return '*'.join([dim.inSpace(space).localLattice for dim in field.dimensions])
  
  def mpiDimRepForSpace(self, space):
    return [dim.inSpace(space) for dim in self.mpiDimensions if dim.inSpace(space).hasLocalOffset][0]
  
  def fullTransformDimensionsForField(self, field):
    result = []
    for dim in field.transverseDimensions:
      if not self.transformNameMap.get(dim.name) in self.distributedMPIKinds:
        break
      result.append(dim)
    return result
  
  def isSpaceSwapped(self, space):
    return (space & self.swappedSpace) == self.swappedSpace
  
  def orderedDimensionsForFieldInSpace(self, field, space):
    """Return a list of the dimensions for field in the order in which they should be looped over"""
    dimensions = field.dimensions[:]
    if self.isSpaceSwapped(space) and self.isFieldDistributed(field):
      firstMPIDimIndex = field.indexOfDimension(self.mpiDimensions[0])
      secondMPIDimIndex = field.indexOfDimension(self.mpiDimensions[1])
      (dimensions[secondMPIDimIndex], dimensions[firstMPIDimIndex]) = (dimensions[firstMPIDimIndex], dimensions[secondMPIDimIndex])
    return dimensions
  
  def availableTransformations(self):
    results = super(_FourierTransformFFTW3MPI, self).availableTransformations()
    
    # Create transpose operations
    transposeOperations = []
    communicationsCost = None
    for firstDimRep, secondDimRep in permutations(*[dim.representations for dim in self.mpiDimensions]):
      if not communicationsCost: communicationsCost = firstDimRep.lattice * secondDimRep.lattice
      basisA = ('distributed ' + firstDimRep.name, secondDimRep.name)
      basisB = ('distributed ' + secondDimRep.name, firstDimRep.name)
      transposeOperations.append(frozenset([basisA, basisB]))
    # transpose operations
    results.append(dict(transformations=transposeOperations,
                        communicationsCost=communicationsCost))
    
    # Create partial forward / back operations
    untransformedBasis = ('distributed ' + self.mpiDimensions[0].representations[0].name,
                          self.mpiDimensions[1].representations[0].name)
    transformedBasis = ('distributed ' + self.mpiDimensions[1].representations[1].name,
                        self.mpiDimensions[0].representations[1].name)
    
    transformCost = self.fftCost([dim.name for dim in self.mpiDimensions])
    
    # Partial transform
    results.append(dict(transformations=[frozenset([untransformedBasis, transformedBasis])],
                        communicationsCost=communicationsCost,
                        cost=transformCost))
    
    # Fuller forward/reverse transforms would be good in the future for the case of more than two dimensions
    # This isn't necessary for the moment though.
    # PROBLEM: The required bases need to be known at about preflight time.
    
    return results
  
  def canonicalBasisForBasis(self, basis):
    if all([set(rep.name for rep in mpiDim.representations).intersection(basis) for mpiDim in self.mpiDimensions]):
      # Decide what the order is.
      basis = list(basis)
      mpiDimRepNames = [list(set(rep.name for rep in mpiDim.representations).intersection(basis))[0] for mpiDim in self.mpiDimensions]
      if all(mpiDim.representations[1].name in mpiDimRepNames for mpiDim in self.mpiDimensions):
        # Then we are swapped
        basis[0:2] = reversed(mpiDimRepNames)
      else:
        basis[0:2] = mpiDimRepNames
      basis[0] = 'distributed ' + basis[0]
      basis = tuple(basis)
    return basis
  

