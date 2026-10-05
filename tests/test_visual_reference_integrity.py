"""Reject damaged reference binaries without an image-library dependency."""
from pathlib import Path
import struct
import zlib


def test_final_visual_references_have_valid_png_chunks_and_complete_pixels():
    root = Path(__file__).resolve().parents[1] / 'doc/ui/reference/user-app-final'
    for name in ('today', 'watchlist', 'ledger', 'stock-detail'):
        data = (root / f'{name}.png').read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n', name
        offset, compressed = 8, bytearray()
        while offset < len(data):
            size = int.from_bytes(data[offset:offset + 4], 'big')
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + size]
            crc = data[offset + 8 + size:offset + 12 + size]
            assert len(crc) == 4 and zlib.crc32(kind + payload) == int.from_bytes(crc, 'big'), (name, kind)
            if kind == b'IHDR':
                width, height, depth, color, _, _, interlace = struct.unpack('>IIBBBBB', payload)
                assert (width, height, depth, interlace) == (941, 1672, 8, 0), name
                assert color in (2, 6), name
            if kind == b'IDAT':
                compressed.extend(payload)
            offset += size + 12
        assert kind == b'IEND' and offset == len(data), name
        pixels = zlib.decompress(compressed)
        stride = width * (3 if color == 2 else 4) + 1
        assert len(pixels) == stride * height, name
        assert all(filter_type <= 4 for filter_type in pixels[::stride]), name
