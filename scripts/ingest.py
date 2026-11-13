#!/usr/bin/env python3
"""
Sync ./docs to the platform's docs bucket and re-run the Bedrock ingestion job.
Resource IDs come from SSM parameters published by the rag-platform-infra repo.

    python scripts/ingest.py                 # env=dev, project=rag-platform
    ENVIRONMENT=prod python scripts/ingest.py

Used by the deploy pipeline, and handy locally.
"""
import hashlib
import os
import sys
import time
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
PROJECT = os.environ.get("PROJECT", "rag-platform")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
SUFFIXES = {".md", ".txt", ".pdf", ".docx", ".html", ".csv"}

ssm = boto3.client("ssm", region_name=REGION)
s3 = boto3.client("s3", region_name=REGION)
agent = boto3.client("bedrock-agent", region_name=REGION)


def param(name: str) -> str:
    return ssm.get_parameter(Name=f"/{PROJECT}/{ENVIRONMENT}/{name}")["Parameter"]["Value"]


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def sync_docs(bucket: str) -> int:
    """Upload new/changed files, delete removed ones. Returns the number of changes."""
    local = {p.name: p for p in DOCS_DIR.iterdir() if p.is_file() and p.suffix in SUFFIXES}
    remote = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            remote[obj["Key"]] = obj["ETag"].strip('"')

    changes = 0
    for name, path in local.items():
        if remote.get(name) != md5(path):
            s3.upload_file(str(path), bucket, name)
            print(f"uploaded  {name}")
            changes += 1
    for key in remote.keys() - local.keys():
        s3.delete_object(Bucket=bucket, Key=key)
        print(f"deleted   {key}")
        changes += 1
    return changes


def run_ingestion(kb_id: str, ds_id: str) -> None:
    job = agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)["ingestionJob"]
    job_id = job["ingestionJobId"]
    print(f"ingestion job {job_id} started")
    while True:
        job = agent.get_ingestion_job(
            knowledgeBaseId=kb_id, dataSourceId=ds_id, ingestionJobId=job_id
        )["ingestionJob"]
        if job["status"] in ("COMPLETE", "FAILED", "STOPPED"):
            break
        time.sleep(5)
    print(f"status: {job['status']}  stats: {job.get('statistics')}")
    if job["status"] != "COMPLETE":
        sys.exit(f"ingestion failed: {job.get('failureReasons')}")


def main() -> None:
    bucket = param("docs-bucket")
    kb_id = param("knowledge-base-id")
    ds_id = param("data-source-id")

    changes = sync_docs(bucket)
    if changes == 0 and os.environ.get("FORCE_INGEST") != "1":
        print("docs unchanged; skipping ingestion (set FORCE_INGEST=1 to run anyway)")
        return
    run_ingestion(kb_id, ds_id)


if __name__ == "__main__":
    main()
