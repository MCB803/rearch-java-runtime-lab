<?php
declare(strict_types=1);

// Self-owned synthetic lab. CLI only: never serve this intentionally unsafe fixture.
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }

function emit(array $row): void {
    echo json_encode($row, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), "\n";
    flush();
}
function cpuNs(): int {
    $r = getrusage();
    return (($r['ru_utime.tv_sec'] + $r['ru_stime.tv_sec']) * 1000000
        + $r['ru_utime.tv_usec'] + $r['ru_stime.tv_usec']) * 1000;
}
function digest(array $rows): string {
    return hash('sha256', json_encode($rows, JSON_THROW_ON_ERROR));
}
function fixture(int $size, int $customerCount): array {
    $orders = [];
    for ($i = 0; $i < $size; $i++) {
        $orders[] = ['id' => $i + 1, 'customer_id' => (($i * 73) % $customerCount) + 1,
            'status' => $i % 4 === 0 ? 'closed' : 'open', 'total_cents' => 1000 + (($i * 7919) % 100000)];
    }
    return $orders;
}
function repeatedScan(array $orders, int $customerCount): array {
    $result = [];
    for ($customer = 1; $customer <= $customerCount; $customer++) {
        $total = 0;
        foreach ($orders as $order) {
            if ($order['customer_id'] === $customer && $order['status'] === 'open') {
                $total += $order['total_cents'];
            }
        }
        $result[] = [$customer, $total];
    }
    return $result;
}
function onePass(array $orders, int $customerCount): array {
    // The aggregate is rebuilt inside every timed call; no cached-answer advantage.
    $totals = array_fill(1, $customerCount, 0);
    foreach ($orders as $order) {
        if ($order['status'] === 'open') {
            $totals[$order['customer_id']] += $order['total_cents'];
        }
    }
    $result = [];
    for ($customer = 1; $customer <= $customerCount; $customer++) {
        $result[] = [$customer, $totals[$customer]];
    }
    return $result;
}
function measure(callable $fn): array {
    gc_collect_cycles();
    $cpu = cpuNs();
    $start = hrtime(true);
    $result = $fn();
    $wall = hrtime(true) - $start;
    $cpu = cpuNs() - $cpu;
    return ['result' => $result, 'wallSeconds' => $wall / 1e9, 'cpuSeconds' => $cpu / 1e9];
}
function database(array $orders, int $customerCount, bool $indexed): PDO {
    $db = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $db->exec('CREATE TABLE customers (id INTEGER PRIMARY KEY);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL,
        status TEXT NOT NULL, total_cents INTEGER NOT NULL)');
    $db->beginTransaction();
    $customer = $db->prepare('INSERT INTO customers VALUES (?)');
    for ($i = 1; $i <= $customerCount; $i++) { $customer->execute([$i]); }
    $insert = $db->prepare('INSERT INTO orders VALUES (?, ?, ?, ?)');
    foreach ($orders as $order) { $insert->execute(array_values($order)); }
    $db->commit();
    if ($indexed) { $db->exec('CREATE INDEX orders_customer_status_total ON orders(customer_id, status, total_cents)'); }
    return $db;
}
function queryRows(PDO $db, string $sql): array {
    return array_map(static fn(array $row) => [(int)$row[0], (int)$row[1]], $db->query($sql)->fetchAll(PDO::FETCH_NUM));
}
function security(): array {
    $db = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $db->exec('CREATE TABLE invoices(id INTEGER PRIMARY KEY, tenant_id INTEGER, reference TEXT)');
    $stmt = $db->prepare('INSERT INTO invoices VALUES(?, ?, ?)');
    for ($tenant = 1; $tenant <= 2; $tenant++) {
        for ($n = 1; $n <= 5; $n++) { $stmt->execute([($tenant - 1) * 6 + $n, $tenant, sprintf('T%d-%03d', $tenant, $n)]); }
        $stmt->execute([$tenant * 6, $tenant, "T$tenant-O'Brian"]);
    }
    $cases = [
        ['id' => 'normal', 'input' => 'T1-001', 'expected' => [1], 'adversarial' => false],
        ['id' => 'missing', 'input' => 'does-not-exist', 'expected' => [], 'adversarial' => false],
        ['id' => 'apostrophe', 'input' => "T1-O'Brian", 'expected' => [6], 'adversarial' => false],
        ['id' => 'boolean-injection', 'input' => "' OR 1=1 --", 'expected' => [], 'adversarial' => true],
        ['id' => 'tenant-injection', 'input' => "' OR tenant_id=2 --", 'expected' => [], 'adversarial' => true],
        ['id' => 'direct-cross-tenant', 'input' => 'T2-001', 'expected' => [], 'adversarial' => true],
    ];
    $results = [];
    foreach ($cases as $case) {
        $arms = [];
        foreach (['legacy-concatenation', 'prepared-only-control', 'prepared-and-scoped'] as $arm) {
            $rows = []; $error = false;
            try {
                if ($arm === 'legacy-concatenation') {
                    $rows = $db->query("SELECT id, tenant_id FROM invoices WHERE reference='" . $case['input'] . "' ORDER BY id")->fetchAll(PDO::FETCH_NUM);
                } else {
                    $sql = $arm === 'prepared-only-control'
                        ? 'SELECT id, tenant_id FROM invoices WHERE reference=? ORDER BY id'
                        : 'SELECT id, tenant_id FROM invoices WHERE tenant_id=? AND reference=? ORDER BY id';
                    $stmt = $db->prepare($sql);
                    $stmt->execute($arm === 'prepared-only-control' ? [$case['input']] : [1, $case['input']]);
                    $rows = $stmt->fetchAll(PDO::FETCH_NUM);
                }
            } catch (PDOException $e) { $error = true; }
            $ids = array_map(static fn(array $r) => (int)$r[0], $rows);
            $arms[$arm] = ['rowIds' => $ids, 'rowsReturned' => count($rows),
                'otherTenantRows' => count(array_filter($rows, static fn(array $r) => (int)$r[1] !== 1)),
                'queryError' => $error, 'passed' => !$error && $ids === $case['expected']];
        }
        if (!$arms['prepared-and-scoped']['passed']) { throw new RuntimeException('Secure fixture regression'); }
        $results[] = array_merge($case, ['arms' => $arms]);
    }
    return ['kind' => 'security', 'synthetic' => true, 'scope' => 'owned-in-memory-lab',
        'tenant' => 1, 'fixtureRows' => 12, 'cases' => $results];
}

