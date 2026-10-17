import unittest
from unittest import mock

from pac import spotify
from pac.__main__ import status_lines
from pac.playlist import parse

A = "4uLU6hMCjMI75M1A2tKUQC"
B = "11dFghVXANMlKmJXsNCbNl"
C = "7snQQk1zcKl8gZ92AnueZW"


def track(track_id, name="Song", artist="Artist"):
    return {
        "id": track_id,
        "name": name,
        "artists": [{"name": artist}],
        "external_urls": {"spotify": f"https://open.spotify.com/track/{track_id}"},
    }


def playlist(*ids):
    text = "# @title Test\n# @playlist pl123\n" + "".join(f"spotify:track:{i}\n" for i in ids)
    return parse(text, "playlists/test.txt")


class PlaylistTracksTest(unittest.TestCase):
    def test_follows_pages_and_reads_item_or_track(self):
        client = spotify.Client("token")
        pages = [
            {"items": [{"item": track(A)}, {"track": track(B)}], "next": "more"},
            {"items": [{"item": None}], "next": None},
        ]
        with mock.patch.object(client, "request", side_effect=pages) as request:
            tracks = client.playlist_tracks("pl")
        self.assertEqual([t["id"] if t else None for t in tracks], [A, B, None])
        self.assertIn("offset=2", request.call_args_list[1].args[1])


class StatusLinesTest(unittest.TestCase):
    def test_matching_playlist_lists_tracks(self):
        text = "\n".join(status_lines(playlist(A, B), [track(A, "One|Two"), track(B)]))
        self.assertIn("2 tracks, ✅ matches the file", text)
        self.assertIn(f"| 1 | [One\\|Two](https://open.spotify.com/track/{A}) | Artist |", text)
        self.assertNotIn("➖", text)

    def test_reports_differences(self):
        text = "\n".join(status_lines(playlist(A, B), [track(A), track(C, "Extra")]))
        self.assertIn("⚠️ differs from the file", text)
        self.assertIn(f"➖ In the file but not on Spotify: {B}", text)
        self.assertIn("➕ On Spotify but not in the file: Artist - Extra", text)

    def test_order_change_is_a_difference(self):
        text = "\n".join(status_lines(playlist(A, B), [track(B), track(A)]))
        self.assertIn("⚠️ differs", text)


if __name__ == "__main__":
    unittest.main()
