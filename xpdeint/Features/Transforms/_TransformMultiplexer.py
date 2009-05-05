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
    self.neededTransformations = []
  
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
    # We need to add a few transforms of our own.
    
    # Out-of-place copy
    self.availableTransformations.append(dict(
      transformations = [frozenset()],
      cost = 1,
      outOfPlace = True
    ))
    
    # In-place multiply
    self.availableTransformations.append(dict(
      transformations = [frozenset()],
      cost = 1,
      scaling = True
    ))
    
    # Out-of-place multiply
    self.availableTransformations.append(dict(
      transformations = [frozenset()],
      cost = 2,
      outOfPlace = True,
      scaling = True
    ))
    print self.availableTransformations
  
  def globals(self):
    return '\n'.join([t['transformGlobals'](t) for t in self.neededTransformations if 'transformGlobals' in t])
  
  def buildTransformMap(self):
    # The mighty plan is to do the following for each vector:
    # 1. Convert all required spaces to the new-style spaces
    
    def transformedBasis(basis, transformationPair):
      if not transformationPair: return basis, (basis, tuple(), tuple())
      
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
            return basis, (tuple(basis[:offset]), sourceBasis, tuple(basis[offset+len(sourceBasis):]))
      return None, (None, None, None)
    
    class BasisState(DijkstraSearch.State):
      __slots__ = []
      availableTransformations = self.availableTransformations
      
      IN_PLACE = 0
      OUT_OF_PLACE = 1
      UNSCALED = 0
      SCALED = 1
      
      def next(self):
        results = []
        
        currentBasis, currentState = self.location
        for transformID, transformation in enumerate(self.availableTransformations):
          for transformationPair in transformation['transformations']:
            resultBasis, (prefixBasis, matchedSourceBasis, postfixBasis) = transformedBasis(currentBasis, transformationPair)
            if not resultBasis: continue
            costMultiplier = reduce(
              operator.mul,
              [self.representationMap[repName.split()[-1]].lattice \
                for repName in currentBasis if not repName in matchedSourceBasis],
              1
            )
            
            resultState = list(currentState)
            if transformation.get('outOfPlace', False):
              resultState[0] = {
                BasisState.IN_PLACE: BasisState.OUT_OF_PLACE,
                BasisState.OUT_OF_PLACE: BasisState.IN_PLACE
              }[currentState[0]]
            if transformation.get('scaling', False):
              resultState[1] = BasisState.SCALED
            
            resultState = tuple(resultState)
            
            newCost = [costMultiplier * transformation.get(key, 0) for key in ['communicationsCost', 'cost']]
            newCost = tuple(old + new for old, new in zip(self.cost, newCost))
            transformSpecifier = None
            if 'transformSpecifier' in transformation:
              transformSpecifier = transformation['transformSpecifier'](
                frozenset([currentBasis, resultBasis]),
                self.vector,
                prefixBasis,
                postfixBasis,
                self.representationMap
              )
            newState = BasisState(newCost, (resultBasis, resultState), previous = (self.location, (transformID, transformSpecifier)))
            results.append(newState)
        return results
      
    
    def convertSpaceInFieldToBasis(space, field):
      return tuple(dim.inSpace(space).name for dim in field.dimensions)
    
    def pathsFromBasisToBasis(start, end, shortestPaths):
      # Final state must be net in-place.
      # But we may or may not need scaling
      scaled = BasisState.UNSCALED
      stack = [(end, (BasisState.IN_PLACE, scaled))]
      result = []
      
      startState = (start, (BasisState.IN_PLACE, BasisState.UNSCALED))
      
      def _paths():
        if not stack[-1] in shortestPaths: return
        for basisAndState, (transformID, transformSpecifier) in shortestPaths[stack[-1]].previous:
          if not scaled and BasisState.availableTransformations[transformID].get('requiresScaling', False):
            continue
          stack.extend([(transformID, transformSpecifier), basisAndState])
          if basisAndState == startState:
            result.append(list(reversed(stack)))
          else:
            _paths()
          del stack[-2:]
      
      _paths()
      
      scaled = BasisState.SCALED
      stack = [(end, (BasisState.IN_PLACE, scaled))]
      _paths()
      
      return result
    
    geometry = self.getVar('geometry')
    representationMap = dict()
    for dim in geometry.dimensions:
      representationMap.update((rep.name, rep) for rep in dim.representations)
    BasisState.representationMap = representationMap
    
    vectors = [v for v in self.getVar('vectors') if v.needsTransforms]
    driver = self._driver
    transformsNeeded = set()
    transformMap = dict()
    for vector in vectors:
      basesNeeded = set(convertSpaceInFieldToBasis(space, vector.field) for space in vector.spacesNeeded)
      basesNeeded = set(driver.canonicalBasisForBasis(basis) for basis in basesNeeded)
      print vector.id, basesNeeded
      
      BasisState.vector = vector
      
      # Next step: Perform Dijkstra search over the provided transforms to find the optimal transform map.
      for basis in basesNeeded:
        startState = BasisState((0, 0), (basis, (BasisState.IN_PLACE, BasisState.UNSCALED)))
        shortestPaths = DijkstraSearch.perform(startState)
        
        # Now we want to extract useful information from this
        for aBasis in [b for b in basesNeeded if not b == basis]:
          transformation = frozenset([basis, aBasis])
          if transformation in transformMap: continue
          # Now to obtain concrete lists of potential transform steps
          paths = pathsFromBasisToBasis(basis, aBasis, shortestPaths)
          print 'paths', paths
          
          # Now we need to rank the bloody things. And it has to be stable from one run to the next.
          # Simple ordering: Least steps, least out-of-place operations, most reused transforms, alphabetic
          # Because we are doing an ascending sort, but want the *most* reused transforms,
          # we use the negative of the number of transforms we could reuse that is used below
          
          rankedPaths = [(len(path),
                          sum([self.availableTransformations[tID].get('outOfPlace', False) 
                                for tID, tS in path[1::2]], 0),
                          -sum([td in transformsNeeded for td in path[1::2]]),
                          path) for path in paths]
          rankedPaths.sort()
          path = rankedPaths[0][-1]
          print path, path[1::2], path[:-2:2], path[2::2]
          transformsNeeded.update([transformDescriptor for transformDescriptor in path[1::2]])
          transformMap[transformation] = path
      
    print transformMap
    print transformsNeeded
    # Now we need to extract the transforms and include that information in choosing transforms
    # One advantage of this method is that we no longer have to make extra fft plans or matrices when we could just re-use others.
    
    for transformID, transformSpecifier in transformsNeeded:
      transformation = self.availableTransformations[transformID].copy()
      transformation['transformSpecifier'] = transformSpecifier
      del transformation['transformations']
      # transformation['transformPair'] = transformPair
      self.neededTransformations.append(transformation)
    print self.neededTransformations
  

