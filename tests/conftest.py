import pyarrow as pa


# The benchmark contains deeply nested source packets. Keep test resource use
# deterministic on laptops and CI instead of creating one Arrow worker per CPU.
pa.set_cpu_count(1)
pa.set_io_thread_count(1)
