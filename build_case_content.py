#!/usr/bin/env python3
"""Create the bilingual case from every verified measurement, never from smoke data."""
import argparse
from datetime import datetime
import html
import importlib.util
import json
from pathlib import Path
import statistics
import shutil

spec = importlib.util.spec_from_file_location('publication', Path(__file__).with_name('prepare_publication.py'))
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)
SIZES = [1000, 5000, 10000, 50000, 100000, 500000, 1000000]
ARMS = [(8, 'platform', 16), (25, 'platform', 16), (25, 'virtual', 16), (25, 'platform', 128), (25, 'virtual', 128)]
REPO = 'https://github.com/MCB803/rearch-java-runtime-lab'
BASE = 'https://rearchlabs.com/labs/java8-25-2026-10-14'
METHOD = 'java8-25-synthetic-order-report'
SLUGS = {'tr':'java-8-25-siparis-raporu', 'en':'java-8-25-order-report'}


def frontmatter(data):
    # JSON is a YAML subset; explicit types avoid language-dependent date/number parsing.
    return '---\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n---\n\n'


def number(value, lang, digits=3):
    result = f'{value:,.{digits}f}'.rstrip('0').rstrip('.') if digits else f'{value:,.0f}'
    return result.replace(',', '_').replace('.', ',').replace('_', '.') if lang == 'tr' else result


