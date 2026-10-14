# Java 8 → 25: yerel deney hazırlığı

**Durum: hazırlık ve doğruluk denemesi. Yayınlanabilir laboratuvar vakası değildir.**

Bu paket, Java deneyinin teknik hazırlığını site sahibinin üzerinden alır. Mevcut JDK'ları bulur, aynı kaynak kodunu Java 8 bytecode'una bir kez derler, iki runtime'da çalıştırır ve sonuçları bağımsız bir hesapla kontrol eder. Java 25'te platform thread ve virtual thread karşılaştırmasını ayrıca yapar. Ağdan paket indirmez; müşteri verisi kullanmaz; sadece `127.0.0.1` üzerinde geçici bir bağımlılık servisi açar. Başka süreçleri veya Docker konteynerlerini durdurmaz.

İlk paket, yeni yazılmış sentetik bir test uygulamasıdır. Eski bir müşteri uygulaması veya modernize edilmiş açık kaynak ürün diye sunulamaz. Site koleksiyonlarına otomatik veri aktarmaz. `--full` dahil **bütün çıktılarda `publishable: false`** vardır.

## Çalıştırma

Depo kökünden, Python 3 ve mevcut Java 8/25 JDK'larıyla:

```sh
python3 -m unittest discover -s docs/labs/java-modernization -p 'test_*.py' -v
python3 docs/labs/java-modernization/run.py --inspect
python3 docs/labs/java-modernization/run.py --smoke
```

Varsayılan çalışma `--smoke` ile aynıdır: 14 kısa koşu; 100 ms ısınma ve en az 150 ms ölçüm penceresi. Bu süreler yalnız bağlantı, executor ve çıktı doğruluğunu sınamak içindir; JIT'in kararlı hale geldiğini göstermez.

macOS'ta `/usr/libexec/java_home`, Linux'ta yaygın JDK dizinleri ve SDKMAN dizini aranır. Kesin kurulum seçimi için sistemin `JAVA_HOME` değerini değiştirmeden `REARCH_JDK8_HOME` ve `REARCH_JDK25_HOME` kullanılabilir. İstenen ana sürüm ve `javac` bulunamazsa betik açık hata verir; kurulum yapmaz.

Uzun pilot **yalnız açık komutla** çalışır:

```sh
python3 docs/labs/java-modernization/run.py --full --inspect
python3 docs/labs/java-modernization/run.py --full
```

`--full`, her koşuyu yeni JVM'de başlatır; 5 saniye ısınma ve en az 1 saniye ölçüm kullanır. Toplam 440 süreç koşusu, başlatma ve iş tamamlama süreleri hariç yaklaşık 44 dakikalık pencere içerir. Varsayılan profilden kazanç oranı üretmek veya yalnız iyi koşuları seçmek amaçlanmaz. Tam pilotu çalıştırmak, yayın kabulünü sağlamaz.

## Aynı işin tanımı

| İş yükü | İş ve doğru sonuç | Noktalar / kollar |
| --- | --- | --- |
| Rapor | Sentetik sipariş tutarlarını bölge ve ay için toplar; iptal durumundaki kayıtları dışarıda bırakır. Tam sayı kuruş kullanır; 84 kovadan ağırlıklı checksum üretir. | 1.000, 5.000, 10.000, 50.000, 100.000, 500.000, 1.000.000 kayıt. Java 8 ve 25; her noktada 10 bağımsız JVM koşusu. |
| I/O | Bir anda gönderilen işlerin her biri loopback TCP servisine kimlik gönderip tam sayı cevap okur. Bağımlılık 32 platform thread'i ve açıkça yapılandırılmış 2 ms bekleme kullanır. | 16, 64, 256 **birlikte sunulan iş**. Bunlar sürekli kullanıcı veya gerçek sipariş trafiği değildir. |
| CPU kontrolü | Aynı eşzamanlılık düzeninde, I/O yerine 20.000 adımlık modüler hesap yapar. | I/O ile aynı iş sayıları ve executor kolları. Virtual thread'in CPU işini hızlandıracağı varsayılmaz. |

