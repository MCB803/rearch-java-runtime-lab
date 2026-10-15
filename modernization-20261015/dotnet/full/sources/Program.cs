using System.Buffers.Binary;
using System.Collections.Frozen;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;

// Same business contract and .NET runtime for every arm. No sleeps or network I/O.
internal static class Program
{
    private sealed record Product(string Sku, long PriceCents);
    private sealed record ImportRow(string Sku, int Quantity);
    private sealed record Batch(long[] Outputs, long IndexBuildNanos);
    [StructLayout(LayoutKind.Sequential)]
    private struct Timespec { public long Seconds; public long Nanoseconds; }
    [DllImport("libc", EntryPoint = "clock_gettime", SetLastError = true)]
    private static extern int ClockGetTime(int clockId, out Timespec value);
    private static long CpuNanos()
    {
        // Linux CLOCK_PROCESS_CPUTIME_ID: finer than Process.TotalProcessorTime's
        // /proc tick resolution for the sub-millisecond indexed implementation.
        if (ClockGetTime(2, out Timespec value) != 0) throw new InvalidOperationException("Process CPU clock unavailable");
        return checked(value.Seconds * 1_000_000_000L + value.Nanoseconds);
    }

    private static long Nanos(long ticks) => (long)(ticks * (1_000_000_000.0 / Stopwatch.Frequency));
    private static string Sku(int id) => "SKU-" + id.ToString("D5", CultureInfo.InvariantCulture);

    private static Batch Execute(string arm, List<Product> catalog, ImportRow[] rows)
    {
        long started = Stopwatch.GetTimestamp();
        Dictionary<string, Product>? dictionary = null;
        FrozenDictionary<string, Product>? frozen = null;
        if (arm == "modern-dictionary")
        {
            dictionary = new Dictionary<string, Product>(catalog.Count, StringComparer.Ordinal);
            foreach (Product product in catalog) dictionary.Add(product.Sku, product);
        }
        else if (arm == "modern-frozen")
        {
            frozen = catalog.ToFrozenDictionary(product => product.Sku, StringComparer.Ordinal);
        }
        else if (arm != "legacy-linear") throw new ArgumentException("Unknown arm");
        long indexBuildNanos = arm == "legacy-linear" ? 0 : Nanos(Stopwatch.GetTimestamp() - started);
        var outputs = new long[rows.Length];
        if (arm == "legacy-linear")
        {
            for (int i = 0; i < rows.Length; i++)
            {
                ImportRow row = rows[i];
                // A common import implementation: repeat a list scan for each CSV row.
                // The capturing predicate and its allocations belong to this implementation.
                Product? product = catalog.Find(candidate => candidate.Sku == row.Sku);
                outputs[i] = product is null ? -1 : product.PriceCents * row.Quantity;
            }
        }
        else if (dictionary is not null)
        {
            for (int i = 0; i < rows.Length; i++)
            {
                ImportRow row = rows[i];
                outputs[i] = dictionary.TryGetValue(row.Sku, out Product? product) ? product.PriceCents * row.Quantity : -1;
            }
        }
        else
        {
            for (int i = 0; i < rows.Length; i++)
            {
                ImportRow row = rows[i];
                outputs[i] = frozen!.TryGetValue(row.Sku, out Product? product) ? product.PriceCents * row.Quantity : -1;
            }
        }
        return new Batch(outputs, indexBuildNanos);
    }

    private static object Run(string arm, int size, int repeat, bool warmup)
    {
        const int catalogSize = 10_000;
        var catalog = Enumerable.Range(0, catalogSize)
            .Select(id => new Product(Sku(id), 1000L + (id * 37L) % 100_000L)).ToList();
        var rows = Enumerable.Range(0, size).Select(i => new ImportRow(
            i % 17 == 0 ? "MISSING-" + i.ToString(CultureInfo.InvariantCulture) : Sku((i * 7919) % catalogSize),
            i % 5 + 1)).ToArray();

        // Input creation and a full collection are outside all arms' measurement window.
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
        long cpuStarted = CpuNanos();
        long allocatedStarted = GC.GetTotalAllocatedBytes(true);
        long started = Stopwatch.GetTimestamp();
        Batch result = Execute(arm, catalog, rows);
        long elapsedNanos = Nanos(Stopwatch.GetTimestamp() - started);
        long allocatedBytes = GC.GetTotalAllocatedBytes(true) - allocatedStarted;
        long cpuNanos = CpuNanos() - cpuStarted;

        // Hash validation is deliberately outside the measured import operation.
        byte[] bytes = new byte[result.Outputs.Length * 8];
        for (int i = 0; i < result.Outputs.Length; i++)
            BinaryPrimitives.WriteInt64LittleEndian(bytes.AsSpan(i * 8, 8), result.Outputs[i]);
        string digest = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        return new
        {
            arm, size, repeat, warmup, catalogSize, elapsedNanos,
            indexBuildNanos = result.IndexBuildNanos, processCpuNanos = cpuNanos, allocatedBytes,
            resultHash = digest, outputCount = result.Outputs.Length,
            missing = result.Outputs.Count(value => value == -1),
            sumCents = result.Outputs.Where(value => value >= 0).Sum(),
            errors = 0,
            runtimeVersion = RuntimeInformation.FrameworkDescription,
            architecture = RuntimeInformation.ProcessArchitecture.ToString(),
            osDescription = RuntimeInformation.OSDescription
        };
    }

    public static void Main(string[] args)
    {
        if (args.Length != 1) throw new ArgumentException("Pass job-plan JSON path");
        var plan = JsonSerializer.Deserialize<List<Job>>(File.ReadAllText(args[0]),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
        foreach (Job job in plan)
        {
            object record = Run(job.Arm, job.Size, job.Repeat, job.Warmup);
            Console.WriteLine(JsonSerializer.Serialize(record));
        }
    }

    private sealed record Job(string Arm, int Size, int Repeat, bool Warmup);
}