if (basename(__FILE__) !== basename($_SERVER['SCRIPT_FILENAME'])) { return; }
$smoke = in_array('--smoke', $argv, true);
$sizes = $smoke ? [100, 200, 500] : [1000, 3000, 10000, 30000, 60000, 100000, 200000];
$runs = $smoke ? 2 : 10;
$warmups = 2;
$customers = 200;
$correlated = "SELECT c.id, (SELECT COALESCE(SUM(o.total_cents), 0) FROM orders o WHERE o.customer_id=c.id AND o.status='open') FROM customers c ORDER BY c.id";
$grouped = "SELECT c.id, COALESCE(t.total, 0) FROM customers c LEFT JOIN (SELECT customer_id, SUM(total_cents) AS total FROM orders WHERE status='open' GROUP BY customer_id) t ON t.customer_id=c.id ORDER BY c.id";
emit(['kind' => 'environment', 'startedAt' => gmdate('c'), 'phpVersion' => PHP_VERSION,
    'sqliteVersion' => (new PDO('sqlite::memory:'))->query('SELECT sqlite_version()')->fetchColumn(),
    'architecture' => php_uname('m'), 'os' => php_uname('s'), 'cpuCount' => (int)trim((string)shell_exec('getconf _NPROCESSORS_ONLN')),
    'opcacheCli' => ini_get('opcache.enable_cli'), 'memoryLimit' => ini_get('memory_limit'),
    'sizes' => $sizes, 'runs' => $runs, 'warmups' => $warmups, 'customers' => $customers,
    'timing' => 'hrtime(true) monotonic wall clock; getrusage process user+system CPU',
    'scope' => 'same-runtime implementation and SQL-index experiments, not a PHP/DB version comparison']);
foreach ($sizes as $size) {
    $orders = fixture($size, $customers);
    $unindexed = database($orders, $customers, false);
    $indexed = database($orders, $customers, false);
    $pagesBefore = (int)$indexed->query('PRAGMA page_count')->fetchColumn();
    $indexStart = hrtime(true);
    $indexed->exec('CREATE INDEX orders_customer_status_total ON orders(customer_id, status, total_cents)');
    $indexSeconds = (hrtime(true) - $indexStart) / 1e9;
    $pageSize = (int)$indexed->query('PRAGMA page_size')->fetchColumn();
    $pagesAfter = (int)$indexed->query('PRAGMA page_count')->fetchColumn();
    // Independent SQL GROUP BY oracle; includes customers with no open balance.
    $expected = queryRows($unindexed, $grouped);
    $expectedHash = digest($expected);
    emit(['kind' => 'fixture', 'size' => $size, 'customers' => $customers, 'inputSha256' => digest($orders),
        'outputSha256' => $expectedHash, 'outputRows' => count($expected),
        'indexBuildSeconds' => $indexSeconds, 'tableBytes' => $pagesBefore * $pageSize,
        'withIndexBytes' => $pagesAfter * $pageSize, 'indexExtraBytes' => ($pagesAfter - $pagesBefore) * $pageSize,
        'plans' => ['unindexed-correlated' => $unindexed->query('EXPLAIN QUERY PLAN ' . $correlated)->fetchAll(PDO::FETCH_ASSOC),
            'indexed-correlated' => $indexed->query('EXPLAIN QUERY PLAN ' . $correlated)->fetchAll(PDO::FETCH_ASSOC),
            'indexed-grouped-control' => $indexed->query('EXPLAIN QUERY PLAN ' . $grouped)->fetchAll(PDO::FETCH_ASSOC)]]);
    $arms = [
        'php-repeated-scan' => static fn() => repeatedScan($orders, $customers),
        'php-one-pass' => static fn() => onePass($orders, $customers),
        'sql-unindexed-correlated' => static fn() => queryRows($unindexed, $correlated),
        'sql-indexed-correlated' => static fn() => queryRows($indexed, $correlated),
        'sql-indexed-grouped-control' => static fn() => queryRows($indexed, $grouped),
    ];
    for ($round = -$warmups; $round < $runs; $round++) {
        // Deterministic rotation balances position without choosing winning runs.
        $names = array_keys($arms);
        $shift = ($round + $warmups) % count($names);
        $names = array_merge(array_slice($names, $shift), array_slice($names, 0, $shift));
        foreach ($names as $position => $name) {
            $m = measure($arms[$name]);
            if ($m['result'] !== $expected) { throw new RuntimeException("Output mismatch: $size $name"); }
            emit(['kind' => 'sample', 'size' => $size, 'arm' => $name, 'run' => $round,
                'warmup' => $round < 0, 'position' => $position, 'wallSeconds' => $m['wallSeconds'],
                'cpuSeconds' => $m['cpuSeconds'], 'outputSha256' => digest($m['result']), 'outputRows' => count($m['result'])]);
        }
    }
    unset($orders, $arms, $unindexed, $indexed);
}
emit(security());
emit(['kind' => 'completion', 'finishedAt' => gmdate('c'), 'allOutputsEquivalent' => true]);
