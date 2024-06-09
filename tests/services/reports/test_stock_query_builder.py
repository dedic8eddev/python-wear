import re

import pytest

from spynl.services.reports.stock import StockFilter
from spynl.services.reports.stock_query_builder import (
    LABEL_SEPARATOR,
    _build_group_by,
    _build_select,
    _build_sort,
    build,
    build_stock_return_value,
)

TEST_DATA = [
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Amsterdam',
        'article': '017T30BK-I18',
        'sizename': '37',
        'label': 'zwar{sep}zwar{sep}Amsterdam'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 3,
        'n_stock': 5,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Amsterdam',
        'article': '017T30BK-I18',
        'sizename': '37',
        'label': 'blau{sep}blau{sep}Amsterdam'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 3,
        'n_stock': 0,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '017T30BK-I18',
        'sizename': '38',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 4,
        'n_stock': 1,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '017T30BK-I18',
        'sizename': '39',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 5,
        'n_stock': 0,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '017T30BK-I18',
        'sizename': '40',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 6,
        'n_stock': 0,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '017T30BK-I18',
        'sizename': '41',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 7,
        'n_stock': 0,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018060G',
        'sizename': 'S',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 2,
        'n_stock': 6,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018060G',
        'sizename': 'S',
        'label': 'zwar{sep}zwar{sep}Hoofddorp'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 2,
        'n_stock': 6,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018060G',
        'sizename': 'M',
        'label': 'zwar{sep}zwar{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 3,
        'n_stock': 1,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018064G',
        'sizename': 'S',
        'label': 'blau{sep}blau{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 2,
        'n_stock': 0,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018064G',
        'sizename': 'M',
        'label': 'blau{sep}blau{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 3,
        'n_stock': -1,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Haarlem',
        'article': '018317G',
        'sizename': 'ONE',
        'label': 'blau{sep}blau{sep}Haarlem'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 1,
        'n_stock': 100,
    },
    {
        'tenantname': 'ILSE Hoofddorp',
        'warehouse': 'Rotterdam',
        'article': '018317G',
        'sizename': 'ONE',
        'label': 'blau{sep}blau{sep}Rotterdam'.format(sep=LABEL_SEPARATOR),
        'sizeidx': 1,
        'n_stock': 0,
    },
]

TEST_DATA_HISTORY = [
    {
        'article': '017T30BK-I18',
        'sizename': '37',
        'label': 'PNE G{sep}20191126154703{sep}Amstelveen{sep}01{sep}2{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 3,
        'n_stock': 5,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '37',
        'label': 'NAT D{sep}20191126154703{sep}Amstelveen{sep}01{sep}2{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 3,
        'n_stock': 0,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '38',
        'label': 'grijs {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 4,
        'n_stock': 1,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '38',
        'label': 'grijs {sep}20180101000000{sep}Magazijn{sep} {sep}14{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 4,
        'n_stock': 1,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '39',
        'label': 'wit {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 5,
        'n_stock': 0,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '40',
        'label': 'zwart {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 6,
        'n_stock': 0,
    },
    {
        'article': '017T30BK-I18',
        'sizename': '41',
        'label': 'grijs {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 7,
        'n_stock': 0,
    },
    {
        'article': '018060G',
        'sizename': 'S',
        'label': 'wit {sep}Amsterdam{sep}20180101000000{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 2,
        'n_stock': 6,
    },
    {
        'article': '018060G',
        'sizename': 'S',
        'label': 'wit {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 2,
        'n_stock': 6,
    },
    {
        'article': '018060G',
        'sizename': 'M',
        'label': 'zwart {sep}20180101000000{sep}Magazijn{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 3,
        'n_stock': 1,
    },
    {
        'article': '018064G',
        'sizename': 'S',
        'label': 'grijs {sep}20180101000000{sep}Lisse{sep} {sep}0{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 2,
        'n_stock': 0,
    },
    {
        'article': '018064G',
        'sizename': 'M',
        'label': 'Paars {sep}20190620164903{sep}Amstelveen{sep} {sep}3{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 3,
        'n_stock': -1,
    },
    {
        'article': '018317G',
        'sizename': 'ONE',
        'label': 'Paars {sep}20190620171326{sep}Amstelveen{sep}11{sep}2{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 1,
        'n_stock': 100,
    },
    {
        'article': '018317G',
        'sizename': 'ONE',
        'label': 'Paars {sep}20190620171459{sep}Amstelveen{sep}11{sep}2{sep}20'.format(
            sep=LABEL_SEPARATOR
        ),
        'sizeidx': 1,
        'n_stock': 0,
    },
]


