from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SchemaRegistryClient:
    base_url: str

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def list_subjects(self) -> list[str]:
        with urllib.request.urlopen(self._url("/subjects"), timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def register_schema(
        self,
        subject: str,
        schema: dict[str, Any],
        *,
        schema_type: str = "AVRO",
    ) -> int:
        payload = json.dumps(
            {"schemaType": schema_type, "schema": json.dumps(schema)}
        ).encode("utf-8")
        request = urllib.request.Request(
            self._url(f"/subjects/{subject}/versions"),
            data=payload,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
        return int(body["id"])

    def get_latest_schema(self, subject: str) -> dict[str, Any]:
        with urllib.request.urlopen(
            self._url(f"/subjects/{subject}/versions/latest"), timeout=10
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        return json.loads(body["schema"])

    def get_latest_subject_metadata(self, subject: str) -> dict[str, Any]:
        with urllib.request.urlopen(
            self._url(f"/subjects/{subject}/versions/latest"), timeout=10
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        body["schema"] = json.loads(body["schema"])
        body["schemaType"] = body.get("schemaType", "AVRO")
        return body

    def get_latest_schema_id(self, subject: str) -> int:
        with urllib.request.urlopen(
            self._url(f"/subjects/{subject}/versions/latest"), timeout=10
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
        return int(body["id"])

    def assert_subject_registered(self, subject: str) -> None:
        subjects = set(self.list_subjects())
        if subject not in subjects:
            raise RuntimeError(f"Schema subject not registered: {subject}")
