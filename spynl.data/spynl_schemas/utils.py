import logging
import re

import bleach
from marshmallow import ValidationError, validate

BAD_CHOICE_MSG = 'Must be one of {choices}, got {input}.'


def obfuscate(setting, num=3):
    """
    Obfuscate a string by replacing every character with a * apart from the last num
    characters.
    """
    if not num:
        return '*' * len(setting)
    if len(setting) <= num:
        return '*' * num
    return '{}{}'.format('*' * (len(setting) - num), setting[-num:])


def cast_percentage(val):
    return int(round(val * 100, 2))


def validate_unique_list(value):
    """validate that the list provided is unique"""
    if len(set(value)) != len(value):
        raise ValidationError('All items should be unique')


def validate_warehouse_id(value):
    """validate the id of a warehouse/shop/location"""
    try:
        id = int(value)
    except ValueError:
        raise ValidationError('Must be numerical.')
    validate.Range(min=33, max=254)(id)


def contains_one_primary(value):
    """
    Validate that a list of contacts or addresses contains one primary
    contact or address if the list is not empty.
    """
    if value and sum(1 for item in value if item['primary']) != 1:
        raise ValidationError('You can only have one primary contact or address.')


def get_address(addresses, type_=None):
    """
    Get the first address in the list of type type_. If type_ is None or the address is
    not found, return the primary address.
    To be able to deal with addresses without primary (old addresses), it returns the
    first item in the list if no primary is found.
    """
    if not addresses or not isinstance(addresses, list):
        return {}
    if type_:
        for address in addresses:
            if address.get('type') == type_:
                return address
    for address in addresses:
        if address.get('primary'):
            return address
    return addresses[0]


def split_address(address):
    """function for splitting addresses into street + houseno + houseadd"""
    # problems for 55-57 -57 can be the addition, or it can be two addresses. We can
    # probably safely put -57 in the addition in both cases.
    m = re.match(r'(.+) (\d+)(.*)', address)
    try:
        address = {'street': m[1].strip(), 'houseno': m[2].strip()}
    except (KeyError, TypeError):
        raise ValidationError('Invalid address')
    if m[3]:
        address['houseadd'] = m[3].strip()
    return address


def lookup(dictionary, key, default=None):
    """lookup a value in a dictionary using dot notation"""
    if '.' not in key:
        return dictionary.get(key, default)
    head, tail = key.split('.', 1)
    inner_object = dictionary.get(head)
    if inner_object is None:
        return default
    return lookup(inner_object, tail, default)


def bleach_html(html):
    """Sanitize html."""
    return bleach.clean(
        html,
        # (default ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code', 'em',
        #           'i', 'li', 'ol', 'strong', 'ul']
        tags=bleach.sanitizer.ALLOWED_TAGS
        + [
            'img',
            'br',
            'h1',
            'h2',
            'h3',
            'h4',
            'h5',
            'h6',
            'u',
            'strike',
            'pre',
            'p',
            'span',
            'div',
            'sup',
            'sub',
            'table',
        ],
        # (default: no styles)
        styles=bleach.sanitizer.ALLOWED_STYLES
        + [
            'color',
            'border-style',
            'width',
            'heigth',
            'display',
            'vertical-align',
            'horizontal-align',
            'margin-left',
            'margin-right',
            'margin-bottom',
            'margin-top',
            'border-left',
            'border-right',
            'border-bottom',
            'border-top',
            'padding-left',
            'padding-right',
            'padding-bottom',
            'padding-top',
            'text-align',
            'font-family',
            'font-size',
            'line-height',
            'border-collapse',
            'page-break-inside',
        ],
        # (default {u'a': [u'href', u'title'],
        #                  u'acronym': [u'title'],
        #                  u'abbr': [u'title']}
        attributes=dict(
            **bleach.sanitizer.ALLOWED_ATTRIBUTES,
            img=['style', 'width', 'height', 'src', 'alt'],
            span=['style', 'class'],
            p=['style', 'class'],
            div=['style', 'class'],
            table=['style', 'class']
        ),
    )


def get_card_provider(card_type):
    card_type = card_type.lower()

    def is_debit(card_type):
        return 'debit' in card_type or 'debet' in card_type

    def is_vpay(card_type):
        return re.search(r'v ?pay', card_type)

    # Note these names are used as keys for the foxpro event.
    patterns = [
        ('maestro', lambda c: 'maestro' in c),
        ('vpay', lambda c: is_vpay(c)),
        ('mastercarddebit', lambda c: 'masterc' in c and is_debit(c)),
        ('mastercardcredit', lambda c: 'masterc' in c and not is_debit(c)),
        ('visadebit', lambda c: 'visa' in c and not is_vpay(c) and is_debit(c)),
        ('visacredit', lambda c: 'visa' in c and not is_vpay(c) and not is_debit(c)),
        ('amex', lambda c: re.search(r'amex|american.?express', c)),
    ]
    matches = []
    for key, check in patterns:
        if check(card_type):
            matches.append(key)
    if not matches:
        return 'othereft'
    elif len(matches) > 1:
        logger = logging.getLogger('spynl.data')
        logger.warning(
            'Card type %s matches more than one card category: %s', card_type, matches
        )
    return matches[0]