@pytest.mark.parametrize('keep_zero_lines', [False, True])
def test_build_matrixes(keep_zero_lines):

    result = build_stock_return_value(
        TEST_DATA, ['warehouse', 'tenantname'], keep_zero_lines=keep_zero_lines
    )

    expected = [
        {'header': 'Amsterdam, ILSE Hoofddorp'},
        {
            'article': '017T30BK-I18',
            'skuStockMatrix': [
                ['color', 'color-supplier', 'location', '37'],
                ['zwar', 'zwar', 'Amsterdam', 5],
            ],
            'tenantname': 'ILSE Hoofddorp',
            'warehouse': 'Amsterdam',
        },
        {'header': 'Haarlem, ILSE Hoofddorp'},
        {
            'article': '017T30BK-I18',
            'skuStockMatrix': [
                ['color', 'color-supplier', 'location', '38', '39', '40', '41'],
                ['zwar', 'zwar', 'Haarlem', 1, 0, 0, 0],
            ],
            'tenantname': 'ILSE Hoofddorp',
            'warehouse': 'Haarlem',
        },
        {
            'article': '018060G',
            'skuStockMatrix': [
                ['color', 'color-supplier', 'location', 'S', 'M'],
                ['zwar', 'zwar', 'Haarlem', 6, 1],
                ['zwar', 'zwar', 'Hoofddorp', 6, None],
            ],
            'tenantname': 'ILSE Hoofddorp',
            'warehouse': 'Haarlem',
        },
        {
            'article': '018064G',
            'skuStockMatrix': [
                ['color', 'color-supplier', 'location', 'S', 'M'],
                ['blau', 'blau', 'Haarlem', 0, -1],
            ],
            'tenantname': 'ILSE Hoofddorp',
            'warehouse': 'Haarlem',
        },
        {
            'article': '018317G',
            'skuStockMatrix': [
                ['color', 'color-supplier', 'location', 'ONE'],
                ['blau', 'blau', 'Haarlem', 100],
            ],
            'tenantname': 'ILSE Hoofddorp',
            'warehouse': 'Haarlem',
        },
    ]

    if keep_zero_lines:
        expected[1]['skuStockMatrix'].insert(1, ['blau', 'blau', 'Amsterdam', 0])
    assert result == expected


def test_build_matrixes_history():
    result = build_stock_return_value(TEST_DATA_HISTORY, [], history=True)

    headers = ['color', 'time', 'location', 'user', 'type', 'reference']
    expected = [
        {'header': ''},
        {
            'article': '017T30BK-I18',
            'skuStockMatrix': [
                [*headers, '37', '38', '39', '40', '41'],
                ['PNE G', None, None, None, None, None, None, None, None, None, None],
                [
                    '',
                    '20191126154703',
                    'Amstelveen',
                    '01',
                    'trtype-2',
                    '20',
                    5,
                    None,
                    None,
                    None,
                    None,
                ],
                ['', 'end-stock', '', '', '', '', 5, 0, 0, 0, 0],
                ['grijs ', None, None, None, None, None, None, None, None, None, None],
                [
                    '',
                    '20180101000000',
                    'Magazijn',
                    ' ',
                    'trtype-0',
                    '20',
                    None,
                    1,
                    None,
                    None,
                    0,
                ],
                [
                    '',
                    '20180101000000',
                    'Magazijn',
                    ' ',
                    'trtype-14',
                    '20',
                    None,
                    1,
                    None,
                    None,
                    None,
                ],
                ['', 'end-stock', '', '', '', '', 0, 1, 0, 0, 0],
            ],
        },
        {
            'article': '018060G',
            'skuStockMatrix': [
                [*headers, 'S', 'M'],
                ['wit ', None, None, None, None, None, None, None],
                ['', '20180101000000', 'Magazijn', ' ', 'trtype-0', '20', 6, None],
                ['', 'Amsterdam', '20180101000000', ' ', 'trtype-0', '20', 6, None],
                ['', 'end-stock', '', '', '', '', 12, 0],
                ['zwart ', None, None, None, None, None, None, None],
                ['', '20180101000000', 'Magazijn', ' ', 'trtype-0', '20', None, 1],
                ['', 'end-stock', '', '', '', '', 0, 1],
            ],
        },
        {
            'article': '018064G',
            'skuStockMatrix': [
                [*headers, 'S', 'M'],
                ['Paars ', None, None, None, None, None, None, None],
                ['', '20190620164903', 'Amstelveen', ' ', 'trtype-3', '20', None, -1],
                ['', 'end-stock', '', '', '', '', 0, -1],
            ],
        },
        {
            'article': '018317G',
            'skuStockMatrix': [
                [*headers, 'ONE'],
                ['Paars ', None, None, None, None, None, None],
                ['', '20190620171326', 'Amstelveen', '11', 'trtype-2', '20', 100],
                ['', 'end-stock', '', '', '', '', 100],
            ],
        },
    ]
    assert result == expected


