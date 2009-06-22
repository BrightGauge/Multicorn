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
# along with Koral library.  If not, see <http://www.gnu.org/licenses/>.

from kalamar.storage.base import AccessPoint
from kalamar import utils
from kalamar import Item
from array import array

def _opener(content):
    def opener():
        return StringIO(content)
    return opener

class DBAPIStorage(AccessPoint):
    """Base class for SQL SGBD Storage.
    
    Descendant class must override ``get_connection'' and ``_get_primary_keys''.
    
    """
    
    protocol = None
    
    # Provided to ensure compatibility with as many SGDB as possible.
    # May be modified by a descendant.
    operators = {
        '=':   '=',
        '!=':  '!=',
        '>':   '>',
        '>=':  '>=',
        '<':   '<',
        '<=':  '<=',
        }
    
    def __init__(self, **config):
        super(DBAPIStorage, self).__init__(**config)
        self._operatorsfrom_function = dict([(b,a) for (a,b)
                                            in utils.operator.items()])
    
    def get_connection():
        """Return a DB-API connection object and the table name in a tuple.
        
        This method must be overriden.
        This method can use config['url'] to connect and may keep connection in
        cache for later calls.
        
        """
        raise NotImplementedError('Abstract method')
    
    def get_storage_properties(self):
        cur = self._connection.cursor()
        cur.execute('select * from %s where 0'%self._table)
        return [prop[0] for prop in cur.description]
    
    def _storage_search(self, conditions):
        """Return a list of items matching the ``conditions''.
        
        ``conditions'' must be a list of tuples (name, function, value), where
        function is in kalamar.utils.operators' values.
        
        """
        
        connection, table = self.get_connection()
        
        request = "SELECT * FROM "+table+" WHERE "
        parameters = []
        remaining_conditions = []
        for cond in conditions[-1]:
            oper = self.operators_from_function[cond[1]]
            try:
                oper = self.operators[oper]
                request += cond[0] + "=? AND "
                parameters.append(cond[2])
            except KeyError:
                remaining_conditions.append(cond)
                
        oper = self.operators_from_function[conditions[-1][1]]
        try:
            oper = self.operators[oper]
            request += conditions[-1][0] + "=?;"
            parameters.append(conditions[-1][2])
        except KeyError:
            remaining_conditions.append(conditions[-1])
        
        request, parameters = self._format_request(request, parameters)
        
        cur = connection.cursor()
        cur.execute(request, parameters)
        
        res = cur.fetchmany()
        items_ok = []
        while res:
            for line in res:
                ok = True
                line = dict(zip(cur.description,line))
                for name, funct, value in remaining_conditions:
                    if not funct(line[name],value):
                        ok = False
                        break
                if ok:
                    opener = _opener(line[self.config["content_column"]])
                    items_ok.append(Item.get_item_parser(format,opener,line))
            res = cur.fetchmany()
        
        cur.close()
        return items_ok
            
    def save(self, item):
        connection, table = self.get_connection()
        req = array('u',u'UPDATE %s SET '%table)
        pk = self._get_primary_keys()
        keys = item.properties.storage_properties.keys()
        
        item.properties[self.config['content_column']] = item.serialize()
        # There is no field '_content' in the DB.
        del item.properties['_content']
        
        for key in keys[:-1]:
            req.extend(u'%s = %s , ' % (key, item.properties[key]))
        req.extend(u'%s = %s WHERE' % (keys[-1], item.properties[keys[-1]]))
        
        for key in pk[-1]:
            req.extend(u' %s = %s' % (key, item.properties[key]))
        req.extend(u' %s = %s;' % (pk[-1], item.properties[pk[-1]]))
        
        cursor = connection.cursor()
        cursor.execute(req)
        n = cursor.rowcount()
        if n == 0:
            # item does not exist. Let's do an insert.
            req = array('u', u'INSERT INTO %s ( ' % table)
            for key in keys[:-1]:
                req.extend('%s , ' % key)
            req.extend('%s ) VALUES ( ' % keys[-1])
            
            for key in keys[:-1]:
                req.extend('%s , ' % item.properties[key])
            req.extend('%s );' % item.properties[key[-1]])
            
            cursor.execute(req)
        elif n > 1:
            # problem ocurred
            connection.rollback()
            cursor.close()
            raise ManyItemsUpdatedError()
        # everythings fine
        cursor.commit()
        cursor.close()
    
    class ManyItemsUpdatedError(Exception): pass

    def remove(self, item):
        connection, table = self.get_connection()
        req = array('u', 'REMOVE FROM %s WHERE ' % table)
        pk = self._get_primary_keys()
        for key in pk[:-1]:
            req.extend('%s = %s AND ' % (key, item.properties[key]))
        req.extend('%s = %s ;' % (pk[-1], item.properties[pk[-1]]))
        
        cursor = connection.cursor()
        cursor.execute(req)
    
    def _format_request(self, request, parameters=tuple()):
        """Return a tuple (formated_request, typed_parameters).
        
        ``request'' must be in the DB-API's 'qmark' style.
        ``parameters'' must be a sequence of strings.
        
        The returned ``formated_request'' is in the DB-API 2 style given by
        paramstyle (see DB-API spec.).
        The returned ``typed_parameters'' is a list or a dictionnary.
        
        """
        connection, table = self.get_connection()
        style = connection.paramstyle
        if style == 'qmark':
            # ... where a=? and b=?
            pass # Nothing to do :-)
        
        elif style =='numeric':
            # ... where a=:1 and b=:2
            def new_request_parts(parts):
                yield parts[0]
                for i,part in enumerate(parts[1:]):
                    yield ':' + str(i+1) + part
                    
            parts = request.split('?')
            request = ''.join(new_request_parts(parts))
            
        elif style == 'named':
            # ... where a=:name0 and b=:name1
            def new_request_parts(parts):
                yield parts[0]
                for i,part in enumerate(parts[1:]):
                    yield ':name' + str(i) + part
                    
            parts = request.split('?')
            request = ''.join(new_request_parts(parts))
            parameters = dict([("name"+str(i), value)
                                for i,value in enumerate(parameters)])
            
        elif style == 'format':
            # ... where a=%s and b=%d
            raise NotImplementedError # TODO
            
        elif style == 'pyformat':
            # ... where name=%(name)s
            raise NotImplementedError # TODO
        else:
            UnsupportedParameterStyleError(style)
            
        
        return (request, parameters)
        
    class UnsupportedParameterStyleError(Exception): pass
    
    def _get_primary_keys(self):
        """Return a list of primary keys names."""
        raise NotImplementedError('Abstract method')
