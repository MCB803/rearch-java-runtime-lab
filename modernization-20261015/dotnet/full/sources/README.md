# .NET: ürün listesini her satırda yeniden aramamak

10.000 ürünlü bir katalogla içe aktarılan sipariş satırlarını eşleştiriyoruz. Eski kalıp, her satırda ürün listesini `List.Find` ile yeniden tarıyor ve yakalayan lambda oluşturuyor. Modern kalıp kataloğu anahtara göre `Dictionary` içine alıp satırları bu indeksle eşliyor. `FrozenDictionary` üçüncü, salt okunur indeks kontrolü olarak kalıyor.

**Üç kol da aynı .NET 10 runtime'ında çalışır.** Bu, .NET Framework → .NET 10 sürüm performansı deneyi değildir. `Dictionary` eski .NET sürümlerinde de vardır; burada kazanım işin algoritmasını ve tahsis düzenini değiştirmekten gelir. Modern runtime'ın güncel bir API'si olan `FrozenDictionary` her işte daha iyi varsayılmaz: kurulması daha pahalı olabilir. Kontrolün yavaş çıkan sonuçları da korunur.

## Önceden sabitlenen yöntem

- Katalog: 10.000 tekil, güvenilir test SKU'su. İçe aktarma boyutları: **1.000, 10.000, 50.000 satır**.
- Her 17. satırın SKU'su katalogda yoktur. Bulunan satırın sonucu fiyat × adettir; bulunamayan `-1` olur. SKU eşitliği bütün kollar için ordinal ve büyük/küçük harfe duyarlıdır.
- Her nokta/kol için **2 ısınma + 10 ölçüm**, toplam 18 ısınma ve 90 ölçüm. Önceden üretilen sabit seed'li sıra. Aynı süreç içinde çalışır; bağımsız süreç tekrarları değildir.
- **Birincil süre tüm işi kapsar:** her batch'te yeni indeks kurma, satır eşleştirme ve çıktı dizisini üretme. İndeks kurma süresi ayrıca kaydedilir fakat toplamdan çıkarılmaz. Böylece bir kez oluşturulmuş indeksin maliyeti gizlenmez.
- Test verisi üretimi, her koldan önceki açık GC ve çıktı hash'i süre dışında; bütün kollarda aynı sınır kullanılır. İç döngüde uyku, ağ veya yapay gecikme yoktur.
- Official `mcr.microsoft.com/dotnet/sdk:10.0` native `linux/arm64` imajı; gerçek image digest/runtime/SDK manifest ve loglarda. Çalışma konteyneri tek CPU, 768 MiB ve kapalı ağla çalışır. NuGet paket bağımlılığı yoktur. JIT'in tier geçişleri bu kısa karşılaştırmada kapatılmıştır (`DOTNET_TieredCompilation=0`); gerçek uygulamanın varsayılan JIT politikası ölçülmez.

Fiyat kuruşu `1000 + (ürünId * 37) % 100000`; satır `i` için SKU kimliği `(i*7919)%10000`, adet `i%5+1` olur. `i%17==0` ise satır eksik SKU kullanır. Bütün sonuçların sırasıyla signed little-endian 64-bit kodlanmış SHA-256'sı, satır sayısı, bulunamayan sayısı ve toplamı Python'ın bağımsız referansıyla doğrulanır. Isınmaların çıktıları da kontrol edilir. Yanlış sonuç veya süreç hatası tamamlanmış ölçüm diye yayımlanmaz.

## Kaynak ölçümü

`elapsedNanos` için monoton `Stopwatch` kullanılır. `processCpuNanos` aynı işlemin Linux `clock_gettime(CLOCK_PROCESS_CPUTIME_ID)` process CPU süresidir; kısa indeksli işlemleri `/proc` sayaç çözünürlüğünde sıfıra yuvarlamamak için yüksek çözünürlüklü CPU saati kullanılır. `allocatedBytes`, `GC.GetTotalAllocatedBytes(true)` farkıdır: işlem sırasında tahsis edilen yönetilen bellek. **Anlık/tepe bellek, RSS, toplam sunucu maliyeti veya para değildir.** İndeksin sabit maliyeti küçük dosyalarda tahsisi artırabilir; bütün boyutlar birlikte gösterilir.

## Yeniden çalıştırma

Python 3 ve Docker ile, bu dizinden:

```sh
python3 -m unittest discover -s . -p 'test_harness.py' -v
docker pull --platform linux/arm64 mcr.microsoft.com/dotnet/sdk:10.0
python3 run.py --output /tmp/rearch-dotnet-catalog
```

Donmuş imaj için manifestteki digest'i `--image mcr.microsoft.com/dotnet/sdk@sha256:...` ile kullanın. Betik otomatik image indirmez, mevcut dizini yeniden kullanmaz. Ağ yalnız açık `docker pull` adımında gerekir. Çıktıda bütün 108 tekrar `raw.jsonl`/`raw.csv`, ölçüm özetleri `summary.json`, parametreler ve sıra `manifest.json`/`plan.json`, kaynaklar `sources/`, derleme ve süreç çıktıları `logs/`, bütünlük karmaları `SHA256.json` içinde tutulur. Kaynak DLL hash'i manifesttedir.

Paylaşılan Apple geliştirici bilgisayarı ve Docker VM üzerinde ölçülür. Diğer laboratuvarların ağır ölçüm pencereleriyle çakıştırılmaz. CPU kotası vardır, tüm host izole değildir. Bu yeni yazılmış laboratuvar işidir; müşteri veya üretim uygulaması sonucu değildir. Güvenlik, bulut faturası veya web istek kapasitesi ölçülmez.

## Birincil kaynaklar — 15 Ekim 2026

- [Microsoft List.Find](https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1.find?view=net-10.0): listedeki eşleşmeyi arama davranışı ve doğrusal iş.
- [Microsoft FrozenDictionary](https://learn.microsoft.com/en-us/dotnet/api/system.collections.frozen.frozendictionary-2?view=net-10.0): sık okunan, seyrek kurulan sözlükler; oluşturma maliyeti ve güvenilir anahtar koşulu.
- [Microsoft GC.GetTotalAllocatedBytes](https://learn.microsoft.com/en-us/dotnet/api/system.gc.gettotalallocatedbytes?view=net-10.0): process ömründeki yönetilen tahsis sayacı. Deney ardışık iki sayaç değerinin farkını alır.
- [Linux clock_gettime](https://man7.org/linux/man-pages/man3/clock_gettime.3.html): process CPU clock kapsamı; wall-clock zamanından ayrı sayaç.
