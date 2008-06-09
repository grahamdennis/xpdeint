#!/usr/bin/env python
# encoding: utf-8
"""
_IntegerDistributedMPIDriver.py

Created by Graham Dennis on 2008-03-29.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.SimulationDrivers.DistributedMPIDriver import DistributedMPIDriver

import xpdeint.Geometry.IntegerDimension

class _IntegerDistributedMPIDriver (DistributedMPIDriver):
  def __init__(self, *args, **KWs):
    DistributedMPIDriver.__init__(self, *args, **KWs)
    
    transverseDimensions = filter(lambda x: x.transverse, self.getVar('geometry').dimensions)
    self.mpiDimension = transverseDimensions[0]
    assert isinstance(self.mpiDimension, xpdeint.Geometry.IntegerDimension.IntegerDimension)
    self.distributedDimensionNames.append(self.mpiDimension.name)
  
  @property
  def geometryVariableSuffixesToBeShadowed(self):
    return ['_local_lattice_' + self.mpiDimension.name, '_local_offset_' + self.mpiDimension.name]
  
  def mpiDimensionForSpace(self, space):
    return self.mpiDimension
  
  def mayHaveLocalOffsetForDimensionInFieldInSpace(self, dimension, field, space):
    if dimension.name == self.mpiDimension.name:
      return True
    else:
      return False
  
  def isFieldDistributed(self, field):
    return field.hasDimension(self.mpiDimension)
  
  def localOffsetForDimensionInFieldInSpace(self, dimension, field, space):
    if not (self.isFieldDistributed(field) and self.mayHaveLocalOffsetForDimensionInFieldInSpace(dimension, field, space)):
      return "0"
    return ''.join(['_', field.name, '_local_offset_', self.dimensionNameForSpace(dimension, space)])
  
  def localLatticeForDimensionInFieldInSpace(self, dimension, field, space):
    if not (self.isFieldDistributed(field) and self.mayHaveLocalOffsetForDimensionInFieldInSpace(dimension, field, space)):
      return ''.join(['_', field.name, '_lattice_', self.dimensionNameForSpace(dimension, space)])
    return ''.join(['_', field.name, '_local_lattice_', self.dimensionNameForSpace(dimension, space)])
  

