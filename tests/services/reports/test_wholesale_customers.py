"""
EXAMPLE QUERY

SELECT "ccountry" as "customerCountry",
       COALESCE("season", '') || '-' || COALESCE("_year", '') as "collection",
       "brand" as "brand",
       "aatr3" as "articleGroup3",
       case
           when "qty_ex_cancelled" != 0 then("n_presold" / "qty_ex_cancelled") * 100.0
           else 0
       end as "qtyDeliveredPercentage",
       "catr1" as "customerGroup1",
       case
           when "qty_ex_cancelled" < 0 then
               ("qty_picklist" / "qty_ex_cancelled") * 100.0
           else 0
       end as "qtyPicklistPer",
       "cbscode" as "cbs",
       "value_ex_cancelled" as "valueOrderExcludingCancelled",
       "a_return" as "valueReturned",
       "klcode_lev" as "colorCodeSupplier",
       "a_presold" as "valueDelivered",
       case
           when "qty_ex_cancelled" != 0 then("n_sold" / "qty_ex_cancelled") * 100.0
           else 0
       end as "qtyPostDeliveryPercentage",
       "sizename" as "size",
       "catr2" as "customerGroup2",
       "n_sold" as "qtyPostDelivery",
       "mcolor" as "colorCode",
       "a_sold" as "valuePostDelivery",
       "n_return" as "qtyReturned",
       "cname" as "customerName",
       "aatr2" as "articleGroup2",
       "qty" as "qty",
       "aatr6" as "articleGroup6",
       case
           when "value_ex_cancelled" != 0 then ("a_sold" / "value_ex_cancelled") * 100
           else 0
       end as "valuePostDeliveryPercentage",
       "catr3" as "customerGroup3",
       "qty_picklist" as "qtyPicklist",
       "mcolordesc" as "color",
       "ccity" as "customerCity",
       "n_presold" as "qtyDelivered",
       case
           when "value_ex_cancelled" < 0 then ("a_return" / "value_ex_cancelled") * 100
           else 0
       end as "valueReturnedPercentage",
       "czip" as "customerPostalCode",
       "aatr1" as "articleGroup1",
       case
           when "qty_ex_cancelled" < 0 then ("n_return" / "qty_ex_cancelled")* 100.0
           else 0
       end as "qtyReturnedPercentage",
       "value_picklist" as "valuePicklist",
       "aatr7" as "articleGroup7",
       "aatr5" as "articleGroup5",
       "value" as "value",
       "agent" as "agent",
       "aatr4" as "articleGroup4",
       case
           when "value_ex_cancelled" < 0 then
               ("value_picklist" / "value_ex_cancelled") * 100.0
           else 0
       end as "valuePicklistPer",
       "aatr8" as "articleGroup8",
       case
           when "value_ex_cancelled" != 0 then
               ("a_presold" / "value_ex_cancelled") * 100
           else 0
       end as "valueDeliveredPercentage",
       "aatr9" as "articleGroup9",
       "qty_ex_cancelled" as "qtyOrderExcludingCancelled",
       "kl_lev" as "colorDescSupplier",
       "article" as "articleCode"
FROM
  (SELECT "ccountry",
          "brand",
          "aatr3",
          "catr1",
          "cbscode",
          sum(case
            when "timestamp" >= 1287525600
                and "timestamp" <= 1916085600 then
                    case when "astate" = 'active' then "qty" else 0
                end
            else 0
              end) as "value_ex_cancelled",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "a_return"
                  else 0
              end) as "a_return",
          "klcode_lev",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "a_presold"
                  else 0
              end) as "a_presold",
          "sizename",
          "catr2",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "n_sold"
                  else 0
              end) as "n_sold",
          "mcolor",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "a_sold"
                  else 0
              end) as "a_sold",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "n_return"
                  else 0
              end) as "n_return",
          "cname",
          "aatr2",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "n_ordered" + "n_preord"
                  else 0
              end) as "qty",
          "aatr6",
          "catr3",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "n_picked" + "n_prepick"
                  else 0
              end) as "qty_picklist",
          "mcolordesc",
          "ccity",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "n_presold"
                  else 0
              end) as "n_presold",
          "_year",
          "czip",
          "aatr1",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "a_picked" + "a_prepick"
                  else 0
              end) as "value_picklist",
          "aatr7",
          "aatr5",
          sum(case
                  when "timestamp" >= 1287525600
                       and "timestamp" <= 1916085600 then "a_ordered" + "a_preord"
                  else 0
              end) as "value",
          "agent",
          "aatr4",
          "aatr8",
          "aatr9",
          "season",
          sum(case
                when "timestamp" >= 1287525600 and "timestamp" <= 1916085600 then
                    case when "astate" = 'active' then "qty" else 0 end
                else 0 end) as "qty_ex_cancelled",
          "kl_lev",
          "article"
   FROM "transactions"
   WHERE "tenant" IN (91773)
   GROUP BY "ccountry",
            "aatr3",
            "brand",
            "catr1",
            "cbscode",
            "klcode_lev",
            "catr2",
            "sizename",
            "mcolor",
            "cname",
            "aatr2",
            "aatr6",
            "catr3",
            "mcolordesc",
            "ccity",
            "_year",
            "czip",
            "aatr1",
            "aatr7",
            "aatr5",
            "agent",
            "aatr4",
            "aatr8",
            "aatr9",
            "season",
            "kl_lev",
            "article") as "inner"
"""
import os
import re

