import unittest
from datetime import datetime, timezone

from scripts.sync_kibtek_outages import parse_post


NOW = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
URL = "https://www.facebook.com/elektrikkurumu/posts/123456789"


class OutageParsingTests(unittest.TestCase):
    def test_planned_notice_keeps_official_estimate_without_claiming_outage(self):
        post = {
            "message": "PLANLI KESİNTİ (GİRNE İLÇESİ)\n28 Eylül 2026 Pazartesi günü orta gerilim elektrik şebekesinde yapılacak bakım çalışması nedeniyle 18:00 ile 20:00 saatleri arasında; Lapta ve Alsancak bölgelerine elektrik enerjisi verilemeyecektir.",
            "created_time": "2026-09-28T11:00:00+0000", "permalink_url": URL,
        }
        notice = parse_post(post, NOW)
        self.assertEqual(notice["status"], "planned")
        self.assertEqual(notice["area"], "Lapta ve Alsancak bölgelerine")
        self.assertEqual(notice["estimatedEndAt"], "2026-09-28T20:00:00+03:00")

    def test_missing_area_never_publishes_a_red_badge(self):
        post = {
            "message": "ARIZALI KESİNTİ 28 Eylül 2026 saat 17:00 itibarıyla çalışma sürüyor.",
            "created_time": "2026-09-28T11:00:00+0000", "permalink_url": URL,
        }
        self.assertIsNone(parse_post(post, NOW))

    def test_old_and_wrong_source_posts_are_rejected(self):
        post = {
            "message": "PLANLI KESİNTİ 28 Eylül 2026 bakım nedeniyle 18:00 ile 20:00 saatleri arasında; Lapta bölgesine elektrik enerjisi verilemeyecektir.",
            "created_time": "2026-09-01T11:00:00+0000", "permalink_url": URL,
        }
        self.assertIsNone(parse_post(post, NOW))
        post["created_time"] = "2026-09-28T11:00:00+0000"
        post["permalink_url"] = "https://example.com/notice"
        self.assertIsNone(parse_post(post, NOW))


if __name__ == "__main__":
    unittest.main()
