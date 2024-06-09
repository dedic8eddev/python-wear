sale = {
    'vat': {'hightotal': 131.27, 'highamount': 22.78, 'lowtotal': 106, 'lowamount': 6},
    'totalAmount': 154.94,
    'totalDiscountCoupon': 0,
    "overallReceiptDiscount": 0.20,
    'totalCoupon': 15.67,
    'receipt': [
        {
            'articleCode': 'B.Drake T-shirt',
            'articleDescription': 'Drake T-shirt 16,5',
            'barcode': '13',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': False,
            'color': 'blackberryamazone',
            'found': True,
            'group': None,
            'nettPrice': 127.75,
            'price': 127.75,
            'qty': 1,
            'sizeLabel': '-',
            'vat': 21.0,
        },
        {
            'articleCode': 'B.Drake T-shirt',
            'articleDescription': 'Drake T-shirt 16,5',
            'barcode': '13',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': True,
            'color': 'blackberryamazone',
            'found': True,
            'group': None,
            'nettPrice': 127.75,
            'price': 114.97,
            'qty': 1,
            'reason': {'desc': 'Anders', 'key': '0'},
            'sizeLabel': '-',
            'vat': 21.0,
        },
        {
            'articleCode': 'B.Drake Cap',
            'articleDescription': 'Drake Cap',
            'barcode': '11',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': False,
            'color': 'BUBBLE GUM',
            'found': True,
            'group': None,
            'nettPrice': 9.99,
            'price': 9.99,
            'qty': 1,
            'sizeLabel': '-',
            'vat': 21.0,
        },
        {
            'articleCode': 'B.Drake Cap',
            'articleDescription': 'Drake Cap',
            'barcode': '11',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': False,
            'color': 'BUBBLE GUM',
            'found': True,
            'group': None,
            'nettPrice': 9.99,
            'price': 9.99,
            'qty': 1,
            'sizeLabel': '-',
            'vat': 21.0,
        },
        {
            'barcode': '+KAV1KIQX9UIA7',
            'category': 'coupon',
            'couponNr': 'KAV1KIQX9UIA7',
            'found': True,
            'group': '',
            'nettPrice': 13.67,
            'price': 13.67,
            'qty': 1,
            'type': 'A',
            'vat': 0,
        },
        {
            'articleCode': 'B.Drake Cap',
            'articleDescription': 'Drake Cap',
            'barcode': '11',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': False,
            'color': 'BUBBLE GUM',
            'found': True,
            'group': None,
            'nettPrice': 9.99,
            'price': 9.99,
            'qty': 1,
            'sizeLabel': '-',
            'vat': 21.0,
        },
        {
            'barcode': '+kadobon',
            'category': 'coupon',
            'couponNr': 'kadobon',
            'found': True,
            'group': '',
            'nettPrice': 2.0,
            'price': 2.0,
            'qty': 1,
            'type': 'U',
            'vat': 0,
        },
        {
            'category': 'storecredit',
            'found': True,
            'group': '',
            'nettPrice': 10.0,
            'price': 10.0,
            'qty': 1,
            'reqid': '28bf',
            'type': 'O',
        },
        {
            'articleCode': 'B.Drake T-shirt',
            'articleDescription': 'Drake T-shirt 16,5',
            'barcode': '13',
            'brand': 'My God',
            'category': 'barcode',
            'changeDisc': False,
            'color': 'blackberryamazone',
            'found': True,
            'group': None,
            'nettPrice': 127.75,
            'price': 127.75,
            'qty': -1,
            'sizeLabel': '-',
            'vat': 21.0,
        },
    ],
}

# data to test calculate_totals_and discounts:
data1 = {
    'receipt': [{'category': 'barcode', 'nettPrice': 9.99, 'price': 9.99, 'qty': 4}],
    'totalAmount': 39.96,
    'totalDiscount': 9.99,
    'overallReceiptDiscount': 9.99,
    'totalDiscountCoupon': 0.00,
}
expected1 = {'receipt': [{'discount': 2.50, 'total': 29.97}], 'display_discount': 9.99}
data2 = {
    'receipt': [
        {'category': 'barcode', 'nettPrice': 9.99, 'price': 9.99, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 9.99, 'price': 9.99, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 9.99, 'price': 9.99, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 9.99, 'price': 9.99, 'qty': 1},
    ],
    'totalAmount': 39.96,
    'totalDiscount': 9.99,
    'overallReceiptDiscount': 9.99,
    'totalDiscountCoupon': 0.00,
}
expected2 = {
    'receipt': [
        {'discount': 2.49, 'total': 7.50},
        {'discount': 2.50, 'total': 7.49},
        {'discount': 2.50, 'total': 7.49},
        {'discount': 2.50, 'total': 7.49},
    ],
    'display_discount': 9.99,
}
data3 = {
    'receipt': [
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 10.00, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 10.00, 'qty': 1},
    ],
    'totalAmount': 20.00,
    'totalDiscount': 4.99,
    'overallReceiptDiscount': 4.99,
    'totalDiscountCoupon': 0.00,
}
expected3 = {
    'receipt': [{'discount': 2.49, 'total': 7.51}, {'discount': 2.50, 'total': 7.50}],
    'display_discount': 4.99,
}
# storecredit does not count as discountable, and should not be used for correcting
# rounding errors, plus only qty 1 should be used:
data4 = {
    'receipt': [
        {'category': 'storecredit', 'qty': 1, 'price': 8.99, 'type': 'O'},
        {'category': 'barcode', 'nettPrice': 5.00, 'price': 5.00, 'qty': 2},
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 10.00, 'qty': 1},
    ],
    'totalAmount': 28.99,
    'totalDiscount': 4.99,
    'overallReceiptDiscount': 4.99,
    'totalDiscountCoupon': 0.00,
}
expected4 = {
    'receipt': [
        {'total': 8.99},
        {'discount': 1.25, 'total': 7.50},
        {'discount': 2.49, 'total': 7.51},
    ],
    'display_discount': 4.99,
}
# only line discount:
data5 = {
    'receipt': [
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 8.00, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 9.00, 'qty': 2},
    ],
    'totalAmount': 26.00,
    'totalDiscount': 0.00,
    'overallReceiptDiscount': 0.00,
    'totalDiscountCoupon': 0.00,
}
expected5 = {
    'receipt': [{'discount': 2.00, 'total': 8.00}, {'discount': 1.00, 'total': 18.00}],
    'display_discount': 4.00,
}
# line and total discount:
data6 = {
    'receipt': [
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 8.00, 'qty': 1},
        {'category': 'barcode', 'nettPrice': 10.00, 'price': 9.00, 'qty': 2},
    ],
    'totalAmount': 26.00,
    'totalDiscount': 4.99,
    'overallReceiptDiscount': 4.99,
    'totalDiscountCoupon': 0.00,
}
expected6 = {
    'receipt': [{'discount': 3.54, 'total': 6.46}, {'discount': 2.73, 'total': 14.55}],
    'display_discount': 8.99,
}
