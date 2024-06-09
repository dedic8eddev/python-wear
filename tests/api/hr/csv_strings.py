"""
CSV strings needed for testing account provisioning
"""
# flake8: noqa

csv_1 = '''# some comment
[TENANTS]
_id|name|legalname|uploadDirectory|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177|NL
91538|MaddoxE TEST|MaddoxE TEST|915773719506213492681|NL

[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
91539|maddoxb.haarlem|maddoxx.haarlem||saarlem|Europe/Amsterdam|device|pos-device|53
91539|maddoxb.bobby|Bobby||bobby|Europe/Amsterdam|standard|emptyrole|

[CASHIERS]
tenant_id|name|fullname|password
91539|99|Softwear.Admin|99
91539|05|Miranda|05
91539|06|Laura|06
'''

csv_2 = (
    csv_1
    + '''

[WAREHOUSES]
tenant_id|name|fullname|ean|email|wh|datafeed

[SOME_NAME]
fjieofhghoeihs
jgioejgoisj

[POS_REASONS]
jefoijeoif
gjoihjga
'''
)

csv_3 = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|wholesale|countryCode
81300|RoleTest|RoleTest|813004542489399474403|dashboard|true|false|NL

[USERS]
81300|username|fullname|email|password|tz|type|roles|wh|language
81300|evp54719@xcoxc.com|evp54719@xcoxc.com|evp54719@xcoxc.com||Europe/Amsterdam|standard|dashboard-user,products-brand_owner||nl-nl
'''

csv_standard_user = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh|language
existing|username||email@bla.com|||standard|dashboard-user,account-admin||en-gb
'''  # password should not be used
standard_user = {
    'tenant_id': ['existing'],
    'username': 'username',
    'fullname': 'Username',
    'email': 'email@bla.com',
    'type': 'standard',
    'tz': 'Europe/Amsterdam',
    'roles': {'existing': {'tenant': ['account-admin', 'dashboard-user']}},
    'default_application': {},
    'language': 'en-gb',
    'reportacls': {
        '0845d79e-abbd-41fd-b613-071ac44ea84c': False,
        '1ba601c7-b8f6-41e0-8005-62ef23947f7d': False,
        '5efb9fb1-50a6-4d2b-bc1d-e0cbb531ab82': False,
        '708a0b73-e4dd-4969-b96e-23dbeb4f74ce': False,
        'b5905518-fba9-49ca-9673-cb8a15b891b8': False,
        'f0adf069-f964-468f-a089-c2154a7af9fd': False,
        'f27870b0-107e-11e3-8ffd-0800200c9a66': False,
        'f42120d1-b97b-45c4-baf4-5c45bd1f1a7e': False,
        'f743ebbc-14cc-485d-afaa-bd3b58f8fdf4': False,
    },
    'settings': {
        'noAutoPrint': False,
        'displayAndPrintDiscountReason': False,
        'dashboardAllowedLocations': [],
        'printer': 'browser',
        'printerId': '',
    },
    'active': True,
}

