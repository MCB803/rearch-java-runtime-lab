# Java sipariş akışı — tamamlanan ölçüm

140/140 yeni JVM koşusu ve bütün 18,560 sipariş çıktısı doğrulandı. 10 protokol/yayın bütünlüğü testi geçti. Ölçüm penceresi 2026-10-15T09:16:13.987358+00:00 — 2026-10-15T09:25:40.111934+00:00.

| Sipariş | Kol | Medyan batch (ms) | Min–maks (ms) | Koşu p95 medyanı (ms) | Platform thread medyanı |
| --- | --- | ---: | ---: | ---: | ---: |
| 16 | Java 8 / eski akış | 182.873 | 173.654–197.677 | 182.836 | 12 |
| 16 | Java 25 / aynı eski akış | 184.777 | 167.062–203.370 | 184.744 | 14 |
| 16 | Java 25 / fanout + platform | 31.538 | 28.635–55.493 | 31.525 | 70 |
| 16 | Java 25 / fanout + virtual | 31.610 | 27.590–44.189 | 31.596 | 18 |
| 64 | Java 8 / eski akış | 729.540 | 709.428–785.307 | 729.191 | 12 |
| 64 | Java 25 / aynı eski akış | 725.443 | 693.619–746.240 | 725.373 | 14 |
| 64 | Java 25 / fanout + platform | 97.516 | 90.766–126.343 | 97.382 | 70 |
| 64 | Java 25 / fanout + virtual | 97.451 | 86.802–101.854 | 97.321 | 18 |
| 256 | Java 8 / eski akış | 2949.735 | 2906.581–3086.326 | 2848.080 | 12 |
| 256 | Java 25 / aynı eski akış | 2930.172 | 2849.259–3016.992 | 2841.425 | 14 |
| 256 | Java 25 / fanout + platform | 399.298 | 376.525–433.248 | 398.356 | 70 |
| 256 | Java 25 / fanout + virtual | 380.910 | 332.544–398.512 | 380.653 | 18 |

256 siparişte eski Java 8 akışı 2949.735 ms, modern virtual akış 380.910 ms: **7.744×** süre oranı. Bu, mimari/iş akışı ve eşzamanlılık değişimiyle birlikte ölçülür. Aynı eski kodun Java 25 sonucu 2930.172 ms; sürüm tek başına büyük fark üretmedi.

Aynı 64 çağrı kapasitesinde modern platform kolu 399.298 ms ve 70 platform thread; virtual kolu 380.910 ms ve 18 platform thread kullandı. Bu sayaç sanal thread'leri ve bağımlılık JVM'sini kapsamaz; bellek veya para tasarrufu diye dönüştürülmez.

Darboğaz kontrolü: bağımlılık kapasitesi 8'de eski akış 2935.953 ms, modern virtual akış 2777.251 ms. Oran 1.057×. Dış servis sınırı korununca büyük kazanç ortadan kalkıyor.

1 dakikalık host load aralığı: 4.87–16.32. Apple M3, 24 GiB, native arm64; paylaşılan iş istasyonu. Java 8 yaması güncel Java 8'i temsil etmez. 25 ms bütün kolların ortak bağımlılık modelidir. Müşteri, internet servisi, CPU hızlanması, güvenlik veya parasal tasarruf sonucu iddia edilmez.

- [Yöntem ve ölçülen kaynak](full/sources/README.md)
- [Tüm ham koşular ve çıktılar](full/raw.jsonl)
- [CSV](full/raw.csv)
- [Özet](full/summary.json)
- [Ortam ve sıra](full/manifest.json)
- [Bütünlük karmaları](full/SHA256.json)

Önceki 440 koşuluk runtime deneyi korunur. Bu yeni paket, onun yerine sonuç seçmek için değil, farklı bir iş akışı sorusunu ölçmek için eklenmiştir.
