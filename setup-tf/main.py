import boto3
import typer
import sys
import os
from github import Github
from botocore.exceptions import ClientError
from rich import print

app = typer.Typer()

def bootstrap_s3_backend(bucket_name: str, region: str):
    """Creates an S3 bucket for Terraform state if it doesn't exist."""
    s3 = boto3.client("s3", region_name=region)
    
    print(f"[bold blue]🔍 Checking S3 bucket:[/bold blue] {bucket_name}")
    
    try:
        # 1. Create the bucket
        # Note: us-east-1 is a special case in S3 and doesn't take a LocationConstraint
        if region == "eu-west-2":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": region}
            )
        print(f"✅ [green]Created bucket:[/green] {bucket_name}")

        # 2. Enable Versioning (Crucial for TF State)
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": "Enabled"}
        )
        
        # 3. Block Public Access (Security Best Practice)
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True
            }
        )
        print(f"🔒 [green]Security and Versioning enabled.[/green]")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "BucketAlreadyOwnedByYou":
            print(f"ℹ️  [yellow]Bucket already exists and you own it.[/yellow]")
        elif error_code == "BucketAlreadyExists":
            print(f"❌ [red]Error:[/red] Bucket name '{bucket_name}' is taken by someone else.")
            sys.exit(1)
        else:
            print(f"❌ [red]AWS Error:[/red] {e}")
            sys.exit(1)

@app.command(name="backend", help="Provision the Terraform backend.")
def bootstrap(
    env: str = typer.Argument("dev", help="The environment name"), 
    region: str = typer.Argument("eu-west-2", help="The AWS region")
):
    """
    Command to provision the Terraform backend.
    Example: python deployer.py bootstrap --env dev --region eu-west-2
    """
    # Standardized naming convention
    bucket_name = f"rd0550-tfstate-{env}"

    bootstrap_s3_backend(bucket_name, region)
    print(f"\n🚀 [bold green]Backend for {env} is ready for Terraform![/bold green]")

@app.command(name="github", help="Add Terraform backend details to GitHub as variables for target repository.")
@app.command()
def register_backend(
    repo_name: str,  # e.g., "your-org/your-repo"
    env: str,
    token: str = typer.Option(None, envvar="GITHUB_TOKEN")
):
    """
    Writes the S3 bucket name to a GitHub Repository Variable.
    """
    if not token:
        print("[red]Error: GITHUB_TOKEN not found in environment.[/red]")
        raise typer.Exit(1)

    bucket_name = f"rd0550-tfstate-{env}"
    token_github = Github(token)
    
    try:
        repo = token_github.get_repo(repo_name)
        
        # Industry standard: Variable names should be predictable
        variable_name = f"TF_BACKEND_BUCKET_{env.upper()}"
        
        # Note: PyGithub currently requires manual API calls for 'Variables' 
        # as it is a newer feature, but we can use the repo's 'create_variable' 
        # or update logic via a direct request if needed.
        # For simplicity, here is the conceptual flow:
        print(f"🚀 Registering {bucket_name} to {repo_name} as {variable_name}...")
        
        # Using the GitHub API to create/update the variable
        # (This uses the 'actions/variables' endpoint)
        repo.create_variable(variable_name, bucket_name)
        
        print(f"✅ [green]Successfully registered variable in GitHub![/green]")
        
    except Exception as e:
        print(f"❌ [red]Failed to update GitHub:[/red] {e}")
@app.callback()
def main():
    """
    My CLI for managing Terraform backends.
    """
    pass

if __name__ == "__main__":
    app()