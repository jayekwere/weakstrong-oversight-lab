"""Scan every tracked file for common secret formats; validate docs links and dataset artifact."""

import json
import re
import subprocess
import sys
from pathlib import Path

# git is invoked with a fixed argument vector, never model or dataset strings.
paths = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
patterns = [
    r"gh[pousr]_" + r"[A-Za-z0-9_]{30,}",
    r"github_pat_" + r"[A-Za-z0-9_]{30,}",
    r"sk-" + r"[A-Za-z0-9_-]{25,}",
    r"AKIA" + r"[A-Z0-9]{16}",
    r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
]
findings = []
forbidden_terms = (
    "em" + "ployer",
    "recrui" + "ting",
    "recrui" + "tment",
    "inter" + "view",
    "job appli" + "cation",
    "career moti" + "vation",
    "resi" + "dency",
)

for name in filter(None, paths):
    path = Path(name)
    if not path.is_file():
        continue
    content = path.read_bytes().decode("utf-8", errors="replace")
    for pattern in patterns:
        if re.search(pattern, content):
            findings.append(name)
    if any(re.search(r"\b" + re.escape(term) + r"s?\b", content, re.IGNORECASE) for term in forbidden_terms):
        findings.append(f"forbidden content: {name}")
    if path.suffix == ".md":
        for link in re.findall(r"\]\(([^ )]+)\)", content):
            if ":" in link or link.startswith("#"):
                continue
            if not (path.parent / link.split("#")[0]).exists():
                findings.append(f"broken link: {name}: {link}")
assert not findings, findings
cases = json.loads(Path("data/scenarios.json").read_text())
assert len(cases) >= 100 and len({s["id"] for s in cases}) == len(cases)
print(
    json.dumps(
        {
            "tracked_files_scanned": len(list(filter(None, paths))),
            "secret_patterns": len(patterns),
            "findings": 0,
            "dataset_cases": len(cases),
        }
    )
)

scan = subprocess.check_output(
    [
        sys.executable,
        "-m",
        "detect_secrets",
        "scan",
        "--disable-plugin",
        "HexHighEntropyString",
        "--disable-plugin",
        "Base64HighEntropyString",
        *filter(None, paths),
    ]
)
assert not json.loads(scan)["results"], "credential-pattern scanner reported findings"
