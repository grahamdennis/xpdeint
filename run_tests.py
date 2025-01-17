#!/usr/bin/env python
# encoding: utf-8
"""
run_tests.py

Created by Graham Dennis on 2008-06-15.

Copyright (c) 2008-2012, Graham Dennis

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import xpdeint.Python24Support

import os
import re
import sys
import getopt
import shutil
import hashlib
import unittest
import subprocess

from xml.dom import minidom
import xpdeint.minidom_extras
from xpdeint import CodeParser

from xpdeint.XSILFile import XSILFile

import numpy

help_message = '''
The help message goes here.
'''


class Usage(Exception):
  def __init__(self, msg):
    self.msg = msg

def pass_nan_test(array1, array2):
    """Return `True` if isNaN(`array1`) == isNaN(`array2`)"""
    # NaN test. array2 is allowed to be NaN at an index if array1 is also NaN there.
    nanTestPassed = numpy.equal(numpy.isnan(array1), numpy.isnan(array2)).all()
    return nanTestPassed

def array_approx_equal(array1, array2, absTol, relTol):
  """Return `True` if all of (`array1` - `array2`) <= `absTol` or (`array1` - `array2`) <= `relTol` * `array2`"""
  diff = array1-array2
  # NaN values would fail this test. So we have to exclude them. But only exclude them if array2 (the expected results)
  # have a NaN
  return numpy.logical_or(numpy.logical_or(numpy.abs(diff) <= 0.5 * relTol * (numpy.abs(array2) + numpy.abs(array1)), numpy.abs(diff) <= absTol), numpy.isnan(array2)).all()

def scriptTestingFunction(root, scriptName, testDir, absPath, self):
  if not os.path.exists(testDir):
    os.makedirs(testDir)
  
  proc = subprocess.Popen('xmds2 --no-version ' + '"' + absPath + '"',
                          shell=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          cwd=testDir)
  (stdout, stderr) = proc.communicate()
  returnCode = proc.wait()
  
  message = ''.join(["\n%(handleName)s:\n%(content)s" % locals() for handleName, content in [('stdout', stdout), ('stderr', stderr)] if content])
  
  # A few tests require specific features.  If it isn't available, skip the test
  # rather than failing.
  # The skip functionality for the unittest class is only available
  # in python 2.7 and later, so check for that too.
  if returnCode != 0 and sys.version_info[:2] >= (2, 7):
    # A few tests require XMDS1. If XMDS1 isn't present we should just
    # skip that test rather than failing.
    if re.search(r'^The missing \w+ feature\(s\) were: .*xmds.*', message, re.MULTILINE):
      self.skipTest("Skipping test as XMDS1 is required and not installed")
    if re.search(r'^The missing \w+ feature\(s\) were:', message, re.MULTILINE):
      self.skipTest("Skipping test as feature required is not installed")
    if re.search(r'This script requires the python package', message, re.MULTILINE):
      self.skipTest("Skipping test as python package required is not installed")

  self.assert_(returnCode == 0, ("Failed to compile." % locals()) + message)
  
  xmlDocument = minidom.parse(absPath)
  simulationElement = xmlDocument.getChildElementByTagName('simulation')
  nameElement = simulationElement.getChildElementByTagName('name')
  testingElement = simulationElement.getChildElementByTagName('testing')
  
  simulationName = nameElement.innerText()
  
  # If the source is the same as the last known good, then we don't need to compile or execute the simulation.
  sourceFilePath = os.path.join(testDir, simulationName + '.cc')
  checksumFilePath = os.path.join(testDir, simulationName + '_last_known_good.checksum')
  sourceContents = file(sourceFilePath).read()
  h = hashlib.sha1()
  h.update(sourceContents)
  currentChecksum = h.hexdigest()
  
  if os.path.exists(checksumFilePath):
    lastKnownGoodChecksum = file(checksumFilePath).read()
    
    if lastKnownGoodChecksum == currentChecksum:
      # The checksums check out, so we don't need to go any further
      return
  
  # Now we have compiled, we need to copy any input data needed and then run the simulation
  inputXSILElements = testingElement.getChildElementsByTagName('input_xsil_file', optional=True)
  
  filesToCopy = []
  
  for inputXSILElement in inputXSILElements:
    name = inputXSILElement.getAttribute('name').strip()
    filesToCopy.append(name)
    inputXSILFile = XSILFile(os.path.join(os.path.split(absPath)[0], name), loadData=False)
    filesToCopy.extend([os.path.join(os.path.split(name)[0], xsil.data.filename) for xsil in inputXSILFile.xsilObjects if hasattr(xsil.data, 'filename')])
  
  for fileToCopy in filesToCopy:
    sourceFile = os.path.join(os.path.split(absPath)[0], fileToCopy)
    shutil.copy(sourceFile, testDir)
  
  # Allow command-line arguments to be specified for the simulation
  commandLineElement = testingElement.getChildElementByTagName('command_line', optional=True)
  argumentsElement = testingElement.getChildElementByTagName('arguments', optional=True)
  commandLineString = '"./' + simulationName + '"'
  if commandLineElement:
    # The command line element overrides the prefix
    commandLineString = commandLineElement.innerText().strip()
  if argumentsElement:
    commandLineString += ' ' + argumentsElement.innerText().strip()
  
  simulationProc = subprocess.Popen(commandLineString,
                                    shell=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    cwd=testDir)
  (stdout, stderr) = simulationProc.communicate()
  returnCode = simulationProc.wait()
  
  self.assert_(returnCode == 0, "Failed to execute compiled simulation correctly. Got returnCode %(returnCode)i;\nstdout = %(stdout)s;\nstderr = %(stderr)s\n" % locals())
  
  # The next thing to check is that the generated data agrees with the expected data to within the set error margins.
  xsilFileElements = testingElement.getChildElementsByTagName('xsil_file', optional=True)
  for xsilFileElement in xsilFileElements:
    sourceFile = xsilFileElement.getAttribute('name').strip()
    expectedResultsFile = xsilFileElement.getAttribute('expected').strip()
    # Defaults
    absoluteTolerance = 0 
    relativeTolerance = 1e-9
    
    if xsilFileElement.hasAttribute('absolute_tolerance'):
      absoluteTolerance = float(xsilFileElement.getAttribute('absolute_tolerance'))
    if xsilFileElement.hasAttribute('relative_tolerance'):
      relativeTolerance = float(xsilFileElement.getAttribute('relative_tolerance'))
    
    resultsFullPath = os.path.join(testDir, sourceFile)
    results = XSILFile(resultsFullPath)
    expectedResultsFullPath = os.path.join(os.path.split(absPath)[0], expectedResultsFile)
    if not os.path.exists(expectedResultsFullPath):
      print >> sys.stderr, "Expected results file '%(expectedResultsFile)s' missing. Using current. " % locals()
      
      # If there are any NaN's in the results, issue a warning.
      for mgNum, o in enumerate(results.xsilObjects):
        for v in o.independentVariables:
          if numpy.isnan(v['array']).any():
            print >> sys.stderr, "Warning: Coordinate '%s' in moment group %i of file '%s' contains a NaN." % (v['name'], mgNum+1, sourceFile)
        for v in o.dependentVariables:
          if numpy.isnan(v['array']).any():
            print >> sys.stderr, "Warning: Dependent variable '%s' in moment group %i of file '%s' contains a NaN." % (v['name'], mgNum+1, sourceFile)
      
      resultsFileContents = file(resultsFullPath).read()
      
      for xsilObject in results.xsilObjects:
        if hasattr(xsilObject.data, 'filename'):
          # If the moment group has a data file name, then we need to copy it to the expected results file
          newDataFilename = xsilObject.data.filename.replace(os.path.splitext(sourceFile)[0], os.path.splitext(expectedResultsFile)[0], 1)
          
          resultsFileContents = resultsFileContents.replace(xsilObject.data.filename, newDataFilename)
          
          shutil.copyfile(os.path.join(testDir, xsilObject.data.filename),
                          os.path.join(os.path.split(absPath)[0], newDataFilename))
      
      file(expectedResultsFullPath, 'w').write(resultsFileContents)
    else:
      expectedResults = XSILFile(expectedResultsFullPath)
      
      self.assert_(len(results.xsilObjects) == len(expectedResults.xsilObjects))
      
      momentGroupElements = xsilFileElement.getChildElementsByTagName('moment_group', optional=True)
      if momentGroupElements:
        self.assert_(len(momentGroupElements) == len(results.xsilObjects))
      else:
        momentGroupElements = [None]*len(results.xsilObjects)
      
      for mgNum, (o1, o2, mgElem) in enumerate(zip(results.xsilObjects, expectedResults.xsilObjects, momentGroupElements)):
        currentAbsoluteTolerance = absoluteTolerance
        currentRelativeTolerance = relativeTolerance
        self.assert_(len(o1.independentVariables) == len(o2.independentVariables),
                     "The number of independent variables in moment group %(mgNum)i doesn't match." % locals())
        self.assert_(len(o1.dependentVariables) == len(o2.dependentVariables),
                     "The number of dependent variables in moment group %(mgNum)i doesn't match." % locals())
        
        if mgElem:
          if mgElem.hasAttribute('absolute_tolerance'):
            currentAbsoluteTolerance = float(mgElem.getAttribute('absolute_tolerance'))
          if mgElem.hasAttribute('relative_tolerance'):
            currentRelativeTolerance = float(mgElem.getAttribute('relative_tolerance'))
        
        self.assert_(currentAbsoluteTolerance != None and currentRelativeTolerance != None, "An absolute and a relative tolerance must be specified.")
        
        for v1, v2 in zip(o1.independentVariables, o2.independentVariables):
          self.assert_(v1['name'] == v2['name'])
          self.assert_(v1['length'] == v2['length'])
          # These are the coordinates, we just specify a constant absolute and relative tolerance.
          # No-one should need to change these
          self.assert_(array_approx_equal(v1['array'], v2['array'], 1e-7, 1e-6),
                      "Coordinate '%s' in moment group %i of file '%s' didn't pass tolerance criteria." % (v1['name'], mgNum+1, sourceFile))
        
        for v1, v2 in zip(o1.dependentVariables, o2.dependentVariables):
          self.assert_(v1['name'] == v2['name'])
          self.assert_(pass_nan_test(v1['array'], v2['array']),
                       "Dependent variable '%s' in moment group %i of file '%s' had a NaN where the expected results didn't (or vice-versa)." % (v1['name'], mgNum+1, sourceFile))
          self.assert_(array_approx_equal(v1['array'], v2['array'], currentAbsoluteTolerance, currentRelativeTolerance),
                       "Dependent variable '%s' in moment group %i of file '%s' failed to pass tolerance criteria." % (v1['name'], mgNum+1, sourceFile))
  
  # Test has succeeded, so save our checksum for the source file and copy the source file
  file(checksumFilePath, 'w').write(currentChecksum)
  
  lastKnownGoodSourcePath = os.path.join(testDir, simulationName + '_last_known_good.cc')
  file(lastKnownGoodSourcePath, 'w').write(sourceContents)

def partial(func, *args, **keywords):
  def newfunc(*fargs, **fkeywords):
    newkeywords = keywords.copy()
    newkeywords.update(fkeywords)
    return func(*(args + fargs), **newkeywords)
  return newfunc


def main(argv=None):
  verbose = False
  
  if argv is None:
    argv = sys.argv
  try:
    try:
      opts, args = getopt.getopt(argv[1:], "ho:v", ["help", "output="])
    except getopt.error, msg:
      raise Usage(msg)
  
    # option processing
    for option, value in opts:
      if option == "-v":
        verbose = True
      if option in ("-h", "--help"):
        raise Usage(help_message)
      if option in ("-o", "--output"):
        output = value
  
  except Usage, err:
    print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
    print >> sys.stderr, "\t for help use --help"
    return 2
  
  basePath = os.path.dirname(__file__)
  
  resultsPath = os.path.join(basePath, 'testsuite_results')
  if not os.path.exists(resultsPath):
    os.mkdir(resultsPath)
  resultsPath = os.path.abspath(resultsPath)
  
  print "Saving test results in %(resultsPath)s" % locals()
  
  testsuites = {}
  baseSuiteName = 'testsuite'
  baseSuitePath = os.path.join(basePath, baseSuiteName)
  
  for root, dirs, files in os.walk(baseSuitePath):
    # First remove directories we don't want to traverse
    for dirName in ['.svn']:
      if dirName in dirs:
        dirs.remove(dirName)
    # Remove the 'testsuite/' part of the path
    dirRelativeToBase = root[(len(baseSuitePath)+1):]
    if dirRelativeToBase:
      testSuiteName = os.path.join(baseSuiteName, dirRelativeToBase)
    else:
      testSuiteName = baseSuiteName
    
    # If we have .xmds files in this path, then create a TestCase subclass
    xmdsTestScripts = [filename for filename in files if os.path.splitext(filename)[1].lower() == '.xmds']
    
    if xmdsTestScripts:
      class ScriptTestCase(unittest.TestCase):
        # Create test functions for each test script using 'scriptTestingFunction'
        # These test function names are of the form 'test_ScriptName'
        for scriptName in xmdsTestScripts:
          prefix = os.path.splitext(scriptName)[0]
          absPath = os.path.abspath(os.path.join(root, scriptName))
          testDir = os.path.join(resultsPath, dirRelativeToBase)
          locals()['test_' + prefix] = partial(scriptTestingFunction, root, scriptName, testDir, absPath)
          locals()['test_' + prefix].__doc__ = os.path.join(dirRelativeToBase, scriptName)
      
      # Create a TestSuite from that class
      suite = unittest.defaultTestLoader.loadTestsFromTestCase(ScriptTestCase)
      testsuites[testSuiteName] = suite
    
    if not testSuiteName in testsuites:
      testsuites[testSuiteName] = unittest.TestSuite()
    
    if not any(filename == 'do_not_run_tests_by_default' for filename in files):
      # Add our TestSuite as a sub-suite of all parent suites
      suite = testsuites[testSuiteName]
      head = testSuiteName
      while True:
        head, tail = os.path.split(head)
        if not head or not tail:
          break
        testsuites[head].addTest(suite)
  
  
  suitesToRun = list()
  if len(args):
    for suiteName in args:
      fullSuiteName = os.path.join(baseSuiteName, suiteName)
      if fullSuiteName in testsuites:
        suitesToRun.append(testsuites[fullSuiteName])
      else:
        print >> sys.stderr, "Unable to find test '%(suiteName)s'" % locals()
  else:
    suitesToRun.append(testsuites[baseSuiteName])
  suitesToRun.append(unittest.defaultTestLoader.loadTestsFromModule(CodeParser))
  
  fullSuite = unittest.TestSuite(tests=suitesToRun)
  
  return not unittest.TextTestRunner(verbosity = 2 if verbose else 1).run(fullSuite).wasSuccessful()


if __name__ == "__main__":
  sys.exit(main())
