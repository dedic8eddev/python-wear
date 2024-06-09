import re

import pytest

from spynl.services.reports.article_status_query_builder import (
    COMPUTED,
    _build_dependencies,
    _build_group_by,
    _build_inner_selects,
    _build_outer_selects,
    _build_sort,
    _build_sum,
    _build_super_selects,
    _build_where,
    build,
)


def test_build_dependencies():
    assert _build_dependencies({'end_stock', 'avg_stockX', 'collection'}, COMPUTED) == {
        'n_stock',
        'n_recieved',
        'n_transit',
        'n_change',
        'n_sold',
        'n_stock',
        'n_recieved',
        'n_transit',
        'n_change',
        'n_sold',
        'n_diffX',
        '_year',
        'season',
        'n_presold',
    }


def test_sort_single(postgres_cursor):
    result = _build_sort([('field1', 'ASC')])
    assert result.as_string(postgres_cursor) == ' ORDER BY "field1" ASC'


def test_sort(postgres_cursor):
    result = _build_sort([('field1', 'ASC'), ('field2', 'DESC'), 'field3'])
    assert (
        result.as_string(postgres_cursor)
        == ' ORDER BY "field1" ASC, "field2" DESC, "field3" ASC'
    )


def test_group_by(postgres_cursor):
    result = _build_group_by({'field1', 'field2'})
    # it doesn't preserve order so check both possibilities
    assert result.as_string(postgres_cursor) in [
        ' GROUP BY "field1", "field2"',
        ' GROUP BY "field2", "field1"',
    ]


def test_where_empty_values(postgres_cursor):
    result = _build_where({'y': '', 'x': {}, 'z': []}).as_string(postgres_cursor)
    assert result == ' WHERE "y" = \'\''


def test_where_clause(postgres_cursor):
    result = _build_where(
        {'tenant': [1], 'brand': 'nike', 'warehouse': [51, 52]}
    ).as_string(postgres_cursor)
    # it doesn't preserve order so check all is present
    assert result.startswith(' WHERE ') and {
        '"brand" = \'nike\'',
        '"warehouse" IN (51, 52)',
        '"tenant" IN (1)',
    } == set(result[7:].split(' AND '))


def test_where_clause_nested(postgres_cursor):
    result = _build_where(
        {
            'tenant': [1],
            'brand': 'nike',
            'collection': {'_year': '18', 'season': 'zomer'},
        }
    ).as_string(postgres_cursor)
    # it doesn't preserve order so check all is present
    assert result.startswith(' WHERE ') and {
        '"brand" = \'nike\'',
        '"tenant" IN (1)',
        '"_year" = \'18\'',
        '"season" = \'zomer\'',
    } == set(result[7:].split(' AND '))


def test_where_clause_nested_list(postgres_cursor):
    result = _build_where(
        {
            'tenant': [1],
            'brand': 'nike',
            'collection': [
                {'_year': '18', 'season': 'zomer'},
                {'_year': '16', 'season': 'winter'},
            ],
        }
    ).as_string(postgres_cursor)
    # it doesn't preserve order so check all is present
    assert result.startswith(' WHERE ') and {
        '"brand" = \'nike\'',
        '"tenant" IN (1)',
        '(("_year" = \'18\' AND "season" = \'zomer\') OR '
        '("_year" = \'16\' AND "season" = \'winter\'))',
    } == set(result[7:].split(' AND ', 2))


@pytest.mark.parametrize(
    'input,expected',
    [
        (
            ('a_recieved', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
                '"a_recieved" else 0 end) as "a_recieved"'
            ),
        ),
        (
            ('n_diffX', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
                '("n_recieved" + "n_transit" + "n_change" - "n_sold") * '
                '(1 - "timestamp") else 0 end) as "n_diffX"'
            ),
        ),
        (
            ('a_diffX', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
                '("a_recieved" + "a_transit" + "a_change" - "c_sold") * '
                '(1 - "timestamp") else 0 end) as "a_diffX"'
            ),
        ),
        (
            ('max_turnover', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then 100 * '
                '"n_sold" * "sell" / (100 + "vat") else 0 end) as "max_turnover"'
            ),
        ),
        (
            ('a_prepick_retail', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
                '"a_prepick" else 0 end) as "a_prepick_retail"'
            ),
        ),
        (
            ('n_prepick_retail', 0, 1),
            (
                'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
                '"n_prepick" else 0 end) as "n_prepick_retail"'
            ),
        ),
    ],
)
def test_sum(input, expected, postgres_cursor):
    assert _build_sum(*input).as_string(postgres_cursor) == expected


