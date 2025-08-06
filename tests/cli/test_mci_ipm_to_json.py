import io
import json
import os
import tempfile
import unittest

from tests import print_stream
from cardutil.cli import mci_csv_to_ipm, mci_ipm_to_json
from cardutil.config import config


class MciIpmToJsonParserTestCase(unittest.TestCase):
    def test_mci_ipm_to_json_cli_parser(self):
        args = vars(mci_ipm_to_json.cli_parser().parse_args(['file1.ipm']))
        self.assertEqual(
            args,
            {'in_filename': 'file1.ipm', 'out_filename': None, 'in_encoding': None, 'out_encoding': 'utf-8',
             'no1014blocking': False, 'config_file': None, 'debug': False, 'indent': 2, 'compact': False})

    def test_mci_ipm_to_json_cli_parser_with_options(self):
        args = vars(mci_ipm_to_json.cli_parser().parse_args([
            'file1.ipm', '-o', 'output.json', '--compact', '--indent', '4', '--debug'
        ]))
        self.assertEqual(
            args,
            {'in_filename': 'file1.ipm', 'out_filename': 'output.json', 'in_encoding': None, 'out_encoding': 'utf-8',
             'no1014blocking': False, 'config_file': None, 'debug': True, 'indent': 4, 'compact': True})


class MciIpmToJsonIOTestCase(unittest.TestCase):
    def test_mci_csv_to_ipm_to_json(self):
        """
        create an ipm file from csv, then create json from ipm. Check data integrity.
        """
        def do_test(no_blocking):
            csv_data = 'MTI,DE2,DE4,DE12\n0100,1111222233334444,100,2020-06-18'
            in_csv = io.StringIO(csv_data)
            print_stream(in_csv, 'in_csv')
            in_csv.seek(0)
            out_ipm = io.BytesIO()

            mci_csv_to_ipm.mci_csv_to_ipm(in_csv=in_csv, out_ipm=out_ipm, no1014blocking=no_blocking, config=config)
            out_ipm.seek(0)
            print_stream(out_ipm, 'out_ipm')
            out_ipm.seek(0)

            out_json = io.StringIO()
            mci_ipm_to_json.mci_ipm_to_json(in_ipm=out_ipm, out_json=out_json, config=config, no1014blocking=no_blocking)
            print_stream(out_json, 'out_json')
            out_json.seek(0)

            # Parse the JSON and verify content
            json_data = json.load(out_json)
            self.assertIsInstance(json_data, list)
            self.assertEqual(len(json_data), 1)
            
            record = json_data[0]
            self.assertEqual(record['MTI'], '0100')
            self.assertEqual(record['DE2'], '1111222233334444')
            self.assertEqual(record['DE4'], 100)  # DE4 is correctly parsed as integer
            # DateTime will be serialized as ISO format string
            self.assertTrue(record['DE12'].startswith('2020-06-18'))
            
        do_test(no_blocking=False)
        do_test(no_blocking=True)

    def test_mci_ipm_to_json_compact_format(self):
        """
        Test compact JSON format output
        """
        csv_data = 'MTI,DE2\n0100,1111222233334444'
        in_csv = io.StringIO(csv_data)
        in_csv.seek(0)
        out_ipm = io.BytesIO()

        mci_csv_to_ipm.mci_csv_to_ipm(in_csv=in_csv, out_ipm=out_ipm, no1014blocking=True, config=config)
        out_ipm.seek(0)

        out_json = io.StringIO()
        mci_ipm_to_json.mci_ipm_to_json(
            in_ipm=out_ipm, out_json=out_json, config=config, 
            no1014blocking=True, compact=True
        )
        out_json.seek(0)
        
        json_text = out_json.read()
        # Compact JSON should not have newlines or extra spaces
        self.assertNotIn('\n', json_text)
        
        # But should still be valid JSON
        json_data = json.loads(json_text)
        self.assertIsInstance(json_data, list)
        self.assertEqual(len(json_data), 1)

    def test_mci_ipm_to_json_custom_indent(self):
        """
        Test custom indentation
        """
        csv_data = 'MTI,DE2\n0100,1111222233334444'
        in_csv = io.StringIO(csv_data)
        in_csv.seek(0)
        out_ipm = io.BytesIO()

        mci_csv_to_ipm.mci_csv_to_ipm(in_csv=in_csv, out_ipm=out_ipm, no1014blocking=True, config=config)
        out_ipm.seek(0)

        out_json = io.StringIO()
        mci_ipm_to_json.mci_ipm_to_json(
            in_ipm=out_ipm, out_json=out_json, config=config, 
            no1014blocking=True, indent=4
        )
        out_json.seek(0)
        
        json_text = out_json.read()
        # Should contain proper indentation
        self.assertIn('    ', json_text)  # 4 spaces
        
        # Should still be valid JSON
        json_data = json.loads(json_text)
        self.assertIsInstance(json_data, list)


