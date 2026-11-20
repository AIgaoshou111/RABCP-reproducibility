"""Regenerate the stage instructions actually supplied to the answer model, offline."""

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"


def profile(history):
    posterior = [0.2] * 5
    observations = []
    for row in history:
        level = (
            1
            + 1.5 * int(row["archived_G"])
            + 0.25 * (int(row["archived_L"]) + int(row["archived_C"]))
        )
        kernel = [math.exp(-((k - level) ** 2) / (2 * 0.8**2)) for k in range(1, 6)]
        observations.append([v / sum(kernel) for v in kernel])
        recent = observations[-5:]
        n = len(recent)
        smooth = [
            sum(2 * (i + 1) / (n * (n + 1)) * q[k] for i, q in enumerate(recent))
            for k in range(5)
        ]
        logs = [
            math.log(max(x, 1e-300)) + 0.75 * math.log(max(q, 1e-300))
            for x, q in zip(posterior, smooth)
        ]
        highest = max(logs)
        values = [math.exp(x - highest) for x in logs]
        posterior = [x / sum(values) for x in values]
    return posterior


def original_instruction(probs, mean):
    stages = ", ".join(f"level {k}: {p:.3f}" for k, p in enumerate(probs, 1))
    return (
        "History-derived overall profile (uncertain estimate, not certified ability):\n"
        f"Domain: Docker; prior questions: 5; mean level: {mean:.3f} / 5; distribution: {stages}. "
        "Use this only to calibrate explanation depth when useful; specific evidence and the current question take priority."
    )


def followup_instruction(probs, mean):
    if sum(probs[:2]) >= 0.75:
        mode = "guided"
    elif sum(probs[2:]) >= 0.75:
        mode = "compact"
    else:
        mode = "standard"
    wording = json.loads((CODE / "depth_modes.json").read_text(encoding="utf-8"))[mode]
    template = (CODE / "followup_profile_template.txt").read_text(encoding="utf-8")
    for k, p in enumerate(probs, 1):
        # The archived formatter retained the period following the fifth probability.
        template = template.replace(
            "{{P" + str(k) + "}}", f"{p:.3f}" + ("." if k == 5 else "")
        )
    return mode, template.replace("{{MEAN}}", f"{mean:.3f}").replace(
        "{{DEFAULT_DEPTH}}", wording
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--supplement", type=Path, help="extracted Supplement_S1 directory"
    )
    parser.add_argument(
        "--show", help="print the rebuilt stage instructions for one case, e.g. U086"
    )
    args = parser.parse_args()
    histories = defaultdict(list)
    with (ROOT / "data/human_lcg_200.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        for row in csv.DictReader(stream):
            histories[row["sample_user_code"]].append(row)
    if args.show and args.show not in histories:
        parser.error("unknown case")
    followup = {}
    if args.supplement:
        with (args.supplement / "followup/cases.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            followup = {r["case_id"]: r for r in csv.DictReader(stream)}
        assert len(followup) == 27 and followup.keys() <= histories.keys()
    assert len(histories) == 40
    for case, rows in sorted(histories.items()):
        ordered = sorted(rows, key=lambda r: int(r["history_position"]))
        assert [int(r["history_position"]) for r in ordered] == list(range(1, 6))
        probs = profile(ordered)
        mean = sum(k * p for k, p in enumerate(probs, 1))
        original = original_instruction(probs, mean)
        prompts = ROOT / "data/answer_prompts_redacted"
        evidence = (prompts / f"{case}_E.txt").read_text(encoding="utf-8").rstrip()
        combined = (prompts / f"{case}_F.txt").read_text(encoding="utf-8").rstrip()
        assert combined == evidence + "\n\n" + original, case
        mode, instruction = followup_instruction(probs, mean)
        if case in followup:
            rec = followup[case]
            assert mode == rec["mode"] and all(
                abs(p - float(rec[f"p{k}"])) < 1e-12 for k, p in enumerate(probs, 1)
            ), case
            dr = args.supplement / "followup/prompts"
            combined = (dr / f"{case}_F3.txt").read_text(encoding="utf-8").strip()
            base = (dr / f"{case}_E3.txt").read_text(encoding="utf-8").strip()
            assert (
                combined.startswith(base)
                and combined[len(base) :].strip() == instruction
            ), case
        if case == args.show:
            print(original, "\n\n", instruction, sep="")
    print(
        f"Verified 40 original combined prompts and {len(followup)} supplied follow-up pairs."
    )


if __name__ == "__main__":
    main()
