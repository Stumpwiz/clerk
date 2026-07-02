#!/usr/bin/env python3
"""
deploy_to_aws.py - Automated deployment script for the community administration application to AWS

This script handles:
1. Building Docker images for backend and frontend
2. Pushing images to AWS ECR
3. Triggering AWS App Runner deployments
4. Monitoring deployment status
5. Running health checks

Prerequisites:
- AWS CLI configured with credentials (aws configure)
- Docker installed and running
- boto3 installed (pip install boto3)

Usage:
    python scripts/deploy_to_aws.py --target both
    python scripts/deploy_to_aws.py --target backend
    python scripts/deploy_to_aws.py --target frontend
    python scripts/deploy_to_aws.py --help
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("ERROR: boto3 is not installed. Please run: pip install boto3")
    sys.exit(1)


# Configuration - Update these values for your AWS environment
CONFIG = {
    "aws_region": "us-east-1",
    "ecr_backend_repository": "clerk-backend",
    "ecr_frontend_repository": "clerk-frontend",
    "backend_service_arn": "arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d",
    "frontend_service_arn": "arn:aws:apprunner:us-east-1:365591166807:service/clerk-frontend/7d7f42151edb48fb87d706a4cceb2e4a",
    "production_api_url": "https://api.mrrc.online",
    "production_frontend_url": "https://test.mrrc.online",
}


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str):
    """Print a formatted header message"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print an info message"""
    print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")


def run_command(command: list, cwd: Optional[Path] = None, env: Optional[Dict] = None) -> bool:
    """
    Run a shell command and return success status

    Args:
        command: Command as list of strings
        cwd: Working directory for command execution
        env: Environment variables for command

    Returns:
        True if command succeeded, False otherwise
    """
    try:
        print_info(f"Running: {' '.join(command)}")
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env or os.environ.copy(),
            check=True,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print(f"STDOUT:\n{e.stdout}")
        if e.stderr:
            print(f"STDERR:\n{e.stderr}")
        return False


def check_prerequisites() -> bool:
    """Check if all prerequisites are met"""
    print_header("Checking Prerequisites")

    # Check Docker
    print_info("Checking Docker...")
    if not run_command(["docker", "--version"]):
        print_error("Docker is not installed or not in PATH")
        return False
    print_success("Docker is available")

    # Check AWS CLI
    print_info("Checking AWS CLI...")
    if not run_command(["aws", "--version"]):
        print_error("AWS CLI is not installed or not in PATH")
        return False
    print_success("AWS CLI is available")

    # Check AWS credentials
    print_info("Checking AWS credentials...")
    try:
        sts = boto3.client('sts', region_name=CONFIG['aws_region'])
        identity = sts.get_caller_identity()
        print_success(f"AWS credentials valid for account: {identity['Account']}")
    except NoCredentialsError:
        print_error("AWS credentials not found. Run 'aws configure' to set them up.")
        return False
    except ClientError as e:
        print_error(f"AWS credentials error: {e}")
        return False

    return True


def get_ecr_login_password() -> Optional[str]:
    """Get ECR authentication token"""
    try:
        ecr = boto3.client('ecr', region_name=CONFIG['aws_region'])
        response = ecr.get_authorization_token()
        return response['authorizationData'][0]['authorizationToken']
    except ClientError as e:
        print_error(f"Failed to get ECR login: {e}")
        return None


def ecr_login() -> Optional[str]:
    """Login to AWS ECR and return registry URL"""
    print_header("Logging in to AWS ECR")

    try:
        ecr = boto3.client('ecr', region_name=CONFIG['aws_region'])
        response = ecr.get_authorization_token()

        auth_data = response['authorizationData'][0]
        registry_url = auth_data['proxyEndpoint'].replace('https://', '')

        # Use AWS CLI for Docker login
        login_command = [
            'aws', 'ecr', 'get-login-password',
            '--region', CONFIG['aws_region']
        ]

        docker_login = [
            'docker', 'login',
            '--username', 'AWS',
            '--password-stdin',
            registry_url
        ]

        # Get password
        password_process = subprocess.run(
            login_command,
            capture_output=True,
            text=True,
            check=True
        )

        # Login to Docker
        login_process = subprocess.run(
            docker_login,
            input=password_process.stdout,
            capture_output=True,
            text=True,
            check=True
        )

        print_success(f"Logged in to ECR: {registry_url}")
        return registry_url

    except (ClientError, subprocess.CalledProcessError) as e:
        print_error(f"ECR login failed: {e}")
        return None


def build_and_push_backend(registry_url: str, project_root: Path) -> bool:
    """Build and push backend Docker image"""
    print_header("Building and Pushing Backend Image")

    backend_path = project_root / "backend"
    image_tag = f"{registry_url}/{CONFIG['ecr_backend_repository']}"

    # Build image
    print_info("Building backend Docker image...")
    if not run_command(
        ["docker", "build", "-t", f"{image_tag}:latest", "."],
        cwd=backend_path
    ):
        return False
    print_success("Backend image built successfully")

    # Also tag with commit hash if in git repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()
        run_command(["docker", "tag", f"{image_tag}:latest", f"{image_tag}:{commit_hash}"])
        print_info(f"Tagged with commit hash: {commit_hash}")
    except subprocess.CalledProcessError:
        print_warning("Not in a git repository, skipping commit hash tag")

    # Push image
    print_info("Pushing backend image to ECR...")
    if not run_command(["docker", "push", f"{image_tag}:latest"]):
        return False
    print_success("Backend image pushed successfully")

    return True


