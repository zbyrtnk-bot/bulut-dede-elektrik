# KIB-TEK kesinti tablosu

Hamburger menüdeki kesinti tablosu, `kesintiler.json` dosyasındaki resmî duyuruları gösterir. Veri dosyası örnek kayıt içermez. Bağlantı kurulmadıysa tablo bu durumu açıkça yazar.

## Canlı kaynak bağlantısı

Kaynak, KIB-TEK'in [resmî Facebook sayfasıdır](https://www.facebook.com/elektrikkurumu/). GitHub Actions, sayfadaki son 30 gönderiyi yaklaşık 15 dakikada bir Graph API üzerinden kontrol eder. Duyurunun açıklama metni yetmiyorsa Facebook gönderisindeki resim yerel Tesseract `tur+eng` OCR ile okunur. Sitede Facebook akışı veya gönderi resmi açılmaz; sadece çıkarılan bölge, sebep ve saatler tabloya yazılır.

1. Meta for Developers uygulamasında, yönetmediğiniz bir Facebook sayfasının herkese açık gönderilerini okumak için onaylanmış **Page Public Content Access** ve uygun kullanıcı erişim belirtecini kullanın.
2. GitHub deposunun **Settings → Secrets and variables → Actions** bölümüne `META_FACEBOOK_TOKEN` gizli anahtarını ve `KIBTEK_FACEBOOK_PAGE_ID` değişkenini ekleyin. Belirteci kod dosyasına veya JSON dosyasına yazmayın.
3. **Actions → KIB-TEK official social notices → Run workflow** ile ilk kontrolü başlatın. Başarılı çalışmadan sonra `kesintiler.json` güncellenir; GitHub `main` dalından siteye otomatik yayın devreye girer.

## Durum ve güvenlik kuralları

- Sarı: planlı kesinti duyurusu.
- Kırmızı: KIB-TEK'in açıkça arıza kaynaklı diye bildirdiği ve hâlâ güncel olan kesinti.
- Gri: planlı zaman aralığı geçti; KIB-TEK sonucu ayrıca teyit etmedi.
- Yeşil: son kontrol zamanı güncelse, tabloda güncel resmî kesinti duyurusu bulunmadığını belirtir. Bu, elektrik şebekesinin genel durumu hakkında bağımsız teyit değildir.
- Saat aralığının gelmesi kesintinin başladığını, bitmesi elektriğin verildiğini kanıtlamaz. Sistem planlı duyuruyu kırmızıya çevirmez veya yeşil “giderildi” durumu uydurmaz.
- Açık tarih, saat aralığı ve etkilenen bölge bulunamayan gönderi yayımlanmaz. Kaynak hatasında önceki JSON korunur. Son kaynak kontrolü bir saati aşarsa tablo güncelliği uyarısı verir.

Yerel kontrol: `python -m unittest discover -s tests`

Meta belgeleri:

- https://developers.facebook.com/docs/pages-api/posts/
- https://developers.facebook.com/docs/features-reference/page-public-content-access/