def test_build_matrixes_pdf():
    result = build_stock_return_value(
        TEST_DATA,
        ['warehouse', 'tenantname'],
        keep_zero_lines=False,
        headers_in_separate_row=False,
        calculate_totals=True,
    )

    expected = [
        {
            'header': 'Amsterdam, ILSE Hoofddorp',
            'products': [
                {
                    'article': '017T30BK-I18',
                    'skuStockMatrix': [
                        ['color', 'color-supplier', 'location', '37', '#'],
                        ['zwar', 'zwar', 'Amsterdam', 5, 5],
                        ['end-stock', '', '', 5, 5],
                    ],
                    'tenantname': 'ILSE Hoofddorp',
                    'warehouse': 'Amsterdam',
                }
            ],
        },
        {
            'header': 'Haarlem, ILSE Hoofddorp',
            'products': [
                {
                    'article': '017T30BK-I18',
                    'skuStockMatrix': [
                        [
                            'color',
                            'color-supplier',
                            'location',
                            '38',
                            '39',
                            '40',
                            '41',
                            '#',
                        ],
                        ['zwar', 'zwar', 'Haarlem', 1, 0, 0, 0, 1],
                        ['end-stock', '', '', 1, 0, 0, 0, 1],
                    ],
                    'tenantname': 'ILSE Hoofddorp',
                    'warehouse': 'Haarlem',
                },
                {
                    'article': '018060G',
                    'skuStockMatrix': [
                        ['color', 'color-supplier', 'location', 'S', 'M', '#'],
                        ['zwar', 'zwar', 'Haarlem', 6, 1, 7],
                        ['zwar', 'zwar', 'Hoofddorp', 6, None, 6],
                        ['end-stock', '', '', 12, 1, 13],
                    ],
                    'tenantname': 'ILSE Hoofddorp',
                    'warehouse': 'Haarlem',
                },
                {
                    'article': '018064G',
                    'skuStockMatrix': [
                        ['color', 'color-supplier', 'location', 'S', 'M', '#'],
                        ['blau', 'blau', 'Haarlem', 0, -1, -1],
                        ['end-stock', '', '', 0, -1, -1],
                    ],
                    'tenantname': 'ILSE Hoofddorp',
                    'warehouse': 'Haarlem',
                },
                {
                    'article': '018317G',
                    'skuStockMatrix': [
                        ['color', 'color-supplier', 'location', 'ONE', '#'],
                        ['blau', 'blau', 'Haarlem', 100, 100],
                        ['end-stock', '', '', 100, 100],
                    ],
                    'tenantname': 'ILSE Hoofddorp',
                    'warehouse': 'Haarlem',
                },
            ],
        },
    ]
    assert result == expected


