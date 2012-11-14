import sys
import logging
from ..lib.mapping import Mapping
from ..lib.filters import FilterSet
from httplib import HTTPException

from ..lib.connection import EmptyResponseWarning

log = logging.getLogger("bc_aapi")


class ResourceAccessor(object):
    """
    Provides methods that will create, get, and enumerate resourcesObjects.
    """
    
    def __init__(self, resource_name, connection):
        """
        Constructor
        
        @param resource_name: The name of the resource being accessed.  There must be a
                              corresponding ResourceObject class
        @type resource_name: String
        @param connection: Connection to the bigCommerce REST API
        @type connection: {Connection}
        """
        self._parent = None
        self.__resource_name = resource_name
        self._connection = connection
        
        mod = __import__('%s' % resource_name, globals(), locals(), [resource_name], -1)
        self._klass = getattr(mod, resource_name)
            
        # Work around for option values URL being incorrect
        if resource_name == "OptionValues":
            self._url = "/options/values"
        else:
            self._url = self._connection.get_resource_url(self.__resource_name.lower())
            
         
    def __get_page(self, page, limit, query={}):
        """
        Get specific pages
        """
        _query = {"page": page,
                  "limit": limit}
        _query.update(query)
        return self._connection.get(self._url, _query)
    
    
    def enumerate(self, start=0, limit=0, query={}, max_per_page=50):
        """
        Enumerate resources
        
        @param start: The instance to start on
        @type pages: int
        @param limit: The number of items to return, Set to 0 to return all items
        @type start_page: int
        @param query: Search criteria
        @type query: FilterSet
        @param max_per_page: Number of items to return per request
        @type max_per_page: int
        """
        _query = {}
        if query:
            _query = query.query_dict()
        
            
        requested_items = limit if limit else sys.maxint
        max_per_page = min(max_per_page, 250)
        max_per_page = min(requested_items, max_per_page)
        
        current_page = int( start / max_per_page )
        offset = start % max_per_page
         
        #while current_page < total_pages and requested_items:
        while requested_items:
            current_page += 1
            page_index = 0
            
            try:
                for res in self.__get_page(current_page, max_per_page, _query):
                    if offset <= page_index:
                        offset = 0  # Start on the first item for the next page
                        if not requested_items:
                            break
                        else:
                            requested_items -= 1
                            page_index += 1
                            yield self._klass(self._connection, self._url, res, self._parent)
                    else:
                        page_index += 1
            # If the response was empty - we are done
            except(EmptyResponseWarning):
                requested_items = 0
            except:
                raise
                    


    def get(self, id):
        url = "%s/%s" % (self._url, id)
        try:
            result = self._connection.get(url)
            return self._klass(self._connection, self._url, result, self._parent)
        except:
            return None
    
    
    def get_count(self, query={}):
        if query:
            _query = query.query_dict()
        result = self._connection.get("%s/%s" % (self._url, "count"), query)
        return result.get("count")
    
    def filters(self):
        try:
            return self._klass.filter_set()
        except:
            return FilterSet()
    
    
    
class SubResourceAccessor(ResourceAccessor):
    
    def __init__(self, klass, url, connection, parent):
        """
        """
        self._parent = parent
        self._connection = connection
        self._klass = klass
        self._url = url if isinstance(url, basestring) else url["resource"]
        
    

class ResourceObject(object):
    writeable = [] # list of properties that are writeable
    read_only = [] # list of properties that are read_only
    sub_resources = {}  # list of properties that are subresources
    
    
    def __init__(self, connection, url, fields, parent):
        self._parent = parent
        self._connection = connection
        self._fields = fields or dict()
        self._url = "%s/%s" % (url, self.id)
        self.updates = {} # the fields to update
        
    def __getattr__(self, attrname):
        
        data = self._fields.get(attrname,None)
        if data is None:
            raise AttributeError
        else:
            
            # if we are dealing with a sub resource and we have not cast it to a list
            if self.sub_resources.has_key(attrname) and isinstance(data, dict):
                
                _con = SubResourceAccessor(self.sub_resources[attrname].get("klass", ResourceObject), 
                                           data, self._connection, 
                                           self)
                
                if not self.sub_resources[attrname].get("single", False):
                    _list = []
                    for sub_res in _con.enumerate():
                        _list.append(sub_res)
                    self._fields[attrname] = _list
                    
                else:
                    self._fields[attrname] = _con.get("")
                    
            # Cast all dicts to Mappings - for . access
            elif isinstance(data, dict):
                val = Mapping(data)
                self._fields[attrname] = val
                
            return self._fields[attrname]
            
        raise AttributeError
    
    def attr(self, name, value):
        self.updates.update({name:value})

        
    def get_url(self):
        return self._url
    
    def create(self, data):
        log.info("Creating %s" % self.get_url())
        
    # HACK JOB
    def save(self):
        log.info("Updating %s" % self.get_url())
        log.info("Data: %s" % self.updates)
        self._connection.update(self.get_url(), self.updates)
                 
        
    def __repr__(self):
        return str(self._fields)
    
    def to_dict(self):
        return self._fields
    
