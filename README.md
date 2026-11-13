# rag-app

The RAG application: documents, the query API (Lambda), and the pipeline that deploys both.
The AWS foundations (S3, S3 Vectors, Bedrock Knowledge Base, IAM roles for this repo's pipeline) come from the separate **rag-platform-infra** repo.

```
rag-app/
├── docs/            source documents (markdown, txt, pdf, docx...)  → synced to S3, ingested into the KB
├── src/handler.py   Lambda: question → Bedrock RetrieveAndGenerate → answer + sources
├── terraform/       Lambda, execution role, Function URL (reads KB IDs from SSM)
├── scripts/
│   ├── ingest.py    sync docs/ to the bucket and run the Bedrock ingestion job
│   └── ask.py       call the deployed API with a SigV4-signed request
└── .github/workflows/
    ├── terraform-plan.yml   PR: fmt, validate, plan (comment on PR)
    └── deploy.yml           main: terraform apply, then docs sync + ingestion
```

## Pipelines

| Workflow | Trigger | Steps | AWS role |
|---|---|---|---|
| `terraform-plan` | PR touching `terraform/**` or `src/**` | fmt, init, validate, plan, PR comment | `rag-platform-app-plan` (read-only) |
| `deploy` | Push to `main` | plan, apply (behind `production` approval), then `scripts/ingest.py` | `rag-platform-app-deploy` (scoped to `rag-app-*` resources) |

Changing a file in `docs/` and merging is enough to re-index: the pipeline uploads changed files, deletes removed ones, and starts a Bedrock ingestion job.

## Setup

Prerequisite: **rag-platform-infra** is deployed (its README ends with the variables to set here).

```bash
gh repo create <org>/rag-app --private --source=. --push

gh variable set AWS_REGION          --body us-east-1
gh variable set TF_STATE_BUCKET     --body <tf_state_bucket>
gh variable set AWS_PLAN_ROLE_ARN   --body <app_plan_role_arn>
gh variable set AWS_DEPLOY_ROLE_ARN --body <app_deploy_role_arn>
```

In **Settings → Environments**, create `production` with a required reviewer. The deploy role's trust policy only accepts jobs from that environment.

Pick the Claude model: list the inference profiles in your account and set `model_id` in `terraform/envs/dev.tfvars`.
```bash
aws bedrock list-inference-profiles --region us-east-1 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId"
```

Then open a PR, review the plan, merge, and approve the deployment.

## Try it

```bash
pip install boto3
export API_URL=<api_url printed at the end of the deploy job>
python scripts/ask.py "How many weeks of parental leave do I get?"
python scripts/ask.py "What is the dress code?"      # not in the docs: should say it doesn't know
```
The Function URL uses `AWS_IAM` auth, so your AWS identity needs `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` on `rag-app-dev-api`.

## Change something

| I want to... | Do this |
|---|---|
| Add or edit knowledge | Change files in `docs/`, merge to `main` |
| Use a different Claude model | Edit `model_id` in `terraform/envs/dev.tfvars` |
| Retrieve more context | Edit `top_k` in the same file |
| Change chunk size or embedding model | That is a platform change: edit `rag-platform-infra`, then re-run ingestion with `FORCE_INGEST=1 python scripts/ingest.py` |
| Customize the prompt | Replace `retrieve_and_generate` in `src/handler.py` with `retrieve` + your own prompt + `bedrock-runtime` `converse` |

## Teardown

Run `terraform destroy` for this repo's stack first, then the platform repo.
