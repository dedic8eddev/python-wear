"""
Functions to (de)serialise objects.
"""

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import date_format_str, date_from_str, localize_date
from spynl.main.serial import MalformedRequestException
from spynl.main.utils import parse_value


def decode_id(dic, fieldname, context):
    """
    Decode an incoming id field.
    If the value itself is a dict, it could contain $in or $nin as
    keys, and these keys contain a list of ID's that should
    be parsed correctly. eg:
    {'_uuid': {'$in': [uuid1, uuid2], '$nin': [uuid3]}}
    """
    id_classes = [str]
    if hasattr(context, 'id_class'):
        id_classes = context.id_class
    if isinstance(dic[fieldname], dict):
        for okey in ('$in', '$nin'):
            if okey in dic[fieldname]:
                if isinstance(dic[fieldname][okey], list):
                    dic[fieldname][okey] = [
                        parse_value(anid, id_classes) for anid in dic[fieldname][okey]
                    ]
                else:
                    raise MalformedRequestException(
                        _(
                            'malformed-field-not-list',
                            mapping={'fieldname': fieldname, 'okey': okey},
                        )
                    )
    elif isinstance(dic[fieldname], str):
        dic[fieldname] = parse_value(dic.get(fieldname), id_classes)
    elif dic[fieldname] is None or dic[fieldname] == 0:
        pass  # FIXME: This is here so aggregation queries can remove _id field
        # from grouping. Remove when all agg pipelines are built in Spynl
    else:
        raise MalformedRequestException(
            _('malformed-field-not-string-or-dict', mapping={'fieldname': fieldname})
        )


def decode_date(dic, fieldname, context):
    """
    Decode dates so we either do nothing (date starts with $, MongoDB will
    handle this), or localize the date to UTC, so all dates in the database
    are UTC. We also make sure that dates from queries are properly localized.
    """
    try:
        if isinstance(dic[fieldname], dict):
            # In queries, dates are mostly used with operators
            # ({operator: thedate}). Deal with only the ones expected
            # to be used with dates (e.g. $exists is not expected)
            date_ops = ('$gt', '$gte', '$lt', '$lte')
            for operator in [op for op in dic[fieldname] if op in date_ops]:
                dic[fieldname][operator] = parse_date(dic[fieldname][operator])
        elif dic[fieldname] not in (-1, 0, 1):  # e.g. sort directions
            dic[fieldname] = parse_date(dic[fieldname])
    except Exception:
        raise ValueError(
            _(
                'decode-date-value-error',
                mapping={
                    'value': dic[fieldname],
                    'key': fieldname,
                    'date_fmt': date_format_str(),
                },
            )
        )


def parse_date(dstr):
    """Parse a date into a DateTime object."""
    if dstr.startswith('$'):  # let MongoDB handle this
        return dstr
    return localize_date(date_from_str(dstr), tz='UTC')
