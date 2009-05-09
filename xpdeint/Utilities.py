#!/usr/bin/env python
# encoding: utf-8
"""
Utilities.py

Created by Graham Dennis on 2008-09-15.
Copyright (c) 2008 __MyCompanyName__. All rights reserved.
"""

from xpdeint.ParserException import ParserException
import re

from heapq import heapify, heappush, heappop

class lazy_property(object):
  """
  A data descriptor that provides a default value for the attribute
  represented via a user-defined function, and this function is evaluated
  at most once with the result cached. Additionally, the property can be
  overridden.
  """
  
  def __init__(self, fget, doc=None):
    self.fget = fget
    self.__doc__ = doc
    if not self.__doc__:
      self.__doc__ = fget.__doc__
    self.__name__ = fget.__name__
  
  def __get__(self, obj, objtype=None):
    if obj is None:
      return self
    if self.fget is None:
      raise AttributeError, "unreadable attribute"
    result = obj.__dict__[self.__name__] = self.fget(obj)
    return result
  

def valueForKeyPath(base, keyPath):
  """
  Return the value for a dotted-name lookup of `keyPath` anchored at `base`.

  This is similar to the KVC methods in Objective-C, however its use is appropriate in Python.
  Evaluating the `keyPath` 'foo.bar.baz' returns the object that would be returned by evaluating
  the string (in Python) base.foo.bar.baz
  """
  attrNames = keyPath.split('.')
  try:
    currentObject = base
    for attrName in attrNames:
      if isinstance(currentObject, dict):
        # Access via dictionary key
        currentObject = currentObject[attrName]
      else:
        # Access attribute
        currentObject = getattr(currentObject, attrName)
  except Exception, err:
    baseRep = repr(base)
    print >> sys.stderr, "Hit exception trying to get keyPath '%(keyPath)s' on object %(baseRep)s." % locals()
    raise
  return currentObject

def setValueForKeyPath(base, value, keyPath):
  """Set the value of the result of the dotted-name lookup of `keyPath` anchored at `base` to `value`."""
  attrNames = keyPath.split('.')
  lastAttrName = attrNames.pop()
  currentObject = base
  try:
    for attrName in attrNames:
      currentObject = getattr(currentObject, attrName)
    if isinstance(currentObject, dict):
      # Set dictionary entry
      currentObject[lastAttrName] = value
    else:
      # Set attribute
      setattr(currentObject, lastAttrName, value)
  except Exception, err:
    baseRep = repr(base)
    print >> sys.stderr, "Hit exception trying to set keyPath '%(keyPath)s' on object %(baseRep)s." % locals()
    raise


def greatestCommonFactor(num):
    t_val = num[0]
    for cnt in range(len(num)-1):
        num1 = t_val
        num2 = num[cnt+1]
        if num1 < num2:
            num1,num2=num2,num1
        while num1 - num2:
            num3 = num1 - num2
            num1 = max(num2,num3)
            num2 = min(num2,num3)
        t_val = num1
    return t_val

def leastCommonMultiple(num):
    if len(num) == 0:
        return 1
    t_val = num[0]
    for cnt in range(len(num)-1):
        num1 = t_val
        num2 = num[cnt+1]
        tmp = greatestCommonFactor([num1,num2])
        t_val = tmp * num1/tmp * num2/tmp
    return t_val

def leopardWebKitHack():
    """
    Hack for Mac OS X Leopard and above so that it doesn't import
    the web rendering framework WebKit when Cheetah tries to import
    the Python web application framework WebKit.
    """
    import sys
    if sys.platform == 'darwin' and not 'WebKit' in sys.modules:
        module = type(sys)
        sys.modules['WebKit'] = module('WebKit')

protectedNamesSet = set("""
gamma nan ceil floor trunc round remainder abs sqrt hypot
exp log pow cos sin tan cosh sinh tanh acos asin atan
j0 j1 jn y0 y1 yn erf real complex Re Im mod2 integer mod
""".split())

def symbolsInString(string, xmlElement = None):
    wordRegex = re.compile(r'\b\w+\b')
    symbolRegex = re.compile(r'[a-zA-Z]\w*')
    words = wordRegex.findall(string)
    for word in words:
        if not symbolRegex.match(word):
            raise ParserException(
                xmlElement,
                "'%(word)s' is not a valid name. All names must start with a letter, "
                "after that letters, numbers and underscores ('_') may be used." % locals()
            )
        if word in protectedNamesSet:
            raise ParserException(
                xmlElement,
                "'%(word)s' cannot be used as a name because it conflicts with an internal function or variable of the same name. "
                "Choose another name." % locals()
            )
    return words