class MciIpmToJsonTestCase(unittest.TestCase):
    temp_filenames = []

    def setUp(self) -> None:
        self.temp_filenames = []

    def tearDown(self) -> None:
        for filename in self.temp_filenames:
            if os.path.exists(filename):
                os.remove(filename)

    def run_cli_with_ipm_from_csv(self, csv, **kwargs):
        """Helper to create IPM file from CSV and then convert to JSON"""
        # Create IPM from CSV first
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as in_csv:
            in_csv.write(csv)
            in_csv_name = in_csv.name
            in_csv.close()
        
        ipm_filename = in_csv_name + '.ipm'
        mci_csv_to_ipm.cli_run(in_filename=in_csv_name, out_filename=ipm_filename)
        
        self.temp_filenames.extend([in_csv_name, ipm_filename])
        
        # Now convert IPM to JSON
        json_filename = kwargs.pop('out_filename', ipm_filename + '.json')
        
        mci_ipm_to_json.cli_run(in_filename=ipm_filename, out_filename=json_filename, **kwargs)
        self.temp_filenames.append(json_filename)
        
        # Read and return JSON data
        with open(json_filename, 'r') as json_file:
            return json.load(json_file)

    def test_ipm_to_json_basic_conversion(self):
        """Test basic IPM to JSON conversion via CLI"""
        in_csv_data = 'MTI,DE2,DE4\n0100,1111222233334444,100'
        
        json_data = self.run_cli_with_ipm_from_csv(in_csv_data)
        
        self.assertIsInstance(json_data, list)
        self.assertEqual(len(json_data), 1)
        
        record = json_data[0]
        self.assertEqual(record['MTI'], '0100')
        self.assertEqual(record['DE2'], '1111222233334444')
        self.assertEqual(record['DE4'], 100)  # DE4 is correctly parsed as integer

    def test_ipm_to_json_with_custom_filename(self):
        """Test IPM to JSON with custom output filename"""
        in_csv_data = 'MTI,DE2,DE4\n0100,1111222233334444,100'
        
        custom_output = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        custom_output.close()
        
        json_data = self.run_cli_with_ipm_from_csv(in_csv_data, out_filename=custom_output.name)
        
        self.assertIsInstance(json_data, list)
        self.assertEqual(len(json_data), 1)

    def test_ipm_to_json_compact_output(self):
        """Test compact JSON output via CLI"""
        in_csv_data = 'MTI,DE2\n0100,1111222233334444'
        
        # Create temp file to check the actual output format
        temp_json = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        temp_json.close()
        
        self.run_cli_with_ipm_from_csv(in_csv_data, out_filename=temp_json.name, compact=True)
        
        # Read the raw JSON text to check formatting
        with open(temp_json.name, 'r') as f:
            json_text = f.read()
        
        # Compact JSON should not have newlines except potentially at the very end
        lines = json_text.strip().split('\n')
        self.assertEqual(len(lines), 1, "Compact JSON should be on a single line")


if __name__ == '__main__':
    unittest.main()