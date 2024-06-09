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

# These are computed columns along with their dependencies.
COMPUTED = {
    'collection': {'_year', 'season'},
    'qty_del_per': {'qty_ex_cancelled', 'n_presold'},
    'value_del_per': {'value_ex_cancelled', 'a_presold'},
    'qty_post_del_per': {'qty_ex_cancelled', 'n_sold'},
    'value_post_del_per': {'value_ex_cancelled', 'a_sold'},
    'qty_returned_per': {'n_return', 'qty_ex_cancelled'},
    'value_returned_per': {'a_return', 'value_ex_cancelled'},
    'qty_picklist_per': {'qty_picklist', 'qty_ex_cancelled'},
    'value_picklist_per': {'value_picklist', 'value_ex_cancelled'},
}


# These columns are aggregated over a period of time.
AGGREGATED = {
    'n_sold',
    'n_presold',
    'a_sold',
    'a_presold',
    'qty',
    'value',
    'qty_ex_cancelled',
    'value_ex_cancelled',
    'qty_picklist',
    'value_picklist',
    'n_return',
    'a_return',
}


def _build_sum(alias, t1, t2):
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
        'then {result} else 0 end) as {alias}'
    )

    if alias == 'qty':
        result = sql.SQL(' "n_ordered" + "n_preord" ')
    elif alias == 'value':
        result = sql.SQL(' "a_ordered" + "a_preord" ')
    elif alias in 'qty_ex_cancelled':
        result = sql.SQL(
            'case when {column} = {value} then "n_ordered" + "n_preord" else 0 end '
        ).format(
            alias=alias, column=sql.Identifier('astate'), value=sql.Literal('active')
        )
    elif alias == 'value_ex_cancelled':
        result = sql.SQL(
            'case when {column} = {value} then "a_ordered" + "a_preord" else 0 end '
        ).format(
            alias=alias, column=sql.Identifier('astate'), value=sql.Literal('active')
        )
    elif alias == 'qty_picklist':
        result = sql.SQL(' "n_picked" + "n_prepick" ')
    elif alias == 'value_picklist':
        result = sql.SQL(' "a_picked" + "a_prepick" ')
    else:
        result = sql.Identifier(alias)

    return template.format(
        t1=sql.Literal(t1),
        t2=sql.Literal(t2),
        result=result,
        alias=sql.Identifier(alias),
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
            selects.append(_build_sum(c, t1, t2))
        else:
            selects.append(sql.Identifier(c))
    return sql.SQL(' SELECT ') + sql.SQL(', ').join(selects)


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

        if c == 'qty_del_per':
            selects.append(
                sql.SQL(
                    'case when "qty_ex_cancelled" != 0 then'
                    '("n_presold" / "qty_ex_cancelled") * 100.0 '
                    'else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'qty_post_del_per':
            selects.append(
                sql.SQL(
                    'case when "qty_ex_cancelled" != 0 then'
                    '("n_sold" / "qty_ex_cancelled") * 100.0 '
                    'else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'qty_returned_per':
            selects.append(
                sql.SQL(
                    'case when "qty_ex_cancelled" < 0 then '
                    '("n_return" / "qty_ex_cancelled")'
                    '* 100.0 else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'value_del_per':
            selects.append(
                sql.SQL(
                    'case when "value_ex_cancelled" != 0 then '
                    '("a_presold" / "value_ex_cancelled") * 100 '
                    'else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'value_post_del_per':
            selects.append(
                sql.SQL(
                    'case when "value_ex_cancelled" != 0 then '
                    '("a_sold" / "value_ex_cancelled") * 100 '
                    'else 0 end as {alias}'
                ).format(alias=alias)
            )

        elif c == 'value_returned_per':
            selects.append(
                sql.SQL(
                    'case when "value_ex_cancelled" < 0 then '
                    '("a_return" / "value_ex_cancelled") * 100 else '
                    '0 end as {alias}'
                ).format(alias=alias)
            )
        elif c == 'qty_picklist_per':
            selects.append(
                sql.SQL(
                    'case when "qty_ex_cancelled" < 0 then '
                    '("qty_picklist" / "qty_ex_cancelled") * 100.0 else '
                    '0 end as {alias}'
                ).format(alias=alias)
            )
        elif c == 'value_picklist_per':
            selects.append(
                sql.SQL(
                    'case when "value_ex_cancelled" < 0 then '
                    '("value_picklist" / "value_ex_cancelled") * 100.0 else '
                    '0 end as {alias}'
                ).format(alias=alias)
            )
        else:
            selects.append(_build_select_column(c, aliases))

    return sql.SQL('SELECT ') + sql.SQL(', ').join(selects)


def _build_inner_query(columns, where, t1, t2):
    query = _build_inner_selects(columns, t1, t2)
    group_by = columns - (AGGREGATED | COMPUTED.keys())
    query += sql.SQL(' FROM "transactions"')
    query += _build_where(where) if where else sql.SQL('')
    if group_by:
        query += _build_group_by(group_by)
    return query


def build(columns, where, sort, t1, t2, aliases=None):
    if isinstance(t1, datetime):
        t1 = int(t1.timestamp())

    if isinstance(t2, datetime):
        t2 = int(t2.timestamp())

    dependencies = _build_dependencies(columns, COMPUTED)
    # if dependencies == columns:
    #     return _build_inner_query(columns, where, t1, t2)

    inner_query = _build_inner_query(dependencies, where, t1, t2)
    query = _build_outer_selects(columns, t1, t2, aliases)
    query += sql.SQL(' FROM ({}) as "inner"').format(inner_query)

    # Append the sort
    if sort:
        query += _build_sort(sort, aliases)

    return query
