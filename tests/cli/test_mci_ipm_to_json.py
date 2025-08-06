import contextlib
import io
import json
import os
import tempfile
import unittest

from cardutil.cli import mci_ipm_to_json
from cardutil.config import config

CONFIG_DATA = """
{
    "bit_config": {
        "38": {
            "field_name": "Approval code",
            "field_type": "FIXED",
            "field_length": 6
        }
    }
}
"""


class MciIpmToJsonTestCase(unittest.TestCase):
    def test_mci_ipm_to_json_cli_parser(self):
        args = vars(mci_ipm_to_json.cli_parser().parse_args(['file1.ipm']))
        self.assertEqual(
            args,
            {'in_encoding': None, 'out_encoding': None, 'in_filename': 'file1.ipm', 'no1014blocking': False,
             'out_filename': None, 'config_file': None, 'debug': False})

        args = vars(mci_ipm_to_json.cli_parser().parse_args(['file1.ipm', '--in-encoding', 'latin_1']))
        self.assertEqual(
            args,
            {'in_encoding': 'latin_1', 'out_encoding': None, 'in_filename': 'file1.ipm', 'no1014blocking': False,
             'out_filename': None, 'config_file': None, 'debug': False})

    def test_ipm_to_json_bad_data_de38(self):
        """
        prod issue - auth code DE38 contains non-ascii characters.
        Added new out-encoding parameter to support this -- changed to latin_1 which supports full 256 bits.
        Also need to set in-encoding to latin_1 for the same reason
        I have only seen this issue on one transaction once after processing 1000's of input files
        """
        in_ipm = io.BytesIO(b'\x00\x00\x00\x1a0100\x80\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                            b'n\x9cm\x9cl\x9c\x00\x00\x00\x00')
        with tempfile.TemporaryFile(mode='w', encoding='utf-8') as out_json:
            mci_ipm_to_json.mci_ipm_to_json(
                in_ipm=in_ipm, out_json=out_json, config=config, no1014blocking=True)

    def test_ipm_to_json_input_params(self):
        """
        Actually run using real files
        :return:
        """
        in_ipm_data = (b'\x00\x00\x00\x1a0100\x80\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                       b'nXmXlX\x00\x00\x00\x00')

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as in_ipm:
            in_ipm.write(in_ipm_data)
            in_ipm_name = in_ipm.name
            print(in_ipm_name)
            in_ipm.close()

        result = mci_ipm_to_json.cli_run(in_filename=in_ipm_name, out_encoding='utf-8')
        self.assertFalse(result)

        result = mci_ipm_to_json.cli_run(
            in_filename=in_ipm_name, out_filename=in_ipm_name + '.json', out_encoding='utf-8')
        self.assertFalse(result)

        # run with config file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as in_config:
            config_filename = in_config.name
            in_config.write(CONFIG_DATA)
            in_config.close()
            result = mci_ipm_to_json.cli_run(
                in_filename=in_ipm_name,
                out_filename=in_ipm_name + '.json',
                config_file=in_config.name,
                out_encoding='utf-8',
                debug=True
            )
            os.remove(config_filename)

        self.assertFalse(result)

        with open(in_ipm_name + '.json', 'r') as json_data:
            json_output = json_data.read()
            parsed_json = json.loads(json_output)

        # Verify the JSON structure and content
        self.assertIsInstance(parsed_json, list)
        self.assertEqual(len(parsed_json), 1)
        self.assertEqual(parsed_json[0]['MTI'], '0100')
        self.assertEqual(parsed_json[0]['DE38'], 'nXmXlX')

        os.remove(in_ipm_name)
        os.remove(in_ipm_name + '.json')

    def test_ipm_to_json_exception_max_reclen(self):
        """
        Actually run using real files, and exception generated
        Triggered through negative RDW on second record -- invalid record length
        KNOWN ISSUE: when pytest run with logging, this test will fail.
        TODO Fix so this test works with pytest debug on
        :return:
        """
        in_ipm_data = (b'\x00\x00\x00\x1a0100\x80\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                       b'nXmXlX\xFF\xFF\xFF\xFF')

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as in_ipm:
            in_ipm.write(in_ipm_data)
            in_ipm_name = in_ipm.name
            print(in_ipm_name)
            in_ipm.close()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = mci_ipm_to_json.cli_run(in_filename=in_ipm_name, out_encoding='utf-8')
            output = f.getvalue()  # .splitlines()
        os.remove(in_ipm_name)
        os.remove(in_ipm_name + '.json')
        print(output)
        self.assertEqual(-1, result)
        assert output.splitlines()[4] == '*** ERROR - processing has stopped ***'

    def test_ipm_to_json_exception_bad_encoding(self):
        in_ipm_data = (b'\x00\x00\x00\x1a'  # reclen
                       b'\xf0\xf1\xf0\xf0'  # mti (cp037)
                       b'\x80\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                       b'nXmXlX\xFF\xFF\x00\x00'
                       )

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as in_ipm:
            in_ipm.write(in_ipm_data)
            in_ipm_name = in_ipm.name
            print(in_ipm_name)
            in_ipm.close()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = mci_ipm_to_json.cli_run(in_filename=in_ipm_name, out_encoding='utf-8')
            output = f.getvalue().splitlines()
        os.remove(in_ipm_name)
        os.remove(in_ipm_name + '.json')
        print(output)
        self.assertEqual(-1, result)

    def test_ipm_to_json_exception_reclen_over_3000_bytes(self):
        """
        Check that diagnostics shows that file is invalid and reason
        """
        in_ipm_data = (b'\x00\x00\x0b\xb9'  # reclen
                       b'0100'              # mti
                       b'\x80\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                       b'nXmXlX')           # data

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as in_ipm:
            in_ipm.write(in_ipm_data)
            in_ipm_name = in_ipm.name
            print(in_ipm_name)
            in_ipm.close()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = mci_ipm_to_json.cli_run(in_filename=in_ipm_name, out_encoding='utf-8')
            output = f.getvalue().splitlines()
        os.remove(in_ipm_name)
        os.remove(in_ipm_name + '.json')
        self.assertEqual(-1, result)
        print(output)

    def test_ipm_to_json_invalid_file(self):
        """
        Check that detected as invalid IPM file
        """
        in_ipm_data = (b'\xFF\xFF\xFF\xFF')  # bad record

        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as in_ipm:
            in_ipm.write(in_ipm_data)
            in_ipm_name = in_ipm.name
            print(in_ipm_name)
            in_ipm.close()

        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            result = mci_ipm_to_json.cli_run(in_filename=in_ipm_name, out_encoding='utf-8')
            output = f.getvalue().splitlines()
        os.remove(in_ipm_name)
        os.remove(in_ipm_name + '.json')
        self.assertEqual(-1, result)
        print(output)

    def test_dicts_to_json_with_field_list(self):
        """
        Test the dicts_to_json function with a specific field list
        """
        test_data = [
            {'MTI': '0100', 'DE38': 'ABC123', 'DE22': '021'},
            {'MTI': '0110', 'DE38': 'DEF456', 'DE22': '022'}
        ]
        
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as out_json:
            mci_ipm_to_json.dicts_to_json(test_data, out_json, field_list=['MTI', 'DE38'])
            out_json.seek(0)
            result = json.load(out_json)
            
        expected = [
            {'MTI': '0100', 'DE38': 'ABC123'},
            {'MTI': '0110', 'DE38': 'DEF456'}
        ]
        
        self.assertEqual(result, expected)

    def test_dicts_to_json_without_field_list(self):
        """
        Test the dicts_to_json function without a field list (should include all fields)
        """
        test_data = [
            {'MTI': '0100', 'DE38': 'ABC123'},
            {'MTI': '0110', 'DE38': 'DEF456'}
        ]
        
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as out_json:
            mci_ipm_to_json.dicts_to_json(test_data, out_json)
            out_json.seek(0)
            result = json.load(out_json)
            
        self.assertEqual(result, test_data)


if __name__ == '__main__':
    unittest.main()