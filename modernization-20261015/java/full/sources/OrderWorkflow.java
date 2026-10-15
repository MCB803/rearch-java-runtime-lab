import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;

/** Deterministic order quote workflow; source is compiled ONCE with Java 8. */
public final class OrderWorkflow {
    private static final int CALLS = 3;

    private static ExecutorService virtualExecutor() throws Exception {
        return (ExecutorService) Executors.class.getMethod("newVirtualThreadPerTaskExecutor").invoke(null);
    }

    private static long dependencyValue(int order, int kind) {
        switch (kind) {
            case 0: return 10000L + order * 17L; // Price, integer cents
            case 1: return (order * 7L) % 31L;   // Available stock
            case 2: return 300L + (order % 13L) * 19L; // Shipping, integer cents
            default: throw new IllegalArgumentException("Unknown dependency");
        }
    }

    private static void serve(final int capacity, final int delayMillis) throws Exception {
        final Semaphore permits = new Semaphore(capacity, true);
        final ExecutorService requests = virtualExecutor();
        try (ServerSocket server = new ServerSocket(0, 1024, InetAddress.getByName("127.0.0.1"))) {
            System.out.println(server.getLocalPort());
            System.out.flush();
            while (true) {
                final Socket socket = server.accept();
                requests.submit(new Runnable() {
                    public void run() {
                        try (Socket current = socket;
                             DataInputStream input = new DataInputStream(current.getInputStream());
                             DataOutputStream output = new DataOutputStream(current.getOutputStream())) {
                            current.setSoTimeout(10000);
                            int order = input.readInt();
                            int kind = input.readInt();
                            permits.acquire();
                            try {
                                // This is the SAME dependency service for EVERY arm. The delay is
                                // the declared service contract, not a delay inserted in legacy code.
                                Thread.sleep(delayMillis);
                                output.writeLong(dependencyValue(order, kind));
                                output.flush();
                            } finally {
                                permits.release();
                            }
                        } catch (Exception error) {
                            error.printStackTrace(System.err);
                        }
                    }
                });
            }
        }
    }

    private static long lookup(int port, int order, int kind) throws Exception {
        try (Socket socket = new Socket()) {
            socket.connect(new java.net.InetSocketAddress("127.0.0.1", port), 10000);
            socket.setSoTimeout(10000);
            socket.setTcpNoDelay(true);
            DataOutputStream output = new DataOutputStream(socket.getOutputStream());
            DataInputStream input = new DataInputStream(socket.getInputStream());
            output.writeInt(order);
            output.writeInt(kind);
            output.flush();
            long value = input.readLong();
            if (value != dependencyValue(order, kind)) {
                throw new IllegalStateException("Dependency response mismatch");
            }
            return value;
        }
    }

    private static final class Batch {
        final long elapsed;
        final long[] completionNanos;
        final long[] outputs;
        Batch(long elapsed, long[] completionNanos, long[] outputs) {
            this.elapsed = elapsed;
            this.completionNanos = completionNanos;
            this.outputs = outputs;
        }
    }