def mean_batch(row):
    return row['elapsedNanos'] / row['batches'] / 1e9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--repository', required=True, type=Path)
    args = parser.parse_args()
    manifest, rows, groups = publication.verify(args.run)
    stats = publication.derived(groups)
    seconds = {jdk:[stats[f'report/{jdk}/platform/16/{size}']['batchSeconds']['median'] for size in SIZES] for jdk in [8, 25]}
    wall = (datetime.fromisoformat(manifest['finishedAt']) - datetime.fromisoformat(manifest['startedAt'])).total_seconds()
    loads = [row[key] for row in rows for key in ['hostLoad1mBefore', 'hostLoad1mAfter']]
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    for lang in ['tr', 'en']:
        tr = lang == 'tr'
        fmt = lambda n, digits=3: number(n, lang, digits)
        b, a = seconds[8][-1] * 1000, seconds[25][-1] * 1000
        d8 = stats['report/8/platform/16/1000000']['batchSeconds']
        d25 = stats['report/25/platform/16/1000000']['batchSeconds']
        difference = abs(a - b) / b * 100
        direction = ('daha kısa' if a < b else 'daha uzun') if tr else ('shorter' if a < b else 'longer')
        summary = f'Aynı bytecode ile bellekte 1 milyon sipariş raporu: {fmt(b)} ms → {fmt(a)} ms. Yedi veri boyutu ve 440 gerçek JVM koşusuyla sentetik runtime deneyi.' if tr else f'The same bytecode reports over 1 million in-memory orders in {fmt(b)} ms → {fmt(a)} ms. A synthetic runtime study across seven data sizes and 440 real JVM runs.'
        title = 'Java 8 → 25: aynı sipariş raporu, iki runtime' if tr else 'Java 8 → 25: one order report, two runtimes'
        data = dict(translationKey='java8-25-synthetic-orders', title=title, summary=summary, kind='lab', status='completed', date='2026-10-14', service='app-modernization', technologies=['java'], segments=['kobi','kurumsal','partner'],
                    **{'from':['Corretto 8u432'], 'to':['Corretto 25.0.3']}, repoUrl=REPO, rawDataUrl=BASE + '/raw.csv', featured=True, draft=False,
                    media={'before':f'../../../assets/labs/java8-25/report-8-{lang}.png', 'after':f'../../../assets/labs/java8-25/report-25-{lang}.png'},
                    metrics=[dict(id='million-order-report', label='Bellekte 1 milyon sipariş raporu' if tr else 'In-memory report over 1 million orders', unit='ms', direction='lower_is_better', before=b, after=a, runs=10, aggregation='median', method=METHOD, primary=True, pillars=['performance'])],
                    series=[dict(id='report-record-count', title='Sipariş sayısına göre rapor süresi' if tr else 'Report duration by order count', xLabel='Sentetik sipariş kaydı' if tr else 'Synthetic order records', yUnit='µs', x=SIZES, before=[v*1e6 for v in seconds[8]], after=[v*1e6 for v in seconds[25]], beforeFailures=[])],
                    environment=dict(summary='Apple M3 · 8 çekirdek · 24 GiB RAM · macOS Darwin 25.5.0 · native arm64. Paylaşılan geliştirme makinesi; tarayıcı ve site geliştirme sunucusu açık.' if tr else 'Apple M3 · 8 cores · 24 GiB RAM · macOS Darwin 25.5.0 · native arm64. Shared developer workstation with a browser and the website development server running.',
                        data='1.000–1.000.000 deterministik sipariş; müşteri verisi yok. Tam sayı kuruşlar, iptal filtresi ve 84 bölge/ay kovası; aynı çıktı checksum ile doğrulandı.' if tr else '1,000–1,000,000 deterministic orders; no customer data. Integer amounts, cancellation filter and 84 region/month buckets; equal outputs checked by checksum.',
                        tools=['Amazon Corretto 1.8.0_432-b06', 'Amazon Corretto 25.0.3+9-LTS', 'Java 8 javac → same bytecode', 'Python standard library oracle', '-Xms256m -Xmx256m -XX:+UseG1GC'],
                        repetitions='44 kol × 10 taze JVM = 440 koşu. Her JVM: 5 sn ısınma, en az 1 sn ölçüm; sabit rastgele sıra; bütün tekrarlar dahil.' if tr else '44 arms × 10 fresh JVMs = 440 runs. Each JVM: 5 s warmup, at least 1 s measurement; fixed randomized order; every repetition included.'),
                    process=[
                        dict(title='Deney kapsamı' if tr else 'Experiment scope', ai='Aynı iş çıktısını üreten sentetik rapor, I/O ve CPU kontrolü tasarlandı.' if tr else 'Designed synthetic report, I/O and CPU controls that produce the same output.', human='Site sahibi yaygın Java sistemlerini karşılaştırma ve gerçek ölçüm yayımlama yönünü belirledi.' if tr else 'The site owner requested common Java migration examples and publication of actual measurements.', hours=None),
                        dict(title='Çalıştırma ve doğrulama' if tr else 'Execution and verification', ai='Düzenek yazıldı; gerçek JVM süreçleri çalıştırıldı, bağımsız checksum ve dosya bütünlüğü denetlendi. Başarısız ilk deneme ayrı korundu.' if tr else 'Implemented the harness, ran actual JVM processes, checked independent output checksums and file integrity, and retained the failed initial attempt separately.', human='Yerel makinede tam ölçüm yapılması onaylandı. Bu adım için ayrı insan çalışma saati veya kod inceleme kaydı tutulmadı.' if tr else 'Local full measurement was authorised. No separate human time log or human code-review record was kept for this step.', hours=None),
                        dict(title='Açık kanıt paketi' if tr else 'Open evidence package', ai='Tüm ölçümler, kaynaklar, kontrol kolları ve iki dilde sonuç metni hazırlandı; ham değerler değiştirilmedi.' if tr else 'Prepared all measurements, sources, control arms and bilingual findings without changing raw values.', human='Site sahibi yayına açılmasını istedi. Otomasyon süresi insan emeği saati olarak yazılmadı.' if tr else 'The site owner requested launch. Automation wall time was not reported as human working hours.', hours=None),
                    ])
        if tr:
            body = f'''## Bu rapor hangi işi yapıyor?

Bir sipariş listesinden iptal edilen kayıtları çıkarıp tutarları bölge ve aya göre topluyoruz. Veri bir kez üretiliyor; zamanlanan bölüm tarama, toplama ve sonuç kontrolü. Veritabanı, ağ veya ekran çizimi rapor süresine dahil değil.

Kod Java 8 ile bir kez derlendi. Aynı bytecode, aynı veri ve aynı heap/GC bayraklarıyla iki kurulu runtime'da çalıştı. Bu çalışma için yeni yazılan sentetik uygulama kullanıldı; geçmiş bir müşteri uygulamasının dönüşümü olarak sunulmuyor. Yukarıdaki görseller, gerçek ölçümlerden üretilen rapor görüntüleyicisinin ekranlarıdır.

## Bir milyon kayıtta ne değişti?

Önceden seçilen birincil noktada medyan süre **{fmt(b)} ms'den {fmt(a)} ms'ye** geldi: bu koşullarda **%{fmt(difference, 1)} {direction}**. Her değer on ayrı JVM'nin rapor başına ortalama sürelerinin medyanıdır. Tekrar aralığı Java 8 için {fmt(d8["min"]*1000)}–{fmt(d8["max"]*1000)} ms, Java 25 için {fmt(d25["min"]*1000)}–{fmt(d25["max"]*1000)} ms oldu. Yedi veri noktasının tamamı grafikte ve ham dosyada bulunur; yavaş tekrarlar çıkarılmadı.

Bu küçük medyan farkı, örtüşen tekrar aralıklarıyla birlikte okunmalı. Bu işte yalnız runtime değiştirmek belirgin bir hız kazancı göstermedi; %0,3 farkı tek başına geçişin gerekçesi yapmıyoruz. İstatistiksel anlamlılık iddiası veya güven aralığı hesaplaması yoktur.

Runtime değişimini ürününüzde değerlendirmek için ilk iş, sizin günlük raporunuzu veya bekleyen işleminizi aynı çıktı kontrolüyle karşılaştırmaktır. Böylece teknoloji sürümünden önce işin kendisi için karar verirsiniz.

## Bekleyen iş ile hesap yapan iş aynı değil

Rapor deneyine iki kontrol ekledik: gerçek loopback TCP bağlantısıyla cevap bekleyen işler ve 20.000 adımlı sayısal hesap yapan işler. Her grupta 16, 64 ve 256 iş bir arada sunuldu. Bunlar eşzamanlı insan kullanıcı sayıları değildir.

Java 25'te platform ve virtual thread kolları hem 16 hem 128 izinle ölçüldü. İzin sayısını artırmanın etkisiyle thread türünün etkisini ayrı okuyabilirsiniz. Bağımlılık servisinin 32 çalışanı ve her istekte tanımlı 20 ms beklemesi vardır; daha fazla istemci işi bağımlılığın kapasitesini ortadan kaldırmaz.

Aşağıdaki değerler on JVM koşusunun medyan **batch** süresidir; iş başına gecikme değildir. Her işin kuyruğu içeren p95'i ayrıca ham veride ve dağılım dosyasında tutulur.

'''
        else:
            body = f'''## What does the report do?

It filters cancelled orders and groups integer amounts by region and month. Data is generated once; the timed section scans, aggregates and checks the result. Database access, networking and screen rendering are outside this report duration.

The source was compiled once with Java 8. The same bytecode, data and heap/GC flags ran on both installed runtimes. The application was written for this synthetic study; it is not presented as a historical customer migration. The images above are screenshots of a report viewer generated from the actual measurements.

## What changed at one million records?

At the preselected primary point, median duration moved from **{fmt(b)} ms to {fmt(a)} ms**: **{fmt(difference, 1)}% {direction}** in these conditions. Each value is the median of per-JVM average report durations across ten fresh JVMs. Run ranges were {fmt(d8["min"]*1000)}–{fmt(d8["max"]*1000)} ms for Java 8 and {fmt(d25["min"]*1000)}–{fmt(d25["max"]*1000)} ms for Java 25. All seven data points are retained in the chart and raw file; slow repetitions were not removed.

Read this small median difference alongside the overlapping run ranges. Changing only the runtime did not show a material speed gain for this task; a 0.3% difference is not a migration case on its own. No statistical-significance claim or confidence interval is made.

For your product, the next step is to compare your own daily report or waiting operation with the same output checks. That makes the actual task, rather than a version number, the basis for a migration decision.

## Waiting for I/O and computing are different workloads

Two controls accompany the report: jobs waiting for a reply over a real loopback TCP connection, and jobs running a 20,000-step numerical calculation. Each batch submits 16, 64 or 256 jobs together. These counts do not represent simultaneous human users.

Java 25 platform and virtual threads were measured with budgets of both 16 and 128 permits. This separates a larger work budget from executor choice. The dependency has 32 workers and a configured 20 ms wait per request; more client jobs do not remove that dependency limit.

The tables show median **batch** duration across ten JVMs, not per-job latency. Per-job p95 including queue time is retained separately in the raw data and distribution file.

'''
        for task, heading in [('io', 'TCP bekleme kontrolü' if tr else 'TCP waiting control'), ('cpu', 'CPU kontrolü' if tr else 'CPU control')]:
            body += f'### {heading}\n\n'
            body += ('| Runtime / executor / izin | 16 iş · ms | 64 iş · ms | 256 iş · ms |\n' if tr else '| Runtime / executor / permits | 16 jobs · ms | 64 jobs · ms | 256 jobs · ms |\n')
            body += '| --- | ---: | ---: | ---: |\n'
            for jdk, executor, limit in ARMS:
                values = [fmt(stats[f'{task}/{jdk}/{executor}/{limit}/{size}']['batchSeconds']['median']*1000) for size in [16,64,256]]
                body += f'| Java {jdk} / {executor} / {limit} | ' + ' | '.join(values) + ' |\n'
            body += '\n'
        if tr:
            body += f'''## Bu ortamın sınırları

Ölçüm tek bir paylaşılan Apple M3 makinede yapıldı. Tarayıcı ve geliştirme sunucusu açık kaldı; başka ajanlardan ağır test/build çalıştırmamaları istendi. Bir dakikalık sistem yükü {fmt(min(loads),2)}–{fmt(max(loads),2)} aralığındaydı; her koşunun öncesi/sonrası ham kayıtta bulunur. CPU kotası veya ayrı yük üretici kullanılmadı; doğal işletim sistemi ve tarayıcı etkinliği ayrı izole edilmedi. Sabit 5 saniyelik ısınma, JIT'in tamamen kararlı duruma ulaştığını kanıtlamaz.

Corretto **8u432-b06** ile **25.0.3+9-LTS** karşılaştırıldı. Java 8 tarafı güncel yama diye tanımlanmaz; ana sürüm ve yama farklılıkları bu deneyde ayrı ayrı izole edilmedi. Sonuçlar bu build'lere ve işlere aittir. Fiyat, lisans, RSS/tepe bellek, GC duraklamaları veya güvenlik açığı ölçülmedi; bunlardan tasarruf ya da güvenlik oranı türetilmedi.

İlk tam deneme üçüncü süreçte geçici TCP portları tükenince durdu. Tüm kayıtları korundu. Bağımlılığın sentetik beklemesi 2 ms'den 20 ms'ye alındı ve her JVM için yeni bağımlılık portu açıldı; ardından 440 koşunun tamamı baştan çalıştırıldı. İlk denemenin iki tamamlanan sonucu bu tabloya eklenmedi.

Tam koşunun duvar saati süresi {fmt(wall/60,1)} dakikadır; bu, insan çalışma saati değildir. İnsan saatleri kayıtlı olmadığı için süreç bölümünde sayısal emek iddiası yoktur.

## Kaynaklar ve tekrar çalıştırma

[440 ham ölçüm — CSV]({BASE}/raw.csv), [tüm dağılımlar]({BASE}/distributions.json), [ortam ve koşu manifesti]({BASE}/manifest.json), [yayın inceleme kaydı]({BASE}/publication-review.json) ve [kaynak + tüm loglar — ZIP]({BASE}/rearch-java-runtime-lab-2026-10-14.zip) açıktır. Ham dosyalardaki `publishable: false`, koşucunun otomatik yayın onayı vermediğini belirtir; bu bayraklar değiştirilmeden ayrı bir yayın inceleme kaydı hazırlanmıştır.

[Açık kaynak deposundaki]({REPO}) komutlarla aynı matrisi yeniden çalıştırabilirsiniz. [Oracle'ın virtual thread açıklaması](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html) bekleyen I/O ve CPU işlerinin ayrımını açıklar. [Amazon Corretto 8](https://docs.aws.amazon.com/corretto/latest/corretto-8-ug/what-is-corretto-8.html) ve [Corretto 25](https://docs.aws.amazon.com/corretto/latest/corretto-25-ug/what-is-corretto-25.html) dağıtım belgeleri destek modelini açıklar; bu sayfalar kurulu eski build'in güncel olduğunu göstermez. Harness [JMH](https://github.com/openjdk/jmh) kullanmaz.
'''
        else:
            body += f'''## Limits of this environment

Measurement used one shared Apple M3 workstation. A browser and the development server remained open; other agents were asked to avoid heavy builds and tests. One-minute system load ranged from {fmt(min(loads),2)} to {fmt(max(loads),2)}; before/after values for every run are in the raw data. There was no CPU quota or separate load generator; background OS and browser activity was not separately isolated. A fixed five-second warmup does not establish full JIT steady state.

The exact builds were Corretto **8u432-b06** and **25.0.3+9-LTS**. The Java 8 build is not described as current; major-version and patch differences were not isolated. Findings belong to these builds and tasks. Price, licensing, RSS/peak memory, GC pauses and vulnerabilities were not measured, so no cost or security percentage is derived.

The initial full attempt stopped at process three when ephemeral TCP ports were exhausted. All records were retained. The controlled dependency delay changed from 2 ms to 20 ms and each JVM received a fresh dependency port; the entire 440-run matrix then restarted. The two completed measurements from that attempt are excluded from this dataset.

The full run took {fmt(wall/60,1)} minutes of wall-clock time. That is not human work time. Human hours were not tracked, so the process section makes no numerical effort claim.

## Sources and reproduction

[440 raw measurements — CSV]({BASE}/raw.csv), [all distributions]({BASE}/distributions.json), [environment and run manifest]({BASE}/manifest.json), [publication review]({BASE}/publication-review.json) and [source + all logs — ZIP]({BASE}/rearch-java-runtime-lab-2026-10-14.zip) are public. The raw `publishable: false` flags mean the runner does not automatically approve publication. The flags remain unchanged; a separate publication review documents this study's scope.

Reproduce the same matrix with the commands in the [source repository]({REPO}). [Oracle's virtual thread documentation](https://docs.oracle.com/en/java/javase/25/core/virtual-threads.html) explains the distinction between waiting I/O and CPU work. [Amazon Corretto 8](https://docs.aws.amazon.com/corretto/latest/corretto-8-ug/what-is-corretto-8.html) and [Corretto 25](https://docs.aws.amazon.com/corretto/latest/corretto-25-ug/what-is-corretto-25.html) document the distribution's support model, not the currency of this installed old build. The harness does not use [JMH](https://github.com/openjdk/jmh).
'''
        path = output / 'cases' / lang / (SLUGS[lang] + '.mdx')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(frontmatter(data) + body)
    method = dict(id=METHOD, title={'tr':'Aynı bytecode ile sipariş raporu süresi', 'en':'Order-report duration using the same bytecode'}, description={'tr':'1.000–1.000.000 kayıt, her noktada iki runtime ve on taze JVM. Aynı çıktı bağımsız Python hesabıyla doğrulanır; rapor başına sürelerin medyanı alınır.', 'en':'1,000–1,000,000 records, two runtimes and ten fresh JVMs per point. An independent Python oracle checks equal output; median per-report duration is reported.'}, protocol={'tr':'Java 8 javac ile bir kez derlenen aynı bytecode; Corretto 1.8.0_432-b06 ve 25.0.3+9-LTS, native arm64 Apple M3, 24 GiB RAM. Her JVM -Xms256m -Xmx256m -XX:+UseG1GC, 5 sn ısınma ve en az 1 sn ölçüm kullanır. Veri üretimi pencere dışında; tarama, gruplama, checksum ve harness döngüsü içinde. elapsedNanos/batches her koşunun rapor süresidir; on koşunun medyanı gösterilir. Yedi boyut ve tüm tekrarlar saklanır. Paylaşılan masaüstü, kısa ölçüm penceresi ve farklı patch seviyeleri sınırlardır; JMH veya üretim kapasitesi testi değildir.', 'en':'The same bytecode is compiled once by Java 8 javac; Corretto 1.8.0_432-b06 and 25.0.3+9-LTS on native arm64 Apple M3 with 24 GiB RAM. Each JVM uses -Xms256m -Xmx256m -XX:+UseG1GC, 5 s warmup and at least 1 s measurement. Data generation is outside the window; scanning, grouping, checksums and harness-loop overhead are inside. elapsedNanos/batches is the per-run report duration; the median of ten runs is shown. All seven sizes and repetitions are retained. Shared desktop, short windows and different patch levels are limitations; this is not JMH or a production capacity test.'}, scriptsUrl=REPO + '/blob/main/docs/labs/java-modernization/run.py', draft=False)
    (output/'methods').mkdir(exist_ok=True)
    (output/'methods'/f'{METHOD}.yaml').write_text(json.dumps(method, ensure_ascii=False, indent=2)+'\n')
    simulation = {'case':'tr/'+SLUGS['tr'], 'dataScale':[{'taskId':'order-report', 'taskLabel':{'tr':'Bellekteki siparişleri bölge ve aya göre topla', 'en':'Aggregate in-memory orders by region and month'}, 'sizes':SIZES, 'beforeSeconds':seconds[8], 'afterSeconds':seconds[25], 'beforeFailures':[], 'why':{'tr':'İş kuralı, veri ve bytecode aynı; iki kurulu runtime karşılaştırılıyor. JIT, GC uygulaması ve patch düzeyleri birlikte değiştiğinden farkı tek bir Java özelliğine bağlamıyoruz. Ağ veya veritabanı süresi dahil değil. Her nokta on ayrı JVM koşusunun medyanı; bunlar gerçek ürününüzün yanıt süreleri değildir.', 'en':'Business logic, data and bytecode are identical; the two installed runtimes differ. JIT, GC implementation and patch level change together, so the difference is not attributed to one Java feature. Networking and database time are excluded. Each point is the median of ten fresh JVMs, not a response-time estimate for your product.'}, 'runs':10, 'aggregation':'median', 'method':METHOD}]}
    (output/'simulations').mkdir(exist_ok=True)
    (output/'simulations'/'java8-25-orders.json').write_text(json.dumps(simulation, ensure_ascii=False, indent=2)+'\n')
    # Standalone, actual-result viewer; its browser screenshots are the case media.
    for lang in ['tr','en']:
        for jdk in [8,25]:
            table = ''.join(f'<tr><td>{number(size,lang,0)}</td><td>{number(stats[f"report/{jdk}/platform/16/{size}"]["batchSeconds"]["median"]*1e6,lang)}</td><td>{number(stats[f"report/{jdk}/platform/16/{size}"]["batchSeconds"]["min"]*1e6,lang)}–{number(stats[f"report/{jdk}/platform/16/{size}"]["batchSeconds"]["max"]*1e6,lang)}</td><td>10/10</td></tr>' for size in SIZES)
            tr = lang == 'tr'
            build = manifest['jdks'][str(jdk)]['properties']['java.runtime.version']
            title = 'Sipariş raporu' if tr else 'Order report'
            text = f'''<!doctype html><html lang="{lang}"><meta charset="utf-8"><title>Java {jdk} · {title}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f1eb;color:#172722;font:20px ui-monospace,SFMono-Regular,Consolas,monospace}}main{{padding:52px;max-width:1280px}}header{{display:flex;justify-content:space-between;padding-bottom:30px;border-bottom:1px solid #b6bcb4}}.brand{{font-size:22px;letter-spacing:-1px}}.date{{color:#56625b;font-size:16px}}h1{{font:500 50px system-ui;margin:38px 0 12px;letter-spacing:-2px}}.runtime{{color:#56625b;font-size:18px;margin:0 0 34px}}.metrics{{display:flex;gap:50px;padding:24px 0;border-top:1px solid #b6bcb4;border-bottom:1px solid #b6bcb4}}.metrics strong{{display:block;font-size:32px;margin-top:8px}}.label{{font-size:14px;color:#56625b}}table{{width:100%;border-collapse:collapse;font-size:19px;margin-top:26px}}th{{font-size:13px;color:#56625b;letter-spacing:.04em}}td,th{{padding:14px 0;text-align:right;border-bottom:1px solid #d1d4cb}}td:first-child,th:first-child{{text-align:left}}tbody tr:last-child{{background:#e1e7db;font-weight:bold}}footer{{font-size:14px;line-height:1.8;color:#56625b;padding-top:22px}}.ok{{color:#28664d}}</style><main><header><span class="brand">ReArch Labs / Java {jdk}</span><span class="date">2026-10-14 · {'GERÇEK ÖLÇÜM' if tr else 'MEASURED OUTPUT'}</span></header><h1>{title}</h1><p class="runtime">Amazon Corretto {html.escape(build)} · arm64 · same Java 8 bytecode</p><div class="metrics"><div><span class="label">{'VERİ NOKTASI' if tr else 'DATA POINTS'}</span><strong>7</strong></div><div><span class="label">{'TAZE JVM' if tr else 'FRESH JVMS'}</span><strong>70</strong></div><div><span class="label">{'DOĞRU ÇIKTI' if tr else 'CORRECT OUTPUT'}</span><strong class="ok">70 / 70</strong></div><div><span class="label">WARMUP / WINDOW</span><strong>5s / 1s</strong></div></div><table><thead><tr><th>{'SİPARİŞ' if tr else 'ORDERS'}</th><th>{'MEDYAN' if tr else 'MEDIAN'} µs</th><th>MIN–MAX µs</th><th>{'KOŞU' if tr else 'RUNS'}</th></tr></thead><tbody>{table}</tbody></table><footer>Apple M3 · 8 cores · 24 GiB · G1GC · heap 256 MiB<br>{'Sentetik veri · müşteri uygulaması değil · elapsedNanos / batches' if tr else 'Synthetic data · not a customer application · elapsedNanos / batches'}</footer></main></html>'''
            (output/f'report-{jdk}-{lang}.html').write_text(text)
    all_table = '| Group | n | Median batch ms | Min ms | Max ms |\n| --- | ---: | ---: | ---: | ---: |\n'
    for key, values in stats.items():
        d=values['batchSeconds']
        all_table += f'| {key} | {d["n"]} | {d["median"]*1000:.6f} | {d["min"]*1000:.6f} | {d["max"]*1000:.6f} |\n'
    (args.repository/'RESULTS.md').write_text('# Complete results · 14 October 2026\n\n440 fresh JVM runs; all 44 groups have ten repetitions. No completed-matrix outliers were removed. Each batch duration is elapsedNanos/batches. Per-run p95 is a separate measure, not this batch duration.\n\nGroup keys are `task / Java major / executor / concurrent-job permit budget / size`. For `report`, size is the number of generated order records; the report is single-threaded and does not use the executor/permit fields. For `io` and `cpu`, size is the number of jobs submitted together, not a human-user count. Compare platform and virtual arms at the same budget; changing 16 to 128 also changes the configuration. The 32-worker dependency remains shared and bounded.\n\n'+all_table+'\nAll raw measurements and distribution summaries are in data/2026-10-14. The initial failed 2 ms attempt is retained separately and not pooled.\n')
    readme_path = args.repository / 'README.md'
    readme = readme_path.read_text().split('\n## Completed dataset\n')[0].replace('and, after the complete matrix is reviewed, every raw measurement', 'and every raw measurement from the completed, reviewed matrix')
    readme = readme.replace('Results and publication review will be added when the complete matrix has finished and its integrity checks pass.', 'The complete results are in [RESULTS.md](RESULTS.md), the raw dataset in [data/2026-10-14](data/2026-10-14), and the explicit publication scope in [PUBLICATION_SCOPE.md](PUBLICATION_SCOPE.md).')
    readme += f'\n## Completed dataset\n\nAll 440 planned fresh-JVM runs completed with equal outputs and no process or dependency errors. At the preselected 1,000,000-record report point, median duration was **{seconds[8][-1]*1000:.6f} ms** on Corretto 8u432 and **{seconds[25][-1]*1000:.6f} ms** on Corretto 25.0.3. Every other point, all control arms and min/max distributions remain available.\n\nThe approximately 0.3% primary difference has overlapping run ranges and is not a material migration benefit by itself. This exploratory workstation study makes no statistical-significance claim.\n\nThe full matrix took {wall/60:.2f} minutes of automation wall time; human working hours were not tracked. The result-viewer images are screenshots of this measured dataset, not fabricated historical application screens.\n\nThe frozen protocol README retains its pre-run preparation status and future-work notes as measurement provenance. Current acceptance is described in PUBLICATION_SCOPE.md and data/2026-10-14/publication-review.json. Original pilot flags remain false; this separate review approves only the stated synthetic runtime/executor scope, not a customer migration or universal speedup.\n'
    readme_path.write_text(readme)
    for collection in ['cases', 'methods', 'simulations']:
        shutil.copytree(output / collection, args.repository / 'website-content' / collection, dirs_exist_ok=True)
    (args.repository / 'results').mkdir(exist_ok=True)
    for path in output.glob('report-*.html'):
        shutil.copy2(path, args.repository / 'results' / path.name)
    print('Prepared 2 cases, 1 method, 1 simulation, 4 actual-result views and all 44 result groups.')


if __name__ == '__main__':
    main()
