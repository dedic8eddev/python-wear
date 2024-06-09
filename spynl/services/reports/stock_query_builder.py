from itertools import groupby

from psycopg2 import sql

from spynl.locale import SpynlTranslationString as _

from spynl.services.reports.utils import build_filter_values  # noqa: F401
from spynl.services.reports.utils import COLLECTION_SQL, _build_sort, _build_where

N_STOCK = 'n_stock'
LABEL_SEPARATOR = '-LABEL_SEPARATOR-'


TYPE_LABELS = {
    '0': _('trtype-0'),
    '1': _('trtype-1'),
    '2': _('trtype-2'),
    '3': _('trtype-3'),
    '4': _('trtype-4'),
    '5': _('trtype-5'),
    '6': _('trtype-6'),
    '7': _('trtype-7'),
    '14': _('trtype-14'),
    '15': _('trtype-15'),
    '18': _('trtype-18'),
    '93': _('trtype-93'),
    '94': _('trtype-94'),
    '95': _('trtype-95'),
    '96': _('trtype-96'),
    '97': _('trtype-97'),
    '98': _('trtype-98'),
}

# Changes in the order also need to be taken into account in _select_label
LABEL_HEADERS = [_('color'), _('color-supplier'), _('location')]
LABEL_HISTORY_HEADERS = [
    _('color'),
    _('time'),
    _('location'),
    _('user'),
    _('type'),
    _('reference'),
]
TYPE_INDEX = 4


def _select_label(history=False):
    # Note any changes here also have to be taken into in the above constants
    if not history:
        return sql.SQL(
            "COALESCE({color},'') "
            "|| ' ' "
            "|| COALESCE({scolor},'') "
            "|| '{seperator}' "
            "|| COALESCE({klcode_lev},'') "
            "|| ' ' "
            "|| COALESCE({kl_lev},'') "
            "|| '{seperator}' "
            "|| COALESCE({warehouse},' ') "
            "as {alias}"
        ).format(
            color=sql.Identifier('color'),
            scolor=sql.Identifier('scolor'),
            kl_lev=sql.Identifier('kl_lev'),
            klcode_lev=sql.Identifier('klcode_lev'),
            seperator=sql.SQL(LABEL_SEPARATOR),
            warehouse=sql.Identifier('warehouse'),
            alias=sql.Identifier('label'),
        )
    else:
        return sql.SQL(
            "   COALESCE({color}, '') "
            "|| ' ' "
            "|| COALESCE({scolor}, '') "
            "|| ' / ' "
            "|| COALESCE({kl_lev}, '') "
            "|| ' / ' "
            "|| COALESCE({klcode_lev}, '') "
            "|| '{seperator}' "
            "|| to_char(to_timestamp({from_time}, {dtformat}) at time zone 'UTC',"
            "{output_dtformat})"
            "|| '{seperator}' "
            "|| COALESCE({warehouse}, ' ') "
            "|| '{seperator}' "
            "|| COALESCE({agent}, ' ') "
            "|| '{seperator}' "
            "|| COALESCE({trtype}, 0) "
            "|| '{seperator}' "
            "|| COALESCE({reference}, ' ') "
            "as {alias}"
        ).format(
            color=sql.Identifier('color'),
            scolor=sql.Identifier('scolor'),
            kl_lev=sql.Identifier('kl_lev'),
            klcode_lev=sql.Identifier('klcode_lev'),
            seperator=sql.SQL(LABEL_SEPARATOR),
            warehouse=sql.Identifier('warehouse'),
            from_time=sql.Identifier('from_time'),
            dtformat=sql.Literal('YYYYMMDDHH24MISS'),
            output_dtformat=sql.Literal('YY-MM-DD HH:MI'),
            agent=sql.Identifier('agent'),
            trtype=sql.Identifier('trtype'),
            reference=sql.Identifier('reference'),
            alias=sql.Identifier('label'),
        )


