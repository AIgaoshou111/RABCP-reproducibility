"""Verify a freshly extracted release and reconstruct Table 13 from the call log."""

import csv
import hashlib
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]


def rows(name):
    with (ROOT / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    manifest = rows("MANIFEST.csv")
    names = set()
    for item in manifest:
        path = ROOT / item["path"]
        assert item["path"] not in names and path.resolve().is_relative_to(ROOT), item[
            "path"
        ]
        names.add(item["path"])
        data = path.read_bytes()
        assert (
            len(data) == int(item["bytes"])
            and hashlib.sha256(data).hexdigest() == item["sha256"]
        ), item["path"]
    cases = rows("results/table13_cases.csv")
    calls = rows("results/answer_generation_summary.csv")
    counts = {
        (r["case_id"], r["group"]): int(r["prompt_tokens"])
        for r in calls
        if r["status"] == "completed"
    }
    assert (
        len(counts) == len(calls) == 120
        and len({r["case_id"] for r in cases}) == len(cases) == 40
    )
    classes = Counter()
    for r in cases:
        u = r["case_id"]
        classes[r["observation"]] += 1
        assert all(counts[u, g] == int(r[g]) for g in "BEF")
        n = int(r["selected_posts"])
        assert (
            bool(n)
            == bool(r["reviewed_point_en"])
            == (r["observation"] != "no excerpt selected")
        )
        lines = (
            (ROOT / f"data/answer_prompts_redacted/{u}_F.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert sum(l.startswith("[E") and "; H" in l for l in lines) == n
    assert classes == {
        "explanations differed": 12,
        "similar on reviewed point": 19,
        "no excerpt selected": 9,
    }
    saving = mean(100 * (1 - int(r["F"]) / int(r["B"])) for r in cases)
    print(
        f"{len(names)} manifest entries verified. Table 13: {dict(classes)}; mean input saving {saving:.1f}%."
    )


if __name__ == "__main__":
    main()
