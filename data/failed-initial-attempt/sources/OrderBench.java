import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.lang.management.ManagementFactory;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/** Synthetic correctness/pilot harness; not a customer application or publication benchmark. */
public final class OrderBench {
    private static volatile long sink;

    private static long expectedReply(int id) { return id * 17L + 11L; }

    private static void serve() throws Exception {
        final ExecutorService workers = Executors.newFixedThreadPool(32);
        try (ServerSocket server = new ServerSocket(0, 512, InetAddress.getByName("127.0.0.1"))) {
            System.out.println(server.getLocalPort());
            System.out.flush();
            while (true) {
                final Socket socket = server.accept();
                workers.submit(new Runnable() {
                    public void run() {
                        try (Socket connection = socket) {
                            connection.setSoTimeout(5000);
                            int id = new DataInputStream(connection.getInputStream()).readInt();
                            // Controlled dependency delay, not a measured external-service latency.
                            Thread.sleep(2);
                            new DataOutputStream(connection.getOutputStream()).writeLong(expectedReply(id));
                        } catch (Exception error) {
                            System.err.println("dependency-error: " + error.getClass().getSimpleName());
                        }
                    }
                });
            }
        }
    }

    private static long cpuJob(int id) {
        long value = id + 1L;
        for (int i = 0; i < 20000; i++) value = (value * 48271L) % 2147483647L;
        return value;
    }

    private static long ioJob(int id, int port) throws Exception {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", port), 5000);
            socket.setSoTimeout(5000);
            socket.setTcpNoDelay(true);
            new DataOutputStream(socket.getOutputStream()).writeInt(id);
            long result = new DataInputStream(socket.getInputStream()).readLong();
            if (result != expectedReply(id)) throw new IllegalStateException("Dependency reply mismatch");
            return result;
        }
    }

    private static final class Workload {
        final String task;
        final int size;
        final int port;
        final long[] amounts;
        final ExecutorService executor;
        final Semaphore permits;
        final long expected;

        Workload(String task, String executorKind, int size, int limit, int port) throws Exception {
            this.task = task; this.size = size; this.port = port;
            this.amounts = new long[task.equals("report") ? size : 0];
            long total = 0;
            for (int i = 0; i < amounts.length; i++) {
                amounts[i] = ((i * 37L + 101L) % 99999L) + 1L;
                if (i % 5 != 0) total += amounts[i] * (((i % 7) * 12 + (i % 365) / 31) + 1L);
            }
            if (!task.equals("report")) {
                for (int i = 0; i < size; i++) total += task.equals("io") ? expectedReply(i) : cpuJob(i);
            }
            this.expected = total;
            this.permits = new Semaphore(limit);
            this.executor = task.equals("report") ? null : executorKind.equals("virtual")
                ? (ExecutorService) Executors.class.getMethod("newVirtualThreadPerTaskExecutor").invoke(null)
                : Executors.newFixedThreadPool(limit);
        }

        long batch(final List<Long> latencies) throws Exception {
            long checksum = 0;
            if (task.equals("report")) {
                long started = System.nanoTime();
                long[] buckets = new long[84];
                for (int i = 0; i < amounts.length; i++) {
                    if (i % 5 != 0) buckets[(i % 7) * 12 + (i % 365) / 31] += amounts[i];
                }
                for (int i = 0; i < buckets.length; i++) checksum += buckets[i] * (i + 1L);
                if (latencies != null) latencies.add(System.nanoTime() - started);
            } else {
                List<Future<long[]>> futures = new ArrayList<Future<long[]>>(size);
                for (int i = 0; i < size; i++) {
                    final int id = i;
                    final long submitted = System.nanoTime();
                    futures.add(executor.submit(new Callable<long[]>() {
                        public long[] call() throws Exception {
                            permits.acquire();
                            try {
                                long value = task.equals("io") ? ioJob(id, port) : cpuJob(id);
                                return new long[] { value, System.nanoTime() - submitted };
                            } finally { permits.release(); }
                        }
                    }));
                }
                for (Future<long[]> future : futures) {
                    long[] result = future.get(30, TimeUnit.SECONDS);
                    checksum += result[0];
                    if (latencies != null) latencies.add(result[1]);
                }
            }
            if (checksum != expected) throw new IllegalStateException("Output checksum mismatch");
            sink = checksum;
            return checksum;
        }

        void close() throws InterruptedException {
            if (executor != null) {
                executor.shutdownNow();
                executor.awaitTermination(5, TimeUnit.SECONDS);
            }
        }
    }

    private static long cpuNanos() {
        return ((com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean()).getProcessCpuTime();
    }

    private static long gcCount() {
        long count = 0;
        for (java.lang.management.GarbageCollectorMXBean bean : ManagementFactory.getGarbageCollectorMXBeans()) {
            if (bean.getCollectionCount() >= 0) count += bean.getCollectionCount();
        }
        return count;
    }

    private static long quantile(long[] sorted, double q) {
        return sorted[Math.max(0, (int) Math.ceil(q * sorted.length) - 1)];
    }

    public static void main(String[] args) throws Exception {
        Locale.setDefault(Locale.ROOT);
        if (args.length == 1 && args[0].equals("serve")) { serve(); return; }
        if (args.length != 7) throw new IllegalArgumentException("task executor size limit port warmupMs measurementMs");
        String task = args[0], kind = args[1];
        int size = Integer.parseInt(args[2]), limit = Integer.parseInt(args[3]), port = Integer.parseInt(args[4]);
        long warmupMs = Long.parseLong(args[5]), measurementMs = Long.parseLong(args[6]);
        if (!(task.equals("report") || task.equals("io") || task.equals("cpu")) ||
            !(kind.equals("platform") || kind.equals("virtual")) || size < 1 || size > 1000000 ||
            limit < 1 || limit > 256 || warmupMs < 0 || measurementMs < 1 || measurementMs > 10000)
            throw new IllegalArgumentException("Invalid benchmark arguments");
        Workload workload = new Workload(task, kind, size, limit, port);
        try {
            long warmupStart = System.nanoTime();
            do { workload.batch(null); } while (System.nanoTime() - warmupStart < warmupMs * 1000000L);
            List<Long> latency = new ArrayList<Long>();
            long beforeCpu = cpuNanos(), beforeGc = gcCount(), started = System.nanoTime();
            int batches = 0;
            do { workload.batch(latency); batches++; } while (System.nanoTime() - started < measurementMs * 1000000L);
            long elapsed = System.nanoTime() - started, processCpu = cpuNanos() - beforeCpu;
            long[] sorted = new long[latency.size()];
            for (int i = 0; i < sorted.length; i++) sorted[i] = latency.get(i);
            Arrays.sort(sorted);
            long operations = task.equals("report") ? batches : (long) batches * size;
            System.out.printf("{\"task\":\"%s\",\"executor\":\"%s\",\"size\":%d,\"limit\":%d," +
                "\"batches\":%d,\"operations\":%d,\"elapsedNanos\":%d,\"processCpuNanos\":%d," +
                "\"p50Nanos\":%d,\"p95Nanos\":%d,\"p99Nanos\":%d,\"checksum\":%d," +
                "\"gcCollections\":%d,\"heapUsedAtEndBytes\":%d,\"errors\":0,\"publishable\":false}%n",
                task, kind, size, limit, batches, operations, elapsed, processCpu,
                quantile(sorted, .50), quantile(sorted, .95), quantile(sorted, .99), sink,
                gcCount() - beforeGc, ManagementFactory.getMemoryMXBean().getHeapMemoryUsage().getUsed());
        } finally { workload.close(); }
    }
}