def test_build_matrixes_history_pdf():
    result = build_stock_return_value(
        TEST_DATA_HISTORY,
        ['warehouse', 'tenantname'],
        keep_zero_lines=False,
        headers_in_separate_row=False,
        calculate_totals=True,
        history=True,
    )

    headers = ['color', 'time', 'location', 'user', 'type', 'reference']
    expected = [
        {
            'header': '',
            'products': [
                {
                    'article': '017T30BK-I18',
                    'skuStockMatrix': [
                        [*headers, '37', '38', '39', '40', '41', '#'],
                        [
                            'PNE G',
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        ],
                        [
                            '',
                            '20191126154703',
                            'Amstelveen',
                            '01',
                            'trtype-2',
                            '20',
                            5,
                            None,
                            None,
                            None,
                            None,
                            5,
                        ],
                        ['', 'end-stock', '', '', '', '', 5, 0, 0, 0, 0, 5],
                        [
                            'grijs ',
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                        ],
                        [
                            '',
                            '20180101000000',
                            'Magazijn',
                            ' ',
                            'trtype-0',
                            '20',
                            None,
                            1,
                            None,
                            None,
                            0,
                            1,
                        ],
                        [
                            '',
                            '20180101000000',
                            'Magazijn',
                            ' ',
                            'trtype-14',
                            '20',
                            None,
                            1,
                            None,
                            None,
                            None,
                            1,
                        ],
                        ['', 'end-stock', '', '', '', '', 0, 1, 0, 0, 0, 1],
                    ],
                },
                {
                    'article': '018060G',
                    'skuStockMatrix': [
                        [*headers, 'S', 'M', '#'],
                        ['wit ', None, None, None, None, None, None, None, None],
                        [
                            '',
                            '20180101000000',
                            'Magazijn',
                            ' ',
                            'trtype-0',
                            '20',
                            6,
                            None,
                            6,
                        ],
                        [
                            '',
                            'Amsterdam',
                            '20180101000000',
                            ' ',
                            'trtype-0',
                            '20',
                            6,
                            None,
                            6,
                        ],
                        ['', 'end-stock', '', '', '', '', 12, 0, 12],
                        ['zwart ', None, None, None, None, None, None, None, None],
                        [
                            '',
                            '20180101000000',
                            'Magazijn',
                            ' ',
                            'trtype-0',
                            '20',
                            None,
                            1,
                            1,
                        ],
                        ['', 'end-stock', '', '', '', '', 0, 1, 1],
                    ],
                },
                {
                    'article': '018064G',
                    'skuStockMatrix': [
                        [*headers, 'S', 'M', '#'],
                        ['Paars ', None, None, None, None, None, None, None, None],
                        [
                            '',
                            '20190620164903',
                            'Amstelveen',
                            ' ',
                            'trtype-3',
                            '20',
                            None,
                            -1,
                            -1,
                        ],
                        ['', 'end-stock', '', '', '', '', 0, -1, -1],
                    ],
                },
                {
                    'article': '018317G',
                    'skuStockMatrix': [
                        [*headers, 'ONE', '#'],
                        ['Paars ', None, None, None, None, None, None, None],
                        [
                            '',
                            '20190620171326',
                            'Amstelveen',
                            '11',
                            'trtype-2',
                            '20',
                            100,
                            100,
                        ],
                        ['', 'end-stock', '', '', '', '', 100, 100],
                    ],
                },
            ],
        }
    ]
    assert result == expected


def test_build_select(postgres_cursor):
    select = _build_select(['n_stock', 'collection', 'mcolor']).as_string(
        postgres_cursor
    )
    assert select == (
        ' SELECT sum("n_stock"+"n_bought") as "n_stock", '
        'COALESCE("season",\'\') || \'-\' || COALESCE("_year",\'\') as "collection", '
        '"mcolor" as "mcolor"'
    )


def test_group_by(postgres_cursor):
    group_by = _build_group_by(['n_stock', 'article', 'mcolor']).as_string(
        postgres_cursor
    )
    assert group_by == (' GROUP BY "article", "mcolor"')


def test_build_sort(postgres_cursor):
    sort = _build_sort(['supplier', ('warehouse', 'DESC')]).as_string(postgres_cursor)
    assert sort == (' ORDER BY "supplier" ASC, "warehouse" DESC')


