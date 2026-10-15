<?php
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }

function emit(array $row): void { echo json_encode($row, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES), "\n"; flush(); }
function cpuNs(): int {
    $r = getrusage();
    return (($r['ru_utime.tv_sec'] + $r['ru_stime.tv_sec']) * 1000000 + $r['ru_utime.tv_usec'] + $r['ru_stime.tv_usec']) * 1000;
}
function rows(PDO $db, string $query): array {
    return array_map(static fn(array $r) => [(int)$r[0], (int)$r[1]], $db->query($query)->fetchAll(PDO::FETCH_NUM));
}
function blankDatabase(int $customers): PDO {
    $db = new PDO('sqlite::memory:', null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $db->exec('CREATE TABLE customers(id INTEGER PRIMARY KEY); CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, status TEXT NOT NULL, total_cents INTEGER NOT NULL)');
    $insert = $db->prepare('INSERT INTO customers VALUES(?)');
    for ($i = 1; $i <= $customers; $i++) { $insert->execute([$i]); }
    return $db;
}
function populate(PDO $before, PDO $after, int $size, int $customers): array {
    $totals = array_fill(1, $customers, 0);
    $hash = hash_init('sha256');
    $statements = [$before->prepare('INSERT INTO orders VALUES(?,?,?,?)'), $after->prepare('INSERT INTO orders VALUES(?,?,?,?)')];
    $before->beginTransaction(); $after->beginTransaction();
    for ($i = 0; $i < $size; $i++) {
        $customer = (($i * 73) % $customers) + 1;
        // The cycle term varies status within each customer's history.
        $status = ($i + intdiv($i, $customers)) % 4 === 0 ? 'closed' : 'open';
        $cents = 1000 + (($i * 7919) % 100000);
        $row = [$i + 1, $customer, $status, $cents];
        foreach ($statements as $stmt) { $stmt->execute($row); }
        hash_update($hash, implode(',', $row) . "\n");
        if ($status === 'open') { $totals[$customer] += $cents; }
    }
    $before->commit(); $after->commit();
    $expected = [];
    for ($i = 1; $i <= $customers; $i++) { $expected[] = [$i, $totals[$i]]; }
    return ['expected' => $expected, 'inputSha256' => hash_final($hash)];
}
if (basename(__FILE__) !== basename($_SERVER['SCRIPT_FILENAME'])) { return; }
$smoke = in_array('--smoke', $argv, true);
$protocol = json_decode(file_get_contents(__DIR__ . '/protocol.json'), true, 512, JSON_THROW_ON_ERROR);
$sizes = $smoke ? [100, 200, 500] : $protocol['sizes'];
$customers = $smoke ? 10 : $protocol['customers'];
$runs = $smoke ? 2 : $protocol['runs']; $warmups = $protocol['warmups'];
$correlated = "SELECT c.id, (SELECT COALESCE(SUM(o.total_cents),0) FROM orders o WHERE o.customer_id=c.id AND o.status='open') FROM customers c ORDER BY c.id";
$grouped = "SELECT c.id, COALESCE(t.total,0) FROM customers c LEFT JOIN (SELECT customer_id,SUM(total_cents) AS total FROM orders WHERE status='open' GROUP BY customer_id) t ON t.customer_id=c.id ORDER BY c.id";
emit(['kind' => 'environment', 'protocol' => $protocol['protocol'], 'startedAt' => gmdate('c'), 'sizes' => $sizes, 'customers' => $customers, 'runs' => $runs, 'warmups' => $warmups,
    'phpVersion' => PHP_VERSION, 'sqliteVersion' => (new PDO('sqlite::memory:'))->query('SELECT sqlite_version()')->fetchColumn(), 'architecture' => php_uname('m'),
    'opcacheCli' => ini_get('opcache.enable_cli'), 'memoryLimit' => ini_get('memory_limit'), 'query' => $correlated, 'groupedQuery' => $grouped]);
foreach ($sizes as $size) {
    $before = blankDatabase($customers); $after = blankDatabase($customers);
    $loadStart = hrtime(true);
    $fixture = populate($before, $after, $size, $customers);
    $loadSeconds = (hrtime(true) - $loadStart) / 1e9;
    $expected = $fixture['expected'];
    $outputHash = hash('sha256', json_encode($expected, JSON_THROW_ON_ERROR));
    $pagesBefore = (int)$after->query('PRAGMA page_count')->fetchColumn();
    $indexStart = hrtime(true);
    $after->exec('CREATE INDEX orders_customer_status_total ON orders(customer_id,status,total_cents)');
    $indexSeconds = (hrtime(true) - $indexStart) / 1e9;
    $pagesAfter = (int)$after->query('PRAGMA page_count')->fetchColumn();
    $pageSize = (int)$after->query('PRAGMA page_size')->fetchColumn();
    emit(['kind' => 'fixture', 'size' => $size, 'customers' => $customers, 'inputSha256' => $fixture['inputSha256'], 'outputSha256' => $outputHash, 'expectedRows' => $expected,
        'loadSeconds' => $loadSeconds, 'indexBuildSeconds' => $indexSeconds, 'tableBytes' => $pagesBefore * $pageSize, 'withIndexBytes' => $pagesAfter * $pageSize, 'indexExtraBytes' => ($pagesAfter - $pagesBefore) * $pageSize,
        'plans' => ['sql-unindexed-correlated' => $before->query('EXPLAIN QUERY PLAN ' . $correlated)->fetchAll(PDO::FETCH_ASSOC), 'sql-indexed-correlated' => $after->query('EXPLAIN QUERY PLAN ' . $correlated)->fetchAll(PDO::FETCH_ASSOC), 'sql-indexed-grouped-control' => $after->query('EXPLAIN QUERY PLAN ' . $grouped)->fetchAll(PDO::FETCH_ASSOC)]]);
    $arms = ['sql-unindexed-correlated' => [$before, $correlated], 'sql-indexed-correlated' => [$after, $correlated], 'sql-indexed-grouped-control' => [$after, $grouped]];
    for ($round = -$warmups; $round < $runs; $round++) {
        $names = array_keys($arms); $shift = ($round + $warmups) % count($names);
        $names = array_merge(array_slice($names, $shift), array_slice($names, 0, $shift));
        foreach ($names as $position => $name) {
            $cpu = cpuNs(); $start = hrtime(true);
            $result = rows(...$arms[$name]);
            $wall = hrtime(true) - $start; $cpu = cpuNs() - $cpu;
            if ($result !== $expected) { throw new RuntimeException("Full output mismatch: $size $name"); }
            emit(['kind' => 'sample', 'size' => $size, 'arm' => $name, 'run' => $round, 'warmup' => $round < 0, 'position' => $position, 'wallSeconds' => $wall / 1e9, 'cpuSeconds' => $cpu / 1e9,
                'outputSha256' => hash('sha256', json_encode($result, JSON_THROW_ON_ERROR)), 'outputRows' => count($result), 'rows' => $result]);
        }
    }
    unset($arms, $before, $after);
}
emit(['kind' => 'completion', 'finishedAt' => gmdate('c'), 'allOutputsEquivalent' => true]);
