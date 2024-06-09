"""Tests regarding datetime for spynl.main."""

from datetime import datetime
from json import loads

import pytest
import pytz

from spynl.main.dateutils import date_to_str, localize_date, now


def test_now():
    """Test now function, assuming the system defaults to UTC."""
    utc_now = datetime.utcnow()
    system_dt = now()
    assert system_dt.tzinfo.zone == 'UTC'
    assert utc_now.strftime('%Y-%m-%d %H:%M') == system_dt.strftime('%Y-%m-%d %H:%M')


def test_localize_date_to_str():
    """Test localize_date function."""
    dt = datetime(2014, 10, 3, 4, 15, 00)
    dt = localize_date(dt, tz='UTC')
    # this should be default in dateutils module
    assert date_to_str(dt) == '2014-10-03T04:15:00+0000'
    with pytest.raises(pytz.UnknownTimeZoneError):
        localize_date(dt, False, 'Europ/Amsterdam')
    l_dt = localize_date(dt, tz='Europe/Amsterdam')
    # 2 hours difference due to daylight savings time!
    assert date_to_str(l_dt) == '2014-10-03T06:15:00+0200'


def test_localize_date_with_now():
    """Change tz of result of now with localize_date."""
    system_dt = now()
    local_dt_utc = localize_date(system_dt, tz='UTC')
    assert system_dt.hour == local_dt_utc.hour
    local_dt_ams = localize_date(system_dt, tz='Europe/Amsterdam')
    assert system_dt.hour != local_dt_ams.hour
    assert local_dt_ams.tzinfo.zone == 'Europe/Amsterdam'


def test_get_time(app):
    """Test get time."""
    response = loads(app.get('/time').text)
    dt = datetime.now(tz=pytz.UTC).strftime('%Y-%m-%dT%H:%M')
    server_time = response['server_time']
    assert dt in server_time