def test_build(postgres_cursor):
    query = build(
        ['article', 'sizename', 'label', 'sizeidx', 'n_stock', 'collection'],
        {'tenant': 1},
        [('article', 'ASC'), ('sizeidx', 'ASC'), ('label', 'ASC')],
        0,
        100,
        limit=5000,
    ).as_string(postgres_cursor)
    expected = (
        ' SELECT "article" as "article", "sizename" as "sizename", '
        'COALESCE("color",\'\') || \' \' || COALESCE("scolor",\'\') || '
        '\'-LABEL_SEPARATOR-\' || COALESCE("klcode_lev",\'\') || \' \' || '
        'COALESCE("kl_lev",\'\') || \'-LABEL_SEPARATOR-\' || COALESCE("warehouse",\' '
        '\') as "label", "sizeidx" as "sizeidx", '
        'sum("n_stock"+"n_bought") as "n_stock", '
        'COALESCE("season",\'\') || \'-\' || COALESCE("_year",\'\') as "collection" '
        'FROM "transactions"  WHERE "tenant" = 1 AND "trtype" IN (0, 1, 2, 3, 4, 5, '
        '6, 8, 93) AND ("timestamp" >= 0 and "timestamp" <= 100) GROUP BY "article", '
        '"sizename", "color", "scolor", "kl_lev", "klcode_lev", "warehouse", '
        '"sizeidx", "season", "_year" ORDER BY "article" ASC, "sizeidx" ASC, "label" '
        'ASC LIMIT 5000'
    )
    assert query == expected


def test_build_history(postgres_cursor):
    query = build(
        ['article', 'sizename', 'label', 'sizeidx', 'n_stock', 'collection'],
        {'tenant': 1},
        [('article', 'ASC'), ('sizeidx', 'ASC'), ('label', 'ASC')],
        0,
        100,
        limit=5000,
        history=True,
    ).as_string(postgres_cursor)
    expected = (
        ' SELECT "article" as "article", "sizename" as "sizename",    '
        'COALESCE("color", \'\') || \' \' || COALESCE("scolor", \'\') || \' / \' || '
        'COALESCE("kl_lev", \'\') || \' / \' || COALESCE("klcode_lev", \'\') || '
        '\'-LABEL_SEPARATOR-\' || to_char(to_timestamp("from_time", '
        "'YYYYMMDDHH24MISS') at time zone 'UTC','YY-MM-DD HH:MI')|| "
        '\'-LABEL_SEPARATOR-\' || COALESCE("warehouse", \' \') || '
        '\'-LABEL_SEPARATOR-\' || COALESCE("agent", \' \') || \'-LABEL_SEPARATOR-\' '
        '|| COALESCE("trtype", 0) || \'-LABEL_SEPARATOR-\' || COALESCE("reference", '
        '\' \') as "label", "sizeidx" as "sizeidx", '
        'sum("n_stock"+"n_bought") as "n_stock", '
        'COALESCE("season",\'\') || \'-\' || COALESCE("_year",\'\') as "collection" '
        'FROM "transactions"  WHERE "tenant" = 1 AND "trtype" IN (0, 1, 2, 3, 4, 5, '
        '6, 8, 93, 14) AND ("timestamp" >= 0 and "timestamp" <= 100) GROUP BY '
        '"article", "sizename", "color", "scolor", "kl_lev", "klcode_lev", '
        '"warehouse", "kl_lev", "klcode_lev", "from_time", "agent", "trtype", '
        '"reference", "sizeidx", "season", "_year" ORDER BY "article" ASC, "sizeidx" '
        'ASC, "label" ASC LIMIT 5000'
    )
    assert query == expected


def test_to_query(postgres_cursor):
    data = StockFilter(context={'tenant_id': '1'}).load({})
    query = StockFilter.to_query(data).as_string(postgres_cursor)
    pattern = re.compile(r'SELECT DISTINCT \'(?P<key>\w+)\' as key')
    matches = pattern.findall(query)
    assert sorted(matches) == sorted(
        [
            'articleCode',
            'articleCodeSupplier',
            'articleDescription',
            'articleGroup1',
            'articleGroup2',
            'articleGroup3',
            'articleGroup4',
            'articleGroup5',
            'articleGroup6',
            'articleGroup7',
            'articleGroup8',
            'articleGroup9',
            'brand',
            'collection',
            'customGroupBy',
            'supplier',
            'warehouse',
        ]
    )
