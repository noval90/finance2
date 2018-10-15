"""Tests for the data_gatherer module."""

from . import data_gatherer
import config
import unittest


class TestCallSearchApi(unittest.TestCase):

    def test_generalTicker(self):
        actual = data_gatherer._callSearchApi('MSFT', config.API_KEY)
        expected = 'Microsoft Corporation'
        self.assertEqual(actual, expected)

    def test_badTicker(self):
        with self.assertRaises(IOError):
            data_gatherer._callSearchApi('ABCXYZ', config.API_KEY)


class TestCallDailyAdjustedApi(unittest.TestCase):

    def test_generalTicker(self):
        actual = data_gatherer._callDailyAdjustedApi('MSFT', config.API_KEY)
        for k, v in actual.items():
            self.assertIsInstance(k, int)
            self.assertIsInstance(v, float)

    def test_badTicker(self):
        with self.assertRaises(IOError):
            data_gatherer._callDailyAdjustedApi('ABCXYZ', config.API_KEY)


class TestGetAllApiData(unittest.TestCase):

    def test_generalTicker(self):
        actual = data_gatherer._getAllApiData('MSFT', config.API_KEY)
        expected = {}
        self.assertEqual(len(actual.keys()), 1)
        self.assertEqual(list(actual)[0], 'MSFT')
        self.assertSetEqual(set(actual['MSFT'].keys()), {'name', 'price_data'})

if __name__ == '__main__':
    unittest.main()