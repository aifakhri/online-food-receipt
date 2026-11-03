import sys
import time
import resource
import polars as pl


from pathlib import Path


CSV_PATH = Path("customer_data/customers-2000000.csv")
N_ROWS = 200000



def normal_load():
    pl.read_csv(CSV_PATH).head(N_ROWS)


def lazy_in_memory():
    pl.scan_csv(CSV_PATH).head(N_ROWS).collect(engine="in-memory")


def lazy_streaming():
    pl.scan_csv(CSV_PATH).head(N_ROWS).collect(engine="streaming")


def peak_rss_mb():
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1024 ** 2


def main():
    TESTS = {
        "normal_load": normal_load,
        "lazy_in_memory": lazy_in_memory,
        "lazy_streaming": lazy_streaming
    }

    # Get filesize in Megabytes (MB)
    csv_size_mb = CSV_PATH.stat().st_size / 1024 ** 2
    print(f"CSV size: {csv_size_mb:.0f} MB")


    name = sys.argv[1]
    start = time.perf_counter()
    TESTS[name]()
    elapsed = time.perf_counter() - start
    print(f"{name:<18}{peak_rss_mb():>10.1f} MB{elapsed:>8.2f} s")

if __name__ == "__main__":
    main()