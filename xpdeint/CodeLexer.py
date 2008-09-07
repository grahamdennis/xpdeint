#!/usr/bin/env python
# encoding: utf-8
"""
CodeLexer.py

Created by Graham Dennis on 2008-09-04.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.

The purpose of this module is to facilitate better understanding of user
code blocks by breaking the code up into Tokens (strings of text with an
associated meaning) and using this as the basis for all code modification.
We need to modify user code in a number of situations, the most obvious being
IP and EX operators where an expression like 'L[u]' in 'du_dt = L[u];' must be 
found and replaced with some other string. The trouble with using regular
expressions is that they would also match inside comments, string constants,
and so giving the user different results to what they were expecting.
"""

from pygments import lexers
from pygments.token import Token

cppLexer = lexers.get_lexer_by_name('c++')

from xpdeint.ParserException import ParserException, parserWarning

class LexerException(ParserException):
  """
  A class for exceptions thrown by the C++ code lexer.
  This class determines the line in the original script that
  corresponds to the part of the code block that triggered the
  exception.
  """
  def __init__(self, codeEntity, codeIndex, msg):
    ParserException.__init__(self, codeEntity.xmlElement, msg)
    
    if not hasattr(codeEntity, 'isFake'):
      # We have a real code entity that actually correseponds to a CDATA section in the script.
      
      self.columnNumber = None
      
      lines = codeEntity.value.splitlines(True)
      indexCounter = 0
      for lineNumber, line in enumerate(lines):
        indexCounter += len(line)
        if indexCounter > codeIndex:
          self.lineNumber = codeEntity.xmlElement.lineNumberForCDATASection() + lineNumber
          break
    

def balancedTokens(tokenGenerator, openingToken, finalPunctuation, codeEntity):
  """
  Returns a nested list of tokens (tuples of ``(stringIndex, tokenKind, tokenString)`` )
  starting at the current state of the `tokenGenerator` with all balanced sub-expressions
  stored as lists. Where 'balanced' means the expressions between matching brackets or 
  parentheses.
  
  For example ``'( abc[3] );'`` would be returned as::
  
    [   (0, Token.Text, ''),
        [   (0, Token.Punctuation, '('),
            (1, Token.Text, ' '),
            (2, Token.Name, 'abc'),
            [   (5, Token.Punctuation, '['),
                (6, Token.Literal.Number.Integer, '3'),
                (7, Token.Punctuation, ']')],
            (8, Token.Text, ' '),
            (9, Token.Punctuation, ')')],
        (10, Token.Punctuation, ';'),
        (11, Token.Text, '')]
  """
  results = []
  if openingToken:
    results.append(openingToken)
  for token in tokenGenerator:
    charIndex, tokenKind, string = token
    if tokenKind in Token.Punctuation:
      if string == finalPunctuation:
        results.append(token)
        return results
      pairedPunctuation = ['()', '[]', '{}']
      result = token
      for startChar, endChar in pairedPunctuation:
        if string == startChar:
          result = balancedTokens(tokenGenerator, token, endChar, codeEntity)
          break
      results.append(result)
    else:
      results.append(token)
  if finalPunctuation:
    raise LexerException(codeEntity, charIndex, "Unable to parse code due to mismatched brackets.")
  return results

def flatten(lst):
  """
  Flatten out nested lists into one list.
  i.e. turn ``[a, [b, c], d]`` into ``[a, b, c, d]``.
  """
  result = []
  for element in lst:
    if isinstance(element, list):
      result.extend(flatten(element))
    else:
      result.append(element)
  return result

def strippedTokenStream(tokenStream):
  """
  Take a nested list of tokens and extract the string content.
  i.e. perform the opposite operation to lexing.
  """
  result = []
  startIndex = None
  endIndex = None
  for charIndex, tokenKind, string in flatten(tokenStream):
    if startIndex == None:
      startIndex = charIndex
    endIndex = charIndex + len(string)
    if tokenKind in Token.Comment:
      pass
    else:
      result.append(string)
  return ''.join(result), slice(startIndex, endIndex)


