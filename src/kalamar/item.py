# -*- coding: utf-8 -*-
# This file is part of Dyko
# Copyright © 2008-2009 Kozea
#
# This library is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Kalamar library.  If not, see <http://www.gnu.org/licenses/>.

"""This module contains base classes to make kalamar items.

You probably want to use the Item.get_item_parser method to get the parser
you need.
You may also want to inherit from one of the followings so you can write your
own parsers :
 - CapsuleItem
 - AtomItem

Any item parser class has to have a static attribute "format" set to the
format parsed. Else this class will be hidden to get_item_parser.

A parser class must implement the following methods :
 - _custom_parse_data(self)
 - _serialize(self, properties)

and have a class attribute ``format'' which is name of the parsed format.

"""

from kalamar import utils
from copy import deepcopy

class Item(object):
    """The base of any item parser. This is an abstract class.
    
    You can use the Item.get_item_parser static method to get automatically the
    parser you want.
    Useful attributes :
     - properties : acts like a defaultdict. The keys are strings and the values
       are lists of python objects. Default value is [].
     - _access_point : where, in kalamar, is stored the item. It is an instance
       of AccessPoint.

    """
    # This class is abstract and used by AtomItem and CapsuleItem, which are
    #inherited by the parsers.
    
    format = None

    def __init__(self, access_point, opener, accessor_properties={}):
        """Return an instance of Item
        
        Parameters :
        - access_point : an instance of the AccessPoint class.
        - opener : a function taking no parameters and returning file-like
          object.
        - accessor_properties : properties generated by the accessor for this
          item.
        
        """
        self._opener = opener
        self._stream = None
        self.properties = ItemProperties(self, accessor_properties)
        self._access_point = access_point
        self.aliases = self._access_point.parser_aliases
        self.aliases_rev = dict((b,a) for (a,b) in enumerate(self.aliases))
    
    @staticmethod
    def get_item_parser(format, *args, **kwargs):
        """Return an appropriate parser instance for the given format.
        
        Your kalamar distribution should have, at least, a paser for the "binary
        format.
        
        >>> from _test.corks import CorkAccessPoint, cork_opener
        >>> ap = CorkAccessPoint()
        >>> Item.get_item_parser("binary", ap, cork_opener, {"artist" : "muse"})
        ...  # doctest:+ELLIPSIS
        <kalamar.parser.binaryitem.BinaryItem object at ...>
        
        An invalid format will raise a ValueError
        >>> Item.get_item_parser("I do not exist", ap, cork_opener)
        Traceback (most recent call last):
        ...
        ValueError: Unknown format: I do not exist
        
        """
        import kalamar.parser
        for subclass in utils.recursive_subclasses(Item):
            if getattr(subclass, 'format', None) == format:
                return subclass(*args, **kwargs)
        
        raise ValueError('Unknown format: ' + format)
    
    # TODO: TO BE DELETED ??????????
    # NO !! Items need to override operators functions
    # See vorbis item for example : comments can be lists.
    #
    #def matches(self, prop_name, operator, value):
    #    """Return boolean
    #
    #    Check if the item's property <prop_name> matches <value> for the given
    #    operator.
    #
    #    Availables operators are (see kalamar doc for further info) :
    #    - "=" -> equal
    #    - "!=" -> different
    #    - ">" -> greater than (alphabetically)
    #    - "<" -> lower than (alphabetically)
    #    - ">=" -> greater or equal (alphabetically)
    #    - "<=" -> lower or equal (alphabetically)
    #    - "~=" -> matches the given regexp
    #    - "~!=" -> does not match the given regexp
    #        availables regexp are python's re module's regexp
    #    
    #    >>> from _test.corks import CorkAccessPoint, cork_opener
    #    >>> ap = CorkAccessPoint()
    #    >>> item = Item(ap, cork_opener, {"toto" : "ToTo"})
    #    
    #    Example :
    #    >>> item.matches("toto", "~=", "[a-zA-Z]*")
    #    True
    #    >>> item.matches("toto", "#", "")
    #    Traceback (most recent call last):
    #    ...
    #    OperatorNotAvailable: #
    #
    #    Some descendants of Item class may overload _convert_value_type to get
    #    the "greater than/lower than" operators working with a numerical
    #    order (for instance).
    #
    #    """
    #
    #    prop_val = self.properties[prop_name]
    #    value = self._convert_value_type(prop_name, value)
    #    
    #    try:
    #        return utils.operators[operator](prop_val, value)
    #    except KeyError:
    #        raise kalamar.OperatorNotAvailable(operator)

    def serialize(self):
        """Return the item serialized into a string"""
        # Remove aliases
        props = dict((self.aliases.get(key,key), self.properties[key])
                     for key in self.properties.keys())
        return _serialize(self, props)
    
    def _serialize(self, properties):
        """Called by ``self.serialize''. Must return a data string"""
        raise NotImplementedError("Abstract class")
    
    # TODO: TO BE DELETED ??????????
    #def _convert_value_type(self, prop_name, value):
    #    """Do nothing by default"""
    #    return value

    @property
    def encoding(self):
        """Return a string

        Return the item's encoding, based on what the parser can know from
        the items's data or, if unable to do so, on what is specified in the
        access_point.

        """
        return access_point.default_encoding

    def _custom_parse_data(self):
        """Parse properties from data, return a dictionnary.
        
        ***This method have to be overriden***
        This method must not worry about aliases.
        This method must not modify ``self.properties''. It just returns a dict.

        """
        raise NotImplementedError("Abstract method")
    
    def _parse_data(self):
        """Call ``_custom_parse_data'' and do some stuff to the result."""
        self._open()
        props = self._custom_parse_data()
        self.properties.update(props)

    def _open(self):
        """Open the stream when called for the first time.
        
        >>> from _test.corks import CorkAccessPoint, cork_opener
        >>> ap = CorkAccessPoint()
        >>> item = Item(ap, cork_opener, {"toto" : "ToTo"})
        
        >>> item._stream
        >>> item._open()
        >>> stream = item._stream
        >>> print stream  # doctest:+ELLIPSIS
        <open file '...kalamar/_test/toto', mode 'r' at ...>
        >>> item._open()
        >>> stream is item._stream
        True
        
        """
        if self._stream is None:
            self._stream = self._opener()

