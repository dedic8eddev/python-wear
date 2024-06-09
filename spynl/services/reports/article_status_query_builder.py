"""
This module implements a function which returns the query for an article status

report.
"""

from datetime import datetime

from psycopg2 import sql

from spynl.services.reports.utils import build_filter_values  # noqa: F401
from spynl.services.reports.utils import (
    _build_dependencies,
    _build_group_by,
    _build_select_column,
    _build_sort,
    _build_where,
)

T0 = 946684800

# These columns are aggregated over a period of time.
AGGREGATED = {
    'a_recieved',
    'a_transit',
    'a_change',
    # amount sold, including vat, discount is taken into account:
    # a_sold = sell * nsold - discount (in which discount is not a column)
    'a_sold',
    'a_stock',
    'c_sold',
    'a_sold',
    'a_sold_ex',
    'n_stock',
    'n_recieved',
    'n_transit',
    'n_change',
    'n_sold',  # number of items sold
    'n_diffX',
    'qty',
    'a_diffX',
    'a_prepick',
    'n_prepick',
    'a_prepick_retail',
    'n_prepick_retail',
    'n_presold',
    'a_presold',
    'sell',  # sell price (without discount), including vat
    'sell_ex_vat',
    'cost',
    'price',
    'n_bought',
    'a_bought',
    'max_turnover',
    'vat',
    'a_revalue',
    'last_received',
}

# These are computed columns along with their dependencies.
COMPUTED = {
    'end_stock': {
        'n_stock',
        'n_recieved',
        'n_transit',
        'n_change',
        'n_sold',
        'n_presold',
    },
    'a_end_stock': {
        'a_stock',
        'a_recieved',
        'a_transit',
        'a_change',
        'c_sold',
        'a_presold',
        'a_revalue',
    },
    'avg_stockX': {'n_stock', 'n_diffX'},
    'collection': {'_year', 'season'},
    'a_avg_stockX': {'a_stock', 'a_diffX'},
    'a_turnover_velocity': {'a_avg_stockX', 'c_sold'},
    'n_turnover_velocity': {'avg_stockX', 'n_sold'},
    'sellout_percentage': {'end_stock', 'n_sold'},
    'margin': {'a_sold_ex', 'c_sold'},
    'start_margin': {'sell_ex_vat', 'cost'},
    'profitability': {'a_sold_ex', 'c_sold', 'a_avg_stockX'},
    'net_profit': {'a_sold_ex', 'c_sold'},
    'roi': {'a_sold_ex', 'a_recieved', 'a_transit'},
    'amount_vat': {'a_sold', 'a_sold_ex'},
    'discount': {'a_sold_ex', 'max_turnover', 'vat'},
    'leakage': {'discount', 'max_turnover', 'vat'},
}

# super query is required if the dependencies of a computed field are also computed:
REQUIRE_SUPERQUERY = {key for key, value in COMPUTED.items() if value & COMPUTED.keys()}

# Any of these fields require a subquery
REQUIRE_SUBQUERY = COMPUTED.keys() | AGGREGATED


def _build_sum(column, t1, t2):
    """
    Format an aggregation of a column.

    sum(case
        when "timestamp" >= 946684800
            and "timestamp" <= 1526367020 then "n_stock"
        else 0
    end) as "n_stock"
    """
    template = sql.SQL(
        'sum(case when "timestamp" >= {t1} and "timestamp" <= {t2} '
        'then {result} else 0 end) as {column}'
    )
    if column == 'n_diffX':
        result = sql.SQL(
            '("n_recieved" + "n_transit" + "n_change" - "n_sold") '
            '* ({t2} - "timestamp")'
        ).format(t2=sql.Literal(t2))
    elif column == 'a_diffX':
        result = sql.SQL(
            '("a_recieved" + "a_transit" + "a_change" - "c_sold") '
            '* ({t2} - "timestamp")'
        ).format(t2=sql.Literal(t2))
    elif column == 'max_turnover':
        # TODO: Can probably be simplified to 'n_sold * sell_ex_vat'
        result = sql.SQL('100 * "n_sold" * "sell" / (100 + "vat")')
    elif column == 'a_prepick_retail':
        result = sql.Identifier('a_prepick')
    elif column == 'n_prepick_retail':
        result = sql.Identifier('n_prepick')
    else:
        result = sql.Identifier(column)

    return template.format(
        t1=sql.Literal(t1),
        t2=sql.Literal(t2),
        result=result,
        column=sql.Identifier(column),
    )


