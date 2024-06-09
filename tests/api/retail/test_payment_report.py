from spynl.api.retail.payments import PaymentsReportSchema, format_result


def test_pipeline():
    data = {
        'groups': ['user', 'location', 'device', 'dow', 'day', 'week', 'month', 'year'],
        'filter': {'location': ['Amstelveen']},
        'sort': [{'direction': 1, 'field': 'location'}],
    }
    pipeline = PaymentsReportSchema(context={'tenant_id': '1'}).load(data)
    assert pipeline == [
        {'$match': {'shop.name': {'$in': ['Amstelveen']}, 'tenant_id': {'$in': ['1']}}},
        {
            '$group': {
                '_id': {
                    'cardType': '$cardType',
                    'day': {
                        '$dateToString': {'date': '$created.date', 'format': '%Y-%m-%d'}
                    },
                    'device': '$device.name',
                    'dow': {'$dateToString': {'date': '$created.date', 'format': '%w'}},
                    'location': '$shop.name',
                    'month': {
                        '$dateToString': {'date': '$created.date', 'format': '%m'}
                    },
                    'user': '$created.user._id',
                    'week': {
                        '$dateToString': {'date': '$created.date', 'format': '%U'}
                    },
                    'year': {
                        '$dateToString': {'date': '$created.date', 'format': '%Y'}
                    },
                },
                'cash': {'$sum': '$payments.cash'},
                'couponin': {'$sum': '$payments.couponin'},
                'creditcard': {'$sum': '$payments.creditcard'},
                'creditreceipt': {'$sum': '$payments.creditreceipt'},
                'pin': {'$sum': '$payments.pin'},
                'storecredit': {'$sum': '$payments.storecredit'},
            }
        },
        {
            '$group': {
                '_id': {
                    'day': '$_id.day',
                    'device': '$_id.device',
                    'dow': '$_id.dow',
                    'location': '$_id.location',
                    'month': '$_id.month',
                    'user': '$_id.user',
                    'week': '$_id.week',
                    'year': '$_id.year',
                },
                'cash': {'$sum': '$cash'},
                'couponin': {'$sum': '$couponin'},
                'creditcard': {'$sum': '$creditcard'},
                'creditreceipt': {'$sum': '$creditreceipt'},
                'pin': {
                    '$push': {
                        'k': {'$ifNull': ['$_id.cardType', 'unknown']},
                        'v': '$pin',
                    }
                },
                'storecredit': {'$sum': '$storecredit'},
            }
        },
        {'$sort': {'_id.location': 1}},
        {
            '$addFields': {
                'day': {'$ifNull': ['$_id.day', '']},
                'device': {'$ifNull': ['$_id.device', '']},
                'dow': {'$ifNull': ['$_id.dow', '']},
                'location': {'$ifNull': ['$_id.location', '']},
                'month': {'$ifNull': ['$_id.month', '']},
                'pin': {'$arrayToObject': '$pin'},
                'pin-total': {
                    '$reduce': {
                        'in': {'$sum': ['$$value', '$$this.v']},
                        'initialValue': 0,
                        'input': '$pin',
                    }
                },
                'user': {'$ifNull': ['$_id.user', '']},
                'week': {'$ifNull': ['$_id.week', '']},
                'year': {'$ifNull': ['$_id.year', '']},
            }
        },
        {'$project': {'_id': 0}},
    ]


