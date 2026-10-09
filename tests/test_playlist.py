import unittest

from pac.playlist import parse, parse_track_ref

A = "4uLU6hMCjMI75M1A2tKUQC"
B = "11dFghVXANMlKmJXsNCbNl"


class ParseTrackRefTest(unittest.TestCase):
    def test_accepts_uri_url_and_bare_id(self):
        for ref in (
            f"spotify:track:{A}",
            f"https://open.spotify.com/track/{A}",
            f"https://open.spotify.com/track/{A}?si=abc123",
            f"https://open.spotify.com/intl-ja/track/{A}",
            A,
        ):
            with self.subTest(ref=ref):
                self.assertEqual(parse_track_ref(ref), A)

    def test_rejects_other_things(self):
        for ref in ("spotify:album:" + A, "https://example.com/track/" + A, A[:-1], A + "x", "hello"):
            with self.subTest(ref=ref):
                self.assertIsNone(parse_track_ref(ref))


class ParseTest(unittest.TestCase):
    def test_directives_tracks_and_notes(self):
        pl = parse(f"# @title Mood\n# @playlist {B}\n# comment\n\n{A}  # Rick Astley\nspotify:track:{B}\n")
        self.assertEqual(pl.title, "Mood")
        self.assertEqual(pl.spotify_id, B)
        self.assertEqual([t.id for t in pl.tracks], [A, B])
        self.assertEqual(pl.tracks[0].note, "Rick Astley")
        self.assertEqual(pl.tracks[0].line, 5)
        self.assertEqual(pl.uris, [f"spotify:track:{A}", f"spotify:track:{B}"])
        self.assertEqual(pl.errors, [])
        self.assertEqual(pl.warnings, [])

    def test_playlist_directive_accepts_url(self):
        pl = parse(f"# @playlist https://open.spotify.com/playlist/{B}?si=x\n")
        self.assertEqual(pl.spotify_id, B)

    def test_duplicates_are_errors(self):
        pl = parse(f"{A}\nhttps://open.spotify.com/track/{A}\n")
        self.assertEqual(len(pl.tracks), 1)
        self.assertIn("duplicate", pl.errors[0].message)
        self.assertEqual(pl.errors[0].line, 2)

    def test_bad_lines_are_errors(self):
        pl = parse("not a track\n")
        self.assertEqual(pl.errors[0].line, 1)

    def test_missing_playlist_id_is_a_warning(self):
        pl = parse(A)
        self.assertEqual(pl.errors, [])
        self.assertIn("@playlist", pl.warnings[0].message)


if __name__ == "__main__":
    unittest.main()