I/O ve CPU kolları: Java 8 platform/16, Java 25 platform/16, Java 25 virtual/16, Java 25 platform/128, Java 25 virtual/128. Aynı limit karşılaştırmaları, runtime değişimini iş kapasitesi ayarı değişikliğinden ayırır. Virtual thread kolunda ayrı görev başına thread ve semaphore kullanılır. Platform thread'ler sabit havuzdadır. 16'dan 128'e geçişten doğan fark tek başına Java sürümü kazancı olarak yazılamaz.

Raporun veri üretimi ve referans çıktının hazırlanması ölçüm penceresinin dışındadır; raporun taranması/toplanması ve doğruluk kontrolü içindedir. I/O her istekte yeni TCP bağlantısı kurar; bağlantı maliyeti ölçüme dahildir. Bağımlılık gerçek internet, veritabanı, HTTP/TLS veya ödeme servisi değildir. 2 ms, gerçek müşteride ölçülmüş bir süre değildir.

Süreler `System.nanoTime()` farkıyla hesaplanır. İstek gecikmesi, executor'a sunumdan sonucun alınmasına kadar kuyruk ve semaphore beklemesini içerir. p50/p95/p99 her JVM koşusundaki gözlemlerin nearest-rank yüzdelikleridir. Özet `medianRunP95Seconds`, koşuların p95 değerlerinin medyanıdır; bütün ham isteklerin birleştirilmiş p95'i diye adlandırılmaz.

Java'nın her iş için checksum kontrolüne ek olarak Python farklı bir referans hesap uygular. CPU referansı, Java döngüsünün kopyası yerine modüler üs hesabını kullanır. Yanlış cevap, eksik işlem, bozuk süre sıralaması veya süreç hatası koşuyu başarısız yapar. Hatalı koşu sessizce atılmaz; tam koşu başarısız kalır.

## Çıktılar

Sonuçlar `artifacts/java-lab-smoke-<UTC>/` veya `artifacts/java-lab-full-<UTC>/` içine gider. Aynı çıktı dizini yeniden kullanılamaz.

- `manifest.json`: gerçek JDK build'leri, mimari/donanım, JVM bayrakları, süre pencereleri, koşu sırası, kaynak SHA-256'ları, durum ve sınırlar.
- `raw.jsonl`, `raw.csv`: her bağımsız koşunun sayımları, checksum'ı, süreleri, süreç CPU zamanı, GC sayısı ve pencere sonu heap kullanımı.
- `summary.json`: her kol için koşu sayısı, medyan batch süresi, throughput ve koşu p95 medyanı. Kazanç iddiası üretmez.
- `logs/`: derleme, bağımlılık ve bütün Java süreçlerinin stdout/stderr kayıtları. Başarısız veya zaman aşımına uğrayan koşular da korunur.
- `SHA256.json`: çıktı dosyalarının bütünlük karmaları. Yerel Java yolu ve derleme yolları kişisel kullanıcı adını içerebilir; kamu teslimi öncesi yeniden üretim için gerekli sürüm bilgisi korunarak yerel yollar arındırılır.

`heapUsedAtEndBytes` RSS veya tepe bellek değildir. `gcCollections` GC duraklama süresi değildir. `processCpuNanos` yalnız ölçülen istemci/rapor JVM'sinin CPU'sudur; bağımlılık sunucusunun maliyetini içermez. Bu değerlerden sunucu adedi veya para tasarrufu çıkarılmaz.

## 14 Ekim 2026 doğrulaması

