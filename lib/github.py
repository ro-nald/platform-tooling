import os

import typer
from github import Github
from github.Repository import Repository
from rich import print


def get_github_repo(repo_name: str) -> Repository:
    """Load GITHUB_TOKEN from the environment and return the named GitHub repository."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[red]Error: GITHUB_TOKEN environment variable is not set.[/red]")
        print("[yellow]Export it before running: export GITHUB_TOKEN=<your-token>[/yellow]")
        raise typer.Exit(1)
    return Github(token).get_repo(repo_name)
