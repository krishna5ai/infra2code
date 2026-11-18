import json
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from .env
MODEL = "claude-sonnet-5-5"

# Cost and security rules per cloud. Only AWS for now.
# To support another cloud later, add one more entry here.
CLOUD_NOTES = {
    "aws": (
        "Region ap-south-1 unless told otherwise. Use provider hashicorp/aws ~> 5 and default_tags. "
        "Compute: t4g Graviton instances when the software runs on ARM, Lambda or Fargate for spiky or low traffic, Spot only for fault-tolerant work. "
        "Storage: gp3 volumes, S3 lifecycle rules or Intelligent-Tiering. "
        "Network: no NAT gateway unless private subnets truly need internet access, use the free S3 and DynamoDB gateway VPC endpoints, one AZ for dev and two for prod. "
        "Database: db.t4g.micro single-AZ for dev, DynamoDB on-demand for spiky traffic, Multi-AZ and backups for prod. "
        "Security: security groups open only the needed ports, IAM roles with least privilege (never IAM users or access keys), "
        "no secrets in code (use Secrets Manager or SSM Parameter Store), S3 Block Public Access, "
        "encryption at rest with AWS-managed keys (free), IMDSv2 required on EC2, databases never publicly accessible."
    ),
}

# The exact shape we want Claude to answer in.
JSON_SHAPE = """{"summary":"one sentence","files":{"providers.tf":"...","main.tf":"...","variables.tf":"...","outputs.tf":"...","terraform.tfvars.example":"...","README.md":"prerequisites, deploy commands, terraform destroy"},"arch":{"tiers":[{"name":"tier","nodes":["label"]}],"edges":[["label A","label B"]]},"flow":[{"step":1,"from":"label A","to":"label B","what":"what moves and how"}],"security":[{"control":"short name","applies_to":"node label","detail":"what it protects against"}],"cost":{"monthly_usd":0,"typical_usd":0,"basis":"assumptions","items":[{"saving_usd":0,"title":"change","why":"reason","efficiency_impact":"none|low"}]},"findings":[{"level":"hi|lo|fx","title":"","detail":""}]}"""


def build_prompt(requirement, cloud, env):
    return f"""You are a senior {cloud.upper()} architect and Terraform expert.
Turn this client requirement into a complete Terraform project: {requirement}
Environment: {env}. {CLOUD_NOTES[cloud]}
Rules: include everything the client asked for. Choose the cheapest design that still works well:
smallest sufficient sizes, cheaper CPU and disk types, managed or serverless services where cheaper,
no paid NAT gateway unless private networking is needed, single zone for dev, multi-zone and backups for prod.
Use only real provider resources, pin terraform >= 1.6, use variables with defaults,
no credentials in code, encrypt storage, never open admin ports to 0.0.0.0/0.
Reply with ONLY one JSON object, no markdown fences, in this shape:
{JSON_SHAPE}
arch: at most 12 nodes in 2 to 5 tiers, top tier is where traffic enters, edge labels must match node labels.
flow: the request and data path in order, 3 to 8 steps, using the same node labels.
security: every control you applied (encryption, security groups, least-privilege IAM, private subnets, HTTPS) and the node it protects.
cost: monthly estimate at 730 hours, typical_usd is a default non-optimized build.
Only choose a saving when efficiency_impact is none or low for this requirement. Never trade away reliability or speed the client asked for.
findings: remaining risks as hi or lo, fixes you applied as fx."""


def _ask(prompt):
    client = Anthropic()  # finds the key in the environment
    with client.messages.stream(
        model=MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "max_tokens":
        raise RuntimeError("Answer was cut off. Use a shorter requirement.")
    return "".join(b.text for b in message.content if b.type == "text")


def _extract_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Claude did not return JSON.")
    return json.loads(text[start : end + 1])


def generate(requirement, cloud="aws", env="dev"):
    result = _extract_json(_ask(build_prompt(requirement, cloud, env)))
    if "main.tf" not in result.get("files", {}):
        raise ValueError("The result has no main.tf.")
    return result


def repair(files, errors, cloud):
    """Send files and Terraform's errors back to Claude. Returns the fixed files."""
    prompt = f"""These {cloud.upper()} Terraform files failed `terraform validate`.
Fix every error with the smallest change. Do not remove anything the client asked for.
Files (JSON): {json.dumps(files)}
Errors:
{errors[:4000]}
Reply with ONLY one JSON object, no markdown fences: {{"files": {{"<name>": "<full corrected content>"}}}}
Include every file you changed, in full."""
    fixed = _extract_json(_ask(prompt)).get("files")
    if not isinstance(fixed, dict) or not fixed:
        raise ValueError("The repair answer had no files.")
    return fixed


def save(result, folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in result["files"].items():
        if Path(name).name == name:  # blocks names like ../evil
            (folder / name).write_text(content, encoding="utf-8")
    plan = {k: result.get(k) for k in ("summary", "arch", "flow", "security", "cost", "findings")}
    (folder / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")