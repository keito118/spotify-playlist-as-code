import unittest
from unittest import mock

from pac import spotify


class ReplacePlaylistTest(unittest.TestCase):
    def test_replaces_then_appends_in_batches_of_100(self):
        client = spotify.Client("token")
        uris = [f"spotify:track:{i:022d}" for i in range(250)]
        with mock.patch.object(client, "request") as request:
            client.replace_playlist("pl", uris)
        calls = request.call_args_list
        self.assertEqual([c.args[0] for c in calls], ["PUT", "POST", "POST"])
        self.assertTrue(all(c.args[1] == "/playlists/pl/items" for c in calls))
        self.assertEqual([len(c.args[2]["uris"]) for c in calls], [100, 100, 50])
        self.assertEqual(sum((c.args[2]["uris"] for c in calls), []), uris)

    def test_empty_playlist_is_cleared(self):
        client = spotify.Client("token")
        with mock.patch.object(client, "request") as request:
            client.replace_playlist("pl", [])
        request.assert_called_once_with("PUT", "/playlists/pl/items", {"uris": []})


if __name__ == "__main__":
    unittest.main()
