"""Table 8. Replay the original within-user bootstrap and permutation procedure."""

import argparse
import json
import re
from html import unescape
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
CLUSTER_SEED = 20260714
CLUSTER_RESAMPLES = 10000

TECH_TERMS = {
    "docker",
    "container",
    "image",
    "dockerfile",
    "compose",
    "volume",
    "bind",
    "mount",
    "network",
    "bridge",
    "host",
    "port",
    "registry",
    "daemon",
    "entrypoint",
    "cmd",
    "layer",
    "build",
    "tag",
    "swarm",
    "kubernetes",
    "pod",
    "service",
    "deployment",
    "nginx",
    "apache",
    "proxy",
    "ssl",
    "tls",
    "certificate",
    "jenkins",
    "gitlab",
    "ci",
    "cd",
    "postgres",
    "postgresql",
    "mysql",
    "redis",
    "mongodb",
    "aws",
    "ubuntu",
    "linux",
    "windows",
    "macos",
    "permission",
    "uid",
    "gid",
    "root",
    "environment",
    "variable",
    "yaml",
    "yml",
    "json",
    "config",
    "shell",
    "bash",
}

COMMAND_RE = re.compile(
    r"\b(?:docker|docker-compose|kubectl|sudo|apt-get|apt|yum|apk|npm|pip|git|curl|wget|ssh|scp|make|systemctl|service|chmod|chown|grep|ps|netstat|lsof)\b",
    re.I,
)
FLAG_RE = re.compile(r"--[a-zA-Z0-9][a-zA-Z0-9_-]+")
PATH_RE = re.compile(r"(?:^|\s)(/[A-Za-z0-9._~:/-]{2,})")
ENV_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
VERSION_RE = re.compile(
    r"\b(?:v?\d+\.\d+(?:\.\d+)?|ubuntu|debian|centos|alpine|windows|mac|linux|boot2docker|docker-machine)\b",
    re.I,
)


def clean_text(value):
    value = "" if value is None else str(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def contains_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)


def technical_entity_count(text):
    low = text.lower()
    entities = set()
    for term in TECH_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", low):
            entities.add(term)
    entities.update(m.group(0).lower() for m in COMMAND_RE.finditer(text))
    entities.update(m.group(0).lower() for m in FLAG_RE.finditer(text))
    entities.update(m.group(1).lower() for m in PATH_RE.finditer(text))
    entities.update(m.group(0) for m in ENV_RE.finditer(text))
    return len(entities)


def token_count(text):
    return max(1, len(re.findall(r"[A-Za-z0-9_]+", text)))


def context_features(row):
    text = f"{row.get('title_clean', '')} {row.get('body_clean', '')}"
    raw = f"{row.get('title', '')} {row.get('body', '')}"
    has_code = bool(row.get("has_code", False)) or "<code>" in raw.lower()
    has_error = bool(row.get("has_error", False)) or contains_any(
        text,
        [r"\berror\b", r"\bexception\b", r"failed?", r"cannot", r"unable", r"denied"],
    )
    has_command = bool(COMMAND_RE.search(text))
    has_config = contains_any(
        text,
        [
            r"dockerfile",
            r"docker-compose",
            r"\.ya?ml\b",
            r"\.json\b",
            r"nginx\.conf",
            r"\bconfig(?:uration)?\b",
            r"\benv(?:ironment)?\b",
            r"\bFROM\b",
            r"\bRUN\b",
        ],
    )
    has_environment = bool(VERSION_RE.search(text)) or contains_any(
        text, [r"\bOS\b", r"\bversion\b", r"\bhost machine\b", r"\bserver\b"]
    )
    has_attempt = contains_any(
        text,
        [
            r"\btried\b",
            r"\battempt",
            r"\balready\b",
            r"\bwhen I run\b",
            r"\bI ran\b",
            r"\bI have\b",
            r"\bI am using\b",
            r"\bI use\b",
        ],
    )
    has_expected_actual = contains_any(
        text,
        [
            r"\bexpected\b",
            r"\bactual\b",
            r"\binstead\b",
            r"\bshould\b",
            r"\bbut\b",
            r"\bhowever\b",
        ],
    )
    flags = [
        has_code,
        has_error,
        has_command,
        has_config,
        has_environment,
        has_attempt,
        has_expected_actual,
    ]
    return pd.Series(
        {
            "has_code_proxy": int(has_code),
            "has_error_proxy": int(has_error),
            "has_command_proxy": int(has_command),
            "has_config_proxy": int(has_config),
            "has_environment_proxy": int(has_environment),
            "has_attempt_proxy": int(has_attempt),
            "has_expected_actual_proxy": int(has_expected_actual),
            "context_artifact_count": int(sum(flags)),
        }
    )


