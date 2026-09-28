# Kesinti duyurularını güncelleme

`kesintiler.json`, sitedeki **KIB-TEK kesintileri** tablosunun veri kaynağıdır. Boş liste, elektrik olduğu anlamına gelmez; yalnızca doğrulanmış duyuru eklenmediğini gösterir.

Her kontrolün ardından `checkedAt` alanına ISO 8601 tarih ve saat yazın. Her duyuru için aşağıdaki alanlar gereklidir:

| Alan | Anlamı |
| --- | --- |
| `status` | `planned` (sarı), `active` (kırmızı) veya `resolved` (yeşil). Durumu yalnızca resmî açıklamaya göre seçin. |
| `area` | KIB-TEK'in duyurduğu bölge veya mahalleler. |
| `reason` | KIB-TEK'in açıkladığı neden; açıklanmadıysa bunu açıkça yazın. |
| `startsAt` | Duyurulan başlangıç saati. |
| `estimatedEndAt` | Açıklanmışsa yaklaşık bitiş saati; yoksa `null`. |
| `updatedAt` | Bu duyurunun son doğrulama saati. |
| `expiresAt` | Kaydın tablodan otomatik kalkacağı saat. Güncelliğini yitirecek kayıtları açık bırakmayın. |
| `sourceUrl` | KIB-TEK sitesi veya resmî Facebook/X hesabındaki özgün duyuru bağlantısı. |

Tarihleri saat dilimi bilgisi içeren ISO 8601 biçiminde girin (`2026-09-28T12:00:00+03:00` gibi). Sitede saatler Kıbrıs yerel saatinde gösterilir. Aktif bir duyuru 12 saat güncellenmezse kırmızı yerine gri **Güncelliği doğrulanmadı** etiketiyle görünür. Süresi geçmiş kayıtlar gizlenir. Planlı kesintiyi yalnızca saatine bakarak aktif, sessiz kalan kesintiyi de giderilmiş saymayın.

Yeni bir duyuru nesnesi örneği (örnek değerler canlı dosyaya eklenmemelidir):

```json
{
  "status": "planned",
  "area": "DUYURUDA YAZAN BÖLGE",
  "reason": "DUYURUDA YAZAN NEDEN",
  "startsAt": "2099-01-01T09:00:00+02:00",
  "estimatedEndAt": "2099-01-01T12:00:00+02:00",
  "updatedAt": "2098-12-31T17:00:00+02:00",
  "expiresAt": "2099-01-01T12:30:00+02:00",
  "sourceUrl": "https://www.kibtek.com/"
}
```