def _build_select(columns, aliases=None, history=False):
    def _build_select_column(column):
        if column == 'collection':
            return COLLECTION_SQL
        elif column == 'label':
            return _select_label(history=history)
        elif column == N_STOCK:
            return sql.SQL('sum("n_stock"+"n_bought") as {}').format(
                sql.Identifier(aliases.get(column, column))
            )
        else:
            return sql.SQL('{} as {}').format(
                sql.Identifier(column), sql.Identifier(aliases.get(column, column))
            )

    aliases = aliases or {}
    return sql.SQL(' SELECT ') + sql.SQL(', ').join(
        [_build_select_column(column) for column in columns]
    )


def _build_group_by(columns, history=False):
    group_by = []
    for c in columns:
        if c == N_STOCK:
            continue
        elif c == 'collection':
            group_by.extend([sql.Identifier('season'), sql.Identifier('_year')])
        elif c == 'label':
            group_by.extend(
                [
                    sql.Identifier('color'),
                    sql.Identifier('scolor'),
                    sql.Identifier('kl_lev'),
                    sql.Identifier('klcode_lev'),
                    sql.Identifier('warehouse'),
                ]
            )
            if history:
                group_by.extend(
                    [
                        sql.Identifier('kl_lev'),
                        sql.Identifier('klcode_lev'),
                        sql.Identifier('from_time'),
                        sql.Identifier('agent'),
                        sql.Identifier('trtype'),
                        sql.Identifier('reference'),
                    ]
                )
        else:
            group_by.append(sql.Identifier(c))

    return sql.SQL(' GROUP BY ') + sql.SQL(', ').join(group_by)


def build(columns, where, sort, t1, t2, aliases=None, limit=None, history=False):
    if not where:
        where = {}
    if history:
        # also include purchase orders (14)
        where.setdefault('trtype', [0, 1, 2, 3, 4, 5, 6, 8, 93, 14])
    else:
        where.setdefault('trtype', [0, 1, 2, 3, 4, 5, 6, 8, 93])

    if where:
        where = _build_where(where) + sql.SQL(' AND ')

    where += sql.SQL('("timestamp" >= {t1} and "timestamp" <= {t2})').format(
        t1=sql.Literal(t1), t2=sql.Literal(t2)
    )

    query = (
        _build_select(columns, aliases, history)
        + sql.SQL(' FROM {} ').format(sql.Identifier('transactions'))
        + where
        + _build_group_by(columns, history)
        + _build_sort(sort)
    )
    if limit:
        query += sql.SQL(' LIMIT {}').format(sql.Literal(limit))
    return query


def calculate_matrix_totals(matrix):
    start = len(LABEL_HEADERS)
    end_stock = _('end-stock').translate()

    matrix[0].append('#')
    totals = [end_stock] + [''] * (start - 1) + [0 for c in matrix[0][start:]]
    for i in range(1, len(matrix)):
        matrix[i].append(sum([value if value else 0 for value in matrix[i][start:]]))
        for j in range(start, len(matrix[i])):
            totals[j] += matrix[i][j] or 0
    matrix.append(totals)


def calculate_history_totals(matrix, calculate_totals=False, type_labels=None):
    """
    Calculate totals for each color. If calculate_totals is True, also calculate the row
    totals.
    """
    if type_labels is None:
        type_labels = {}
    start = len(LABEL_HISTORY_HEADERS)
    end_stock = _('end-stock').translate()

    new_matrix = matrix[0:1]
    if calculate_totals:
        new_matrix[0].append('#')
    # leave out header
    for color, group in groupby(matrix[1:], lambda x: x[0]):
        new_matrix.append([color] + [None] * (len(new_matrix[0]) - 1))
        totals = ['', end_stock, '', '', '', ''] + [0 for c in new_matrix[0][start:]]
        for line in group:
            line[0] = ''
            if calculate_totals:  # row totals
                line.append(sum([value if value else 0 for value in line[start:]]))
            new_matrix.append(line)
            # skip purchase orders for column totals:
            if line[TYPE_INDEX] == type_labels.get('14', '14'):
                continue
            for i in range(start, len(line)):
                totals[i] += line[i] or 0
        new_matrix.append(totals)

    return new_matrix