# source http://geohack.net/gis/wikipedia-iso-country-codes.csv
COUNTRIES = {
    'AF': 'Afghanistan',
    'AX': 'Åland Islands',
    'AL': 'Albania',
    'DZ': 'Algeria',
    'AS': 'American Samoa',
    'AD': 'Andorra',
    'AO': 'Angola',
    'AI': 'Anguilla',
    'AQ': 'Antarctica',
    'AG': 'Antigua and Barbuda',
    'AR': 'Argentina',
    'AM': 'Armenia',
    'AW': 'Aruba',
    'AU': 'Australia',
    'AT': 'Austria',
    'AZ': 'Azerbaijan',
    'BS': 'Bahamas',
    'BH': 'Bahrain',
    'BD': 'Bangladesh',
    'BB': 'Barbados',
    'BY': 'Belarus',
    'BE': 'Belgium',
    'BZ': 'Belize',
    'BJ': 'Benin',
    'BM': 'Bermuda',
    'BT': 'Bhutan',
    'BO': 'Bolivia, Plurinational State of',
    'BA': 'Bosnia and Herzegovina',
    'BW': 'Botswana',
    'BV': 'Bouvet Island',
    'BR': 'Brazil',
    'IO': 'British Indian Ocean Territory',
    'BN': 'Brunei Darussalam',
    'BG': 'Bulgaria',
    'BF': 'Burkina Faso',
    'BI': 'Burundi',
    'KH': 'Cambodia',
    'CM': 'Cameroon',
    'CA': 'Canada',
    'CV': 'Cape Verde',
    'KY': 'Cayman Islands',
    'CF': 'Central African Republic',
    'TD': 'Chad',
    'CL': 'Chile',
    'CN': 'China',
    'CX': 'Christmas Island',
    'CC': 'Cocos (Keeling) Islands',
    'CO': 'Colombia',
    'KM': 'Comoros',
    'CG': 'Congo',
    'CD': 'Congo, the Democratic Republic of the',
    'CK': 'Cook Islands',
    'CR': 'Costa Rica',
    'CI': "Côte d'Ivoire",
    'HR': 'Croatia',
    'CU': 'Cuba',
    'CY': 'Cyprus',
    'CZ': 'Czech Republic',
    'DK': 'Denmark',
    'DJ': 'Djibouti',
    'DM': 'Dominica',
    'DO': 'Dominican Republic',
    'EC': 'Ecuador',
    'EG': 'Egypt',
    'SV': 'El Salvador',
    'GQ': 'Equatorial Guinea',
    'ER': 'Eritrea',
    'EE': 'Estonia',
    'ET': 'Ethiopia',
    'FK': 'Falkland Islands (Malvinas)',
    'FO': 'Faroe Islands',
    'FJ': 'Fiji',
    'FI': 'Finland',
    'FR': 'France',
    'GF': 'French Guiana',
    'PF': 'French Polynesia',
    'TF': 'French Southern Territories',
    'GA': 'Gabon',
    'GM': 'Gambia',
    'GE': 'Georgia',
    'DE': 'Germany',
    'GH': 'Ghana',
    'GI': 'Gibraltar',
    'GR': 'Greece',
    'GL': 'Greenland',
    'GD': 'Grenada',
    'GP': 'Guadeloupe',
    'GU': 'Guam',
    'GT': 'Guatemala',
    'GG': 'Guernsey',
    'GN': 'Guinea',
    'GW': 'Guinea-Bissau',
    'GY': 'Guyana',
    'HT': 'Haiti',
    'HM': 'Heard Island and McDonald Islands',
    'VA': 'Holy See (Vatican City State)',
    'HN': 'Honduras',
    'HK': 'Hong Kong',
    'HU': 'Hungary',
    'IS': 'Iceland',
    'IN': 'India',
    'ID': 'Indonesia',
    'IR': 'Iran, Islamic Republic of',
    'IQ': 'Iraq',
    'IE': 'Ireland',
    'IM': 'Isle of Man',
    'IL': 'Israel',
    'IT': 'Italy',
    'JM': 'Jamaica',
    'JP': 'Japan',
    'JE': 'Jersey',
    'JO': 'Jordan',
    'KZ': 'Kazakhstan',
    'KE': 'Kenya',
    'KI': 'Kiribati',
    'KP': "Korea, Democratic People's Republic of",
    'KR': 'Korea, Republic of',
    'KW': 'Kuwait',
    'KG': 'Kyrgyzstan',
    'LA': "Lao People's Democratic Republic",
    'LV': 'Latvia',
    'LB': 'Lebanon',
    'LS': 'Lesotho',
    'LR': 'Liberia',
    'LY': 'Libyan Arab Jamahiriya',
    'LI': 'Liechtenstein',
    'LT': 'Lithuania',
    'LU': 'Luxembourg',
    'MO': 'Macao',
    'MK': 'Macedonia, the former Yugoslav Republic of',
    'MG': 'Madagascar',
    'MW': 'Malawi',
    'MY': 'Malaysia',
    'MV': 'Maldives',
    'ML': 'Mali',
    'MT': 'Malta',
    'MH': 'Marshall Islands',
    'MQ': 'Martinique',
    'MR': 'Mauritania',
    'MU': 'Mauritius',
    'YT': 'Mayotte',
    'MX': 'Mexico',
    'FM': 'Micronesia, Federated States of',
    'MD': 'Moldova, Republic of',
    'MC': 'Monaco',
    'MN': 'Mongolia',
    'ME': 'Montenegro',
    'MS': 'Montserrat',
    'MA': 'Morocco',
    'MZ': 'Mozambique',
    'MM': 'Myanmar',
    'NA': 'Namibia',
    'NR': 'Nauru',
    'NP': 'Nepal',
    'NL': 'Netherlands',
    'AN': 'Netherlands Antilles',
    'NC': 'New Caledonia',
    'NZ': 'New Zealand',
    'NI': 'Nicaragua',
    'NE': 'Niger',
    'NG': 'Nigeria',
    'NU': 'Niue',
    'NF': 'Norfolk Island',
    'MP': 'Northern Mariana Islands',
    'NO': 'Norway',
    'OM': 'Oman',
    'PK': 'Pakistan',
    'PW': 'Palau',
    'PS': 'Palestinian Territory, Occupied',
    'PA': 'Panama',
    'PG': 'Papua New Guinea',
    'PY': 'Paraguay',
    'PE': 'Peru',
    'PH': 'Philippines',
    'PN': 'Pitcairn',
    'PL': 'Poland',
    'PT': 'Portugal',
    'PR': 'Puerto Rico',
    'QA': 'Qatar',
    'RE': 'Réunion',
    'RO': 'Romania',
    'RU': 'Russian Federation',
    'RW': 'Rwanda',
    'BL': 'Saint Barthélemy',
    'SH': 'Saint Helena, Ascension and Tristan da Cunha',
    'KN': 'Saint Kitts and Nevis',
    'LC': 'Saint Lucia',
    'MF': 'Saint Martin (French part)',
    'PM': 'Saint Pierre and Miquelon',
    'VC': 'Saint Vincent and the Grenadines',
    'WS': 'Samoa',
    'SM': 'San Marino',
    'ST': 'Sao Tome and Principe',
    'SA': 'Saudi Arabia',
    'SN': 'Senegal',
    'RS': 'Serbia',
    'SC': 'Seychelles',
    'SL': 'Sierra Leone',
    'SG': 'Singapore',
    'SK': 'Slovakia',
    'SI': 'Slovenia',
    'SB': 'Solomon Islands',
    'SO': 'Somalia',
    'ZA': 'South Africa',
    'GS': 'South Georgia and the South Sandwich Islands',
    'ES': 'Spain',
    'LK': 'Sri Lanka',
    'SD': 'Sudan',
    'SR': 'Suriname',
    'SJ': 'Svalbard and Jan Mayen',
    'SZ': 'Swaziland',
    'SE': 'Sweden',
    'CH': 'Switzerland',
    'SY': 'Syrian Arab Republic',
    'TW': 'Taiwan, Province of China',
    'TJ': 'Tajikistan',
    'TZ': 'Tanzania, United Republic of',
    'TH': 'Thailand',
    'TL': 'Timor-Leste',
    'TG': 'Togo',
    'TK': 'Tokelau',
    'TO': 'Tonga',
    'TT': 'Trinidad and Tobago',
    'TN': 'Tunisia',
    'TR': 'Turkey',
    'TM': 'Turkmenistan',
    'TC': 'Turks and Caicos Islands',
    'TV': 'Tuvalu',
    'UG': 'Uganda',
    'UA': 'Ukraine',
    'AE': 'United Arab Emirates',
    'GB': 'United Kingdom',
    'US': 'United States',
    'UM': 'United States Minor Outlying Islands',
    'UY': 'Uruguay',
    'UZ': 'Uzbekistan',
    'VU': 'Vanuatu',
    'VE': 'Venezuela, Bolivarian Republic of',
    'VN': 'Viet Nam',
    'VG': 'Virgin Islands, British',
    'VI': 'Virgin Islands, U.S.',
    'WF': 'Wallis and Futuna',
    'EH': 'Western Sahara',
    'YE': 'Yemen',
    'ZM': 'Zambia',
    'ZW': 'Zimbabwe',
}

# https://ec.europa.eu/eurostat/statistics-explained/index.php/Glossary:Country_codes
EUROPEAN_COUNTRIES = [
    'BE',
    'BG',
    'CZ',
    'DK',
    'DE',
    'EE',
    'IE',
    'GR',  # in reference this is EL
    'ES',
    'FR',
    'HR',
    'IT',
    'CY',
    'LV',
    'LT',
    'LU',
    'HU',
    'MT',
    'NL',
    'AT',
    'PL',
    'PT',
    'RO',
    'SI',
    'SK',
    'FI',
    'SE',
]
# TODO: do we need to add European Free Trade Association (EFTA) countries?
# (IS)
# (LI)
# (NO)
# (CH)
# TODO: do we add UK?
# TODO: test if api gives nice error message that we can reraise so we don't need this.
