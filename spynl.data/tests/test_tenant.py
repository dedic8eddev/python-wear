import pytest
from marshmallow import ValidationError

from spynl_schemas.tenant import (
    Campaign,
    Counters,
    Loyalty,
    LoyaltyException,
    SalesSettings,
    Settings,
    generate_regions_fp_query,
)


@pytest.mark.parametrize(
    'field', ['invoice', 'salesOrder', 'packingList', 'posInstanceId']
)
def test_passing_lower_values_for_new_counters(field):
    """All new counters must have higher values than the current ones."""
    old_counters = {field: 2}
    schema = Counters(context=dict(old_counters=old_counters))
    with pytest.raises(ValidationError, match=field):
        schema.load({field: 1})


def test_load_by_roles():
    with pytest.raises(
        ValidationError, match='You do not have rights to edit this setting'
    ):
        SalesSettings(context={'user_roles': ['pos-device']}).load(
            {'orderTemplate': {}}
        )


def test_campaigns():
    with pytest.raises(ValidationError, match='Invalid date format'):
        Campaign().load({'startDate': '1234pp', 'endDate': '2021-12-7', 'factor': 1.2})

    with pytest.raises(ValidationError, match='All fields are required'):
        Campaign(partial=True).load({'endDate': '2021-12-7', 'factor': 1.2})

    with pytest.raises(LoyaltyException, match='Start date should be before end date'):
        Campaign(partial=True).load(
            {'startDate': '2021-12-12', 'endDate': '2021-12-7', 'factor': 1.2}
        )


def test_check_overlapping_campaigns():
    with pytest.raises(LoyaltyException, match='Campaign overlap'):
        Loyalty().load(
            {
                'campaigns': [
                    {'startDate': '2021-12-1', 'endDate': '2021-12-7', 'factor': 1.2},
                    {'startDate': '2021-12-8', 'endDate': '2021-12-12', 'factor': 1.3},
                    {'startDate': '2021-12-10', 'endDate': '2021-12-14', 'factor': 1.4},
                ]
            }
        )


def test_loyalty_fp_queries():
    data = Loyalty.generate_fpqueries(
        {
            'pointValue': 9.95,
            'suppressPointsOnDiscount': True,
            'campaigns': [
                {
                    'factor': 1.4,
                    'startDate': '2016-12-1',
                    'endDate': '2016-12-14',
                },
                {
                    'factor': 1.5,
                    'startDate': '2017-12-12',
                    'endDate': '2017-12-16',
                },
            ],
            'cashback': {'validity': 2},
        }
    )
    assert data == [
        ('setLoyaltyPointValue', 'setLoyaltyPointValue/setting__pointValue/value__995'),
        ('setLoyaltynoPointsonDiscount', 'setLoyaltynoPointsonDiscount/value__true'),
        (
            'setLoyaltyCampaigns',
            'setLoyaltyCampaigns/startdate__2016121/enddate__20161214/factor__140/'
            'startdate__20171212/enddate__20171216/factor__150',
        ),
        ('setsetting', 'setsetting/key__InKadobonAge/value__2/type__N'),
    ]


def test_generate_regions_fp_query():
    expected = [('setsetting', 'setsetting/key__gcRayons/value__NL%2CBE%2CDE/type__M')]
    assert expected == generate_regions_fp_query(['NL', 'BE', 'DE'])


def test_sensitive_settings_get_obfuscated():
    data = Settings().dump(
        {
            'payNLToken': '1234567',
            'sendcloudApiToken': 'abcdef',
            'sendcloudApiSecret': 'abc123',
        }
    )
    expected = {
        'payNLToken': '****567',
        'sendcloudApiToken': '***def',
        'sendcloudApiSecret': '***123',
    }
    for key, value in expected.items():
        assert data[key] == value
