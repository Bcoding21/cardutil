import argparse
import json
import logging

from cardutil.cli import add_version, get_config, print_banner, print_exception_details
from cardutil.mciipm import IpmReader, MciIpmDataError, ipm_info


def cli_entry():
    return cli_run(**vars(cli_parser().parse_args()))


def print_check_details(in_ipm_info):
    """
    Print diagnostic information based on ipm_info
    """
    print("IPM file diagnostics:")
    if not in_ipm_info["isValidIPM"]:
        print("The file does not appear to be in the correct format")
        print(f"Reason: {in_ipm_info['reason']}")
        return
    print("The file seems to be valid based on analysis of the file")
    print("The following parameters were detected")
    print(f"File encoding: {in_ipm_info['encoding']}")
    print(f"1014 blocking: {in_ipm_info['isBlocked']}")


def cli_run(**kwargs):

    print_banner('mci_ipm_to_json', kwargs)

    if kwargs.get('debug'):
        logging.basicConfig(level=logging.DEBUG)

    config = get_config('cardutil.json', cli_filename=kwargs.get('config_file'))

    if not kwargs.get('out_filename'):
        kwargs['out_filename'] = kwargs['in_filename'] + '.json'

    # check ipm details
    with open(kwargs['in_filename'], 'rb') as in_ipm:
        in_ipm_info = ipm_info(in_ipm)

    try:
        with open(kwargs['in_filename'], 'rb') as in_ipm:
            with open(kwargs['out_filename'], 'w', encoding=kwargs.get('out_encoding', 'utf-8')) as out_json:
                mci_ipm_to_json(in_ipm=in_ipm, out_json=out_json, config=config, **kwargs)
    except MciIpmDataError as err:
        print_exception_details(err)
        print_check_details(in_ipm_info)
        return -1


def dicts_to_json(data_list, output_file, field_list=None):
    """
    Writes dict data to JSON file

    :param data_list: list of dictionaries that contain the data to be loaded
    :param output_file: output JSON file
    :param field_list: (optional) list of fields to output to JSON file
    :return: None
    """
    
    # Convert the data_list to a list if it's an iterator
    data_list = list(data_list)
    
    # Filter fields if field_list is provided
    if field_list:
        filtered_data = []
        for data_item in data_list:
            filtered_item = {field: data_item.get(field) for field in field_list if field in data_item}
            filtered_data.append(filtered_item)
        data_list = filtered_data
    
    # Write JSON with proper formatting
    json.dump(data_list, output_file, indent=2, ensure_ascii=False)


def cli_parser():
    parser = argparse.ArgumentParser(prog='mci_ipm_to_json', description='Mastercard IPM to JSON')
    parser.add_argument('in_filename')
    parser.add_argument('-o', '--out-filename')
    parser.add_argument('--in-encoding')
    parser.add_argument('--out-encoding')
    parser.add_argument('--no1014blocking', action='store_true')
    parser.add_argument('--config-file', help='File containing cardutil configuration - JSON format')
    parser.add_argument('--debug', action='store_true')
    add_version(parser)

    return parser


def mci_ipm_to_json(in_ipm, out_json, config, in_encoding=None, no1014blocking=False, **_):
    """
    Create a json file given an input Mastercard IPM file

    :param in_ipm: binary input IPM file object
    :param out_json: output json file object
    :param config: dict containing cardutil config
    :param in_encoding: input file encoding string (default latin-1)
    :param no1014blocking: set True if no 1014 blocking used
    :return: None
    """
    blocked = not no1014blocking
    dicts_to_json(
        IpmReader(in_ipm, encoding=in_encoding, blocked=blocked, iso_config=config.get('bit_config')),
        out_json, field_list=config.get('output_data_elements'))