import unittest

from cantools.database import Database, Message, Signal
from cantools.database.errors import DecodeError


class UnknownMultiplexerTest(unittest.TestCase):
    def setUp(self):
        self.message = Message(
            0x7E8, 'OBD_RX', 4,
            [
                Signal('length', 0, 8),
                Signal('pid', 8, 8, is_multiplexer=True),
                Signal('nested', 16, 8, is_multiplexer=True,
                       multiplexer_ids=[12], multiplexer_signal='pid'),
                Signal('rpm', 24, 8,
                       multiplexer_ids=[1], multiplexer_signal='nested'),
                Signal('speed', 16, 8,
                       multiplexer_ids=[13], multiplexer_signal='pid'),
            ],
            header_id=0x123,
        )
        self.db = Database(messages=[self.message])

    def test_unknown_mux_default_is_strict(self):
        data = bytes([4, 16, 0, 0])
        for decode in (self.message.decode, self.message.decode_simple):
            with self.assertRaises(DecodeError):
                decode(data)
        for key in (0x7E8, 'OBD_RX'):
            with self.assertRaises(DecodeError):
                self.db.decode_message(key, data)

    def test_unknown_mux_returns_common_signals(self):
        data = bytes([4, 16, 0, 0])
        expected = {'length': 4, 'pid': 16}
        for decode in (self.message.decode, self.message.decode_simple):
            self.assertEqual(decode(data, allow_unknown_mux=True), expected)
        for key in (0x7E8, 'OBD_RX'):
            self.assertEqual(
                self.db.decode_message(key, data, allow_unknown_mux=True),
                expected,
            )

    def test_known_mux_is_unchanged(self):
        for data, expected in (
            (bytes([4, 13, 80, 0]), {'length': 4, 'pid': 13, 'speed': 80}),
            (bytes([4, 12, 1, 50]),
             {'length': 4, 'pid': 12, 'nested': 1, 'rpm': 50}),
        ):
            self.assertEqual(self.message.decode(data), expected)
            self.assertEqual(
                self.message.decode(data, allow_unknown_mux=True), expected,
            )

    def test_unknown_nested_mux(self):
        data = bytes([4, 12, 99, 50])
        with self.assertRaises(DecodeError):
            self.message.decode(data)
        self.assertEqual(
            self.message.decode(data, allow_unknown_mux=True),
            {'length': 4, 'pid': 12, 'nested': 99},
        )

    def test_truncation_is_independent(self):
        data = bytes([4])
        with self.assertRaises(DecodeError):
            self.message.decode(data, allow_unknown_mux=True)
        self.assertEqual(
            self.message.decode(
                data, allow_truncated=True, allow_unknown_mux=True,
            ),
            {'length': 4},
        )

    def test_container_propagates_option(self):
        payload = bytes([4, 16, 0, 0])
        data = bytes([0, 1, 0x23, len(payload)]) + payload
        container = Message(
            0x700, 'Container', 8, [],
            contained_messages=[self.message],
        )
        db = Database(messages=[container])
        self.assertEqual(
            container.decode(data, decode_containers=True),
            [(self.message, payload)],
        )
        expected = [(self.message, {'length': 4, 'pid': 16})]
        self.assertEqual(
            container.decode_container(data, allow_unknown_mux=True),
            expected,
        )
        self.assertEqual(
            db.decode_message(0x700, data, decode_containers=True,
                              allow_unknown_mux=True),
            expected,
        )