def targetComponentsForOperatorsInString(operatorNames, codeEntity):
  """
  Return a list of pairs of operator names and their targets that are in `codeString`.
  The valid operator names searched for are `operatorNames`. For example, if 'L' is in `operatorNames`,
  then in the code ``L[phi]`` the return value would be ``('L', 'phi', slice(firstCharacterIndex, lastCharacterIndex))``.
  """
  results = []
  tokenGenerator = cppLexer.get_tokens_unprocessed(codeEntity.value)
  for charIndex, tokenKind, string in tokenGenerator:
    if tokenKind in Token.Name and string in operatorNames:
      operatorName = string
      nextToken = tokenGenerator.next()
      if not nextToken[1] in Token.Punctuation or not nextToken[2] == '[':
        raise LexerException(codeEntity, charIndex, "Invalid use of '%(string)s' operator in code block." % locals())
      balancedTokenStream = balancedTokens(tokenGenerator, nextToken, ']', codeEntity)
      strippedContents, tokenRange = strippedTokenStream(balancedTokenStream)
      operatorTarget = strippedContents[1:-1].strip() # Strip leading '[' and trailing ']', and any other whitespace
      tokenRange = slice(charIndex, tokenRange.stop)
      results.append((operatorName, operatorTarget, tokenRange))
  return results


def integerValuedDimensionsForField(tokenGenerator, field, codeEntity):
  """
  Return a ``(dict, slice)`` tuple to extract the integer-valued dimension
  indices starting at the position of `tokenGenerator` given that the indices
  are accessing a component of a vector in `field`.
  
  For example parse ``[j, k+7][m*n, n%3]`` to::
  
    { 'j': ('j', slice(1, 2)),
      'k': ('k+7', slice(4, 7)),
      'm': ('m*n', slice(9, 12)),
      'n': ('n%3', slice(14, 17))}
  
  where the ``slice`` objects are the ranges in the code string where these expressions occur.
  """
  result = {}
  overallStartIndex = None
  overallEndIndex = None
  integerValuedDimensions = field.integerValuedDimensions
  for dimList in integerValuedDimensions:
    nextToken = tokenGenerator.next()
    if not nextToken[1] in Token.Punctuation or not nextToken[2] == '[':
      # The fact that we've just taken a token isn't a problem, as it isn't
      # possible for a name token to immediately follow another name token
      return {}, slice(None)
    if overallStartIndex == None:
      overallStartIndex = nextToken[0]
    balancedTokenStream = balancedTokens(tokenGenerator, nextToken, ']', codeEntity)
    overallEndIndex = balancedTokenStream[-1][0] + len(balancedTokenStream[-1][2])
    tokenStreamIterator = iter(balancedTokenStream[1:-1]) # skip leading '[' and trailing ']'
    for dim in dimList:
      indexString = ''
      startIndex = None
      endIndex = None
      for token in tokenStreamIterator:
        if isinstance(token, list):
          strippedStream, codeSlice = strippedTokenStream(token)
          if startIndex == None:
            startIndex = codeSlice.start
          endIndex = codeSlice.stop
          indexString += strippedStream
        else:
          charIndex, tokenKind, string = token
          if tokenKind in Token.Punctuation and string == ',':
            # We have found the dimension separator
            break
          else:
            if startIndex == None:
              startIndex = charIndex
            endIndex = charIndex + len(string)
            if not tokenKind in Token.Comment:
              indexString += string
      if not indexString:
        raise LexerException(codeEntity, startIndex, "Index for integer-valued dimension '%s' is empty!" % dim.name)
      result[dim.name] = (indexString.strip(), slice(startIndex, endIndex))
  return result, slice(overallStartIndex, overallEndIndex)