def test_build_inner_selects(postgres_cursor):
    result = (
        _build_inner_selects(
            {  # special handling in build inner:
                'last_received',
                'a_stock',
                'n_stock',
                # special handling in build sum:
                'n_diffX',
                # no special handling:
                'n_recieved',
                'n_transit',
                'n_change',
                'n_sold',
                'n_stock',
                'n_recieved',
                'n_transit',
                'n_change',
                'n_sold',
                'a_sold_ex',
                # not aggregated:
                'tenantname',
                'supplier',
            },
            0,
            1,
        )
        .as_string(postgres_cursor)
        .strip()
        .replace('SELECT ', '')
        .split(', ')
    )

    selects = {
        (
            'max(case when "timestamp" >= 0 and "timestamp" <= 1 and "n_recieved" > 0 '
            'then "from_time" else NULL end) as "last_received"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 0 then '
            '"n_stock" else 0 end) as "n_stock"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 0 then '
            '"a_stock" else 0 end) as "a_stock"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '"n_recieved" else 0 end) as "n_recieved"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '"n_transit" else 0 end) as "n_transit"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '"n_sold" else 0 end) as "n_sold"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '("n_recieved" + "n_transit" + "n_change" - "n_sold") * '
            '(1 - "timestamp") else 0 end) as "n_diffX"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '"n_change" else 0 end) as "n_change"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 1 then '
            '"a_sold_ex" else 0 end) as "a_sold_ex"'
        ),
        '"tenantname"',
        '"supplier"',
    }
    assert selects == set(result)


def test_super_selects(postgres_cursor):
    result = (
        _build_super_selects(
            {
                'a_turnover_velocity',
                'n_turnover_velocity',
                'sellout_percentage',
                'profitability',
                'leakage',
            },
            1,
            4,
        )
        .as_string(postgres_cursor)
        .strip()
        .replace('SELECT ', '')
        .split(', ')
    )

    selects = {
        (
            'case when ("end_stock" + "n_sold") != 0 then 100.0 * "n_sold" / '
            '("n_sold" + "end_stock") else 0 end as "sellout_percentage"'
        ),
        (
            'case when "a_avg_stockX" != 0 then (("c_sold" / "a_avg_stockX") '
            '* 31536000) / 3 else 0 end as "a_turnover_velocity"'
        ),
        (
            'case when "a_avg_stockX" != 0 then (cast(100 as bigint) * '
            '("a_sold_ex" - "c_sold")) '
            '/ "a_avg_stockX" else 0 end as "profitability"'
        ),
        (
            'case when "avg_stockX" != 0 then (("n_sold" / "avg_stockX") * '
            '31536000) / 3 else 0 end as "n_turnover_velocity"'
        ),
        (
            'case when "max_turnover" != 0 then "discount" / "max_turnover" * 100 '
            'else 0 end as "leakage"'
        ),
    }
    assert selects == set(result)


def test_outer_selects(postgres_cursor):
    result = (
        _build_outer_selects(
            {
                'end_stock',
                'avg_stockX',
                'a_end_stock',
                'a_avg_stockX',
                'margin',
                'net_profit',
                'roi',
                'amount_vat',
                # no special handling:
                'supplier',
                'n_stock',
            },
            1,
            4,
        )
        .as_string(postgres_cursor)
        .strip()
        .replace('SELECT ', '')
        .split(', ')
    )

    selects = {
        '(1.0 * "a_stock" * 3 + "a_diffX") / 3 as "a_avg_stockX"',
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "avg_stockX"',
        '"supplier" as "supplier"',
        '"n_stock" as "n_stock"',
        '"a_sold_ex" - "c_sold" as "net_profit"',
        '"a_sold_ex" - "a_recieved" + "a_transit" as "roi"',
        '"a_sold" - "a_sold_ex" as "amount_vat"',
        (
            '"n_stock" + "n_recieved" + "n_transit" + "n_change" - '
            '"n_sold" - "n_presold" as "end_stock"'
        ),
        (
            '"a_stock" + "a_recieved" + "a_transit" + "a_change" '
            '+ "a_revalue" - "c_sold" - "a_presold" as "a_end_stock"'
        ),
        (
            'case when "a_sold_ex" != 0 then 100 * ("a_sold_ex" - "c_sold") '
            '/ "a_sold_ex" else 0 end as "margin"'
        ),
    }
    assert selects == set(result)


