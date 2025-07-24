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

from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from typing import BinaryIO, Callable



@dataclass
class IpmMessage:
   mti: bytes
   bitmap: bytes
   data_elements: list[bytes | None]


class _StrictBinaryIO(BinaryIO):

    def __init__(self, file: BinaryIO):
        self._file = file
        super().__init__()

    def read(self, size: int) -> bytes:
        data = self._file.read(size)

        if len(data) < size:
            raise EOFError("Unexpected end of file")

        return data
    
    def seek(self, offset: int | None, whence: int = 0) -> int:
        position = self._file.seek(offset or 0, whence)
        if position < 0:
            raise ValueError("Seek position cannot be negative")
        return position
    

    def tell(self) -> int:
        position = self._file.tell()
        if position < 0:
            raise ValueError("Tell position cannot be negative")
        return position


class IpmMessageIterator(Iterator[IpmMessage]):
    MTI_LENGTH = 4
    BITMAP_LENGTH = 16

    def __init__(self, file: BinaryIO, bit_config: dict):
        self.file = _StrictBinaryIO(file)
        self.bit_config = bit_config
        self.data_element_readers = self._create_reader_index()

    def __iter__(self) -> 'IpmMessageIterator':
        return self
    
    def __next__(self) -> IpmMessage:

        if self._is_end_of_file():
            raise StopIteration("End of file reached")

        mti = self.file.read(self.MTI_LENGTH)
        bitmap = self.file.read(self.BITMAP_LENGTH)
        data_elements = self._read_data_elements(bitmap)
        return IpmMessage(mti=mti, bitmap=bitmap, data_elements=data_elements)
    
    def _is_end_of_file(self) -> bool:
        current_position = self.file.tell()
        try:
            self.file.read(1)
        except EOFError:
            return True
        finally:
            self.file.seek(current_position)

    def _read_data_elements(self, bit_map: bytes) -> list[bytes | None]:
        set_bit_indices = self._determine_set_bit_indices(bit_map)
        data_elements = [None] * len(self.data_element_readers)

        for bit_index in set_bit_indices:
            if self.data_element_readers[bit_index] is not None:
                read_data_element = self.data_element_readers[bit_index]
                data_elements[bit_index] = read_data_element()

        return data_elements
    
    def _create_reader_index(self) -> list[Callable[[], bytes]]:
        max_bit = max(int(bit) for bit in self.bit_config.keys())
        reader_index = [None] * (max_bit + 1)

        for bit, bit_details in self.bit_config.items():
            bit_index = int(bit)
            field_type = bit_details["field_type"]
            field_length = bit_details.get("field_length", 0)

            if field_type == "FIXED":
                reader_index[bit_index] = self._create_fixed_width_reader(field_length)
            elif field_type == "LLVAR":
                reader_index[bit_index] = self._create_llvar_field_reader()
            elif field_type == "LLLVAR":
                reader_index[bit_index] = self._create_lllvar_field_reader()
            else:
                raise ValueError(f"Unknown field type: {field_type}")

        return reader_index

    def _create_fixed_width_reader(self, length: int) -> Callable[[], bytes]:
        return partial(self.file.read, length)

    def _create_variable_length_reader(self, length: int) -> Callable[[], bytes]:

        def reader(length: int = length) -> bytes:
            length_bytes = self.file.read(length)

            if len(length_bytes) < length:
                raise ValueError(
                    f"Expected to read {length} bytes for length prefix, but got {len(length_bytes)} bytes."
                )

            try:
                length = int(length_bytes)
            except ValueError:
                raise ValueError(f"Invalid length prefix: {length_bytes!r} is not a valid integer.")

            data = self.file.read(length)

            if len(data) != length:
                raise ValueError(
                    f"Expected to read {length} bytes of data, but got {len(data)} bytes."
                )

            return data

        return reader

    def _create_llvar_field_reader(self) -> Callable[[], bytes]:
        return self._create_variable_length_reader(2)

    def _create_lllvar_field_reader(self) -> Callable[[], bytes]:
        return self._create_variable_length_reader(3)

    def _determine_set_bit_indices(self, bit_map: bytes) -> list[int]:
        set_bits = []
        for i, byte in enumerate(bit_map):
            for j in range(8):
                if byte & (1 << (7 - j)):
                    set_bits.append(i * 8 + j + 1)
        return set_bits


class RDWIpmMessageIterator(IpmMessageIterator):
    RDW_LENGTH = 4

    def __init__(self, file: BinaryIO, bit_config: dict):
        super().__init__(file, bit_config)

    def __next__(self) -> IpmMessage:
        raw_length = self.file.read(self.RDW_LENGTH)
        length = int.from_bytes(raw_length, byteorder='big')

        if length == 0:
            raise StopIteration("End of file reached")

        return super().__next__()


class BlockedReader(BinaryIO):

    def __init__(self, file: BinaryIO, block_size: int = 1014):
        self._file = file
        self._block_size = block_size
        self._buffer = BytesIO()

    def read(self, total_bytes: int) -> bytes:
       self._fill_buffer_if_needed(total_bytes)
       return self._buffer.read(total_bytes)

    def _fill_buffer_if_needed(self, total_bytes: int) -> None:

         while self._get_bytes_left_in_buffer() < total_bytes:
            block = self._file.read(self._block_size)

            if not block:
                break

            block = block[:self._block_size - 2]
            self._buffer.write(block)

    def _get_bytes_left_in_buffer(self) -> int:
        return self._buffer.getbuffer().nbytes - self._buffer.tell()