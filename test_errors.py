from errors import Errors


def test_add_error():
    e = Errors()
    e.add_error('_1')
    with e.with_path('a'):
        e.add_error('a_1')
        e.add_error('a_2')
        with e.with_path('aa'):
            e.add_error('aa_1')
    with e.with_path('b'):
        e.add_error('b_1')
        with e.with_path(0):
            e.add_error('b0_1')

    assert e
    assert e.has_errors

    assert e.as_dict == {
        '': ['_1'],
        'a': {
            '': ['a_1', 'a_2'],
            'aa': {
                '': ['aa_1'],
            }
        },
        'b': {
            '': ['b_1'],
            0: {
                '': ['b0_1'],
            }
        }
    }
