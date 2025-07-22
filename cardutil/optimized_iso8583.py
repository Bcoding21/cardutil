from functools import partial
from typing import BinaryIO, Callable


def _create_fixed_width_reader(file: BinaryIO, length: int):
   return partial(file.read, length)

def _create_variable_length_reader(file: BinaryIO, length: int) -> Callable[[], bytes | None]:

    def reader(length: int = length) -> bytes | None:
        length_bytes = file.read(length)

        if not length_bytes:
            return None
        
        length = int(length_bytes)
        return file.read(length)
        
    return reader

def _create_llvar_field_reader(file: BinaryIO) -> Callable[[], bytes | None]:
    return _create_variable_length_reader(file, 2)

def _create_lllvar_field_reader(file: BinaryIO) -> Callable[[], bytes | None]:
    return _create_variable_length_reader(file, 3)

def _create_reader_index(file: BinaryIO, bit_config: dict) -> list[Callable[[], bytes | None]]:
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


def _determine_set_bit_indices(bit_map: bytes) -> list[int]:
    """
    Determines the indices of the bits that are set in the provided bit map.

    :param bit_map: A byte string representing the bit map.
    :return: A list of indices where bits are set.
    """
    set_bits = []
    for i, byte in enumerate(bit_map):
        for j in range(8):
            if byte & (1 << (7 - j)):
                set_bits.append(i * 8 + j + 1)
    return set_bits

def create_data_element_reader(file: BinaryIO, bit_config: dict) -> Callable[[], bytes | None]:
    """
    Creates a data element reader based on the provided bit configuration.

    :param file: A binary file object to read from.
    :param bit_config: A dictionary containing the configuration for each bit.
    :return: A callable that reads the next data element.
    """
    reader_index = _create_reader_index(file, bit_config)
    
    def read_data_elements(bit_map: bytes) -> list[bytes | None]:
        """
        Reads data elements based on the provided bit map.

        :param bit_map: A byte string representing the bit map.
        :return: A list of data elements read from the file.
        """
        set_bits = _determine_set_bit_indices(bit_map)
        data_elements = [None] * (len(reader_index))

        for bit_index in set_bits:
            if reader_index[bit_index] is not None:
                data_element = reader_index[bit_index]()
                data_elements[bit_index] = data_element

        return data_elements

    return read_data_elements
