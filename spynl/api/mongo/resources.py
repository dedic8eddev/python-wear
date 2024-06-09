"""
The MongoResource class, a resource class for MongoDB-backed resources
"""

from bson import ObjectId

from spynl.main.routing import Resource


class MongoResource(Resource):
    """
    This is mostly used as base class for specific MongoDB-backed
    resources. It has no paths, since a resource without ACLs cannot be accessed
    with roles.
    """

    paths = []

    def __init__(self, request=None):
        """
        We try finding out which path is being used in this request
        in a generic way.
        """
        if request:
            req_path_elements = request.path_info.split('/')
            for path in self.paths:
                if path in req_path_elements:
                    self.used_path = path
                    break

    @property
    def collection(self):
        """
        Return the DB collection goverened by this resource.
        Subclasses are encouraged to overwrite this or
        use a class name that refers to the collection.
        """
        if hasattr(self, 'used_path'):
            return self.used_path
        else:
            return self.__class__.__name__.lower()

    # ID Class which can be initialised with a value
    # more than one can  be given, to provide fallbacks
    id_class = [ObjectId, str]

    # By default, a collection does not contain public documents (this is only used by
    # extend_filter_by_tenant_id and can be removed when that is removed):
    contains_public_documents = False

    # By default, a collection is not a large collection, but it can
    # be set to True by a subclass, to trigger special handling
    is_large_collection = False