def _build_inner_selects(columns, t1, t2):
    """
    Format the inner selects
    SELECT "supplier",
        "tenantname",
        sum(case
            when "timestamp" >= 1526372935
                and "timestamp" <= 1526561011 then "n_recieved"
            else 0
        end) as "n_recieved",
        ...
    """

    selects = []
    for c in columns:
        if c in AGGREGATED:
            if c == 'last_received':
                selects.append(
                    sql.SQL(
                        'max(case when "timestamp" >= {t1} and "timestamp" <= {t2} and '
                        '"n_recieved" > 0 then "from_time" else NULL end) as '
                        '"last_received"'
                    ).format(
                        t1=sql.Literal(t1), t2=sql.Literal(t2), default=sql.Literal("")
                    )
                )
            elif c in ('a_stock', 'n_stock'):
                selects.append(_build_sum(c, T0, t1))
            else:
                selects.append(_build_sum(c, t1, t2))

        else:
            selects.append(sql.Identifier(c))
    return sql.SQL(' SELECT ') + sql.SQL(', ').join(selects)


def _build_super_selects(columns, t1, t2, aliases=None):
    """
    Format the super selects

    SELECT case
             when "end_stock" != 0
               then 100 * "n_sold" / ("n_sold" - "end_stock") else 0
             end as "sellout_percentage"
           case
             when "a_avg_stockX" != 0
               then (("c_sold" / "a_avg_stockX") * 31536000000) / 3 else 0
             end as "a_turnover_velocity"
    """
    if not aliases:
        aliases = {}
    selects = []

    SECONDS_IN_YEAR = 60 * 60 * 24 * 365

    for c in columns:
        alias = sql.Identifier(aliases.get(c, c))

        if c == 'a_turnover_velocity':
            selects.append(
                sql.SQL(
                    'case when "a_avg_stockX" != 0 then (("c_sold" / "a_avg_stockX") '
                    '* {seconds_in_year}) / {time} else 0 end as {alias}'
                ).format(
                    time=sql.Literal(t2 - t1),
                    alias=alias,
                    seconds_in_year=sql.Literal(SECONDS_IN_YEAR),
                )
            )

        elif c == 'n_turnover_velocity':
            selects.append(
                sql.SQL(
                    'case when "avg_stockX" != 0 then (("n_sold" / "avg_stockX") '
                    '* {seconds_in_year}) / {time} else 0 end as {alias}'
                ).format(
                    time=sql.Literal(t2 - t1),
                    alias=alias,
                    seconds_in_year=sql.Literal(SECONDS_IN_YEAR),
                )
            )

        elif c == 'sellout_percentage':
            selects.append(
                sql.SQL(
                    'case when ("end_stock" + "n_sold") != 0 then 100.0 * "n_sold" / '
                    '("n_sold" + "end_stock") else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'profitability':
            selects.append(
                sql.SQL(
                    'case when "a_avg_stockX" != 0 then (cast(100 as bigint) * '
                    '("a_sold_ex" - "c_sold")) / "a_avg_stockX" else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'leakage':
            # calculate leakage ex vat as a percentage of max-turnover
            selects.append(
                sql.SQL(
                    'case when "max_turnover" != 0 then '
                    '"discount" / "max_turnover" * 100 '
                    'else 0 end as {alias}'
                ).format(alias=alias)
            )

        else:
            selects.append(_build_select_column(c, aliases))

    return sql.SQL('SELECT ') + sql.SQL(', ').join(selects)


def _build_outer_selects(columns, t1, t2, aliases=None):
    """
    Format the outer selects

    SELECT ((2 * "n_stock" * 188076) + "n_diffX") / (2 * 188076) as "avg_stockX",
            "n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold" as
            "end_stock",
            "n_stock",
            "n_transit",
            "supplier",
            "n_sold",
            "n_change",
            "tenantname"
    """
    if not aliases:
        aliases = {}
    selects = []

    for c in columns:
        alias = sql.Identifier(aliases.get(c, c))

        if c == 'end_stock':
            selects.append(
                sql.SQL(
                    '"n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold" '
                    '- "n_presold" as {alias}'
                ).format(alias=alias)
            )

        elif c == 'avg_stockX':
            selects.append(
                sql.SQL(
                    '(1.0 * "n_stock" * {time} + "n_diffX") / {time} as {alias}'
                ).format(time=sql.Literal(t2 - t1), alias=alias)
            )

        elif c == 'a_end_stock':
            selects.append(
                sql.SQL(
                    '"a_stock" + "a_recieved" + "a_transit" + "a_change" + "a_revalue" '
                    '- "c_sold" - "a_presold" as {alias}'
                ).format(alias=alias)
            )

        elif c == 'a_avg_stockX':
            selects.append(
                sql.SQL(
                    '(1.0 * "a_stock" * {time} + "a_diffX") / {time} as {alias}'
                ).format(time=sql.Literal(t2 - t1), alias=alias)
            )

        elif c == 'margin':
            selects.append(
                sql.SQL(
                    'case when "a_sold_ex" != 0 then 100 * ("a_sold_ex" - "c_sold") / '
                    '"a_sold_ex" else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'start_margin':
            selects.append(
                sql.SQL(
                    'case when "sell_ex_vat" != 0 then 100 * '
                    '("sell_ex_vat" - "cost") / "sell_ex_vat" else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'net_profit':
            selects.append(
                sql.SQL('"a_sold_ex" - "c_sold" as {alias}').format(alias=alias)
            )

        elif c == 'roi':
            selects.append(
                sql.SQL('"a_sold_ex" - "a_recieved" + "a_transit" as {alias}').format(
                    alias=alias
                )
            )

        elif c == 'last_received':
            selects.append(
                sql.SQL(
                    'case when "last_received" IS NOT NULL then to_timestamp('
                    '"last_received", {dtformat}) at time zone \'UTC\' '
                    'else NULL end as {alias}'
                ).format(alias=alias, dtformat=sql.Literal('YYYYMMDDHH24MISS'))
            )

        elif c == 'cbirth':
            selects.append(
                sql.SQL(
                    'to_char(to_date("cbirth", {dtformat}), {f}) as {alias}'
                ).format(
                    alias=alias,
                    dtformat=sql.Literal('YYYYMMDD'),
                    f=sql.Literal('DD-MM-YYYY'),
                )
            )

        elif c == 'amount_vat':
            selects.append(
                sql.SQL('"a_sold" - "a_sold_ex" as {alias}').format(alias=alias)
            )

        elif c == 'discount':
            selects.append(
                sql.SQL('"max_turnover" - "a_sold_ex" as {alias}').format(alias=alias)
            )

        else:
            selects.append(_build_select_column(c, aliases))

    return sql.SQL('SELECT ') + sql.SQL(', ').join(selects)


def _build_middle_query(columns, where, t1, t2, aliases=None, filter_sales=False):
    """
    Build the middle query

    The query is at max two tiered

    * the innermost query calculates sums over columns within a specific
      timeframe. (aliased as inner)
    * the middle query uses these sums to calculate metrics using one of more
      of the above mentioned sums. (aliased as middle)

    SELECT "tenantname",
           "n_stock",
           "n_change",
           ((2 * "n_stock" * 188076) + "n_diffX") / (2 * 188076) as "avg_stockX",
           "n_sold",
           "n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold" as
           "end_stock",
           "n_transit",
           "supplier"
    FROM
      (SELECT sum(case
                      when "timestamp" >= 1526372935
                           and "timestamp" <= 1526561011 then "n_recieved"
                      else 0
                  end) as "n_recieved",
              sum(case
                      when "timestamp" >= 946684800
                           and "timestamp" <= 1526372935 then "n_stock"
                      else 0
                  end) as "n_stock",
              "tenantname",
              "supplier",
              ...

       WHERE "tenant" IN (1)
         AND "brand" = 'nike'
         AND "warehouse" IN (51,
                             52)
       GROUP BY "tenantname",
                "supplier"
       FROM transactions) as "inner"
    """
    # Start generating the query starting with the top level selects.
    query = _build_outer_selects(columns - REQUIRE_SUPERQUERY, t1, t2, aliases)
    where = _build_where(where) if where else sql.SQL('')

    if columns & REQUIRE_SUBQUERY:
        inner_columns = _build_dependencies(columns, COMPUTED)

        if filter_sales:
            inner_columns.add('n_sold')

        inner_query = _build_inner_query(inner_columns, where, t1, t2)

        query += sql.SQL(' FROM ({}) as "inner"').format(inner_query)

    # Otherwise we just query straight from the table
    else:
        query += sql.SQL(' FROM "transactions"') + where

    if filter_sales:
        query += sql.SQL(' WHERE "n_sold" != 0 ')

    return query


def _build_inner_query(columns, where, t1, t2):
    """
    Build the inner query

    * the innermost query calculates sums over columns within a specific
      timeframe. (aliased as inner)

    SELECT sum(case
                    when "timestamp" >= 1526372935
                         and "timestamp" <= 1526561011 then "n_recieved"
                    else 0
                end) as "n_recieved",
            sum(case
                    when "timestamp" >= 946684800
                         and "timestamp" <= 1526372935 then "n_stock"
                    else 0
                end) as "n_stock",
            "tenantname",
            "supplier",
            ...

    WHERE "tenant" IN (1)
      AND "brand" = 'nike'
      AND "warehouse" IN (51,
                          52)
    GROUP BY "tenantname",
             "supplier"
    FROM transactions
    """
    inner_columns = _build_dependencies(columns, COMPUTED)

    query = (
        _build_inner_selects(inner_columns, t1, t2)
        + sql.SQL(' FROM "transactions"')
        + where
    )

    # any keys not aggregated or computed need to be part of
    # the group by clause.
    group_by = inner_columns - (AGGREGATED | COMPUTED.keys())
    if group_by:
        query += _build_group_by(group_by)

    return query


def build(columns, where, sort, t1, t2, aliases=None, limit=None, filter_sales=False):
    """
    Build the full query.

    The query is at max three tiered

    * the innermost query calculates sums over columns within a specific
      timeframe. (aliased as inner)
    * the middle query uses these sums to calculate metrics using one of more
      of the above mentioned sums. (aliased as middle)
    * the outermost query calculates metrics using the metrics in the middle
      query.

    SELECT
         case
           when "avg_stockX" != 0
             then (("n_sold" / "avg_stockX") * 31536000000 / 188076
           else 0
           end as "n_turnover_velocity",
         "n_stock",
         "n_change",
         "n_sold",
         "n_transit",
         "supplier",
         "end_stock",
    FROM
      (SELECT "tenantname",
             "n_stock",
             "n_change",
             ((2 * "n_stock" * 188076) + "n_diffX") / (2 * 188076) as "avg_stockX",
             "n_sold",
             "n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold"
             as "end_stock",
             "n_transit",
             "supplier"
      FROM
        (SELECT sum(case
                        when "timestamp" >= 1526372935
                             and "timestamp" <= 1526561011 then "n_recieved"
                        else 0
                    end) as "n_recieved",
                sum(case
                        when "timestamp" >= 946684800
                             and "timestamp" <= 1526372935 then "n_stock"
                        else 0
                    end) as "n_stock",
                "tenantname",
                "supplier",
                ...

         WHERE "tenant" IN (1)
           AND "brand" = 'nike'
           AND "warehouse" IN (51,
                               52)
         GROUP BY "tenantname",
                  "supplier"
         FROM "transactions") as "inner") as "middle)
    ORDER BY "tenantname" ASC,
             "n_sold" DESC

    """
    if isinstance(t1, datetime):
        t1 = int(t1.timestamp())

    if isinstance(t2, datetime):
        t2 = int(t2.timestamp())

    if REQUIRE_SUPERQUERY & columns:
        query = _build_super_selects(columns, t1, t2, aliases)
        # the middle query needs to query everything that is not strictly an
        # aggregration on the outermost level (meaning actual columns, and mid
        # level computations)
        middle_columns = _build_dependencies(columns, COMPUTED) | (
            columns - REQUIRE_SUPERQUERY
        )

        middle_query = _build_middle_query(
            middle_columns, where, t1, t2, filter_sales=filter_sales
        )
        query += sql.SQL(' FROM ({}) as "middle"').format(middle_query)
    else:
        query = _build_middle_query(
            columns, where, t1, t2, aliases=aliases, filter_sales=filter_sales
        )

    # Append the sort
    if sort:
        query += _build_sort(sort, aliases)

    if limit:
        query += sql.SQL(' LIMIT {}').format(sql.Literal(limit))

    return query