class AtomItem(Item):
    """An indivisible block of data
    
    This is an abstract class.
    
    """

    def read(self):
        """Alias for properties["_content"]"""
        return self.properties["_content"]

    def write(self, value):
        """Alias for properties["_content"] = value"""
        self.properties["_content"] = value

class CapsuleItem(Item, list):
    """An ordered list of Items (atoms or capsules)

    A capsule is a multiparts item.
    This is an abstract class.

    """
    pass

class ItemProperties(dict):
    """Acts like a defaultdict. Used as a properties storage.

    You have to give a reference to the item to the constructor.
    You can force some properties to a value using the ``storage_properties''
    argument.
    
    This is for testing
    >>> from _test.corks import CorkItem
    >>> item = CorkItem({"a" : "A", "b" : "B"})
    >>> prop = item.properties
    
    ItemProperties works as a dictionnary :
    >>> prop["cork_prop"]
    'I am a cork prop'
    
    This key has been forced
    >>> prop["b"]
    'B'
    
    Storage properties can be accessed separately by a dictionnary
    >>> prop.storage_properties
    {'a': 'A', 'b': 'B'}
    
    If a storage property has been changed, the old value is still reachable
    >>> prop['b'] = 'toto'
    >>> prop.storage_properties_old
    {'a': 'A', 'b': 'B'}
    
    But the original value is not changed
    >>> super(ItemProperties, prop).__getitem__("b")
    "item's b"
    
    Return None if the key does not exist
    >>> prop["I do not exist"]
    
    CorkItem has an alias "I am aliased" -> "I am not aliased"
    >>> prop["I am aliased"]
    'value of: I am not aliased'
    >>> prop["I am not aliased"]
    'value of: I am not aliased'

    """
    
    def __init__(self, item, storage_properties={}):
        self._item = item
        self.storage_properties = storage_properties
        self.storage_properties_old = deepcopy(storage_properties)
        self._loaded = False

    def __getitem__(self, key):
        if not self._loaded:
            self._item._parse_data()
            self._loaded = True
        # aliasing
        key = self._item.aliases.get(key,key)
        try:
            res = self.storage_properties[key]
        except KeyError:
            try:
                res = super(ItemProperties, self).__getitem__(key)
            except KeyError:
                res = None
        return res
    
    def __setitem__(self, key, value):
        # aliasing
        key = self._item.aliases.get(key,key)
        try:
            self.storage_properties[key] = value
        except KeyError:
            super(ItemProperties, self).__setitem__(key, value)
