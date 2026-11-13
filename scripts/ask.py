#!/usr/bin/env python3
"""
Call the deployed API. The Lambda Function URL uses AWS_IAM auth, so the request is SigV4-signed
with whatever AWS credentials you have configured.

    python scripts/ask.py "How many weeks of parental leave do I get?"
    export API_URL=$(terraform -chdir=terraform output -raw api_url)   # after a local init, or copy it from the deploy job log
    python scripts/ask.py "..."

Your AWS identity needs lambda:InvokeFunctionUrl (and lambda:InvokeFunction) on the function.
"""
import json
import os
import sys
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"


def main() -> None:
    url = os.environ.get("API_URL")
    if not url or len(sys.argv) < 2:
        sys.exit(__doc__)
    question = " ".join(sys.argv[1:])

    body = json.dumps({"question": question})
    request = AWSRequest(method="POST", url=url, data=body, headers={"content-type": "application/json"})
    SigV4Auth(boto3.Session().get_credentials(), "lambda", REGION).add_auth(request)

    req = urllib.request.Request(url, data=body.encode(), headers=dict(request.headers), method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)

    print(f"QUESTION: {question}\n\nANSWER:\n{data['answer']}\n\nSOURCES:")
    for source in data.get("sources", []):
        print(f"  {source}")


if __name__ == "__main__":
    main()