import pytest

from spynl.api.auth.testutils import mkuser

from spynl.services.reports.utils import debug_query
from spynl.services.reports.wholesale_customer_query_builder import build
from spynl.services.reports.wholesale_customer_sales import COLUMNS

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


@pytest.fixture()
def setup_db(db, app):
    db.tenants.insert_one(
        {
            '_id': '91537',
            'applications': ['dashboard'],
            'settings': {
                'logoUrl': {
                    'medium': 'file://{}/examples/square_logo.png'.format(BASE_DIR)
                }
            },
            'name': 'Testing Tenant',
            'addresses': [
                {
                    'address': 'street street 1',
                    'zipcode': '1000 AB',
                    'city': 'The City',
                    'country': 'Nederland',
                    'primary': True,
                }
            ],
        }
    )
    mkuser(
        db,
        'reports_user',
        'bla',
        ['91537'],
        language='nl-nl',
        tenant_roles={'91537': ['dashboard-report_user']},
    )
    app.post_json('/login', {'username': 'reports_user', 'password': 'bla'})
    yield
    app.get('/logout')


def test_build(postgres_cursor):
    query = build(
        {c.column_name for c in COLUMNS}, {'tenant': 1}, [('a_sold', 'ASC')], 0, 2
    ).as_string(postgres_cursor)
    pattern = re.compile(
        r'SELECT (?P<outer_select>.*) FROM \( '
        r'SELECT (?P<inner_select>.*)'
        r'FROM "transactions" '
        r'WHERE (?P<where>.*)'
        r'GROUP BY(?P<group_by>.*)\) as "inner" '
        r'ORDER BY(?P<order_by>.*)'
    )
    matches = pattern.search(query)
    assert matches
    debug_query(postgres_cursor, query)
    assert set(matches['outer_select'].strip().split(', ')) == {
        '"a_presold" as "a_presold"',
        '"a_sold" as "a_sold"',
        '"aatr1" as "aatr1"',
        '"aatr2" as "aatr2"',
        '"aatr3" as "aatr3"',
        '"aatr4" as "aatr4"',
        '"aatr5" as "aatr5"',
        '"aatr6" as "aatr6"',
        '"aatr7" as "aatr7"',
        '"aatr8" as "aatr8"',
        '"aatr9" as "aatr9"',
        '"agent" as "agent"',
        '"article" as "article"',
        '"brand" as "brand"',
        '"catr1" as "catr1"',
        '"catr2" as "catr2"',
        '"catr3" as "catr3"',
        '"ccity" as "ccity"',
        '"ccountry" as "ccountry"',
        '"cname" as "cname"',
        '"czip" as "czip"',
        '"kl_lev" as "kl_lev"',
        '"klcode_lev" as "klcode_lev"',
        '"mcolor" as "mcolor"',
        '"mcolordesc" as "mcolordesc"',
        '"n_presold" as "n_presold"',
        '"n_sold" as "n_sold"',
        '"qty" as "qty"',
        '"sizename" as "sizename"',
        '"value" as "value"',
        '"cbscode" as "cbscode"',
        'COALESCE("season",\'\') || \'-\' || COALESCE("_year",\'\') as "collection"',
        '"value_ex_cancelled" as "value_ex_cancelled"',
        '"qty_ex_cancelled" as "qty_ex_cancelled"',
        '"qty_picklist" as "qty_picklist"',
        '"supplier" as "supplier"',
        '"value_picklist" as "value_picklist"',
        '"a_return" as "a_return"',
        '"n_return" as "n_return"',
        (
            'case when "value_ex_cancelled" < 0 then ("value_picklist" / '
            '"value_ex_cancelled") * 100.0 else 0 end as "value_picklist_per"'
        ),
        (
            'case when "qty_ex_cancelled" < 0 then ("qty_picklist" / '
            '"qty_ex_cancelled") * 100.0 else 0 end as "qty_picklist_per"'
        ),
        (
            'case when "value_ex_cancelled" != 0 then ("a_sold" / '
            '"value_ex_cancelled") * 100 else 0 end as '
            '"value_post_del_per"'
        ),
        (
            'case when "qty_ex_cancelled" != 0 then("n_presold" / '
            '"qty_ex_cancelled") * 100.0 else 0 end as "qty_del_per"'
        ),
        (
            'case when "qty_ex_cancelled" != 0 then("n_sold" / '
            '"qty_ex_cancelled") * 100.0 else 0 end as '
            '"qty_post_del_per"'
        ),
        (
            'case when "value_ex_cancelled" != 0 then ("a_presold" / '
            '"value_ex_cancelled") * 100 else 0 end as "value_del_per"'
        ),
        (
            'case when "qty_ex_cancelled" < 0 then ("n_return" / "qty_ex_cancelled")* '
            '100.0 else 0 end as "qty_returned_per"'
        ),
        (
            'case when "value_ex_cancelled" < 0 then ("a_return" / '
            '"value_ex_cancelled") * 100 else 0 end as "value_returned_per"'
        ),
    }
    assert set(matches['inner_select'].strip().split(', ')) == {
        '"_year"',
        '"aatr1"',
        '"aatr2"',
        '"aatr3"',
        '"aatr4"',
        '"aatr5"',
        '"aatr6"',
        '"aatr7"',
        '"aatr8"',
        '"aatr9"',
        '"agent"',
        '"article"',
        '"brand"',
        '"catr1"',
        '"catr2"',
        '"catr3"',
        '"cbscode"',
        '"ccity"',
        '"ccountry"',
        '"cname"',
        '"czip"',
        '"kl_lev"',
        '"klcode_lev"',
        '"mcolor"',
        '"supplier"',
        '"mcolordesc"',
        '"season"',
        '"sizename"',
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then '
            'case when "astate" = \'active\' then "n_ordered" + "n_preord" '
            'else 0 end  else 0 end) as "qty_ex_cancelled"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then '
            'case when "astate" = \'active\' then "a_ordered" + "a_preord" '
            'else 0 end  else 0 end) as "value_ex_cancelled"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then  "a_ordered" + '
            '"a_preord"  else 0 end) as "value"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then  "n_ordered" + '
            '"n_preord"  else 0 end) as "qty"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "a_presold" else '
            '0 end) as "a_presold"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "a_sold" else 0 '
            'end) as "a_sold"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "n_presold" else '
            '0 end) as "n_presold"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "n_sold" else 0 '
            'end) as "n_sold"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then  "n_picked" + '
            '"n_prepick"  else 0 end) as "qty_picklist"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then  "a_picked" + '
            '"a_prepick"  else 0 end) as "value_picklist"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "a_return" else '
            '0 end) as "a_return"'
        ),
        (
            'sum(case when "timestamp" >= 0 and "timestamp" <= 2 then "n_return" else '
            '0 end) as "n_return"'
        ),
    }
    assert set(matches['where'].strip().split(', ')) == {'"tenant" = 1'}
    assert set(matches['group_by'].strip().split(', ')) == {
        '"_year"',
        '"aatr1"',
        '"aatr2"',
        '"aatr3"',
        '"aatr4"',
        '"aatr5"',
        '"aatr6"',
        '"aatr7"',
        '"aatr8"',
        '"aatr9"',
        '"agent"',
        '"article"',
        '"brand"',
        '"catr1"',
        '"catr2"',
        '"catr3"',
        '"cbscode"',
        '"ccity"',
        '"ccountry"',
        '"cname"',
        '"czip"',
        '"kl_lev"',
        '"klcode_lev"',
        '"mcolor"',
        '"mcolordesc"',
        '"season"',
        '"sizename"',
        '"supplier"',
    }

    assert set(matches['order_by'].strip().split(', ')) == {'"a_sold" ASC'}


@pytest.mark.parametrize(
    'endpoint',
    [
        'wholesale-customer-sales',
        'wholesale-customer-sales-csv',
        'wholesale-customer-sales-excel',
        'wholesale-customer-sales-pdf',
    ],
)
def test_wholesale_customer_sales_endpoint(app, setup_db, endpoint):
    payload = {
        'filter': {
            'startDate': '2000-05-06T22:00:00.000Z',
            'endDate': '2030-04-30T21:59:59.999Z',
        },
        'fields': ['qty'],
        'groups': ['brand', 'agent'],
    }
    app.post_json('/reports/{}'.format(endpoint), payload, status=200)