csv_device_user = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|device|||saarlem1234||device|pos-device|43
existing|device2|||saarlem1234||device|pos-device|44
existing|device3|||saarlem1234||device|pos-device|45
existing|device4|||saarlem1234||device|pos-device|46
'''  # password should not be used
device_user = {
    'tenant_id': ['existing'],
    'username': 'device',
    'fullname': 'Device',
    'type': 'device',
    'tz': 'Europe/Amsterdam',
    'roles': {'existing': {'tenant': ['pos-device']}},
    'default_application': {'existing': 'pos'},
    'language': 'nl-nl',
    'reportacls': {
        '0845d79e-abbd-41fd-b613-071ac44ea84c': False,
        '1ba601c7-b8f6-41e0-8005-62ef23947f7d': False,
        '5efb9fb1-50a6-4d2b-bc1d-e0cbb531ab82': False,
        '708a0b73-e4dd-4969-b96e-23dbeb4f74ce': False,
        'b5905518-fba9-49ca-9673-cb8a15b891b8': False,
        'f0adf069-f964-468f-a089-c2154a7af9fd': False,
        'f27870b0-107e-11e3-8ffd-0800200c9a66': False,
        'f42120d1-b97b-45c4-baf4-5c45bd1f1a7e': False,
        'f743ebbc-14cc-485d-afaa-bd3b58f8fdf4': False,
    },
    'settings': {
        'email': {
            'active': False,
            'autoPopup': False,
            'body': 'Uw kassabon',
            'replyTo': '',
            'sender': 'info@uwkassabon.com',
            'subject': 'Uw kassabon',
        },
        'noAutoPrint': False,
        'displayAndPrintDiscountReason': False,
        'dashboardAllowedLocations': [],
        'printer': 'browser',
        'printerId': '',
        'secondScreen': {
            'duration': 10,
            'playlistId': '',
            'secondScreenId': '',
            'showCustomer': False,
        },
    },
    'active': True,
    'wh': '43',
    'email': None,
}

csv_lots_of_errors = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177||True|NL
91538|MaddoxE TEST|MaddoxE TEST|915773719506213492681||True|NL
91538||MaddoxE TEST|915773719506213492681||True|NL
91538|MaddoxE TEST|MaddoxE TEST|915773719506213492681|pos,bla|True|NL

[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
91539|maddoxb.haarlem|maddoxx.haarlem||saarlem1234|Europe/Amsterdam|device|pos-device|53
91555|maddoxb.bobby|Bobby|bla||Europe/Amsterdam|standard|emptyrole|
91539|maddoxb.bobby2|Bobby|||Europe/Amsterdam|standard|emptyrole|
91539|maddoxb.haarlem|maddoxx.haarlem||saarlem1234|Europe/Amsterdam|device|pos-device|53

[CASHIERS]
tenant_id|name|fullname|password
91539|99|Softwear.Admin|99
91539|05|Miranda|05
91539|06|Laura|06
91539|22|Marco|22
91539|23|Joke|23
91539|24|Jeroen|22
91539|04|Frits|04
91539|07|Meta|07
91539|03|Arnoud|03

[WAREHOUSES]
tenant_id|name|fullname|ean|email|wh
91539|Amsterdam||||50
91539|Amstelveen||6000630000000||51
91539|Lisse|||lisse@softwear.nl|52
91539|Haarlem|||my@email.com|53
91588|Wormer||||53
91539|Den Haag|||bla|55
91539|Zaandam||||56
91539|Heemstede||||57
91539|Kortenhoef||||58
91539|Hoofddorp|||bla|59
91539|Zandvoort||||60
91539|Zandvoort||||60
91540|Zandvoort||||60
91540|Zandvoort||||60
'''
markdown_errors = '''# tenants
| index | field | error |
| --- | --- | --- |
|2|name|['Missing data for required field.']|
|3|applications|["Unknown application(s): {'bla'}"]|
|_schema| |["There are duplicate _ids in the import: ['91538']", "There are duplicate names in the import: ['MaddoxE TEST']"]|
# users
| index | field | error |
| --- | --- | --- |
|1|email|['Not a valid email address.']|
| |roles|defaultdict(<class 'dict'>, {'91555': {'value': {'tenant': ["Unknown role(s): {'emptyrole'}"]}}})|
| |tenant_id|['Non-existing tenant(s): 91555']|
|2|roles|defaultdict(<class 'dict'>, {'91539': {'value': {'tenant': ["Unknown role(s): {'emptyrole'}"]}}})|
|_schema| |["There are duplicate usernames in the import: ['maddoxb.haarlem']"]|
# cashiers
['There are duplicate passwords in the import for tenant_id 91539']
# warehouses
| index | field | error |
| --- | --- | --- |
|12|tenant_id|['Non-existing tenant(s): 91540']|
|13|tenant_id|['Non-existing tenant(s): 91540']|
|4|tenant_id|['Non-existing tenant(s): 91588']|
|5|email|['Not a valid email address.']|
|9|email|['Not a valid email address.']|
|_schema| |["There are duplicate wh numbers in the import for tenant_id 91539: ['60']"]|
'''
csv_tenant_and_owner = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177|pos,dashboard|True|NL
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|device|||saarlem1234||device|pos-device|43
91539|owner_user|maddoxx.haarlem|bla@bla.com||Europe/Amsterdam|owner|pos-device,dashboard-user|
existing|username||email@bla.com|||standard|dashboard-user,account-admin|
'''
csv_owner_existing_tenant = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|owner_user|maddoxx.haarlem|bla@bla.com||Europe/Amsterdam|owner|pos-device,dashboard-user|
'''
csv_validate_pwd = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|maddoxb.haarlem|maddoxx.haarlem||saarlem|Europe/Amsterdam|device|pos-device|53
'''
csv_validate_username = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|_bbbb|maddoxx.haarlem|||Europe/Amsterdam|standard|pos-device|53
'''
csv_lots_of_documents = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177||True|NL
91538|MaddoxE TEST|MaddoxE TEST|915773719506213492681||True|NL
91540|tenant_x|MaddoxE TEST|915773719506213492681|dashboard|True|NL
91541|MaddoxE|MaddoxE TEST|915773719506213492681|pos|True|NL

[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
91539|maddoxb.haarlem|maddoxx.haarlem||saarlem1234|Europe/Amsterdam|device|pos-device|53
91539|maddoxb.bobby|Bobby|bla@bla.com||Europe/Amsterdam|standard||
91539|maddoxb.bobby2|Bobby|bla2@bla.com||Europe/Amsterdam|standard|pos-device,dashboard-user|
91539|maddoxb.haarlem2|maddoxx.haarlem||saarlem1234|Europe/Amsterdam|device|pos-device|53
91540|maddoxb.haarlem3|maddoxx.haarlem||saarlem1234|Europe/Amsterdam|device|pos-device|53

[CASHIERS]
tenant_id|name|fullname|password
91539|99|Softwear.Admin|99
91539|05|Miranda|05
91539|06|Laura|06
91539|22|Marco|22
91539|23|Joke|23
91539|24|Jeroen|24
91539|04|Frits|04
91539|07|Meta|07
91539|03|Arnoud|03

[WAREHOUSES]
tenant_id|name|fullname|ean|email|wh
91539|Amsterdam||||50
91539|Amstelveen||6000630000000||51
91539|Lisse|||lisse@softwear.nl|52
91539|Haarlem|||my@email.com|53
91539|Wormer||||54
91539|Den Haag||||55
91539|Zaandam||||56
91539|Heemstede||||57
91539|Kortenhoef||||58
91539|Hoofddorp||||59
91539|Zandvoort||||60
'''
csv_tenant_no_owner = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177||True|NL
91538|MaddoxE TEST|MaddoxE TEST|915773719506213492681||1|NL

[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
91539|maddoxb.bobby|Bobby|bla@bla.com||Europe/Amsterdam|owner||
'''
csv_wrong_applications = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177|dashboard|true|NL

[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
91539|maddoxb.bobby|Bobby|bla@bla.com||Europe/Amsterdam|standard|dashboard-user,dashboard-user|
existing|existing_user||bla2@bla.com||Europe/Amsterdam|standard|dashboard-user,dashboard-user|
'''
