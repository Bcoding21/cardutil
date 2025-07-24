from io import BytesIO

import pytest
from cardutil.data_element_reader import IpmMessage, IpmMessageIterator


def test_create_reader__fixed_width_element__reads_correctly():
    bit_map = _make_bitmap([1])
    ipm_message = (b"1240" + bit_map + b"12345")
    file = BytesIO(ipm_message)
    config = {"1": {"field_type": "FIXED", "field_length": 5}}
    iterator = IpmMessageIterator(file, config)

    data_elements = list(iterator)

    assert data_elements == [
        IpmMessage(
            mti=b"1240",
            bitmap=bit_map,
            data_elements=[None, b"12345"]
        )
    ]


def test_create_reader__llvar_element__reads_correctly():
    bit_map = _make_bitmap([1])
    ipm_message = (b"1240" + bit_map + b"05hello")
    file = BytesIO(ipm_message)
    config = {"1": {"field_type": "LLVAR"}}
    iterator = IpmMessageIterator(file, config)

    data_elements = list(iterator)

    assert data_elements == [
        IpmMessage(
            mti=b"1240",
            bitmap=bit_map,
            data_elements=[None, b"hello"]
        )
    ]


def test_create_reader__lllvar_element__reads_correctly():
    bit_map = _make_bitmap([1])
    ipm_message = (b"1240" + bit_map + b"005hello")
    file = BytesIO(ipm_message)
    config = {"1": {"field_type": "LLLVAR"}}
    iterator = IpmMessageIterator(file, config)

    data_elements = list(iterator)

    assert data_elements == [
        IpmMessage(
            mti=b"1240",
            bitmap=bit_map,
            data_elements=[None, b"hello"]
        )
    ]


def test_create_reader__multiple_elements__reads_correctly():
    bit_map = _make_bitmap([1, 2, 3])
    ipm_message = (b"1240" + bit_map + b"hello05hello005hello")
    file = BytesIO(ipm_message)
    config = {
        "1": {"field_type": "FIXED", "field_length": 5},
        "2": {"field_type": "LLVAR"},
        "3": {"field_type": "LLLVAR"},
    }
    iterator = IpmMessageIterator(file, config)

    data_elements = list(iterator)

    assert data_elements == [
        IpmMessage(
            mti=b"1240",
            bitmap=bit_map,
            data_elements=[None, b"hello", b"hello", b"hello"]
        )
    ]


def test_iterator__multiple_messages():
    bit_map1 = _make_bitmap([1, 2])
    ipm_message1 = (b"1240" + bit_map1 + b"hello05world")
    
    bit_map2 = _make_bitmap([1, 3])
    ipm_message2 = (b"1241" + bit_map2 + b"world004test")

    file = BytesIO(ipm_message1 + ipm_message2)
    config = {
        "1": {"field_type": "FIXED", "field_length": 5},
        "2": {"field_type": "LLVAR"},
        "3": {"field_type": "LLLVAR"},
    }
    iterator = IpmMessageIterator(file, config)

    data_elements = list(iterator)

    assert len(data_elements) == 2
    assert data_elements[0].mti == b"1240"
    assert data_elements[0].data_elements == [None, b"hello", b"world", None]
    assert data_elements[1].mti == b"1241"
    assert data_elements[1].data_elements == [None, b"world", None, b"test"]

def test_create_reader__llvar_element__raises_error_on_short_length_prefix():
    file = BytesIO(b"1240" + _make_bitmap([2]) + b"1hello")
    config = {"2": {"field_type": "LLVAR"}}
    
    iterator = IpmMessageIterator(file, config)

    with pytest.raises(
        ValueError, match="Invalid length prefix: b'1h' is not a valid integer."
    ):
        list(iterator)


def test_create_reader__llvar_element__raises_error_on_invalid_length_prefix():
    file = BytesIO(b"1240" + _make_bitmap([2]) + b"01hello")
    config = {"2": {"field_type": "LLLVAR"}}
    
    iterator = IpmMessageIterator(file, config)

    with pytest.raises(
        ValueError, match="Invalid length prefix: b'01h' is not a valid integer."
    ):
        list(iterator)


def test_create_reader__llvar_element__raises_error_on_short_data():
    file = BytesIO(b"1240" + _make_bitmap([2]) + b"10hello")
    config = {"2": {"field_type": "LLVAR"}}
    
    iterator = IpmMessageIterator(file, config)

    with pytest.raises(EOFError, match="Unexpected end of file"):
        list(iterator)


def _make_bitmap(indices: list[int]) -> bytes:
    bitmap = bytearray(16)
    for idx in indices:
        byte_idx = (idx - 1) // 8
        bit_idx = 7 - ((idx - 1) % 8)
        bitmap[byte_idx] |= (1 << bit_idx)
    return bytes(bitmap)