def build_and_push_frontend(registry_url: str, project_root: Path) -> bool:
    """Build and push frontend Docker image"""
    print_header("Building and Pushing Frontend Image")

    frontend_path = project_root / "frontend"
    image_tag = f"{registry_url}/{CONFIG['ecr_frontend_repository']}"

    # Build image with production configuration
    print_info("Building frontend Docker image with production settings...")
    build_args = [
        "--build-arg", f"NEXT_PUBLIC_API_URL={CONFIG['production_api_url']}",
    ]

    if not run_command(
        ["docker", "build"] + build_args + ["-t", f"{image_tag}:latest", "."],
        cwd=frontend_path
    ):
        return False
    print_success("Frontend image built successfully")

    # Also tag with commit hash
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
        commit_hash = result.stdout.strip()
        run_command(["docker", "tag", f"{image_tag}:latest", f"{image_tag}:{commit_hash}"])
        print_info(f"Tagged with commit hash: {commit_hash}")
    except subprocess.CalledProcessError:
        print_warning("Not in a git repository, skipping commit hash tag")

    # Push image
    print_info("Pushing frontend image to ECR...")
    if not run_command(["docker", "push", f"{image_tag}:latest"]):
        return False
    print_success("Frontend image pushed successfully")

    return True


def deploy_app_runner_service(service_arn: str, service_name: str) -> bool:
    """Trigger App Runner deployment and wait for completion"""
    print_header(f"Deploying {service_name} to App Runner")

    try:
        apprunner = boto3.client('apprunner', region_name=CONFIG['aws_region'])

        # Start deployment
        print_info("Triggering deployment...")
        apprunner.start_deployment(ServiceArn=service_arn)
        print_success("Deployment initiated")

        # Wait for deployment to complete (max 10 minutes)
        print_info("Waiting for deployment to complete (max 10 minutes)...")
        max_attempts = 60
        for attempt in range(1, max_attempts + 1):
            response = apprunner.describe_service(ServiceArn=service_arn)
            status = response['Service']['Status']

            print_info(f"Deployment status: {status} (check {attempt}/{max_attempts})")

            if status == 'RUNNING':
                print_success(f"{service_name} deployment completed successfully!")
                return True
            elif status == 'OPERATION_IN_PROGRESS':
                time.sleep(10)
            else:
                print_error(f"Unexpected status: {status}")
                return False

        print_warning(f"Deployment timed out after {max_attempts * 10} seconds")
        return False

    except ClientError as e:
        print_error(f"App Runner deployment failed: {e}")
        return False


def health_check(url: str, service_name: str) -> bool:
    """Perform health check on deployed service"""
    print_info(f"Performing health check for {service_name}...")
    print_info("Waiting 10 seconds for service to stabilize...")
    time.sleep(10)

    try:
        import urllib.request
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = response.getcode()
            if status_code == 200:
                print_success(f"{service_name} health check passed!")
                return True
            else:
                print_error(f"{service_name} health check failed with status {status_code}")
                return False
    except Exception as e:
        print_error(f"{service_name} health check failed: {e}")
        return False


def deploy_backend(registry_url: str, project_root: Path) -> bool:
    """Deploy backend to AWS"""
    if not build_and_push_backend(registry_url, project_root):
        return False

    if not deploy_app_runner_service(CONFIG['backend_service_arn'], "Backend"):
        return False

    # Health check
    health_url = f"{CONFIG['production_api_url']}/health"
    return health_check(health_url, "Backend")


def deploy_frontend(registry_url: str, project_root: Path) -> bool:
    """Deploy frontend to AWS"""
    if not build_and_push_frontend(registry_url, project_root):
        return False

    if not deploy_app_runner_service(CONFIG['frontend_service_arn'], "Frontend"):
        return False

    # Health check
    return health_check(CONFIG['production_frontend_url'], "Frontend")


def main():
    """Main deployment function"""
    parser = argparse.ArgumentParser(
        description='Deploy the community administration application to AWS App Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Deploy both backend and frontend:
    python scripts/deploy_to_aws.py --target both

  Deploy only backend:
    python scripts/deploy_to_aws.py --target backend

  Deploy only frontend:
    python scripts/deploy_to_aws.py --target frontend
        """
    )

    parser.add_argument(
        '--target',
        choices=['both', 'backend', 'frontend'],
        default='both',
        help='What to deploy (default: both)'
    )

    parser.add_argument(
        '--skip-checks',
        action='store_true',
        help='Skip prerequisite checks (use with caution)'
    )

    args = parser.parse_args()

    # Get project root
    project_root = Path(__file__).resolve().parent.parent

    print_header("AWS Deployment Script for Community Administration Application")
    print_info(f"Project root: {project_root}")
    print_info(f"Target: {args.target}")
    print_info(f"AWS Region: {CONFIG['aws_region']}")

    # Check prerequisites
    if not args.skip_checks:
        if not check_prerequisites():
            print_error("Prerequisites check failed. Please fix the issues and try again.")
            sys.exit(1)

    # Login to ECR
    registry_url = ecr_login()
    if not registry_url:
        print_error("Failed to login to ECR")
        sys.exit(1)

    # Deploy based on target
    success = True

    if args.target in ['both', 'backend']:
        if not deploy_backend(registry_url, project_root):
            print_error("Backend deployment failed")
            success = False

    if args.target in ['both', 'frontend']:
        if not deploy_frontend(registry_url, project_root):
            print_error("Frontend deployment failed")
            success = False

    # Final summary
    print_header("Deployment Summary")

    if success:
        print_success("All deployments completed successfully! 🎉")
        print_info(f"Backend API: {CONFIG['production_api_url']}")
        print_info(f"Frontend: {CONFIG['production_frontend_url']}")
        sys.exit(0)
    else:
        print_error("One or more deployments failed. Check the logs above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
