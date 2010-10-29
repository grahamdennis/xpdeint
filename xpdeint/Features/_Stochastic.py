#!/usr/bin/env python
# encoding: utf-8
"""
_Stochastic.py

Created by Graham Dennis on 2008-01-13.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.Features._Feature import _Feature
from xpdeint.Vectors.NoiseVector import NoiseVector
from xpdeint.Segments.Integrators.AdaptiveStep import AdaptiveStep as AdaptiveStepIntegrator
from xpdeint.Geometry.NonUniformDimensionRepresentation import NonUniformDimensionRepresentation
from xpdeint.Stochastic.RandomVariables.GaussianRandomVariable import GaussianRandomVariable

from xpdeint.ParserException import ParserException, parserWarning

class _Stochastic (_Feature):
  def adaptiveIntegratorsWithNoises(self):
    adaptiveIntegratorList = [ai for ai in self.getVar('templates') if isinstance(ai, AdaptiveStepIntegrator) and ai.dynamicNoiseVectors]

    return adaptiveIntegratorList

  def xsilOutputInfo(self, dict):
    return self.implementationsForChildren('xsilOutputInfo', dict)
  
  def preflight(self):
    super(_Stochastic, self).preflight()
    
    self.noiseVectors = [o for o in self.getVar('templates') if isinstance(o, NoiseVector)]
    
    self.nonUniformDimRepsNeededForGaussianNoise = set()
    for nv in [nv for nv in self.noiseVectors if isinstance(nv.randomVariable, GaussianRandomVariable)]:
      self.nonUniformDimRepsNeededForGaussianNoise.update(dimRep for dimRep in nv.field.inBasis(nv.initialBasis) if isinstance(dimRep, NonUniformDimensionRepresentation))
    
    # For each adaptive step integrator using noises, we need to reduce the order of the integrator
    for integrator in [ai for ai in self.getVar('templates') if isinstance(ai, AdaptiveStepIntegrator)]:
      integrator.stepper.integrationOrder /= 2.0
    
    
  
