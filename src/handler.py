"""
Lambda handler: question in, grounded answer + citations out.

POST body:  {"question": "How many weeks of parental leave do I get?"}
Response:   {"answer": "...", "sources": ["s3://bucket/parental_leave.md"]}

All the RAG work (embed the question, search the vector index, build the prompt,
call Claude, attach citations) happens inside Bedrock's RetrieveAndGenerate call.
"""
import json
import os

import boto3

KB_ID = os.environ["KB_ID"]
MODEL_ID = os.environ["MODEL_ID"]
TOP_K = int(os.environ.get("TOP_K", "3"))

REGION = os.environ.get("AWS_REGION", "us-east-1")
runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)
account_id = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


def model_arn() -> str:
    """Claude on Bedrock is invoked through an inference profile (global., us., eu., ...)."""
    if MODEL_ID.startswith("arn:"):
        return MODEL_ID
    if MODEL_ID.startswith(("global.", "us.", "eu.", "apac.", "jp.")):
        return f"arn:aws:bedrock:{REGION}:{account_id}:inference-profile/{MODEL_ID}"
    return f"arn:aws:bedrock:{REGION}::foundation-model/{MODEL_ID}"


def respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, _context):
    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return respond(400, {"error": "body must be JSON"})

    question = (payload.get("question") or "").strip()
    if not question:
        return respond(400, {"error": "missing 'question'"})
    if len(question) > 2000:
        return respond(400, {"error": "question too long (max 2000 characters)"})

    result = runtime.retrieve_and_generate(
        input={"text": question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KB_ID,
                "modelArn": model_arn(),
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {"numberOfResults": TOP_K}
                },
            },
        },
    )

    sources = []
    for citation in result.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            uri = ref.get("location", {}).get("s3Location", {}).get("uri")
            if uri and uri not in sources:
                sources.append(uri)

    return respond(200, {"answer": result["output"]["text"], "sources": sources})
