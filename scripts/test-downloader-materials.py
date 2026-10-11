"""Regression checks for license collection and exact text decoding."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('downloader_builder',Path(__file__).with_name('build-downloader.py'))
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class LicenseMaterials(unittest.TestCase):
    def test_actual_metadata_notices_retained(self):
        for path in ('packaging-26.0.dist-info/licenses/LICENSE',
                     'packaging-26.0.dist-info/licenses/LICENSE.BSD',
                     'package-1.0.dist-info/licenses/vendor/terms.txt',
                     'altgraph-0.17.5.dist-info/LICENSE',
                     'PyInstaller-6.22.3.dist-info/licenses/COPYING.txt',
                     'vendor/LICENSE.md','vendor/NOTICE'):
            with self.subTest(path=path):self.assertTrue(builder.is_license_file(path))

    def test_license_named_code_package_excluded(self):
        for path in ('packaging/licenses/__init__.py','packaging/licenses/_spdx.py',
                     'packaging/licenses/__pycache__/_spdx.cpython-313.pyc',
                     'packaging/licenses.py','package.dist-info/licenses/bad.pyd'):
            with self.subTest(path=path):self.assertFalse(builder.is_license_file(path))

    def test_utf8_and_bom_encodings_preserve_legal_text(self):
        text='Copyright holder — 许可。\nPermission granted.\n'
        for encoding in ('utf-8','utf-8-sig','utf-16','utf-32'):
            with self.subTest(encoding=encoding):self.assertEqual(builder.decode_license_text(text.encode(encoding)),text)

    def test_binary_or_corrupt_text_refused(self):
        for data in (b'license\x00text',b'\xff\xfe\x00',b'\xf3\r\r\n\0\0',b'\xff',
                     'license\ufffd'.encode('utf-8')):
            with self.subTest(data=data):
                with self.assertRaises((ValueError,UnicodeError)):builder.decode_license_text(data)


if __name__=='__main__':unittest.main()