def build_matrices(data, keep_zero_lines=False, calculate_totals=False, history=False):
    """
    Every unique combination of article status and any groups selected gets its own
    matrix. (This is the key).
    Each matrix has a header row with the size indexes.
    Each label (one string in this stage, consisting of color, scolor and warehouse,
    separated by LABEL_SEPARATOR) will be one row in the matrix. The rows are sorted on
    label. The label is then split up into a column for color and one for warehouse.
    This returns a dict with article code, any groups selected and the skuStockmatrix as
    keys.
    """
    columns = [k for k in data[0] if k not in ['label', 'sizename', 'sizeidx', N_STOCK]]

    def key(row):
        return {c: row[c] for c in columns}

    for article, group in groupby(data, key):
        articles = list(group)

        sizes = []
        labels = []

        for a in articles:
            if a['label'] not in labels:
                labels.append(a['label'])

            if a['sizename'] not in sizes:
                sizes.append(a['sizename'])

        labels = sorted(labels)
        len_label_fields = len(labels[0].split(LABEL_SEPARATOR))

        # Initialize matrix with the label and size headers as first row (translate
        # headers for pdf):
        if history:
            matrix = [[label.translate() for label in LABEL_HISTORY_HEADERS] + sizes]
        else:
            matrix = [[label.translate() for label in LABEL_HEADERS] + sizes]

        # Initialize the matrix with label fields and None values
        matrix.extend(
            [c.split(LABEL_SEPARATOR) + [None for s in sizes] for c in labels]
        )

        # Transform type numbers into readable labels:
        if history:
            type_labels = {key: value.translate() for key, value in TYPE_LABELS.items()}
            for row in matrix:
                row[TYPE_INDEX] = type_labels.get(row[TYPE_INDEX], row[TYPE_INDEX])

        stock = 0
        for a in articles:
            stock += abs(a[N_STOCK])
            # add one to the indexes since the first row and the first item of
            # each row are reserved for the size header and labels
            # respectively.
            sizeidx = sizes.index(a['sizename']) + len_label_fields
            labelidx = labels.index(a['label']) + 1

            # fill in the stock for the label and size
            matrix[labelidx][sizeidx] = a[N_STOCK]

        if stock:
            if not keep_zero_lines:
                # strip out empty rows
                matrix = [row for row in matrix if any(row[len_label_fields:])]

            if history:
                matrix = calculate_history_totals(
                    matrix, calculate_totals=calculate_totals, type_labels=type_labels
                )
            elif calculate_totals:
                calculate_matrix_totals(matrix)

            article.update(skuStockMatrix=matrix)
            yield article


def build_stock_return_value(
    data,
    order,
    keep_zero_lines=False,
    headers_in_separate_row=True,
    empty_group_tag='???',
    group_separator=', ',
    calculate_totals=False,
    history=False,
):
    """
    Group the stock matrices for different articles into the requested groups. Every
    combination of groups has a header.
    """
    rv = []

    def key(row):
        return [
            i
            for i in row.items()
            if i[0] not in ['article', 'artnr_lev', 'descript', 'skuStockMatrix']
        ]

    for header, group in groupby(
        build_matrices(
            data,
            keep_zero_lines=keep_zero_lines,
            calculate_totals=calculate_totals,
            history=history,
        ),
        key,
    ):
        header = group_separator.join(
            v if v else empty_group_tag
            for k, v in sorted(header, key=lambda r: order.index(r[0]))
        )
        if headers_in_separate_row:
            rv.append({'header': header})
            rv.extend(group)
        else:
            rv.append({'header': header, 'products': list(group)})

    return rv


def add_limit_offset(query, limit, offset):
    return query + sql.SQL(' LIMIT {} OFFSET {}').format(
        sql.Literal(limit), sql.Literal(offset)
    )
