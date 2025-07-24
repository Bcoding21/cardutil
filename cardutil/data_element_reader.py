"""
Module: data_element_reader

This module provides functionality to read data elements from a binary file based on a bit configuration and a bitmap.

Functions:
    - create_data_element_reader: Creates a callable that reads data elements based on a bitmap.

Usage:
    To use `create_data_element_reader`, provide a binary file object and a bit configuration dictionary. 
    The returned callable can then be used to read data elements based on a bitmap.

    Example:
        with open("data_file.bin", "rb") as file:
            bit_config = {
                "1": {"field_type": "FIXED", "field_length": 10},
                "2": {"field_type": "LLVAR"},
                "3": {"field_type": "LLLVAR"},
            }
            reader = create_data_element_reader(file, bit_config)
            bitmap = b'\xC0'  # Example bitmap
            data_elements = reader(bitmap)
            print(data_elements)

Inputs:
    - file (BinaryIO): A binary file object opened in read mode.
    - bit_config (dict): A dictionary where keys are bit positions (as strings) and values are dictionaries 
      containing field details:
        - "field_type" (str): Type of the field. Supported values are "FIXED", "LLVAR", and "LLLVAR".
        - "field_length" (int, optional): Length of the field for "FIXED" type fields.

Outputs:
    - Callable[[bytes], list[bytes | None]]: A callable that takes a bitmap (bytes) as input and returns a list of 
      data elements. Each element corresponds to a bit position in the bitmap. If a bit is not set, the corresponding 
      element is `None`.

Edge Cases:
    - If the bitmap contains bits set for positions not defined in `bit_config`, those positions will be ignored.
    - If the file does not contain enough data for a field, a `ValueError` will be raised.
    - If the length prefix for "LLVAR" or "LLLVAR" fields is invalid or incomplete, a `ValueError` will be raised.

Limitations:
    - The maximum bit position supported is determined by the highest key in `bit_config`.
    - The function assumes the file is properly formatted and does not handle file corruption or unexpected EOF gracefully.

Exceptions:
    - `ValueError`: Raised in the following cases:
        - Unknown field type in `bit_config`.
        - Insufficient bytes in the file for a fixed-length field.
        - Invalid or incomplete length prefix for variable-length fields.
        - Insufficient bytes in the file for the data of a variable-length field.

Example Input and Output:
    Input file data (binary):
        b'123456789005Hello005World'

    Bit configuration:
        bit_config = {
            "1": {"field_type": "FIXED", "field_length": 10},
            "2": {"field_type": "LLVAR"},
            "3": {"field_type": "LLLVAR"},
        }

    Bitmap:
        b'\xE0'  # Bits 1, 2, and 3 are set.

    Output:
        [
            b'1234567890',  # Fixed-width field (10 bytes)
            b'Hello',       # LLVAR field (length prefix: 2 bytes, data: 5 bytes)
            b'World'        # LLLVAR field (length prefix: 3 bytes, data: 5 bytes)
        ]
"""

from functools import partial
from typing import BinaryIO, Callable



def create_data_element_reader(file: BinaryIO, bit_config: dict) -> Callable[[bytes], list[bytes | None]]:
    data_element_readers = _create_reader_index(file, bit_config)
    
    def read_data_elements(bit_map: bytes) -> list[bytes | None]:
        set_bit_indices = _determine_set_bit_indices(bit_map)
        data_elements = [None] * (len(data_element_readers))

        for bit_index in set_bit_indices:

            if data_element_readers[bit_index] is not None:
                read_data_element = data_element_readers[bit_index]
                data_elements[bit_index] = read_data_element()

        return data_elements

    return read_data_elements


def _create_reader_index(file: BinaryIO, bit_config: dict) -> list[Callable[[], bytes]]:
    max_bit = max(int(bit) for bit in bit_config.keys())
    reader_index = [None] * (max_bit + 1)

    for bit, bit_details in bit_config.items():

        bit_index = int(bit)
        field_type = bit_details["field_type"]
        field_length = bit_details.get("field_length", 0)

        if field_type == "FIXED":
            reader_index[bit_index] = _create_fixed_width_reader(file, field_length)

        elif field_type == "LLVAR":
            reader_index[bit_index] = _create_llvar_field_reader(file)

        elif field_type == "LLLVAR":
            reader_index[bit_index] = _create_lllvar_field_reader(file)

        else:
            raise ValueError(f"Unknown field type: {field_type}")
    
    return reader_index

def _create_fixed_width_reader(file: BinaryIO, length: int) -> Callable[[], bytes]:
   return partial(file.read, length)

def _create_variable_length_reader(file: BinaryIO, length: int) -> Callable[[], bytes]:

    def reader(length: int = length) -> bytes:
        length_bytes = file.read(length)

        if len(length_bytes) < length:
            raise ValueError(
                f"Expected to read {length} bytes for length prefix, but got {len(length_bytes)} bytes."
            )

        try:
            length = int(length_bytes)
        except ValueError:
            raise ValueError(f"Invalid length prefix: {length_bytes!r} is not a valid integer.")

        data = file.read(length)

        if len(data) != length:
            raise ValueError(
                f"Expected to read {length} bytes of data, but got {len(data)} bytes."
            )

        return data

    return reader

def _create_llvar_field_reader(file: BinaryIO) -> Callable[[], bytes]:
    return _create_variable_length_reader(file, 2)

def _create_lllvar_field_reader(file: BinaryIO) -> Callable[[], bytes]:
    return _create_variable_length_reader(file, 3)

def _determine_set_bit_indices(bit_map: bytes) -> list[int]:
    set_bits = []
    for i, byte in enumerate(bit_map):
        for j in range(8):
            if byte & (1 << (7 - j)):
                set_bits.append(i * 8 + j + 1)
    return set_bits

