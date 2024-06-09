import pytest
from marshmallow import Schema, ValidationError, fields

from spynl_schemas.shared_schemas import Address, Contact
from spynl_schemas.utils import (
    bleach_html,
    contains_one_primary,
    get_card_provider,
    lookup,
    obfuscate,
    split_address,
    validate_unique_list,
)


@pytest.mark.parametrize(
    'setting,num,result',
    [
        ('123456', None, '***456'),
        ('12345', None, '**345'),
        ('123', None, '***'),
        ('12', None, '***'),
        ('123456', 2, '****56'),
        ('123456', 0, '******'),
    ],
)
def test_obfuscate(setting, num, result):
    if num is not None:
        assert obfuscate(setting, num) == result
    else:
        assert obfuscate(setting) == result


class ExamplePrimary(Schema):
    contacts = fields.Nested(
        Contact, only=['primary'], many=True, validate=contains_one_primary
    )
    addresses = fields.Nested(
        Address, only=['primary'], many=True, validate=contains_one_primary
    )


def test_validate_unique_list():
    """test that an error gets raised"""
    try:
        validate_unique_list(['a', 'b'])
    except ValidationError as e:
        pytest.fail(str(e))

    with pytest.raises(ValidationError):
        validate_unique_list(['a', 'b', 'a'])


def test_validate_contains_one_primary_address():
    """
    test that you get an error when you provide more than one primary address
    """
    addresses = [{'zipcode': '', 'primary': True}, {'primary': True, 'zipcode': ''}]
    with pytest.raises(ValidationError):
        ExamplePrimary().load({'addresses': addresses})


def test_validate_contains_one_primary_contact():
    """
    test that you get an error when you provide more than one primary contact
    """
    contacts = [{'zipcode': '', 'primary': True}, {'primary': True, 'zipcode': ''}]
    with pytest.raises(ValidationError):
        ExamplePrimary().load({'contacts': contacts})


def test_validate_contains_one_primary_no_error():
    """
    test that you get no errors when providing only one primary
    """
    contacts = [{'primary': True}, {'primary': False}]
    addresses = [{'primary': True}, {'primary': False}]
    ExamplePrimary().load({'contacts': contacts, 'addresses': addresses})


@pytest.mark.parametrize(
    'input,expected',
    [
        ('A. Beestraat 40', {'street': 'A. Beestraat', 'houseno': '40'}),
        ('A. Béé 40B', {'street': 'A. Béé', 'houseno': '40', 'houseadd': 'B'}),
        ('A. Bee 40 B', {'street': 'A. Bee', 'houseno': '40', 'houseadd': 'B'}),
        ('1e Beestraat 40', {'street': '1e Beestraat', 'houseno': '40'}),
        ('1e Béé 40B', {'street': '1e Béé', 'houseno': '40', 'houseadd': 'B'}),
        ('1e Bee 40 B', {'street': '1e Bee', 'houseno': '40', 'houseadd': 'B'}),
        ('A. Bee 40 boven', {'street': 'A. Bee', 'houseno': '40', 'houseadd': 'boven'}),
        ('A. Bee 40-42', {'street': 'A. Bee', 'houseno': '40', 'houseadd': '-42'}),
        # Either the commented out will fail, or the one below.
        # ('A. Bee 40 42', {'street': 'A. Bee', 'houseno': '40', 'houseadd': '42'}),
        ('Plein 1945 1', {'street': 'Plein 1945', 'houseno': '1'}),
    ],
)
def test_split_up_address(input, expected):
    assert split_address(input) == expected


def test_split_up_address_raise():
    with pytest.raises(ValidationError):
        split_address('1straat straat straat.')


def test_bleach_html_allowed():
    """Test html bleaching"""
    html = (
        '<img alt="Softwear" height="71" '
        'src="https://s3-eu-west-1.amazonaws.com/softwear-static-assets/'
        'SoftwearLogo.png"'
        ' style="border-style: none;" width="256"><br>'
        '<span class="rangySelectionBoundary"></span>'
        '<span class="someClassWeMightNotWant"></span>'
    )
    # bleach changes the order of the attributes, but it seems it add them in
    # alphabetical order. If this test ever fails, it could be that the order of
    # the attributes changed. (so the html above was constructed to be unchanged)
    bleached = bleach_html(html)
    assert html == bleached


def test_bleach_html_forbidden():
    """Test html bleaching"""
    html = (
        '<img alt="Softwear" height="71" '
        'src="https://s3-eu-west-1.amazonaws.com/softwear-static-assets/'
        'SoftwearLogo.png" style="border-style: none;" width="256"><table></table>'
        '<script>alert()</script>'
    )
    # bleach changes the order of the attributes, but it seems it add them in
    # alphabetical order. If this test ever fails, it could be that the order of
    # the attributes changed. (so the html above was constructed to be unchanged)
    bleached = bleach_html(html)
    assert '<script>' not in bleached


@pytest.mark.parametrize(
    'category,card_types',
    [
        ('maestro', ['Maestro', 'MAESTRO']),
        ('vpay', ['V PAY', 'VISA_VPAY', 'V PAY VISA']),
        ('mastercardcredit', ['MASTERCARD', 'MasterCard']),
        (
            'mastercarddebit',
            ['Debit MasterCard', 'DEBIT Mastercard', 'MasterCard Debit'],
        ),
        ('visacredit', ['VISA CREDIT', 'Visa', 'VISA']),
        ('visadebit', ['VISA DEBIT', 'Visa Debit', 'VISADEBIT']),
        ('amex', ['AMERICAN EXPRESS', 'AMEX', 'Amex']),
        ('othereft', ['BARCLAYCARD', 'DEBIT']),
    ],
)
def test_get_card_provider(category, card_types):
    for card_type in card_types:
        assert get_card_provider(card_type) == category


@pytest.mark.parametrize(
    'dictionary,key,default,result',
    [
        ({'foo': {'bar': {'foobar': '!'}, 'bar2': 'not'}}, 'foo.bar.foobar', None, '!'),
        (
            {'foo': {'bar': {'foobar': '!'}, 'bar2': 'not'}},
            'foo.bar.foobar2',
            None,
            None,
        ),
        (
            {'foo': {'bar': {'foobar': '!'}, 'bar2': 'not'}},
            'foo.bar.foobar2',
            'default',
            'default',
        ),
    ],
)
def test_lookup(dictionary, key, default, result):
    assert lookup(dictionary, key, default) == result
