import datetime as dt

import construct
from satellites.filereceiver.imagereceiver import ImageReceiver

from sats_receiver import utils


_frame = construct.Struct(
    'marker' / construct.Int16ul,   # #0
    'dlen' / construct.Int8ul,      # #2
    'cmd' / construct.Int8ul,       # #3
    'x1' / construct.Int8ul,        # #4
    'offset' / construct.Int16ul,   # #5
    'x2' / construct.Int8ul,        # #7
    'data' / construct.Bytes(construct.this.dlen - 6)
)


class ImageReceiverGeoscan(ImageReceiver):
    MARKER_IMG = 1
    CMD_IMG_START = 1
    CMD_IMG_FRAME = 5
    BASE_OFFSET = 4     # old 16384  # old 32768

    def __init__(self, path, verbose=False, display=False, fullscreen=True):
        super().__init__(path, verbose, display, fullscreen)
        self.base_offset = self.BASE_OFFSET
        self._current_fid = None
        self._last_chunk_hash = None
        self._prev_chunk_sz = -1
        self._miss_cnt = 0

    def generate_fid(self):
        self._current_fid = f'GEOSCAN_{dt.datetime.now()}'.replace(' ', '_')
        return self._current_fid

    def parse_chunk(self, chunk):
        try:
            chunk = _frame.parse(chunk)
        except construct.ConstructError:
            return

        if chunk.marker != self.MARKER_IMG:
            self._miss_cnt += 1
            return

        if chunk.cmd == self.CMD_IMG_START:
            self.base_offset = chunk.offset
            chunk.offset = 0

        else:
            chunk.offset -= self.base_offset

        return chunk

    def file_id(self, chunk):
        ch_hash = hash(chunk.data)
        if (chunk.offset == 0
                and chunk.data.startswith(b'\xff\xd8')
                and ch_hash != self._last_chunk_hash):
            # new image
            self.generate_fid()

        self._last_chunk_hash = ch_hash

        return self._current_fid or self.generate_fid()

    def is_last_chunk(self, chunk):
        prev_sz = self._prev_chunk_sz
        self._prev_chunk_sz = len(chunk.data)
        return (self._prev_chunk_sz < prev_sz) and b'\xff\xd9' in chunk.data

    def on_completion(self, f):
        utils.close(f.f)
        self._current_fid = None
        self.base_offset = self.BASE_OFFSET
