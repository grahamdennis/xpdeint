#!/usr/bin/env python
# encoding: utf-8
"""
_FilterOperator.py

Created by Graham Dennis on 2008-01-01.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from Operator import Operator
from .Geometry.FieldElement import FieldElement

import RegularExpressionStrings
from .ParserException import ParserException

class _FilterOperator (Operator):
  evaluateOperatorFunctionArguments = []
  operatorKind = Operator.OtherOperatorKind
  vectorsMustBeInSubsetsOfIntegrationField = False
  
  @property
  def defaultOperatorSpace(self):
    return 0
  
  def preflight(self):
    super(_FilterOperator, self).preflight()
    
    dimensionNames = set()
    for dependency in self.dependencies:
      dimensionNames.update([dim.name for dim in dependency.field.dimensions])
    
    self.loopingField = FieldElement.sortedFieldWithDimensionNames(dimensionNames)
    
    if self.dependenciesEntity and self.dependenciesEntity.xmlElement.hasAttribute('fourier_space'):
       self.operatorSpace = self.loopingField.spaceFromString(self.dependenciesEntity.xmlElement.getAttribute('fourier_space'),
                                                              xmlElement = self.dependenciesEntity.xmlElement)
  
  


