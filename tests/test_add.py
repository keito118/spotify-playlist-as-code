import tempfile
import unittest
from pathlib import Path

from pac.add import AddError, append_track, pick_playlist, track_label
from pac.playlist import load, load_dir

A = "4uLU6hMCjMI75M1A2tKUQC"
B = "11dFghVXANMlKmJXsNCbNl"


class AddTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "drive.txt").write_text(f"# @title Drive\n# @playlist {B}\n{A}  # Rick", encoding="utf-8")
        (self.dir / "work.txt").write_text("# @title Work BGM\n", encoding="utf-8")
        self.playlists = load_dir(self.dir)

    def test_pick_by_file_name_or_title(self):
        self.assertEqual(pick_playlist(self.playlists, "drive").name, "Drive")
        self.assertEqual(pick_playlist(self.playlists, "work bgm").name, "Work BGM")
        self.assertEqual(pick_playlist(self.playlists, "Work.txt").name, "Work BGM")

    def test_pick_needs_a_name_when_there_are_several(self):
        with self.assertRaisesRegex(AddError, "Choose one of"):
            pick_playlist(self.playlists, "")
        with self.assertRaisesRegex(AddError, "no playlist called"):
            pick_playlist(self.playlists, "party")
        self.assertEqual(pick_playlist(self.playlists[:1], "").name, "Drive")

    def test_append_adds_a_line_with_a_note(self):
        line = append_track(self.playlists[1], B, "Carly Rae Jepsen - Cut To The Feeling")
        self.assertEqual(line, f"https://open.spotify.com/track/{B}  # Carly Rae Jepsen - Cut To The Feeling")
        pl = load(self.dir / "work.txt")
        self.assertEqual([t.id for t in pl.tracks], [B])

    def test_append_keeps_a_file_without_trailing_newline_valid(self):
        append_track(self.playlists[0], B, "")
        pl = load(self.dir / "drive.txt")
        self.assertEqual([t.id for t in pl.tracks], [A, B])
        self.assertEqual(pl.errors, [])

    def test_append_rejects_duplicates(self):
        with self.assertRaisesRegex(AddError, "already in Drive"):
            append_track(self.playlists[0], A, "")

    def test_track_label_is_one_line(self):
        info = {"name": "Song\nTitle", "artists": [{"name": "A"}, {"name": "B"}]}
        self.assertEqual(track_label(info), "A, B - Song Title")
        self.assertEqual(track_label({"name": "Solo"}), "Solo")
