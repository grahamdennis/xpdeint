#!/usr/bin/env python
# encoding: utf-8
"""
_TransformMultiplexer.py

Created by Graham Dennis on 2008-12-23.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.Features._Feature import _Feature
from xpdeint.Utilities import lazy_property, DijkstraSearch

import operator

class _TransformMultiplexer (_Feature):
  featureName = 'TransformMultiplexer'
  transformClasses = dict()
  
  def __init__(self, *args, **KWs):
    _Feature.__init__(self, *args, **KWs)
    self.transforms = set()
    self.availableTransformations = []
  
  def transformsForVector(self, vector):
    return set([dim.transform for dim in vector.field.dimensions if dim.transform.hasattr('goSpaceFunctionContentsForVector')])
  
  def transformWithName(self, name):
    if not name in self.transformClasses:
      return None
    cls = self.transformClasses[name]
    transformWithClass = [t for t in self.transforms if isinstance(t, cls)]
    assert 0 <= len(transformWithClass) <= 1
    if transformWithClass:
      return transformWithClass[0]
    else:
      return cls(parent = self.simulation, **self.argumentsToTemplateConstructors)
  
  def __getattribute__(self, name):
    """
    Call through to all methods on the child transforms. This should only be used for
    the 'insertCodeForFeatures' functions. We don't want this to happen for 'includes', etc.
    This is prevented from occuring because all of these methods are defined on `_ScriptElement`.
    """
    # As we are customising attribute access in this method, attempts to access attributes directly
    # would lead to infinite recursion (bad), so we must access variables specially
    try:
      attr = _Feature.__getattribute__(self, name)
    except AttributeError, err:
      # If the attribute name is not in the list of functions we want to proxy
      # then re-raise the exception
      if not name in ['mainBegin', 'mainEnd']: raise
      # We don't have the attribute, so maybe one of our child transforms does
      transforms = _Feature.__getattribute__(self, 'transforms')
      childAttributes = [getattr(t, name) for t in transforms if t.hasattr(name)]
      # No child has the transform, re-raise the exception
      if not childAttributes: raise
      # A child has the attribute. Check they are all callable. If not, don't multiplex
      # This line is here for debugging only
      # assert all([callable(ca) for ca in childAttributes]), "Tried to multiplex call to non-callable attribute '%(name)s'" % locals()
      if not all([callable(ca) for ca in childAttributes]): raise
      
      if len(childAttributes) == 1:
        return childAttributes[0]
      
      # Create the function that does the actual multiplexing
      def multiplexingFunction(*args, **KWs):
        results = [ca(*args, **KWs) for ca in childAttributes]
        return ''.join([result for result in results if result is not None])
      
      return multiplexingFunction
    else:
      return attr
    
  def preflight(self):
    super(_TransformMultiplexer, self).preflight()
    for transform in self.transforms:
      if hasattr(transform, 'availableTransformations'):
        self.availableTransformations.extend(transform.availableTransformations())
    print self.availableTransformations
    
  def buildTransformMap(self):
    # The mighty plan is to do the following for each vector:
    # 1. Convert all required spaces to the new-style spaces
    
    def transformedBasis(basis, transformationPair):
      transformationPair = list(transformationPair)
      if not isinstance(basis, tuple): basis = tuple([basis])
      for sourceBasis, destBasis in [transformationPair, reversed(transformationPair)]:
        if not isinstance(sourceBasis, tuple): sourceBasis = tuple([sourceBasis])
        if not isinstance(destBasis, tuple): destBasis = tuple([destBasis])
        
        for offset in range(0, len(basis)+1-len(sourceBasis)):
          if basis[offset:offset+len(sourceBasis)] == sourceBasis:
            basis = list(basis)
            basis[offset:offset+len(sourceBasis)] = destBasis
            basis = tuple(basis)
            return basis, sourceBasis
      return None, None
    
    class BasisState(DijkstraSearch.State):
      __slots__ = []
      availableTransformations = self.availableTransformations
      
      def next(self):
        results = []
        for transformation in self.availableTransformations:
          transformationPairs = transformation['transformations']
          for transformationPair in transformationPairs:
            resultBasis, matchedSourceBasis = transformedBasis(self.location, transformationPair)
            if resultBasis:
              costMultiplier = reduce(
                operator.mul,
                [self.representationMap[repName.split()[-1]].lattice for repName in self.location if not repName in matchedSourceBasis],
                1
              )
              
              newCost = [costMultiplier * int(transformation.get(key, 0)) for key in ['communicationsCost', 'cost']]
              newCost = tuple(old + new for old, new in zip(self.cost, newCost))
              newState = BasisState(newCost, resultBasis, previous = self.location)
              results.append(newState)
        return results
    
    def convertSpaceInFieldToBasis(space, field):
      return tuple(dim.inSpace(space).name for dim in field.dimensions)
    
    vectors = [v for v in self.getVar('vectors') if v.needsTransforms]
    driver = self._driver
    for vector in vectors:
      basesNeeded = set(convertSpaceInFieldToBasis(space, vector.field) for space in vector.spacesNeeded)
      basesNeeded = set(driver.canonicalBasisForBasis(basis) for basis in basesNeeded)
      print vector.id, basesNeeded
      
      # Next step: Perform Dijkstra search over the provided transforms to find the optimal transform map.
      representationMap = dict()
      for dim in vector.field.dimensions:
        representationMap.update((rep.name, rep) for rep in dim.representations)
      BasisState.representationMap = representationMap
      transformsNeeded = set()
      for basis in basesNeeded:
        startState = BasisState((0, 0), basis)
        print basis, DijkstraSearch.perform(startState)
    
    
    