def test_format_report():
    data = [
        {
            'cash': 9,
            'couponin': 0,
            'creditcard': 0,
            'creditreceipt': 0,
            'location': 'Amstelveen',
            'pin': {'unknown': 275.5},
            'pin-total': 275.5,
            'storecredit': 0,
            'user': '56388f5c500ce94d78b121f7',
        },
        {
            'cash': 116745.3,
            'couponin': 0.0,
            'creditcard': 9.99,
            'creditreceipt': -501.0,
            'location': 'Amstelveen',
            'pin': {'unknown': 0.0},
            'pin-total': 0.0,
            'storecredit': 0.0,
            'user': '',
        },
        {
            'cash': 3203828.11,
            'couponin': 0.0,
            'creditcard': 11533.72,
            'creditreceipt': -1457.96,
            'location': 'Amstelveen',
            'pin': {
                'A0000000031010': 19.98,
                'A0000000043060': 9.99,
                'American Express': 9.99,
                'Maestro': 19.98,
                'VISA_Credit': 9.99,
                'unknown': 20869.94,
            },
            'pin-total': 20939.87,
            'storecredit': 20818.04,
            'user': '56388f5c500ce94d78b121fb',
        },
    ]
    result = format_result(data)
    assert result == [
        {
            'location': 'Amstelveen',
            'paymentType': 'cash',
            'user': '56388f5c500ce94d78b121f7',
            'value': 9,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'couponin',
            'user': '56388f5c500ce94d78b121f7',
            'value': 0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'creditcard',
            'user': '56388f5c500ce94d78b121f7',
            'value': 0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'creditreceipt',
            'user': '56388f5c500ce94d78b121f7',
            'value': 0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-unknown',
            'user': '56388f5c500ce94d78b121f7',
            'value': 275.5,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-total',
            'user': '56388f5c500ce94d78b121f7',
            'value': 275.5,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'storecredit',
            'user': '56388f5c500ce94d78b121f7',
            'value': 0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'cash',
            'user': '',
            'value': 116745.3,
        },
        {'location': 'Amstelveen', 'paymentType': 'couponin', 'user': '', 'value': 0.0},
        {
            'location': 'Amstelveen',
            'paymentType': 'creditcard',
            'user': '',
            'value': 9.99,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'creditreceipt',
            'user': '',
            'value': -501.0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-unknown',
            'user': '',
            'value': 0.0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-total',
            'user': '',
            'value': 0.0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'storecredit',
            'user': '',
            'value': 0.0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'cash',
            'user': '56388f5c500ce94d78b121fb',
            'value': 3203828.11,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'couponin',
            'user': '56388f5c500ce94d78b121fb',
            'value': 0.0,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'creditcard',
            'user': '56388f5c500ce94d78b121fb',
            'value': 11533.72,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'creditreceipt',
            'user': '56388f5c500ce94d78b121fb',
            'value': -1457.96,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-A0000000031010',
            'user': '56388f5c500ce94d78b121fb',
            'value': 19.98,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-A0000000043060',
            'user': '56388f5c500ce94d78b121fb',
            'value': 9.99,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-American Express',
            'user': '56388f5c500ce94d78b121fb',
            'value': 9.99,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-Maestro',
            'user': '56388f5c500ce94d78b121fb',
            'value': 19.98,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-VISA_Credit',
            'user': '56388f5c500ce94d78b121fb',
            'value': 9.99,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-unknown',
            'user': '56388f5c500ce94d78b121fb',
            'value': 20869.94,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'pin-total',
            'user': '56388f5c500ce94d78b121fb',
            'value': 20939.87,
        },
        {
            'location': 'Amstelveen',
            'paymentType': 'storecredit',
            'user': '56388f5c500ce94d78b121fb',
            'value': 20818.04,
        },
    ]


def test_results(spynl_data_db):
    data = [
        {
            'payments': {
                'cash': 9,
                'couponin': 0,
                'creditcard': 0,
                'creditreceipt': 0,
                'storecredit': 0,
                'pin': 275.5,
            },
            'tenant_id': ['1'],
            'shop': {'name': 'Amstelveen'},
        },
        {
            'payments': {
                'cash': 116745.3,
                'couponin': 0.0,
                'creditcard': 9.99,
                'creditreceipt': -501.0,
                'pin': 0.0,
                'storecredit': 0.0,
            },
            'tenant_id': ['1'],
            'shop': {'name': 'Amsterdam'},
        },
        {
            'payments': {
                'cash': 3203828.11,
                'couponin': 0.0,
                'creditcard': 11533.72,
                'creditreceipt': -1457.96,
                'pin': 19.98,
                'storecredit': 20818.04,
            },
            'tenant_id': ['1'],
            'cardType': 'A0000000031010',
            'shop': {'name': 'Amstelveen'},
        },
        {
            'payments': {
                'cash': 3203828.11,
                'couponin': 0.0,
                'creditcard': 11533.72,
                'creditreceipt': -1457.96,
                'pin': 19.98,
                'storecredit': 20818.04,
            },
            'tenant_id': ['1'],
            'cardType': 'A0000000031010',
            'shop': {'name': 'Utrecht'},
        },
    ]
    spynl_data_db.transactions.insert_many(data)

    query = {
        'groups': ['location'],
        'filter': {'location': ['Amstelveen', 'Amsterdam']},
        'sort': [{'field': 'location', 'direction': -1}],
    }
    pipeline = PaymentsReportSchema(context={'tenant_id': '1'}).load(query)
    result = list(spynl_data_db.transactions.aggregate(pipeline))
    assert result == [
        {
            'cash': 116745.3,
            'couponin': 0.0,
            'creditcard': 9.99,
            'creditreceipt': -501.0,
            'location': 'Amsterdam',
            'pin': {'unknown': 0.0},
            'pin-total': 0.0,
            'storecredit': 0.0,
        },
        {
            'cash': 3203837.11,
            'couponin': 0.0,
            'creditcard': 11533.72,
            'creditreceipt': -1457.96,
            'location': 'Amstelveen',
            'pin': {'A0000000031010': 19.98, 'unknown': 275.5},
            'pin-total': 295.48,
            'storecredit': 20818.04,
        },
    ]
