# .NET ürün eşleştirme — tamamlanan ölçüm

.NET 10.0.13 üzerinde 90 ölçüm + 18 ısınma tamamlandı. Her çıktı dizisinin hash’i bağımsız Python hesabıyla aynı; 7 protokol ve yayın testi geçti. 50.000 satır için ana karşılaştırma deneyden önce Dictionary olarak seçildi.

Bu, bellekte hazırlanmış dosya satırlarını 10.000 ürünle eşleştirme işidir. CSV okuma, ağ ve veritabanı yazma dahil değildir. İndeks her batch’te yeniden kurulur ve ana süreye dahildir. Aynı .NET runtime’ında algoritma/tahsis değişimi ölçülür; .NET Framework → 10 kazancı değildir.

| Satır | Kol | Medyan (ms) | CPU (ms) | Yönetilen tahsis (bayt) | İndeks kurulumu (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| 1000 | List.Find tekrarlı arama | 14.216 | 14.237 | 97064 | 0.000 |
| 1000 | Dictionary ile eşleştirme | 0.210 | 0.229 | 292080 | 0.183 |
| 1000 | FrozenDictionary kontrolü | 0.897 | 0.915 | 1.21816e+06 | 0.871 |
| 10000 | List.Find tekrarlı arama | 143.355 | 142.927 | 961064 | 0.000 |
| 10000 | Dictionary ile eşleştirme | 0.466 | 0.488 | 364080 | 0.187 |
| 10000 | FrozenDictionary kontrolü | 1.059 | 1.076 | 1.29016e+06 | 0.873 |
| 50000 | List.Find tekrarlı arama | 708.219 | 705.682 | 4.80106e+06 | 0.000 |
| 50000 | Dictionary ile eşleştirme | 1.506 | 1.528 | 684080 | 0.183 |
| 50000 | FrozenDictionary kontrolü | 1.961 | 1.991 | 1.61016e+06 | 0.923 |

50.000 satırdaki süre oranı **470.226×**. Bu oran tüm dosya aktarımına veya bütün uygulamaya taşınmaz. Modern kolun 5.119 ms yavaş tekrarı dahil bütün gözlemler korundu.

FrozenDictionary bu dosya başına kurulan indeks işinde Dictionary’den yavaş ve daha fazla tahsis yapıyor; kontrol sonuçları çıkarılmadı. 1.000 satırda Dictionary de eski listeden daha fazla bellek tahsis ediyor. Yönetilen tahsis, canlı/tepe bellek veya RSS değildir; CPU süresi para ya da elektrik ölçümü değildir.

- [Yöntem ve kaynak](full/sources/README.md)
- [Bütün ham ölçümler](full/raw.jsonl)
- [CSV](full/raw.csv)
- [Özet](full/summary.json)
- [Ortam ve image digest](full/manifest.json)
- [SHA-256 karmaları](full/SHA256.json)
