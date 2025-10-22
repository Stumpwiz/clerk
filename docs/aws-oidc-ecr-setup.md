# GitHub OIDC → AWS and ECR Setup
# AWS OIDC + ECR Setup (for Stumpwiz/clerk)

Purpose
- Enable GitHub Actions to assume an AWS IAM role (via OIDC) to build and push Docker images to Amazon ECR.
- No long-lived AWS keys are used.

Your values
- AWS Account ID: 365591166807
- AWS Region: us-east-1
- GitHub Repo: Stumpwiz/clerk
- ECR repositories: clerk-api and clerk-web (defaults used by this repo)

What you’ll do
1) Create an IAM role that trusts GitHub OIDC (restricted to Stumpwiz/clerk).
2) Attach minimal permissions to push to ECR (and optionally force ECS redeploys).
3) Create the ECR repos (or let the workflow auto-create them).
4) Set GitHub secrets/variables and run the CD workflow.

Prerequisites
- AWS CLI configured for account 365591166807 in region us-east-1.
- GitHub repository Stumpwiz/clerk with this code pushed.

---

Step 1: Create the GitHub OIDC role

Option A: Console (beginner-friendly)
- IAM → Roles → Create role
  - Trusted entity: Web identity
  - Identity provider: token.actions.githubusercontent.com
  - Audience: sts.amazonaws.com
  - Next → Name: clerk-github-oidc → Create role.
- Open the newly created role → Trust relationships → Edit trust policy.
- Replace the policy content with deploy/aws/iam/github-oidc-trust.json (see below), which locks to repo Stumpwiz/clerk.

Option B: CLI (advanced)
- Ensure deploy/aws/iam/github-oidc-trust.json contains Stumpwiz/clerk (it is pre-filled in this repo).
- Run:
This repo ships a CD workflow to build/push images to ECR. Follow these steps to wire GitHub Actions to AWS via OIDC and push images.

## 1) Prepare values

- ACCOUNT_ID: your AWS account ID
- REGION: e.g., us-east-1
- OWNER/REPO: your GitHub org/user and repo name
- ROLE_NAME: e.g., clerk-github-oidc

## 2) Create IAM role with GitHub OIDC trust

Edit deploy/aws/iam/github-oidc-trust.json and replace:
- <ACCOUNT_ID>, <OWNER>, <REPO>

Then:
