"""Reproduce DATA-07 in a temporary copy without changing repository code."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from data.generator import identity as source_identity
from data.generator.configuration import DatasetGenerationConfig
from data.generator.main import build_dataset
from data.generator.source_quality import project_facts
from ml.features import identity as feature_identity
from ml.features.ai_demand import AI_FEATURE_COLUMNS
from ml.features.isolated_runtime import WORKER_FILES
from ml.features.worker import transform

repo = Path.cwd()
config = DatasetGenerationConfig(profile="ai-smoke", days=1, products=2, stores=1, warehouses=1)
tables = build_dataset(config)
facts = project_facts(tables)
source_descriptor = source_identity.source_identity(config, tables)[1]
original = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
with TemporaryDirectory(prefix="retailops-ai02-fingerprint-") as tmp:
    bundle = Path(tmp)
    for name in set(original["code_files"]) | set(original["dependency_files"]) | set(WORKER_FILES):
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / name, target)
    with (
        patch.object(source_identity, "ROOT", bundle),
        patch.object(feature_identity, "ROOT", bundle),
    ):
        before = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
        rows_before = transform(facts)
        id_before = feature_identity.feature_identity_from_source(
            config, source_descriptor, rows_before, AI_FEATURE_COLUMNS
        )[0]
        init = bundle / "ml/features/__init__.py"
        init.write_text(
            init.read_text() + '\nimport sys\nsys.stderr.write("AUDIT_EXECUTED_UNHASHED_INIT\\n")\n'
        )
        command = [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys,runpy;sys.path.insert(0,"
            + repr(str(bundle))
            + ');runpy.run_module("ml.features.worker",run_name="__main__")',
        ]
        result = subprocess.run(
            command,
            input=json.dumps(facts),
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        after = source_identity.code_fingerprint(feature_identity.FEATURE_CODE)
        rows_after = json.loads(result.stdout)
        id_after = feature_identity.feature_identity_from_source(
            config, source_descriptor, rows_after, AI_FEATURE_COLUMNS
        )[0]
        print(
            json.dumps(
                {
                    "omitted_worker_files": sorted(set(WORKER_FILES) - set(before["code_files"])),
                    "original_and_temp_fingerprints_equal": original == before,
                    "init_executed": "AUDIT_EXECUTED_UNHASHED_INIT" in result.stderr,
                    "code_fingerprint_before": before["code_sha256"],
                    "code_fingerprint_after": after["code_sha256"],
                    "fingerprints_equal_after_executed_code_change": before == after,
                    "output_equal": rows_before == rows_after,
                    "feature_identity_equal": id_before == id_after,
                    "identity_before": id_before,
                    "identity_after": id_after,
                },
                indent=2,
            )
        )