def symbolInString(string, xmlElement = None):
    words = symbolsInString(string, xmlElement)
    if len(words) > 1:
        raise ParserException(
            xmlElement,
            "Only one name was expected at this point. The problem was with the string '%(string)s'" % locals()
        )
    if words:
        return words[0]
    else:
        return None
    

def unique(seq, idfun=None):
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result

def permutations(*iterables):
    def permuteTwo(it1, it2):
        for o1 in it1:
            for o2 in it2:
                if isinstance(o1, tuple):
                    yield o1 + (o2,)
                else:
                    yield (o1, o2)
    
    if len(iterables) == 1:
        return iterables[0]
    
    it = iterables[0]
    for it2 in iterables[1:]:
        it = permuteTwo(it, it2)
    
    return it

def combinations(itemCount, *lsts):
    """Generator for all unique combinations of each list in `lsts` containing `itemCount` elements."""
    def _combinations(itemCount, lst):
        if itemCount == 0 or itemCount > len(lst):
            return
        if itemCount == 1:
            for o in lst:
                yield (o,)
        elif itemCount == len(lst):
            yield tuple(lst)
        else:
            if not isinstance(lst, list):
              lst = list(lst)
            for o in _combinations(itemCount-1, lst[1:]):
                yield (lst[0],) + o
            for o in _combinations(itemCount, lst[1:]):
                yield o
    if len(lsts) == 1:
        return _combinations(itemCount, lsts[0])
    iterables = [list(_combinations(itemCount, lst)) for lst in lsts]
    return permutations(*iterables)


class DijkstraSearch(object):
    """
    A Dijkstra search is an algorithm to search for the least-cost
    route between one node and all other nodes in a graph.
    
    Typically, only one of the least-cost solutions are desired, however
    as we will have some additional criteria to apply later to the returned
    paths, this implementation returns all of the least-cost paths between
    two nodes.
    """
    class State(object):
        """
        A helper class to store information about a given node, the cost to get there
        and the step that was used to get to this node.
        
        It is intended that this class be subclassed for use in searches.
        """
        __slots__ = ['cost', 'location', 'previous']
        def __init__(self, cost, location, previous = None):
            self.cost = cost
            self.location = location
            self.previous = previous
        
        def next(self):
            """
            This function is to return the nodes reachable from this node, the costs and
            some related information.
            
            This function must be implemented by a subclass.
            """
            assert False
        
    
    class NodeInfo(object):
        """
        This helper class stores the information known about the minimum-cost
        routes to a given node. This information includes the minimum cost
        to reach this node and the previous steps that arrive at this node
        with the minimum cost.
        """
        __slots__ = ['minCost', 'previous']
        def __init__(self, minCost, previous = None):
            self.minCost = minCost
            self.previous = set()
            if previous: self.previous.add(previous)
        
    @staticmethod
    def perform(start):
        """
        This function performs the Dijkstra search from the node `start` to all
        other reachable nodes. This information is returned in a dictionary that
        maps a given node to a `NodeInfo` object that contains information about
        the minimum-cost route to reach that node.
        """
        queue = [(start.cost, start)]
        shortestPaths = dict()
        shortestPaths[start.location] = DijkstraSearch.NodeInfo(start.cost)
        # This algorithm works by iterating over a queue considering paths in
        # order of increasing cost. As a path is considered, every possible
        # single-step extension to this path is considered and added to the queue.
        # Eventually the queue empties when the only paths contained are more expensive
        # versions of paths that have already been considered.
        while queue:
            currentState = heappop(queue)[1]
            if not currentState.location in shortestPaths:
              shortestPaths[currentState.location] = DijkstraSearch.NodeInfo(currentState.cost)
            if shortestPaths[currentState.location].minCost == currentState.cost:
              if currentState.previous:
                shortestPaths[currentState.location].previous.add(currentState.previous)
              for nextState in currentState.next():
                  if nextState.location in shortestPaths and shortestPaths[nextState.location].minCost < nextState.cost:
                      continue
                  heappush(queue, (nextState.cost, nextState))
        return shortestPaths
    