- Beş protokol testi geçti: 7×10 matris, sınırlı smoke, aynı-limit kontrol kolları, bağımsız CPU oracle'ı ve bozuk/yanlış sonuçları reddetme.
- **14/14 kısa JVM koşusu** gerçek Java 8 ve 25 üzerinde çıktı eşitliği kontrolünü geçti. I/O gerçek loopback soketleriyle çalıştı; dış servise istek gönderilmedi.
- Native arm64: Corretto `1.8.0_432-b06` ve `25.0.3+9-LTS`.
- Ham kanıt: [`artifacts/java-lab-smoke-20261014T072846Z/manifest.json`](../../../artifacts/java-lab-smoke-20261014T072846Z/manifest.json), [`raw.csv`](../../../artifacts/java-lab-smoke-20261014T072846Z/raw.csv), [`SHA256.json`](../../../artifacts/java-lab-smoke-20261014T072846Z/SHA256.json).
- Tam pilot çalıştırılmadı. Sürelerden bir Java 8→25 hızlanma oranı veya ticari fayda sonucu çıkarılmadı.

## Yayın deneyine geçiş: ajanın yapacağı işler

1. İlk gerçek uygulamayı seçmek/uyarlamak; eski ve yeni uygulamanın aynı iş çıktısını ürettiği kabul testlerini yazmak. Bu harness altyapı denemesidir, seçilecek uygulamanın yerine geçmez.
2. Deney günü iki runtime'ın tam patch/build ve lisans/support durumunu resmi kaynaktan doğrulamak. Kurulu eski Java 8 build'ini “güncel Java 8” diye sunmamak.
3. Uygun, sessiz ölçüm ortamı ve aynı CPU/RAM kotasını hazırlamak. Mac pilotunu x86 Linux üretim koşusuyla karıştırmamak; yeni JDK'ları kontrollü yüklemek ve checksum doğrulamak.
4. Gerçek iş yükünde ısınma kararlılığını ve ölçüm penceresini incelemek; yük sürücüsünü darboğaz olmaktan çıkarmak; steady-state trafik, hata ve timeout verisini toplamak. İstemci/bağımlılık kaynaklarını ayrı kaydetmek.
5. RSS, CPU, GC duraklamaları ve bütün ham zaman serilerini uygun araçla toplamak. Gerekirse küçük JVM kıyasları için JMH eklemek; bu betiği JMH ile eşdeğer diye sunmamak.
6. Raporlanan değişimi bütünüyle yöntem ve dağılımıyla incelemek; yavaşlayan veya eşit kalan noktaları da tutmak. Tek bir genel “X kat hızlı” oranı üretmemek.
7. Kod/ham veri teslim paketini ve TR/EN vaka, yöntem, simülasyon adaptörlerini hazırlamak; gerçek ekranları üretmek. Yayın kapılarını ancak bu kanıtlar tamamlanınca değerlendirmek.

Site sahibinin katkısı: gerçek müşteri iş akışı kullanılacaksa kullanım izni ve kapsamı; gerekli özel makine/hesap erişimi; açık depo yayımlama yeri ve lisans tercihi; gerçek ticari maliyet bilgisi. Betik yazımı, veri üretimi, ölçüm otomasyonu ve vaka metni teknik işlerdir, kullanıcıya görev olarak devredilmez.

## Yöntem kaynakları

- [Oracle Java 25 virtual threads](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html): blocking I/O, CPU sınırı ve semaphore ile kısıtlama. Virtual thread'i daha hızlı CPU olarak tanımlamaz.
- [Java System.nanoTime](https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/lang/System.html#nanoTime()): monoton süre farkı kullanımı.
- [OpenJDK JMH](https://github.com/openjdk/jmh): JVM kıyaslarında özel harness ve akran incelemesi ihtiyacı. Bu yerel pilot JMH değildir.
- [Amazon Corretto 8](https://docs.aws.amazon.com/corretto/latest/corretto-8-ug/what-is-corretto-8.html): dağıtım ve güncelleme bağlamı; makinedeki yamanın güncelliğine dair tek başına kanıt değildir.

Kaynaklar 14 Ekim 2026'da kontrol edildi. JEP 444 doğrudan isteği 403 döndü; virtual thread davranışı için Oracle'ın Java 25 belgeleri kullanıldı.
