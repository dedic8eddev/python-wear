from copy import deepcopy

import pytest

from spynl_schemas.foxpro_serialize import escape, resolve, serialize


@pytest.mark.parametrize(
    'val,escaped',
    [
        # we test all variations of what urllib.parse.quote does not do by default.
        ('value-thing', 'value%2Dthing'),
        ('value_thing', 'value%5Fthing'),
        ('value/thing', 'value%2Fthing'),
    ],
)
def test_escape(val, escaped):
    assert escape(val) == escaped


@pytest.mark.parametrize(
    'dict_, path, val',
    [
        ({'one': {'two': 'value2'}}, 'one', {'two': 'value2'}),
        ({'one': {'two': 'value2'}}, 'one.two', 'value2'),
        ({'one': {'two': 'value2'}}, 'one.three', ''),
        ({'one': {'two': 'value2'}}, 'five.six', ''),
    ],
)
def test_resolve(dict_, path, val):
    assert resolve(dict_, path) == val


@pytest.mark.parametrize(
    'dict_, path',
    [
        ({'one': {'two': 'value2'}}, 'one.two.three'),
        ({'one': {'two': 2}}, 'one.two.three'),
    ],
)
def test_resolve_fail(dict_, path):
    with pytest.raises(AttributeError):
        resolve(dict_, path)


def test_serialize():
    queries = [
        ('method1', [('key1', 'val1')]),
        ('method2', [('remarks', 'remark1')]),
        ('method3', [('remarks', 'remark1'), ('key1', 'val1')]),
        (
            'method4',
            [('remarks', 'remark1'), ('key1', None), ('key2', ''), ('key3', 'None')],
        ),
    ]
    serialized = serialize(deepcopy(queries))
    assert serialized == [
        ('method1', 'method1/key1__val1'),
        ('method2', 'method2/remarks__remark1'),
        ('method3', 'method3/remarks__remark1/key1__val1'),
        ('method4', 'method4/remarks__remark1/key3__None'),
    ]
    serialized = serialize(deepcopy(queries), pass_empty=True)
    assert serialized == [
        ('method1', 'method1/key1__val1'),
        ('method2', 'method2/remarks__remark1'),
        ('method3', 'method3/remarks__remark1/key1__val1'),
        ('method4', 'method4/remarks__remark1/key1__/key2__/key3__None'),
    ]


def test_serialize_whitelist():
    queries = [
        ('method1', [('key', '2017-05-05')]),
        ('method2', [('key', '2017-05-05')]),
    ]
    serialized = serialize(queries, whitelist=[('method1', 'key')])
    assert serialized == [
        ('method1', 'method1/key__2017-05-05'),
        ('method2', 'method2/key__2017%2D05%2D05'),
    ]