def integerValuedDimensionsForVectors(vectors, codeEntity):
  """
  Find all places in the `codeEntity` where any components of any of the `vectors`
  are accessed with index-valued dimensions and return a ``(componentName, field, resultDict, codeSlice)``
  tuple for each such occurrence. ``codeSlice`` is the character range over which this expression occurs,
  and ``resultDict`` is a dictionary describing how each dimension is accessed. See `integerValuedDimensionsForField`
  for more information about ``resultDict``.
  """
  componentNames = set()
  for v in vectors:
    componentNames.update(v.components)
  results = []
  tokenGenerator = cppLexer.get_tokens_unprocessed(codeEntity.value)
  for charIndex, tokenKind, string in tokenGenerator:
    if tokenKind in Token.Name and string in componentNames:
      componentName = string
      
      field = [v.field for v in vectors if componentName in v.components][0]
      resultDict, codeSlice = integerValuedDimensionsForField(tokenGenerator, field, codeEntity)
      if resultDict:
        results.append((componentName, field, resultDict, slice(charIndex, codeSlice.stop)))
  
  return results

def integerValuedDimensionsForComponentsInField(components, field, codeEntity):
  """
  Find all places in the `codeEntity` where any of `components` are accessed with
  index-valued dimensions and return a ``(componentName, resultDict, codeSlice)``
  tuple for each such occurrence. The companion of `integerValuedDimensionsForVectors` and
  to be used when `components` are components of vectors.
  """
  results = []
  tokenGenerator = cppLexer.get_tokens_unprocessed(codeEntity.value)
  for charIndex, tokenKind, string in tokenGenerator:
    if tokenKind in Token.Name and string in components:
      componentName = string
      resultDict, codeSlice = integerValuedDimensionsForField(tokenGenerator, field, codeEntity)
      if resultDict:
        results.append((componentName, resultDict, slice(charIndex, codeSlice.stop)))
  
  return results

def performIPOperatorSanityCheck(componentName, propagationDimension, operatorCodeSlice, codeEntity):
  """
  Check that the user hasn't tried to use an IP operator where an IP operator cannot be used.
  
  IP operators must be diagonal, so one cannot have expressions of the form ``dy_dt = L[x];`` for IP operators.
  This is valid for EX operators, but not for IP. This is a common mistake for users to make, and so we should
  do our best to spot it and report the error. This method works by ensuring that the given IP operator acting
  on a given component occurs in the same statement as the derivative variable for that component. While a user
  could make their code pass this check when it technically shouldn't, they essentially have to be trying to do
  so. In the vast majority of cases, if the user's code passes this test, then it is very likely to be a correct
  use of the IP operator.
  """
  derivativeString = 'd%(componentName)s_d%(propagationDimension)s' % locals()
  
  statementStartIndex = 0
  statementStopIndex = None
  derivativeStringAppearedInCurrentStatement = False
  tokenGenerator = cppLexer.get_tokens_unprocessed(codeEntity.value)
  for charIndex, tokenKind, string in tokenGenerator:
    if tokenKind in Token.Punctuation and string == ';':
      statementStopIndex = charIndex + len(string)
      # Assert that the operatorCodeSlice (the extent of the operator) is either entirely inside this statement, or it is entirely outside
      # Something has gone wrong if that isn't true.
      assert operatorCodeSlice.stop <= statementStartIndex \
             or (operatorCodeSlice.start >= statementStartIndex and operatorCodeSlice.stop <= statementStopIndex) \
             or operatorCodeSlice.start >= statementStopIndex
      if operatorCodeSlice.start >= statementStartIndex and operatorCodeSlice.stop <= statementStopIndex and not derivativeStringAppearedInCurrentStatement:
        raise LexerException(codeEntity, charIndex, 
                             "Due to the way IP operators work, they can only contribute\n"
                             "to the derivative of the variable they act on,\n"
                             "i.e. dx_dt = L[x] not dy_dt = L[x].\n\n"
                             "What you probably need to use in this circumstance is an EX operator.\n"
                             "The conflict was caused by the operator '%s' in the statement:\n"
                             "'%s'"
                             % (codeEntity.value[operatorCodeSlice], codeEntity.value[statementStartIndex:statementStopIndex].strip()))
      derivativeStringAppearedInCurrentStatement = False
      statementStartIndex = statementStopIndex
    elif tokenKind in Token.Name and string == derivativeString:
      derivativeStringAppearedInCurrentStatement = True
  
