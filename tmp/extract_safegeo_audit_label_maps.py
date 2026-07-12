#!/usr/bin/env python3
import gzip
import json
from pathlib import Path

import pyarrow.dataset as pads

INSTANCE_IDS = [
    "SGI_a250e0cd9fc4434d", "SGI_e3ca419668509f48", "SGI_58d1a66b1d1a3373", "SGI_bd9180f205bc51d6",
    "SGI_a67319ab5aa51283", "SGI_6b035cbb54a3da1c", "SGI_e5d4e7665a23a4e0", "SGI_c51f5d9b8bd6d3e6",
    "SGI_7756469222d334d2", "SGI_f075616efd1a783d", "SGI_896386bf7f94ff1f", "SGI_66d1e96f0d4a805c",
    "SGI_5c7c9ddcea9c91a3", "SGI_8eac3dc51ea9182e", "SGI_341e556842cb5cb0", "SGI_a683ab174b9ce794",
    "SGI_2097911f30df51fb", "SGI_0a5f985004d83d6b", "SGI_25957700c210770e", "SGI_07ab1189f74dd092",
    "SGI_0504fde1005d9800", "SGI_6955a0851c0a885f", "SGI_670f57c6a3ff5afe", "SGI_e2d35c7ef137d84f",
    "SGI_7f406e07ae7481e8", "SGI_c681d138a974100e", "SGI_cb98c0ab651e7a86", "SGI_f19c208a63ebcfa0",
    "SGI_2f4e3d59c2702b4a", "SGI_b81d87d20a43a8f2", "SGI_2aabc3f23d980299", "SGI_aa2eaa6775fd4527",
    "SGI_9e82e57a68def194", "SGI_6d443e96aa64d265", "SGI_027d18773515a84a", "SGI_62d0df4e390570d7",
    "SGI_219e0cef5b770a97", "SGI_dbdd7afe4eafb425", "SGI_70aed3c34775f3b6", "SGI_49d21f585b06f977",
    "SGI_2304a2abc6092b76", "SGI_352e0bc4f969c72c", "SGI_3762e390a00bdc76", "SGI_446607ec097bb997",
    "SGI_8d84a734b79e5697", "SGI_72d4bdaa626fe7c6", "SGI_af3c2b6eb14ceb4e", "SGI_3782522a29d036c5",
    "SGI_909de23c0575b02b", "SGI_f62381d33156925b", "SGI_04ac8f164903d942", "SGI_0901c7c0d42cae22",
    "SGI_f4fee2b44263c484", "SGI_f5ac3b9fec5c80bd", "SGI_a35030819911d737", "SGI_842086db4f82869c",
    "SGI_d36cc5cf3a15a4f0", "SGI_a4c6147ed9e77bac", "SGI_deb0e4bd364af169", "SGI_bc718c0ae8a30cb7",
]


def decode(value):
    if isinstance(value, str):
        s = value.strip()
        if s and s[0] in "[{" and s[-1] in "]}":
            try:
                return decode(json.loads(s))
            except Exception:
                return value
        return value
    if isinstance(value, list):
        return [decode(x) for x in value]
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    return value


dataset = pads.dataset("data/labels", format="parquet")
table = dataset.to_table(filter=pads.field("instance_id").isin(INSTANCE_IDS))
rows = [decode(dict(row)) for row in table.to_pylist()]
if len(rows) != len(INSTANCE_IDS):
    raise RuntimeError(f"Expected {len(INSTANCE_IDS)} labels, found {len(rows)}")
out = Path("safegeo_audit_selected_labels.json.gz")
with gzip.open(out, "wt", encoding="utf-8", compresslevel=9) as f:
    json.dump(rows, f, ensure_ascii=False)
print(f"WROTE {out} {out.stat().st_size} bytes")
