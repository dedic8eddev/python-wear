"""This module contains all the functions that try to protect Mongo queries."""


from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


def reject_excluded_operators(query):
    """Exclude certain operators from queries."""
    for eo in ('$where',):
        if isinstance(query, dict) and eo in query:
            raise SpynlException(
                _('excluded-mongodb-operator', mapping={'operator': eo})
            )