@pytest.mark.parametrize(
    'input,expected',
    [
        (
            'last_received',
            (
                'case when "last_received" IS NOT NULL then '
                'to_timestamp("last_received", \'YYYYMMDDHH24MISS\') at time zone '
                '\'UTC\' else NULL end as "last_received"'
            ),
        ),
        (
            'cbirth',
            'to_char(to_date("cbirth", \'YYYYMMDD\'), \'DD-MM-YYYY\') as "cbirth"',
        ),
        (
            'discount',
            '"max_turnover" - "a_sold_ex" as "discount"',
        ),
        (
            'start_margin',
            (
                'case when "sell_ex_vat" != 0 then 100 * ("sell_ex_vat" - "cost") / '
                '"sell_ex_vat" else 0 end as "start_margin"'
            ),
        ),
    ],
)
def test_outer_selects_2(postgres_cursor, input, expected):
    """
    The above test does not work for statements including commas, this is a nicer way,
    so new fields get added here.
    """
    result = (
        _build_outer_selects({input}, 1, 4)
        .as_string(postgres_cursor)
        .strip()
        .replace('SELECT ', '')
    )

    assert result == expected


def test_outer_selects_with_aliases(postgres_cursor):
    result = (
        _build_outer_selects(
            {'avg_stockX', 'end_stock', 'supplier', 'n_stock'},
            1,
            4,
            aliases={'avg_stockX': 'Average stock'},
        )
        .as_string(postgres_cursor)
        .strip()
        .replace('SELECT ', '')
        .split(', ')
    )

    selects = {
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "Average stock"',
        '"supplier" as "supplier"',
        '"n_stock" as "n_stock"',
        (
            '"n_stock" + "n_recieved" + "n_transit" + "n_change" - '
            '"n_sold" - "n_presold" as "end_stock"'
        ),
    }
    assert selects == set(result)


def test_build(postgres_cursor):
    result = build(
        {
            'leakage',
            'discount',
            'tenantname',
            'end_stock',
            'avg_stockX',
            'supplier',
            'a_turnover_velocity',
        },
        {'tenant': [1], 'brand': 'nike', 'warehouse': ['51', '52']},
        [('tenantname', 'ASC'), ('n_sold', 'DESC')],
        1,
        4,
        {'avg_stockX': 'Average stock'},
        filter_sales=True,
        limit=5000,
    ).as_string(postgres_cursor)

    pattern = re.compile(
        r'SELECT (?P<super_selects>.*) FROM \('
        r'SELECT (?P<outer_select>.*) FROM \( '
        r'SELECT (?P<inner_select>.*)'
        r'FROM "transactions" '
        r'WHERE (?P<where>.*)'
        r'GROUP BY(?P<group_by>.*)\) as "inner" WHERE "n_sold" != 0 \) as "middle" '
        r'ORDER BY(?P<order>.*)'
        r'LIMIT(?P<limit>.*)'
    )
    matches = pattern.search(result)
    assert matches

    assert set(matches['super_selects'].strip().split(', ')) == {
        '"avg_stockX" as "Average stock"',
        '"tenantname" as "tenantname"',
        '"end_stock" as "end_stock"',
        '"supplier" as "supplier"',
        'case when "a_avg_stockX" != 0 then (("c_sold" / "a_avg_stockX") * '
        '31536000) / 3 else 0 end as "a_turnover_velocity"',
        '"discount" as "discount"',
        (
            'case when "max_turnover" != 0 then "discount" / "max_turnover" * 100 '
            'else 0 end as "leakage"'
        ),
    }
    assert set(matches['outer_select'].strip().split(', ')) == {
        '(1.0 * "a_stock" * 3 + "a_diffX") / 3 as "a_avg_stockX"',
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "avg_stockX"',
        '"c_sold" as "c_sold"',
        '"n_diffX" as "n_diffX"',
        '"max_turnover" as "max_turnover"',
        '"a_sold_ex" as "a_sold_ex"',
        '"n_sold" as "n_sold"',
        '"n_change" as "n_change"',
        '"tenantname" as "tenantname"',
        '"n_transit" as "n_transit"',
        '"n_stock" as "n_stock"',
        '"n_recieved" as "n_recieved"',
        '"supplier" as "supplier"',
        '"n_presold" as "n_presold"',
        '"vat" as "vat"',
        '"max_turnover" - "a_sold_ex" as "discount"',
        (
            '"n_stock" + "n_recieved" + "n_transit" + "n_change" - '
            '"n_sold" - "n_presold" as "end_stock"'
        ),
    }

    assert set(matches['inner_select'].strip().split(', ')) == {
        '"supplier"',
        '"tenantname"',
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_presold" else 0 end) as "n_presold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_recieved" else 0 end) as "n_recieved"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 1 then '
            '"n_stock" else 0 end) as "n_stock"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_sold" else 0 end) as "n_sold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_transit" else 0 end) as "n_transit"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '("n_recieved" + "n_transit" + "n_change" - "n_sold") * '
            '(4 - "timestamp") else 0 end) as "n_diffX"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_change" else 0 end) as "n_change"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"c_sold" else 0 end) as "c_sold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '("a_recieved" + "a_transit" + "a_change" - "c_sold") * '
            '(4 - "timestamp") else 0 end) as "a_diffX"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 1 '
            'then "a_stock" else 0 end) as "a_stock"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"a_sold_ex" else 0 end) as "a_sold_ex"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '100 * "n_sold" * "sell" / (100 + "vat") else 0 end) as "max_turnover"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then "vat" else 0 '
            'end) as "vat"'
        ),
    }
    assert set(matches['where'].strip().split(' AND ')) == {
        '"brand" = \'nike\'',
        '"warehouse" IN (\'51\', \'52\')',
        '"tenant" IN (1)',
    }
    assert set(matches['group_by'].strip().split(', ')) == {
        '"supplier"',
        '"tenantname"',
    }
    assert set(matches['order'].strip().split(', ')) == {
        '"tenantname" ASC',
        '"n_sold" DESC',
    }
    assert matches['limit'].strip() == '5000'


