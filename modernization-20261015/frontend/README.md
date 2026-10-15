# Invoice list: full DOM rendering and a virtualized viewport

This is a synthetic browser workload, not a customer migration or framework-version comparison. It compares two implementations of the same overdue-invoice view on the same browser and machine.

Run `python3 serve.py`, open `http://127.0.0.1:4387/` in a visible browser tab, and press **Run recorded benchmark**. Keep the tab visible until its status says completed and saved. The local server accepts only this fixture and its result endpoint; it binds to loopback.

## Reproduce the published summary or a new run

From this directory, run `python3 summarize.py`. It verifies the published `completed.json` and writes a self-contained package into `reproduced/` beside the script. It never assumes a website checkout or writes to a parent directory. Run `python3 test_summarize.py` to check local output, explicit run selection, preservation of existing files and rejection of invalid records.

For a new measurement, the collector prints its saved filename in the terminal, for example `run-20261015T123456Z-<id>-completed.json`. Select that exact file and a fresh output directory:

```sh
python3 summarize.py --input 'run-20261015T123456Z-<id>-completed.json' --output reproduced-new-run
```

Replace the example filename with the actual collector output. A run ending in `failed.json` is not publishable. The output contains the selected raw evidence as `completed.json`, all individual samples as `raw.csv`, verified `summary.json`, source files and their `SHA256.json`. Existing files with different bytes are rejected before any output is written; choose a new output directory for a different run. Original evidence files stay unchanged. The default input always selects the published run, never the newest file implicitly.

The summarizer's input/output handling was made portable after measurement. Its calculations and the timed browser fixture were not changed; regenerating the published summary and CSV produces the original bytes. The collector audit below describes the original published run, not any later reproduction.

The result collector was hardened after the measured run: it now requires a loopback Host and same-origin JSON request, limits body size, chooses subsequent filenames itself, and checks destination containment. This change does not alter `benchmark.html`, the timed browser workload, the recorded samples, or the summary medians. `collector-hardening.json` records the original and updated collector hashes and confirms unchanged benchmark/raw hashes. Run `python3 test_collector.py` to check request rejection and filename safety. Every repeated run gets a separate server-generated filename; the first completed evidence file is never overwritten.

## Frozen protocol

- Source invoice counts: 1,000, 10,000 and 50,000. Deterministic invoice IDs, customer labels, status and integer-cent amounts. No customer data.
- Filter: every invoice whose status is `overdue`; exactly the same filter and source records in both arms.
- Baseline `legacy`: one DOM row for every filtered invoice, rendered in one `innerHTML` assignment. No deliberately inserted delays or per-row network calls.
- Modern `virtualized`: forty DOM rows around the viewport and two spacers preserving the same full scroll height. Customer labels are HTML-encoded. This is handwritten vanilla JavaScript, not a React/Vue/library comparison.
- Each size and arm gets two excluded warmups, followed by ten recorded runs. Arm order alternates every pair. All recorded runs are retained; no removal of slow samples.
- Timed region: filtering, HTML preparation, DOM replacement, layout flush and two `requestAnimationFrame` callbacks. Two callbacks include a rendering opportunity; they are not compositor-presentation instrumentation and the result is not INP or field Core Web Vitals. The shared frame cadence creates a floor for small workloads.
- DOM teardown and dataset creation occur before timing. Full-output checksum and viewport checks occur after timing. Checksums include all selected IDs and amounts, including records outside the virtualized window.
- Every run validates the top visible IDs, bottom visible IDs and full scroll height. The independent Python verifier reconstructs all IDs and amounts, verifies all checksums and verifies every repetition is present.
- The numeric resource metric is rendered invoice DOM rows, not total DOM nodes, memory or CPU. CPU time and device battery usage were not measured.
- The browser user agent, hardware concurrency, viewport, visibility and timestamps are recorded with the raw result. Shared workstation/browser activity remains a limitation. Other laboratory CPU workloads are paused for this run.

## Separate encoding checks

Six fixed synthetic display-name values exercise ordinary text, ampersands, angle brackets, quotes and two benign HTML fragments. The earlier path uses `innerHTML`; the safer path uses `textContent`. Checks retain the input, expected text, actual text and inserted element counts for both paths. The two HTML fragments deliberately create markup in the earlier path; all six are literal text in the safer path.

This is an HTML-injection/output-encoding test, not a claim of a demonstrated account takeover or universal XSS protection. No external request, script execution, credential, real account or production service is involved. The measured modern list uses HTML encoding for its string template; the separate safety replay demonstrates the text-only alternative.

## Scope of the conclusion

If the measured duration falls, the demonstrated intervention is reducing the number of DOM rows created for the initial view. It does not prove that every old frontend is slow or that changing frameworks automatically produces this result. A real product must also preserve accessibility, browser find/print behavior, selection, variable row heights, scrolling and assistive-technology behavior. The fixture proves the specified result set and top/bottom viewport, not every interaction of a full invoice application.

Primary references checked on 15 October 2026:

- [web.dev: Virtualize large lists](https://web.dev/articles/virtualize-long-lists-react-window) describes rendering a moving window of list content instead of populating the entire DOM. This fixture uses that approach without the article's React library.
- [MDN: requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame) describes callbacks before repaint and background-tab pausing; a visible tab is required here.
- [MDN: innerHTML](https://developer.mozilla.org/en-US/docs/Web/API/Element/innerHTML) explains HTML parsing and injection risk.
- [MDN: textContent](https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent) describes setting text content without interpreting it as HTML.
