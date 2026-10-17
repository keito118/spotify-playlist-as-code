import unittest

from pac.issue import find_track, parse_form

A = "4uLU6hMCjMI75M1A2tKUQC"

BODY = f"""### Song link

https://open.spotify.com/intl-ja/track/{A}?si=abc

### Playlist

_No response_

### Why this one?

It's a classic.
Two lines.
"""


class ParseFormTest(unittest.TestCase):
    def test_reads_each_field(self):
        fields = parse_form(BODY)
        self.assertEqual(fields["Song link"], f"https://open.spotify.com/intl-ja/track/{A}?si=abc")
        self.assertEqual(fields["Playlist"], "")
        self.assertEqual(fields["Why this one?"], "It's a classic.\nTwo lines.")

    def test_handles_empty_and_windows_newlines(self):
        self.assertEqual(parse_form(""), {})
        self.assertEqual(parse_form("### A\r\n\r\nx\r\n"), {"A": "x"})


class FindTrackTest(unittest.TestCase):
    def test_finds_track_in_shared_text(self):
        for text in (
            A,
            f"spotify:track:{A}",
            f"Never Gonna Give You Up - Rick Astley https://open.spotify.com/track/{A}?si=x",
        ):
            with self.subTest(text=text):
                self.assertEqual(find_track(text), A)

    def test_ignores_non_tracks(self):
        for text in ("", "hello", f"https://open.spotify.com/album/{A}", f"https://example.com/track/{A}"):
            with self.subTest(text=text):
                self.assertIsNone(find_track(text))
