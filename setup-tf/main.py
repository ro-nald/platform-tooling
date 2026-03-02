import boto3
import json
import typer
from github import Github
from botocore.exceptions import ClientError
from rich import print

app = typer.Typer()


def bootstrap_s3_backend(bucket_name: str, region: str):
    """Creates an S3 bucket for Terraform state if it doesn't exist."""
    s3 = boto3.client("s3", region_name=region)

    print(f"[bold blue]🔍 Checking S3 bucket:[/bold blue] {bucket_name}")

    try:
        # Note: us-east-1 is a special case in S3 — it does not accept a LocationConstraint
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region},
            )
        print(f"✅ [green]Created bucket:[/green] {bucket_name}")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "BucketAlreadyOwnedByYou":
            print("ℹ️  [yellow]Bucket already exists and you own it — re-applying security settings.[/yellow]")
        elif error_code == "BucketAlreadyExists":
            print(f"❌ [red]Error:[/red] Bucket name '{bucket_name}' is already taken globally.")
            raise typer.Exit(1)
        else:
            print(f"❌ [red]AWS Error:[/red] {e}")
            raise typer.Exit(1)

    try:
        # Apply access controls first to close the window between bucket creation
        # and hardening as quickly as possible.
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )

        s3.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "DenyNonTLS",
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            f"arn:aws:s3:::{bucket_name}",
                            f"arn:aws:s3:::{bucket_name}/*",
                        ],
                        "Condition": {
                            "Bool": {"aws:SecureTransport": "false"},
                        },
                    }
                ],
            }),
        )

        s3.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256",
                        },
                        "BucketKeyEnabled": True,
                    }
                ]
            },
        )

        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"},
        )
        print("🔒 [green]Security and versioning enabled.[/green]")
    except ClientError as e:
        print(f"❌ [red]AWS Error applying security settings:[/red] {e}")
        raise typer.Exit(1)


@app.command(name="backend", help="Provision the Terraform S3 state backend.")
def bootstrap(
    bucket_prefix: str = typer.Argument(..., help="Bucket name prefix (e.g. your-org)"),
    env: str = typer.Argument("dev", help="Environment name appended to the bucket name"),
    region: str = typer.Argument("us-east-1", help="AWS region for the S3 bucket"),
):
    """
    Provision an S3 bucket for Terraform state.

    The bucket is named <bucket-prefix>-tfstate-<env>.
    Example: uv run setup-tf/main.py backend my-org dev eu-west-2
    """
    bucket_name = f"{bucket_prefix}-tfstate-{env}"
    bootstrap_s3_backend(bucket_name, region)
    print(f"\n🚀 [bold green]Backend for {env} is ready for Terraform![/bold green]")


@app.command(name="github", help="Write Terraform backend bucket name to a GitHub Actions variable.")
def register_backend(
    repo_name: str = typer.Argument(..., help="GitHub repository in 'owner/repo' format"),
    bucket_prefix: str = typer.Argument(..., help="Bucket name prefix (must match 'backend' command)"),
    env: str = typer.Argument(..., help="Environment name"),
):
    """
    Write the S3 bucket name to a GitHub Actions repository variable.

    Reads GITHUB_TOKEN from the environment — do not pass it on the command line.
    Example: uv run setup-tf/main.py github my-org/my-repo my-org dev
    """
    import os

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[red]Error: GITHUB_TOKEN environment variable is not set.[/red]")
        print("[yellow]Export it before running: export GITHUB_TOKEN=<your-token>[/yellow]")
        raise typer.Exit(1)

    bucket_name = f"{bucket_prefix}-tfstate-{env}"
    variable_name = f"TF_BACKEND_BUCKET_{env.upper()}"

    try:
        repo = Github(token).get_repo(repo_name)
        print(f"🚀 Registering {bucket_name} to {repo_name} as {variable_name}...")
        repo.create_variable(variable_name, bucket_name)
        print("✅ [green]Successfully registered variable in GitHub![/green]")
    except Exception as e:
        print(f"❌ [red]Failed to update GitHub:[/red] {e}")
        raise typer.Exit(1)


@app.callback()
def main():
    """CLI for managing Terraform backends."""


if __name__ == "__main__":
    app()
