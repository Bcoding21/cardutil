from io import BytesIO

import pytest
from cardutil.optimized_iso8583 import create_data_element_reader


def test_create_reader__fixed_width_element__reads_correctly():
    file = BytesIO(b'12345')
    config = {
        "1": {"field_type": "FIXED", "field_length": 5},
    }
    bitmap = _make_bitmap([1])

    read_data_elements = create_data_element_reader(file, config)
    data_elements = read_data_elements(bitmap)

    assert data_elements == [None, b'12345']


def test_create_reader__llvar_element__reads_correctly():
    file = BytesIO(b'05hello')
    config = {
        "2": {"field_type": "LLVAR"},
    }
    bitmap = _make_bitmap([2])

    read_data_elements = create_data_element_reader(file, config)
    data_elements = read_data_elements(bitmap)

    assert data_elements == [None, None, b'hello']

def test_create_reader__lllvar_element__reads_correctly():
    file = BytesIO(b'005hello')
    config = {
        "3": {"field_type": "LLLVAR"},
    }
    bitmap = _make_bitmap([3])

    read_data_elements = create_data_element_reader(file, config)
    data_elements = read_data_elements(bitmap)

    assert data_elements == [None, None, None, b'hello']


def test_create_reader__multiple_elements__reads_correctly():
    file = BytesIO(b'hello05hello005hello')
    config = {
        "1": {"field_type": "FIXED", "field_length": 5},
        "2": {"field_type": "LLVAR"},
        "3": {"field_type": "LLLVAR"},
    }
    bitmap = _make_bitmap([1, 2, 3])

    read_data_elements = create_data_element_reader(file, config)
    data_elements = read_data_elements(bitmap)

    assert data_elements == [None, b'hello', b'hello', b'hello']
    
# TODO: error handling


def _make_bitmap(indices: list[int]) -> bytes:
    bitmap = bytearray(16)
    for idx in indices:
        byte_idx = (idx - 1) // 8
        bit_idx = 7 - ((idx - 1) % 8)
        bitmap[byte_idx] |= (1 << bit_idx)
    return bytes(bitmap)