<?php
declare(strict_types=1);
require __DIR__ . '/benchmark.php';
function check(bool $value, string $label): void { if (!$value) { throw new RuntimeException($label); } }
$orders = [
    ['id' => 1, 'customer_id' => 1, 'status' => 'open', 'total_cents' => 500],
    ['id' => 2, 'customer_id' => 1, 'status' => 'closed', 'total_cents' => 999],
    ['id' => 3, 'customer_id' => 1, 'status' => 'open', 'total_cents' => 300],
    ['id' => 4, 'customer_id' => 2, 'status' => 'open', 'total_cents' => 200],
];
$expected = [[1,800],[2,200],[3,0]];
check(repeatedScan($orders, 3) === $expected, 'Legacy report known totals');
check(onePass($orders, 3) === $expected, 'Modern report known totals, closed excluded, empty customer retained');
check(onePass([], 2) === [[1,0],[2,0]], 'Empty fixture');
check(onePass(fixture(1000, 200), 200) === repeatedScan(fixture(1000, 200), 200), 'Generator parity');
$sec = security();
check(count($sec['cases']) === 6, 'Complete security test set');
$byId = array_column($sec['cases'], null, 'id');
check($byId['normal']['arms']['legacy-concatenation']['rowIds'] === $byId['normal']['arms']['prepared-and-scoped']['rowIds'], 'Same normal output');
check($byId['boolean-injection']['arms']['legacy-concatenation']['otherTenantRows'] === 6, 'Owned injection fixture reproduces exposure');
check($byId['direct-cross-tenant']['arms']['prepared-only-control']['passed'] === false, 'Parameters alone do not authorize tenant');
check($byId['direct-cross-tenant']['arms']['prepared-and-scoped']['passed'] === true, 'Tenant-scoped policy rejects other tenant');
check($byId['apostrophe']['arms']['prepared-and-scoped']['passed'] === true, 'Normal punctuation remains valid');
echo "10 harness assertions passed\n";