    private static Batch batch(final String implementation, ExecutorService executor,
                               final int limit, final int size, final int port) throws Exception {
        final long started = System.nanoTime();
        final long[] completions = new long[size];
        final long[] values = new long[size * CALLS];
        final Semaphore permits = new Semaphore(limit, true);
        List<Future<Void>> futures = new ArrayList<Future<Void>>();
        if (implementation.equals("legacy")) {
            for (int i = 0; i < size; i++) {
                final int order = i;
                futures.add(executor.submit(new Callable<Void>() {
                    public Void call() throws Exception {
                        for (int kind = 0; kind < CALLS; kind++) {
                            values[order * CALLS + kind] = lookup(port, order, kind);
                        }
                        completions[order] = System.nanoTime() - started;
                        return null;
                    }
                }));
            }
        } else if (implementation.equals("fanout")) {
            final java.util.concurrent.atomic.AtomicIntegerArray completed =
                new java.util.concurrent.atomic.AtomicIntegerArray(size);
            for (int i = 0; i < size; i++) {
                for (int k = 0; k < CALLS; k++) {
                    final int order = i;
                    final int kind = k;
                    futures.add(executor.submit(new Callable<Void>() {
                        public Void call() throws Exception {
                            permits.acquire();
                            try {
                                values[order * CALLS + kind] = lookup(port, order, kind);
                            } finally {
                                permits.release();
                            }
                            if (completed.incrementAndGet(order) == CALLS) {
                                completions[order] = System.nanoTime() - started;
                            }
                            return null;
                        }
                    }));
                }
            }
        } else {
            throw new IllegalArgumentException("Unknown implementation");
        }
        for (Future<Void> future : futures) future.get();
        long[] outputs = new long[size];
        for (int order = 0; order < size; order++) {
            long price = values[order * CALLS];
            long stock = values[order * CALLS + 1];
            long shipping = values[order * CALLS + 2];
            outputs[order] = stock > 0 ? price + shipping : -1L;
        }
        return new Batch(System.nanoTime() - started, completions, outputs);
    }

    private static long percentile(long[] input, double fraction) {
        long[] sorted = input.clone();
        Arrays.sort(sorted);
        return sorted[Math.max(0, (int) Math.ceil(sorted.length * fraction) - 1)];
    }

    public static void main(String[] args) throws Exception {
        if (args[0].equals("serve")) {
            serve(Integer.parseInt(args[1]), Integer.parseInt(args[2]));
            return;
        }
        final String implementation = args[0];
        final String executorKind = args[1];
        final int limit = Integer.parseInt(args[2]);
        final int size = Integer.parseInt(args[3]);
        final int port = Integer.parseInt(args[4]);
        final long warmupMillis = Long.parseLong(args[5]);
        ExecutorService executor = executorKind.equals("virtual")
            ? virtualExecutor() : Executors.newFixedThreadPool(limit);
        try {
            long warmupStarted = System.nanoTime();
            int warmupBatches = 0;
            do {
                batch(implementation, executor, limit, size, port);
                warmupBatches++;
            } while (System.nanoTime() - warmupStarted < warmupMillis * 1000000L);
            long warmupNanos = System.nanoTime() - warmupStarted;
            ThreadMXBean threads = ManagementFactory.getThreadMXBean();
            threads.resetPeakThreadCount();
            com.sun.management.OperatingSystemMXBean os =
                (com.sun.management.OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
            long cpuStarted = os.getProcessCpuTime();
            Batch result = batch(implementation, executor, limit, size, port);
            long cpuNanos = os.getProcessCpuTime() - cpuStarted;
            int peakPlatformThreads = threads.getPeakThreadCount();
            StringBuilder outputs = new StringBuilder("[");
            for (int i = 0; i < size; i++) {
                if (i > 0) outputs.append(',');
                outputs.append(result.outputs[i]);
            }
            outputs.append(']');
            System.out.println("{\"implementation\":\"" + implementation + "\",\"executor\":\"" + executorKind
                + "\",\"limit\":" + limit + ",\"size\":" + size
                + ",\"elapsedNanos\":" + result.elapsed + ",\"p50Nanos\":" + percentile(result.completionNanos, .50)
                + ",\"p95Nanos\":" + percentile(result.completionNanos, .95)
                + ",\"p99Nanos\":" + percentile(result.completionNanos, .99)
                + ",\"processCpuNanos\":" + cpuNanos + ",\"peakPlatformThreads\":" + peakPlatformThreads
                + ",\"warmupBatches\":" + warmupBatches + ",\"warmupNanos\":" + warmupNanos
                + ",\"dependencyCalls\":" + (size * CALLS) + ",\"errors\":0,\"outputs\":" + outputs + "}");
        } finally {
            executor.shutdownNow();
            executor.awaitTermination(10, TimeUnit.SECONDS);
        }
    }
}
