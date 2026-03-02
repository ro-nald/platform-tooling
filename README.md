# Platform Tooling

A collection of tools to assist with platform usage and infrastructure maintenance.

## CLI Tools

### `setup-tf`
Configures Terraform to provision an AWS S3 bucket which will be used to store Terraform state.

#### Commands
##### `backend`
Searches for the S3 bucket name provided, creating a new bucket if it doesn't exist.
##### `github`
Add the S3 bucket name to the GitHub repository variables.
