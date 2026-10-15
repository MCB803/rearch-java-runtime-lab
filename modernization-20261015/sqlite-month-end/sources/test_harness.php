<?php
declare(strict_types=1);
require __DIR__ . '/benchmark.php';
$before = blankDatabase(3); $after = blankDatabase(3);
$data = populate($before, $after, 12, 3);
$independent = $before->query("SELECT c.id,COALESCE(SUM(CASE WHEN o.status='open' THEN o.total_cents ELSE 0 END),0) FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.id ORDER BY c.id")->fetchAll(PDO::FETCH_NUM);
$independent = array_map(static fn(array $r) => [(int)$r[0], (int)$r[1]], $independent);
if ($independent !== $data['expected']) { throw new RuntimeException('Independent aggregation mismatch'); }
if ((int)$after->query('SELECT COUNT(*) FROM orders')->fetchColumn() !== 12) { throw new RuntimeException('Fixture mismatch'); }
if (rows($before, 'SELECT id,total_cents FROM orders ORDER BY id') !== rows($after, 'SELECT id,total_cents FROM orders ORDER BY id')) { throw new RuntimeException('Two database inputs differ'); }
echo "3 streaming fixture assertions passed\n";
