#!/usr/bin/env python
# encoding: utf-8
"""
XSILFile.py

Created by Graham Dennis on 2008-06-18.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

import os
import sys
from xml.dom import minidom
import xpdeint.minidom_extras

import numpy

class XSILData(object):
  def __init__(self, independentVariables, dependentVariables):
    self.independentVariables = independentVariables
    self.dependentVariables = dependentVariables
  

class XSILDataASCII(XSILData):
  def __init__(self, independentVariables, dependentVariables, dataString):
    XSILData.__init__(self, independentVariables, dependentVariables)
    self.parseDataString(dataString)
  
  def parseDataString(self, dataString):
    assert False


class XSILDataBinary(XSILData):
  def __init__(self, independentVariables, dependentVariables, uLong, precision, encoding, dataFile):
    XSILData.__init__(self, independentVariables, dependentVariables)
    self.dataFilename = os.path.split(dataFile)[1]
    self.parseDataFile(uLong, precision, encoding, dataFile)
  
  def parseDataFile(self, uLong, precision, encoding, dataFile):
    assert uLong in ['uint32', 'uint64']
    assert precision in ['single', 'double']
    assert encoding in ['BigEndian', 'LittleEndian']
    
    fd = file(dataFile, 'rb')
    
    byteorder = {'LittleEndian': '<', 'BigEndian': '>'}[encoding]
    unsignedLongTypeString = {'uint32': 'u4', 'uint64': 'u8'}[uLong]
    realTypeString = {'single': 'f4', 'double': 'f8'}[precision]
    
    ulongDType = numpy.dtype(byteorder + unsignedLongTypeString)
    floatDType = numpy.dtype(byteorder + realTypeString)
    
    independentGeometry = []
    
    for independentVariable in self.independentVariables:
      size = numpy.fromfile(fd, dtype=ulongDType, count=1)
      size.newbyteorder('=') # Convert to native datatype
      independentGeometry.append(size)
      assert size == independentVariable['length']
      a = numpy.fromfile(fd, dtype=floatDType, count=size)
      a.newbyteorder('=') # Convert to native datatype
      independentVariable['array'] = a
    
    for dependentVariable in self.dependentVariables:
      size = numpy.fromfile(fd, dtype=ulongDType, count=1)
      size.newbyteorder('=') # Convert to native datatype
      a = numpy.fromfile(fd, dtype=floatDType, count=size)
      a.newbyteorder('=') # Convert to native datatype
      a.reshape(*independentGeometry)
      dependentVariable['array'] = a
    

class XSILObject(object):
  def __init__(self, name, dataObject):
    self.name = name
    self.dataObject = dataObject
    self.independentVariables = dataObject.independentVariables
    self.dependentVariables = dataObject.dependentVariables


class XSILFile(object):
  def __init__(self, filename):
    self.filename = filename
    self.xsilObjects = []
    
    xmlDocument = minidom.parse(filename)
    simulationElement = xmlDocument.getChildElementByTagName('simulation')
    xsilElements = simulationElement.getChildElementsByTagName('XSIL')
    for xsilElement in xsilElements:
      xsilName = xsilElement.getAttribute('Name')
      
      paramElement = xsilElement.getChildElementByTagName('Param')
      assert paramElement.hasAttribute('Name') and paramElement.getAttribute('Name') == 'n_independent'
      nIndependentVariables = int(paramElement.innerText())
      
      arrayElements = xsilElement.getChildElementsByTagName('Array')
      assert len(arrayElements) == 2
      
      variableArrayElement = arrayElements[0]
      dataArrayElement = arrayElements[1]
      
      assert variableArrayElement.hasAttribute('Name') and variableArrayElement.getAttribute('Name') == 'variables'
      dimElement = variableArrayElement.getChildElementByTagName('Dim')
      nVariables = int(dimElement.innerText())
      nDependentVariables = nVariables - nIndependentVariables
      assert nDependentVariables > 0
      streamElement = variableArrayElement.getChildElementByTagName('Stream')
      variableNames = streamElement.innerText().strip().split(' ')
      assert len(variableNames) == nVariables
      
      independentVariables = [{'name': name} for name in variableNames[0:nIndependentVariables]]
      dependentVariables = [{'name': name} for name in variableNames[nIndependentVariables:]]
      
      assert len(dependentVariables) == nDependentVariables
      
      dimElements = dataArrayElement.getChildElementsByTagName('Dim')
      assert len(dimElements) == nIndependentVariables + 1
      
      for dimIndex, dimElement in enumerate(dimElements):
        if dimIndex < nIndependentVariables:
          independentVariables[dimIndex]['length'] = int(dimElement.innerText())
        else:
          assert int(dimElement.innerText()) == nVariables
      
      streamElement = dataArrayElement.getChildElementByTagName('Stream')
      metalinkElement = streamElement.getChildElementByTagName('Metalink')
      format = metalinkElement.getAttribute('Format').strip()
      assert format == 'Binary', "ASCII format output currently unsupported"
      
      dataObject = None
      
      if format == 'Binary':
        uLong = metalinkElement.getAttribute('UnsignedLong').strip()
        precision = metalinkElement.getAttribute('precision').strip()
        encoding = metalinkElement.getAttribute('Encoding').strip()
        relativePath = streamElement.innerText().strip()
        dataFileName = os.path.join(os.path.split(filename)[0], relativePath)
        dataObject = XSILDataBinary(independentVariables, dependentVariables, uLong, precision, encoding, dataFileName)
      
      self.xsilObjects.append(XSILObject(xsilName, dataObject))
    
  



