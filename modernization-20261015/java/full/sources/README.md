# Java: sipariş teklifindeki beklemeyi azaltmak

Bu deney, fiyat/stok/kargo bilgilerini bekleyen eski bir sipariş akışını yeniden kurar. Her siparişin üç bağımsız bilgiye ihtiyacı vardır. Eski uygulama sekiz işçiyle çalışır ve her siparişin bağımlılıklarını sırayla çağırır. Modern uygulama bağımsız çağrıları ayrı görevlere ayırır; toplam en fazla 64 bağımlılık çağrısı uçuşta tutulur. Java 25 virtual thread başına bir görev açar; semaphore bağımlılığı aşırı yüklemekten korur.

Bu yeni yazılmış, ölçülmüş bir laboratuvar iş akışıdır. Gerçek müşteri, tarihî bir açık kaynak uygulaması veya gerçek e-ticaret trafiği diye sunulmaz. Eski kalıbın yaşı nedeniyle kaçınılmaz olarak yavaş olduğu varsayılmaz: aynı Java 8 kodunun Java 25 kontrolü ve modern platform-thread kontrolü bütün sonuçlarla yayımlanır.

## Ölçüm öncesinde sabitlenen protokol

- Sipariş sayıları: **16, 64, 256**. Bunlar aynı anda sunulan bir batch'tir; sürekli kullanıcı sayısı değildir.
- Her sipariş için üç loopback TCP çağrısı: fiyat kuruşu, stok adedi, kargo kuruşu. Tüm kollar aynı bağımlılık kodunu kullanır. Her çağrı yeni TCP soketi açar; bu maliyet ölçüme dahildir.
- Bağımlılık her izinli çağrı için **25 ms** bekler. Bu yalnız modelin hizmet süresidir; internette ölçülmüş bir gecikme değildir. Gecikme eski uygulamaya eklenmez; bütün kolların ortak servisi içinde aynıdır.
- Ana deneyde servis kapasitesi **64**; kapasite kontrolünde **8**. Kontrol, dış servis kapasitesi artmadığında istemci tarafı paralelliğin tek başına yeterli olmayacağını sınar.
- Dört ana kol: `legacy-java8` (8 platform işçisi, sıralı bağımlılık), `runtime-java25` (aynı Java 8 bytecode'u, aynı algoritma/8 işçi), `modern-platform-java25` (bağımsız çağrı başına görev, 64 platform işçisi), `modern-virtual-java25` (çağrı başına virtual thread, semaphore 64).
- Darboğaz kontrolünde 256 siparişin eski/modern virtual kolları servis kapasitesi 8 ile tekrarlanır.
- Her nokta/kol için **10 bağımsız yeni JVM**, toplam **140 koşu**. Sabit seed ile karıştırılmış sıra. Her JVM en az **2 saniye ısınır**, başladığı ısınma batch'ini bitirir; ardından bir tam ölçüm batch'i yapılır. Isınma kararlılığı iddiası yoktur.
- Aynı Java kaynağı Java 8 ile **bir kez** derlenir. Native arm64 kurulu Corretto 8 ve 25 seçilir; gerçek sürümler manifesttedir. Eski Java 8 yaması güncel Java 8 diye sunulmaz. Bütün JVM'ler `-Xms128m -Xmx128m -XX:+UseG1GC` kullanır.

## Çıktı ve doğruluk

Sipariş numarası `i` için fiyat `10000 + 17*i`, stok `(7*i) mod 31`, kargo `300 + 19*(i mod 13)` olur. Stok varsa çıktı fiyat+kargo; yoksa `-1` olur. Java bütün servis cevaplarını kontrol eder; Python her siparişin çıktı dizisini bağımsız iş kuralıyla doğrular. Eksik/yanlış cevap, timeout veya süreç hatası çalışmayı durdurur, hatalı kayıtlar silinmez. Güzel çıkan tekrarları seçme adımı yoktur.

`elapsedNanos`, görevlerin sunulmasından sonuçların birleştirilmesine kadar tam batch süresidir. `p95Nanos`, batch başından her siparişin son bağımlılığının dönmesine kadar sürelerin nearest-rank p95'idir; kuyruk beklemesi dahildir. Özet `p95Ms`, 10 ayrı koşunun p95'lerinin medyanıdır; bütün ham isteklerin birleşik yüzdeliği değildir.

`peakPlatformThreads`, Java `ThreadMXBean` tarafından görülen JVM platform thread sayısıdır; sanal thread sayısını içermez. İşçi olmayan JVM thread'leri dahildir; server JVM'si dahil değildir. CPU zamanı yalnız istemci JVM'sidir. Bu değerlerden RSS, toplam donanım maliyeti veya para tasarrufu üretilmez.

## Yeniden çalıştırma

Python 3 ve mevcut Java 8/25 JDK'larıyla, bu dizinden:

```sh
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 run.py --smoke --output /tmp/rearch-java-workflow-smoke
python3 run.py --output /tmp/rearch-java-workflow-full
```

macOS JDK'ları `/usr/libexec/java_home` ile bulunur. Diğer sistemlerde `REARCH_JDK8_HOME` ve `REARCH_JDK25_HOME` tanımlayın. Otomatik JDK kurulumu veya dış servise istek yoktur. Çıktı dizini daha önce var olmamalıdır. Kaynaklar, SHA-256'lar, çalışma sırası, bütün çıktılar ve loglar saklanır; yerel kullanıcı/JDK dizini kamu manifestine yazılmaz.

- `manifest.json`: ortam, JDK build'leri, parametreler, koşu sırası ve sınırlar.
- `raw.jsonl`: tüm koşular ve **tüm sipariş çıktı dizileri**.
- `raw.csv`: tüm koşuların süre/kaynak sayaçları.
- `summary.json`: medyan, min/max, medyan p95 ve platform-thread sayısı; tüm kontrol kolları.
- `sources/`: ölçülen kaynakların donmuş kopyası.
- `logs/`: derleme, her JVM stdout/stderr ve servis hataları.
- `SHA256.json`: veri ve kaynak bütünlüğü.

Paylaşılan geliştirici bilgisayarında tarayıcı/site geliştirme sunucusu çalışıyor olabilir. PHP/SQL laboratuvarıyla tam ölçüm penceresi çakıştırılmaz; host load her koşu öncesi/sonrası kaydedilir. İzole üretim donanımı veya sabit CPU kotası yoktur. Çalışmayı yeniden üretmek aynı sayısal oranı garanti etmez.

## Sonucu nasıl okumalı?

Birincil eski→modern karşılaştırma **iş akışı + eşzamanlılık + runtime** değişimidir. Java 25'e tek başına atfedilmez. Runtime kontrolü, aynı eski akışın sürüm yükseltmesinden elde ettiği farkı gösterir. Aynı eşzamanlılıkta platform kontrolü, fanout ve kapasite ayarının katkısını görünür tutar. Virtual thread'in amacı CPU talimatlarını daha hızlı çalıştırmak değildir; bloklayan işleri daha az platform thread ile ifade edebilmektir. Küçük yüklerde sanal thread overhead'i veya başka darboğazlar faydayı azaltabilir.

Güvenlik ve maliyet sonucu bu deneyde ölçülmez. Modern runtime'a geçiş, desteklenen yama ve güncelleme pratiğinin bir parçasıdır; yalnız sürüm numarası güvenli ürün kanıtı değildir. Servis kapasitesi, hata yönetimi, timeout, iş kuralları ve üretim yükü gerçek proje için ayrıca doğrulanır.

## Birincil yöntem kaynakları — 15 Ekim 2026

- [Oracle Java 25 Virtual Threads](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html): bloklayan I/O, görev başına virtual thread, bağımlılığı semaphore ile sınırlama; CPU hızlanması beklentisinin sınırı. Erişildi.
- [ThreadMXBean, Java 25](https://docs.oracle.com/en/java/javase/25/docs/api/java.management/java/lang/management/ThreadMXBean.html): platform thread sayaçlarının kapsamı; virtual thread'ler dahil değildir.
- [OpenJDK JEP 444](https://openjdk.org/jeps/444): Java 21'de kalıcılaşan virtual threads. Doğrudan belge erişimi bu oturumda 403; davranış açıklaması erişilen Oracle belgesine dayandırıldı.
- [OpenJDK JEP 491](https://openjdk.org/jeps/491): synchronized kaynaklı pinning iyileştirmesi. Doğrudan belge erişimi 403; bu deney synchronized/pinning karşılaştırması yapmaz ve JEP'e özgü kazanım iddia etmez.

Bu laboratuvar önceki 440 koşuluk Java runtime deneyini değiştirmez veya gizlemez; farklı bir soruya yanıt verir.
