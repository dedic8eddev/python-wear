"""Test full URLs."""

import pytest

from spynl.main.urlson import (
    UnexpectedEndOfInput,
    array_ctx,
    handle_ws,
    loads,
    loads_dict,
    object_ctx,
    value_ctx,
)


def test_loads_normal():
    """Test loads_dict with normal get."""
    get = {'k1': 'v1'}
    assert loads_dict(get) == {'k1': 'v1'}


def test_loads_list():
    """Test loads_dict with list in get."""
    get = {'k1': '[1,2,3,4,6]'}
    assert loads_dict(get) == {'k1': ['1', '2', '3', '4', '6']}


def test_loads_dict_function():
    """Test loads_dict with dict in get."""
    get = {'k1': '{1:a,2:b,3:c,4:d,6:e}'}
    assert loads_dict(get) == {'k1': {'1': 'a', '2': 'b', '3': 'c', '4': 'd', '6': 'e'}}


def test_loads_dict_mix():
    """Test loads_dict with mixed get."""
    get = {'k0': "sometext", 'k1': '[1,{bla:5},3,[4,5],6]'}
    assert loads_dict(get)['k0'] == 'sometext'
    assert loads_dict(get)['k1'] == ['1', {'bla': '5'}, '3', ['4', '5'], '6']


# Test Parser in detail


def test_handle_normal():
    """Normal test for handle_ws."""
    assert handle_ws(' \t ') == 3


def test_handle_newline():
    """Test for handle_ws with newline."""
    assert handle_ws('  \n\f ') == 5


class EventCollector:

    """Event collector set up."""

    def __init__(self):
        """Create events list."""
        self.events = []

    def __call__(self, *args):
        """Append the arguments to events every time an object gets called."""
        self.events.append(args)


@pytest.fixture
def collector():
    """Fixture to return a new EventCollector object for tests to use."""
    event_collector = EventCollector()
    return event_collector


def test_value_ctx_empty(collector):
    """Test empty (value_ctx)."""
    assert value_ctx('', collector) == 0
    assert collector.events == [('literal', '')]


def test_value_ctx_ws(collector):
    """Test whitespace (value_ctx)."""
    assert value_ctx('   \t ', collector) == 5
    assert collector.events == [('literal', '')]


def test_value_ctx_literal(collector):
    """Test literal (value_ctx)."""
    assert value_ctx('  abc ', collector) == 6
    assert collector.events == [('literal', 'abc')]


def test_array_ctx_empty(collector):
    """Test empty (array_ctx)."""
    assert array_ctx('[]', collector) == 2
    assert collector.events == [('array_start', None), ('array_stop', None)]


def test_array_ctx_ws(collector):
    """Test whitespace (array_ctx)."""
    assert array_ctx('[   ]', collector) == 5
    assert collector.events == [('array_start', None), ('array_stop', None)]


def test_array_ctx_comma(collector):
    """Test comma (array_ctx)."""
    assert array_ctx('[ , ,, ]', collector) == 8
    assert collector.events == [('array_start', None), ('array_stop', None)]


def test_array_ctx_literal(collector):
    """Test literal (array_ctx)."""
    assert array_ctx('[a,b , , c,]', collector) == 12
    assert collector.events == [
        ('array_start', None),
        ('literal', 'a'),
        ('literal', 'b'),
        ('literal', 'c'),
        ('array_stop', None),
    ]


def test_array_ctx_unexpected(collector):
    """Test unexpected (array_ctx)."""
    with pytest.raises(UnexpectedEndOfInput):
        array_ctx('[a,b', collector)


def test_object_ctx_empty(collector):
    """Test empty (object_ctx)."""
    assert object_ctx('{}', collector) == 2
    assert collector.events == [('object_start', None), ('object_stop', None)]


def test_object_ctx_ws(collector):
    """Test whitespace (object_ctx)."""
    assert object_ctx('{  }', collector) == 4
    assert collector.events == [('object_start', None), ('object_stop', None)]


def test_object_ctx_comma(collector):
    """Test comma (object_ctx)."""
    assert object_ctx('{ ,, , }', collector) == 8
    assert collector.events == [('object_start', None), ('object_stop', None)]


def test_object_ctx_literal(collector):
    """Test literal (object_ctx)."""
    assert object_ctx('{a:abc,b : 4,,c: }', collector) == 18
    assert collector.events == [
        ('object_start', None),
        ('key', 'a'),
        ('literal', 'abc'),
        ('key', 'b'),
        ('literal', '4'),
        ('key', 'c'),
        ('literal', ''),
        ('object_stop', None),
    ]


def test_object_ctx_unexpected(collector):
    """Test unexpected (object_ctx)."""
    with pytest.raises(UnexpectedEndOfInput):
        object_ctx('{a:c', collector)
    with pytest.raises(UnexpectedEndOfInput):
        object_ctx('{a}', collector)


def test_loads_array():
    """Test empty array (loads)."""
    assert loads('[]') == []


def test_loads_array_lit():
    """Test array (loads)."""
    assert loads('[ , a, 1 , , 3, ]') == ['a', '1', '3']


def test_loads_function_dict():
    """Test empty dictionary (loads)."""
    assert loads('{}') == {}


def test_loads_dict_lit():
    """Test dictionary (loads)."""
    assert loads('{a:2,c:, d :5 ,,}') == {'a': '2', 'c': '', 'd': '5'}


def test_loads_string():
    """Test string (loads)."""
    assert loads(' abc \n def ') == 'abc \n def'


def test_loads_nested():
    """Test nested (loads)."""
    assert loads('{a: 2, c: [], d: [{f:1},d]}') == {
        'a': '2',
        'c': [],
        'd': [{'f': '1'}, 'd'],
    }
