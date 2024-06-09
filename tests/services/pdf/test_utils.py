import pytest
from marshmallow.exceptions import ValidationError

from spynl.services.pdf.utils import (
    change_case,
    format_country,
    format_datetime,
    get_email_settings,
)


def test_incorrect_datetime():
    with pytest.raises(ValidationError):
        format_datetime('blah')


@pytest.mark.parametrize(
    'datestring,params,output',
    [
        ('2019-08-08T12:09:41.33', {'format': 'medium'}, 'Aug 8, 2019, 12:09:41 PM'),
        ('2019-08-08T12:09:41.33', {'format': 'short'}, '8/8/19, 12:09 PM'),
        (
            '2019-08-08T12:09:41.33',
            {'format': 'short', 'locale': 'de'},
            '08.08.19, 12:09',
        ),
        (
            '2019-08-08T12:09:41.33',
            {'format': 'short', 'locale': 'nl'},
            '08-08-2019 12:09',
        ),
        (
            '2019-08-08T12:09:41.33',
            {'format': 'short', 'locale': 'nl', 'tzinfo': 'Europe/Amsterdam'},
            '08-08-2019 14:09',
        ),
    ],
)
def test_correct_datetime(datestring, params, output):
    assert format_datetime(datestring, **params) == output


@pytest.mark.parametrize(
    'country,locale,output',
    [('NL', 'nl', 'Nederland'), ('NL', 'en', 'Netherlands'), ('bla', 'nl', 'bla')],
)
def test_format_country(country, locale, output):
    assert format_country(country, locale) == output


@pytest.mark.parametrize(
    'wholesale,sender,subject,output_subject',
    [
        (
            False,
            'noreply@uwkassabon.nl',
            'Your receipt is here',
            'Your receipt is here',
        ),
        (True, None, 'Your receipt is here', 'Your receipt is here'),
        (False, 'noreply@uwkassabon.nl', None, 'email-receipt-default-subject'),
        (True, None, None, 'email-receipt-default-subject-wholesale'),
    ],
)
def test_get_email_setting(wholesale, sender, subject, output_subject):
    user = {
        'settings': {
            'email': {
                'sender': '<aveen@maddoxx.nl>',
                'replyTo': 'aveen@maddoxx.nl',
                'body': 'Here is your receipt!',
                'subject': subject,
            }
        }
    }
    output = get_email_settings(user, wholesale)
    assert output == {
        'sender_name': '<aveen@maddoxx.nl>',
        'sender': sender,
        'reply_to': 'aveen@maddoxx.nl',
        'body': 'Here is your receipt!',
        'subject': output_subject,
    }


def test_change_case():
    test = "they're bill's friends from the UK"
    assert change_case(test) == "They're bill's friends from the UK"
    assert change_case(test, mode='title') == "They're Bill's Friends From The UK"
