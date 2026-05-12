from __future__ import annotations

import json
from pathlib import Path

from demo.avro_contracts import SUBJECT_AVRO_SCHEMAS
from demo.config import Settings
from demo.schema_registry import SchemaRegistryClient


def main() -> int:
    settings = Settings()
    client = SchemaRegistryClient(settings.schema_registry_url)
    schema_dir = Path("contracts") / "avro"
    schema_dir.mkdir(parents=True, exist_ok=True)

    for subject, schema in SUBJECT_AVRO_SCHEMAS.items():
        schema_path = schema_dir / f"{subject}.avsc"
        schema_path.write_text(json.dumps(schema, indent=2) + "\n")
        schema_id = client.register_schema(subject, schema, schema_type="AVRO")
        print(f"Schema ready: {subject} id={schema_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