def test_build_without_super(postgres_cursor):
    result = build(
        set('max_turnover end_stock avg_stockX supplier'.split()),
        {'tenant': [1], 'brand': 'nike', 'warehouse': [51, 52]},
        [('tenantname', 'ASC'), ('n_sold', 'DESC')],
        1,
        4,
        {'avg_stockX': 'Average stock'},
        limit=5000,
    ).as_string(postgres_cursor)

    pattern = re.compile(
        r'SELECT (?P<outer_select>.*) FROM \( '
        r'SELECT (?P<inner_select>.*)'
        r'FROM "transactions" '
        r'WHERE (?P<where>.*)'
        r'GROUP BY(?P<group_by>.*)\) as "inner" '
        r'ORDER BY(?P<order>.*)'
        r'LIMIT(?P<limit>.*)'
    )
    matches = pattern.search(result)
    assert matches
    assert set(matches['outer_select'].strip().split(', ')) == {
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "Average stock"',
        '"supplier" as "supplier"',
        '"max_turnover" as "max_turnover"',
        (
            '"n_stock" + "n_recieved" + "n_transit" + "n_change" - '
            '"n_sold" - "n_presold" as "end_stock"'
        ),
    }
    assert set(matches['inner_select'].strip().split(', ')) == {
        '"supplier"',
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_presold" else 0 end) as "n_presold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_recieved" else 0 end) as "n_recieved"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 1 then '
            '"n_stock" else 0 end) as "n_stock"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_sold" else 0 end) as "n_sold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_transit" else 0 end) as "n_transit"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '("n_recieved" + "n_transit" + "n_change" - "n_sold") * '
            '(4 - "timestamp") else 0 end) as "n_diffX"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_change" else 0 end) as "n_change"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '100 * "n_sold" * "sell" / (100 + "vat") else 0 end) as "max_turnover"'
        ),
    }
    assert set(matches['where'].strip().split(' AND ')) == {
        '"brand" = \'nike\'',
        '"warehouse" IN (51, 52)',
        '"tenant" IN (1)',
    }
    assert matches['group_by'].strip() == '"supplier"'
    assert set(matches['order'].strip().split(', ')) == {
        '"tenantname" ASC',
        '"n_sold" DESC',
    }
    assert matches['limit'].strip() == '5000'


def test_build_without_inner(postgres_cursor):
    result = build(
        set('supplier tenantname'.split()),
        {'tenant': [1], 'brand': 'nike', 'warehouse': [51, 52]},
        [('tenantname', 'ASC')],
        1,
        4,
        {'avg_stockX': 'Average stock'},
        limit=5000,
    ).as_string(postgres_cursor)

    pattern = re.compile(
        r'SELECT (?P<select>.*)'
        'FROM "transactions" '
        'WHERE (?P<where>.*)'
        'ORDER BY(?P<order>.*)'
        r'LIMIT(?P<limit>.*)'
    )
    matches = pattern.search(result)
    assert matches
    assert set(matches['select'].strip().split(', ')) == {
        '"supplier" as "supplier"',
        '"tenantname" as "tenantname"',
    }
    assert set(matches['where'].strip().split(' AND ')) == {
        '"brand" = \'nike\'',
        '"warehouse" IN (51, 52)',
        '"tenant" IN (1)',
    }
    assert matches['order'].strip() == '"tenantname" ASC'
    assert matches['limit'].strip() == '5000'