def intent_proxy(row):
    text = f"{row.get('title_clean', '')} {row.get('body_clean', '')}"
    debugging = bool(row.get("has_error", False)) or contains_any(
        text,
        [
            r"\berror\b",
            r"fail(?:ed|s|ing)?",
            r"not working",
            r"cannot",
            r"unable",
            r"denied",
            r"exception",
            r"\bissue\b",
            r"\bproblem\b",
        ],
    )
    tradeoff = contains_any(
        text,
        [
            r"best way",
            r"best practice",
            r"should I",
            r"reasonable",
            r"\bvs\.?\b",
            r"versus",
            r"compare",
            r"production",
            r"alternative",
            r"trade-?off",
        ],
    )
    mechanism = contains_any(
        text,
        [
            r"why does",
            r"why is",
            r"how does",
            r"under the hood",
            r"internally",
            r"mechanism",
            r"semantics",
            r"what happens",
        ],
    )
    implementation = contains_any(
        text,
        [
            r"how to",
            r"how do I",
            r"install",
            r"run",
            r"build",
            r"configure",
            r"setup",
            r"create",
            r"mount",
            r"use",
        ],
    )
    concept = contains_any(
        text, [r"what is", r"difference between", r"meaning", r"understand"]
    )

    if tradeoff or mechanism:
        level = 2
    elif debugging or implementation:
        level = 1
    else:
        level = 0 if concept else 1

    return pd.Series(
        {
            "intent_proxy_level": level,
            "intent_has_debugging": int(debugging),
            "intent_has_implementation": int(implementation),
            "intent_has_mechanism": int(mechanism),
            "intent_has_tradeoff": int(tradeoff),
            "intent_has_concept": int(concept),
        }
    )


def spearman(x, y):
    mask = ~(pd.isna(x) | pd.isna(y))
    x = np.asarray(x[mask], dtype=float)
    y = np.asarray(y[mask], dtype=float)
    if len(x) < 3 or len(np.unique(x)) < 2 or len(np.unique(y)) < 2:
        return np.nan, np.nan
    if stats is not None:
        r, p = stats.spearmanr(x, y)
        return float(r), float(p)
    # Dependency-free Spearman fallback: Pearson correlation of average ranks.
    xr = pd.Series(x).rank(method="average").to_numpy(float)
    yr = pd.Series(y).rank(method="average").to_numpy(float)
    return float(np.corrcoef(xr, yr)[0, 1]), np.nan


