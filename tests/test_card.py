import unittest
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from pac import card


def track(name, *artists):
    return {"name": name, "artists": [{"name": a} for a in artists]}


class CardTest(unittest.TestCase):
    def test_renders_valid_svg_with_every_track(self):
        svg = card.render(
            "Mix <&>",
            [track("Kitsch", "IVE"), None, track("A & B", "C", "D")],
            now=datetime(2026, 10, 17, 18, 0, tzinfo=timezone.utc),
        )
        root = ET.fromstring(svg)  # raises if the XML is broken
        text = "".join(root.itertext())
        self.assertIn("Mix <&>", text)
        self.assertIn("3 tracks", text)
        self.assertIn("Kitsch", text)
        self.assertIn("(unavailable)", text)
        self.assertIn("A & B", text)
        self.assertIn("C, D", text)
        self.assertIn("updated 2026-10-17 18:00 UTC", text)

    def test_height_grows_with_tracks(self):
        one = ET.fromstring(card.render("x", [track("a", "b")]))
        three = ET.fromstring(card.render("x", [track("a", "b")] * 3))
        self.assertEqual(int(three.get("height")) - int(one.get("height")), 2 * card.ROW)

    def test_empty_playlist(self):
        self.assertIn("No songs yet.", card.render("x", []))

    def test_fit_counts_wide_characters_double(self):
        self.assertEqual(card.fit("abc", 5), "abc")
        self.assertTrue(card.fit("夜に駆ける夜に駆ける", 8).endswith("…"))
        self.assertLessEqual(sum(card._width(c) for c in card.fit("夜に駆ける夜に駆ける", 8)), 8)


if __name__ == "__main__":
    unittest.main()
