#!/usr/bin/env python
# encoding: utf-8
"""
_TransformMultiplexer.py

Created by Graham Dennis on 2008-12-23.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.Features._Feature import _Feature
from xpdeint.Utilities import lazy_property, combinations, DijkstraSearch

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
      """
      This function determines if `basis` can be transformed by the transform represented
      by `transformPair`. If `basis` can be transformed, then it returns the transformed basis,
      the matched part of the basis, and the components of the basis before and after the match.
      """
      if not transformationPair: return basis, (basis, tuple(), tuple())
      
      transformationPair = list(transformationPair)
      if not isinstance(basis, tuple): basis = tuple([basis])
      for sourceBasis, destBasis in [transformationPair, reversed(transformationPair)]:
        # Optimisation: If it's just a single-dimension transform, do it the fast way
        if not isinstance(sourceBasis, tuple):
          if not sourceBasis in basis: continue
          basis = list(basis)
          offset = basis.index(sourceBasis)
          basis[offset] = destBasis
          basis = tuple(basis)
          return basis, (basis[:offset], tuple([sourceBasis]), basis[offset+1:])
        
        for offset in range(0, len(basis)+1-len(sourceBasis)):
          if basis[offset:offset+len(sourceBasis)] == sourceBasis:
            basis = list(basis)
            basis[offset:offset+len(sourceBasis)] = destBasis
            basis = tuple(basis)
            return basis, (basis[:offset], sourceBasis, basis[offset+len(sourceBasis):])
      return None, (None, None, None)
    
    class BasisState(DijkstraSearch.State):
      """
      This class represents a node in the transform graph. This node specifies
      both the current basis and also whether the data for the vector being
      transformed is currently 'in-place' (the data is stored in the same location
      as it was originally) or 'out-of-place' (the data is stored in a different location).
      This distinction is necessary as transforms such as matrix multiplication transforms
      necessitate an out-of-place operation, but overall, we require the data after the 
      complete transform to be back where it was to start with.
      """
      __slots__ = []
      availableTransformations = self.availableTransformations
      
      IN_PLACE = 0
      OUT_OF_PLACE = 1
      UNSCALED = 0
      SCALED = 1
      
      def next(self):
        """
        This function returns the next nodes in the transform graph that can be reached from this node.
        
        It iterates through all available transforms trying to find matches that can transform the current
        basis and determines the cost of doing so.
        """
        results = []
        
        currentBasis, currentState = self.location
        # Loop through all available transforms
        for transformID, transformation in enumerate(self.availableTransformations):
          # Loop through all basis-changes this 'transform' can handle
          for transformationPair in transformation['transformations']:
            # Does the transformPair match?
            resultBasis, (prefixBasis, matchedSourceBasis, postfixBasis) = transformedBasis(currentBasis, transformationPair)
            if not resultBasis: continue
            
            # The cost specified in the transform is per-point in dimensions not listed in the transformationPair
            # So we must multiply that cost by the product of the number of points in all other dimensions
            costMultiplier = reduce(
              operator.mul,
              [self.representationMap[repName.split()[-1]].lattice \
                for repName in currentBasis if not repName in matchedSourceBasis],
              1
            )
            
            # This transformation may change the state and/or the basis.
            # Here we consider state changes like in-place <--> out-of-place
            # and multiplying the data by a constant
            resultState = list(currentState)
            if transformation.get('outOfPlace', False):
              resultState[0] = {
                BasisState.IN_PLACE: BasisState.OUT_OF_PLACE,
                BasisState.OUT_OF_PLACE: BasisState.IN_PLACE
              }[currentState[0]]
            if transformation.get('scaling', False):
              resultState[1] = BasisState.SCALED
            resultState = tuple(resultState)
            
            # Multiply the costMultiplier through the cost listed by the transform
            newCost = [costMultiplier * transformation.get(key, 0) for key in ['communicationsCost', 'cost']]
            # Add that cost to the old cost
            newCost = tuple(old + new for old, new in zip(self.cost, newCost))
            
            # Create the new BasisState and add it to the list of nodes reachable from this node.
            newState = BasisState(newCost, (resultBasis, resultState), previous = (self.location, (transformID, transformationPair)))
            results.append(newState)
        return results
      
    
    def convertSpaceInFieldToBasis(space, field):
      """Transforms an old-style `space` in field `field` to a new-style basis specification."""
      return tuple(dim.inSpace(space).name for dim in field.dimensions)
    
    def pathsFromBasisToBasis(start, end, shortestPaths):
      """
      Given a dictionary of shortest paths provided by a Dijkstra search, determine
      the actual paths that connect the basis `start` and the basis `end`. The returned
      paths will only include valid paths. For example, if a FFT is included in a path,
      the path must also include a scaling operation somewhere.
      """
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
    
    basesFieldMap = dict()
    for vector in vectors:
      vectorBases = set(driver.canonicalBasisForBasis(convertSpaceInFieldToBasis(space, vector.field))
                          for space in vector.spacesNeeded)
      if not vector.field.name in basesFieldMap:
        basesFieldMap[vector.field.name] = set()
      basesFieldMap[vector.field.name].update(vectorBases)
    
    # Next step: Perform Dijkstra search over the provided transforms to find the optimal transform map.
    for basesNeeded in basesFieldMap.values():
      for basis in basesNeeded:
        startState = BasisState( (0, 0), (basis, (BasisState.IN_PLACE, BasisState.UNSCALED)))
        shortestPaths = DijkstraSearch.perform(startState)
        
        # Now we need to extract useful information from this
        for aBasis in [b for b in basesNeeded if not b == basis]:
          transformationPair = frozenset([basis, aBasis])
          # If we already have an entry for this transformationPair, then we don't need to consider it.
          if transformationPair in transformMap: continue
          # Now to obtain concrete lists of potential transform steps
          paths = pathsFromBasisToBasis(basis, aBasis, shortestPaths)
          
          # Now we need to rank the bloody things. And it has to be stable from one run to the next.
          # Ordering: Least steps, least out-of-place operations, most reused transforms, alphabetic
          # Because we are doing an ascending sort, but want the *most* reused transforms,
          # we use the negative of the number of transforms we could reuse.
          
          # Create a list with the ranking information and the actual path
          rankedPaths = [(len(path),
                          sum([self.availableTransformations[tID].get('outOfPlace', False) 
                                for tID, tS in path[1::2]], 0),
                          -sum([td in transformsNeeded for td in path[1::2]]),
                          path) for path in paths]
          # Perform an ascending sort
          rankedPaths.sort()
          path = rankedPaths[0][-1]
          # Add the transforms needed for this path to the list of transforms we need. This way
          # we can try and re-use already-used transforms when there is a choice between two
          # paths that would otherwise have the same rank
          transformsNeeded.update([transformDescriptor for transformDescriptor in path[1::2]])
          transformMap[transformationPair] = path
      
    print transformMap
    
    transformsNeeded.clear()
    for vector in vectors:
      vectorBases = set(driver.canonicalBasisForBasis(convertSpaceInFieldToBasis(space, vector.field))
                          for space in vector.spacesNeeded)
      for transformationPair in combinations(2, vectorBases):
        transformationPair = frozenset(transformationPair)
        path = transformMap[transformationPair]
        for transformID, basisPair in path[1::2]:
          # The transform may decide that different actions of the same transform
          # should be considered different transformations
          # (think FFT's with different numbers of points not in the FFT dimension)
          transformSpecifier = None
          transformation = self.availableTransformations[transformID]
          if 'transformSpecifier' in transformation:
            currentBasis = list(transformationPair)[0]
            resultBasis, (prefixBasis, matchedSourceBasis, postfixBasis) = transformedBasis(currentBasis, transformationPair)
            
            transformSpecifier = transformation['transformSpecifier'](
              basisPair,
              vector,
              prefixBasis,
              postfixBasis,
              representationMap
            )
          transformsNeeded.add((transformID, transformSpecifier))
    
    print transformsNeeded
    # Now we need to extract the transforms and include that information in choosing transforms
    # One advantage of this method is that we no longer have to make extra fft plans or matrices when we could just re-use others.
    # Not only do we need to extract the transforms, but we must also produce a simple list of transforms that must be applied
    # to change between any bases for this vector.
    
    for transformID, transformSpecifier in transformsNeeded:
      transformation = self.availableTransformations[transformID].copy()
      transformation['transformSpecifier'] = transformSpecifier
      del transformation['transformations']
      # transformation['transformPair'] = transformPair
      self.neededTransformations.append(transformation)
    print self.neededTransformations
  

