# Static server for the prototypes (replaces `python3 -m http.server 8000`): same behaviour, plus HTTP Range requests,
# which browsers need to seek inside the video (assets/video/recording.mp4).
# Usage (from ~/wemu-sleep-playback): python3 tools/serve.py [port]
import http.server, os, re, sys

class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        self._range = None
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or os.path.isdir(path) or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)$', rng.strip())
        size = os.path.getsize(path)
        if not m or (m.group(1) == '' and m.group(2) == ''):
            return super().send_head()
        if m.group(1) == '':
            start, end = max(size - int(m.group(2)), 0), size - 1
        else:
            start = int(m.group(1)); end = int(m.group(2)) if m.group(2) else size - 1
        if start >= size:
            self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return None
        end = min(end, size - 1)
        f = open(path, 'rb'); f.seek(start)
        self._range = end - start + 1
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(self._range))
        self.end_headers()
        return f

    def copyfile(self, source, outputfile):
        n = getattr(self, '_range', None)
        if n is None:
            return super().copyfile(source, outputfile)
        while n > 0:
            buf = source.read(min(65536, n))
            if not buf: break
            outputfile.write(buf); n -= len(buf)

    def end_headers(self):
        if getattr(self, '_range', None) is None:
            self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()

    def log_message(self, *a):
        pass

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    http.server.ThreadingHTTPServer(('', port), RangeHandler).serve_forever()
