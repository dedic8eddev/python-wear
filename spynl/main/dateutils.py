"""
Functions for handling dates and times.
"""

from datetime import datetime

import dateutil.parser  # pylint: disable=E0611
from pytz import timezone, utc

from spynl.main.utils import get_request, get_user_info

SPYNL_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S%z'


def now(tz=None):
    """Current time, with timezone localised."""
    return localize_date(datetime.utcnow(), tz=tz)


def date_format_str():
    """Get the date format from the .ini file, or set default."""
    return SPYNL_DATE_FORMAT


def date_to_str(when):
    """Convert date to string according to settings format"""
    return when.strftime(date_format_str())


def date_from_str(dstr):
    """
    Parses a string to a date/time and adds current timezone if no timezone
    information is present.
    """
    # slightly slower than datetime.strptime
    # but can handle different inputs
    _when = dateutil.parser.parse(dstr)  # pylint: disable=no-member
    if not _when.tzinfo:  # pylint: disable=E1103
        _when = utc.localize(_when)
    return _when


def localize_date(when, user_specific=True, tz=None):
    """
    Localises datetime objects to a time zone.
    If no time zone is explicitly given and also no time zone is found
    in or to be used from the user information, then system timezone is used.
    If 'when', the datetime object, has itself has no timezone info,
    then we assume it represents UTC time.
    """
    if not tz:
        tz = 'UTC'
        if user_specific:
            request = get_request()
            if request:  # e.g. in testing there might be no request
                user_info = get_user_info(request)
                if user_info.get('tz'):
                    tz = user_info.get('tz')
    if not when.tzinfo:
        when = when.replace(tzinfo=utc)
    return when.astimezone(timezone(tz))
