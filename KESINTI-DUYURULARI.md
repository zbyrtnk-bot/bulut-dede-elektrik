# KIB-TEK duyuru tablosu

Tablo `kesintiler.json` dosyasını gösterir. Veri dosyası örnek kesinti içermez. Kaynak bağlantısı açılana kadar `checkedAt` değeri `null` kalır ve arayüz bunu açıkça belirtir.

## Meta bağlantısı

KIB-TEK'in resmî Facebook sayfası: https://www.facebook.com/elektrikkurumu/

1. Meta for Developers uygulamasında, yönetmediğiniz bir Facebook sayfasının herkese açık gönderilerini okumak için **Page Public Content Access** erişimini ve uygun kullanıcı erişim belirtecini edinin. KIB-TEK sayfasının sayısal kimliğini Graph API ile doğrulayın.
2. GitHub deposunun **Settings → Secrets and variables → Actions** bölümünde `META_FACEBOOK_TOKEN` gizli anahtarını ve `KIBTEK_FACEBOOK_PAGE_ID` değişkenini tanımlayın. Belirteci kod dosyasına veya `kesintiler.json` içine yazmayın.
3. Instagram isteğe bağlıdır. KIB-TEK'in doğrulanmış profesyonel hesap kullanıcı adı, kendi Instagram profesyonel hesabınızın Business Discovery erişimi ve gerekli onaylar varsa `KIBTEK_INSTAGRAM_USERNAME`, `OWN_INSTAGRAM_BUSINESS_ID` değişkenlerini ve `META_INSTAGRAM_TOKEN` gizli anahtarını tanımlayın. Kullanıcı adı boşsa Instagram kontrol edilmez.
4. İş akışını **Actions → KIB-TEK official social notices → Run workflow** ile çalıştırın. Başarılı erişimden sonra her 15 dakikada bir kontrol yapılır. GitHub zamanlanmış görevleri gecikebilir; tablo son kaynak kontrol saatini gösterir.

İş akışı, kaynak hatasında mevcut JSON'u değiştirmez. Gönderide açık kesinti türü, tarih, saat ve bölge yoksa satır üretmez. Görsel içindeki metin bu sürümde okunmaz; yalnızca gönderinin metni veya Instagram açıklaması işlenir. Planlı saatlerin gelmesi kesintinin başladığını, bitmesi elektriğin geri geldiğini kanıtlamaz. Resmî olarak teyit edilmedikçe otomatik yeşil durum üretilmez. Kesinti sürüyor etiketi yalnızca KIB-TEK'in açık arıza duyurusu için, en fazla 12 saat gösterilir; kaynak kontrolü bir saatten fazla gecikirse griye döner.

Yerel kontrol: `python -m unittest discover -s tests`

Meta belgeleri:

- https://developers.facebook.com/docs/pages-api/posts/
- https://developers.facebook.com/docs/features-reference/page-public-content-access/
- https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/
