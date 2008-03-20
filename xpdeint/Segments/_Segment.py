#!/usr/bin/env python
# encoding: utf-8
"""
_Segment.py

This contains all the pure-python code for segments

Created by Graham Dennis on 2007-10-18.
Copyright (c) 2007 __MyCompanyName__. All rights reserved.
"""

from xpdeint.ScriptElement import ScriptElement

class _Segment (ScriptElement):
  def __init__(self, *args, **KWs):
    ScriptElement.__init__(self, *args, **KWs)
    
    self.segmentNumber = len(filter(lambda x: isinstance(x, _Segment), self.getVar('templates'))) - 1
    self._childSegments = []
    self.parentSegment = None
    self.localCycles = 1
    
    scriptElements = self.getVar('scriptElements')
    
    if not self in scriptElements:
      scriptElements.append(self)
  
  @property
  def name(self):
    return 'segment' + str(self.segmentNumber)
  
  @property
  def childSegments(self):
    return self._childSegments[:]
  
  @property
  def totalCycles(self):
    currSegment = self
    totalCycles = 1
    while currSegment:
      totalCycles *= currSegment.localCycles
      currSegment = currSegment.parentSegment
    return totalCycles
  
  def addSegment(self, seg):
    self._childSegments.append(seg)
    seg.parentSegment = self
  
