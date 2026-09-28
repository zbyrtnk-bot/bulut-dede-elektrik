import unittest
from datetime import datetime, timezone

from scripts.sync_kibtek_outages import image_url, parse_post


NOW = datetime(2026, 9, 28, 14, 0, tzinfo=timezone.utc)
URL = "https://www.facebook.com/elektrikkurumu/posts/123456789"


class OutageParsingTests(unittest.TestCase):
    def test_caption_notice_is_parsed_without_claiming_an_active_outage(self):
        post = {
            "message": "PLANLI KESİNTİ (GİRNE İLÇESİ)\n28 Eylül 2026 Pazartesi günü orta gerilim elektrik şebekesinde yapılacak bakım çalışması nedeniyle 18:00 ile 20:00 saatleri arasında; Lapta ve Alsancak bölgelerine elektrik enerjisi verilemeyecektir.",
            "created_time": "2026-09-28T11:00:00+0000", "permalink_url": URL,
        }
        notice = parse_post(post, NOW)
        self.assertEqual(notice["status"], "planned")
        self.assertEqual(notice["district"], "Girne")
        self.assertEqual(notice["area"], "Lapta ve Alsancak bölgelerine")
        self.assertIn("bakım çalışması", notice["reason"])
        self.assertEqual(notice["estimatedEndAt"], "2026-09-28T20:00:00+03:00")

    def test_ocr_image_notice_extracts_date_reason_district_and_area(self):
        post = {
            "message": "PLANLI KESİNTİ duyurusu",
            "image_text": (
                "ELEKTRİK KESİNTİSİ\nPLANLI KESİNTİ (LEFKOŞA İLÇESİ) 21 Eylül Pazartesi günü, "
                "orta gerilim elektrik hattında yapılacak olan akım temini nedeni ile; "
                "09:00 ile 11:00 saatleri arasında, Yakın Doğu Yatırım Boğaz Villalarından enerji kesilerek "
                "Gönyeli SAM, Pembe Gül Sokak, Cennet Sokak ve civarına enerji kesintisi yapılacaktır."
            ),
            "created_time": "2026-09-19T08:00:00+0000", "permalink_url": URL,
        }
        notice = parse_post(post, datetime(2026, 9, 20, 7, 0, tzinfo=timezone.utc))
        self.assertEqual(notice["status"], "planned")
        self.assertEqual(notice["district"], "Lefkoşa")
        self.assertEqual(notice["startsAt"], "2026-09-21T09:00:00+03:00")
        self.assertEqual(notice["estimatedEndAt"], "2026-09-21T11:00:00+03:00")
        self.assertEqual(notice["reason"], "orta gerilim elektrik hattında yapılacak olan akım temini")
        self.assertEqual(notice["area"], "Gönyeli SAM, Pembe Gül Sokak, Cennet Sokak ve civarına")

    def test_past_estimated_window_becomes_unconfirmed_not_active(self):
        post = {
            "message": "PLANLI KESİNTİ (GİRNE İLÇESİ)\n28 Eylül 2026 Pazartesi günü bakım çalışması nedeniyle 09:00 ile 11:00 saatleri arasında; Lapta bölgesine elektrik enerjisi verilemeyecektir.",
            "created_time": "2026-09-28T06:00:00+0000", "permalink_url": URL,
        }
        notice = parse_post(post, datetime(2026, 9, 28, 9, 30, tzinfo=timezone.utc))
        self.assertEqual(notice["status"], "unconfirmed")
        self.assertEqual(notice["area"], "Lapta bölgesine")

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

    def test_cancelled_notice_is_not_scheduled(self):
        post = {
            "message": "PLANLI KESİNTİ iptal edildi. 28 Eylül 2026 bakım nedeniyle 18:00 ile 20:00 saatleri arasında; Lapta bölgesine elektrik enerjisi verilemeyecektir.",
            "created_time": "2026-09-28T11:00:00+0000", "permalink_url": URL,
        }
        self.assertIsNone(parse_post(post, NOW))

    def test_post_image_url_is_found_in_attachment(self):
        post = {"attachments": {"data": [{"media": {"image": {"src": "https://scontent.example.fbcdn.net/notice.jpg"}}}]}}
        self.assertEqual(image_url(post), "https://scontent.example.fbcdn.net/notice.jpg")


if __name__ == "__main__":
    unittest.main()