def holm_adjust(p_values):
    """Holm family-wise-error correction without an external dependency."""
    p_values = np.asarray(p_values, dtype=float)
    order = np.argsort(p_values)
    adjusted = np.empty(len(p_values), dtype=float)
    running = 0.0
    m = len(p_values)
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p_values[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def clustered_spearman(
    df,
    x_col,
    y_col,
    cluster_col="user_id",
    n_resamples=CLUSTER_RESAMPLES,
    seed=CLUSTER_SEED,
):
    """Question-level rho with user-clustered CI and cluster permutation p.

    The bootstrap resamples complete users and therefore preserves dependence
    among the ten questions contributed by each user. The permutation test
    re-pairs complete x and y user blocks, preserving each user's within-block
    distribution while breaking the cross-variable association.
    """
    work = df[[cluster_col, x_col, y_col]].dropna().copy()
    groups = [
        g[[x_col, y_col]].to_numpy(float)
        for _, g in work.groupby(cluster_col, sort=True)
    ]
    if len(groups) < 3 or any(len(g) == 0 for g in groups):
        return {
            "rho": np.nan,
            "ci_low": np.nan,
            "ci_high": np.nan,
            "cluster_p": np.nan,
            "n_clusters": len(groups),
        }

    observed, _ = spearman(work[x_col], work[y_col])
    rng = np.random.default_rng(seed)
    boot = np.empty(n_resamples, dtype=float)
    perm = np.empty(n_resamples, dtype=float)
    n_groups = len(groups)

    for b in range(n_resamples):
        sampled = rng.integers(0, n_groups, size=n_groups)
        sample = np.concatenate([groups[i] for i in sampled], axis=0)
        boot[b], _ = spearman(pd.Series(sample[:, 0]), pd.Series(sample[:, 1]))

        shuffled = rng.permutation(n_groups)
        x = np.concatenate([groups[i][:, 0] for i in range(n_groups)])
        y = np.concatenate([groups[i][:, 1] for i in shuffled])
        perm[b], _ = spearman(pd.Series(x), pd.Series(y))

    valid_boot = boot[np.isfinite(boot)]
    valid_perm = perm[np.isfinite(perm)]
    cluster_p = (1.0 + np.sum(np.abs(valid_perm) >= abs(observed))) / (
        1.0 + len(valid_perm)
    )
    return {
        "rho": float(observed),
        "ci_low": float(np.percentile(valid_boot, 2.5)),
        "ci_high": float(np.percentile(valid_boot, 97.5)),
        "cluster_p": float(cluster_p),
        "n_clusters": int(n_groups),
    }


def remove_html_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<pre><code>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</code></pre>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<code>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</code>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def records(filename):
    return [
        json.loads(line)
        for line in (ROOT / "data" / filename).read_text(encoding="utf-8").splitlines()
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-redacted-text",
        action="store_true",
        help="also extract indicators from the public redacted text and report the number changed by masking",
    )
    args = parser.parse_args()
    frame = pd.read_csv(ROOT / "data/table8_indicators.csv")
    obs = pd.DataFrame(records("question_observations_870.jsonl"))
    frame = frame.merge(
        obs, on=["question_id", "user_code"], validate="one_to_one", sort=False
    )
    assert len(frame) == 870 and frame.groupby("resampling_block").size().eq(10).all()
    pairs = [
        ("contextual_score", "context_artifact_count"),
        ("linguistic_score", "technical_entity_count"),
        ("cognitive_score", "intent_proxy_level"),
    ]
    if args.check_redacted_text:
        questions = {
            r["question_id"]: r for r in records("real_questions_870_redacted.jsonl")
        }
        extracted = []
        for row in frame.to_dict("records"):
            post = questions[row["question_id"]]
            text = dict(
                row,
                title_clean=post["title"].strip(),
                body_clean=remove_html_tags(post["body_html"]),
                body=post["body_html"],
            )
            combined = clean_text(text["title_clean"] + " " + text["body_clean"])
            extracted.append(
                {
                    "technical_entity_count": technical_entity_count(combined),
                    "context_artifact_count": context_features(text)[
                        "context_artifact_count"
                    ],
                    "intent_proxy_level": intent_proxy(text)["intent_proxy_level"],
                }
            )
        values = pd.DataFrame(extracted)
        print(
            "Question counts where re-extraction differs from frozen pre-redaction inputs:"
        )
        print((values != frame[values.columns]).sum().to_string())
    results = []
    for feature, indicator in pairs:
        result = clustered_spearman(
            frame, feature, indicator, cluster_col="resampling_block"
        )
        results.append(dict(feature=feature, indicator=indicator, **result))
    for result, adjusted in zip(
        results, holm_adjust([r["cluster_p"] for r in results])
    ):
        result["holm_p"] = float(adjusted)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
