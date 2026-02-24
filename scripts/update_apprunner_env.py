#!/usr/bin/env python3
"""
update_apprunner_env.py - Update AWS App Runner service environment variables

This script updates the environment variables for the backend App Runner service
to include the proper CORS origins for production.

Usage:
    python scripts/update_apprunner_env.py
"""

import sys
import boto3
from botocore.exceptions import ClientError

# Configuration
CONFIG = {
    "aws_region": "us-east-1",
    "backend_service_arn": "arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d",
}

# Environment variables to set/update
ENVIRONMENT_VARIABLES = {
    "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,https://test.mrrc.online,https://api.mrrc.online",
    "DEBUG": "False",
    "API_HOST": "0.0.0.0",
    "API_PORT": "8000",
}

def main():
    print("=" * 70)
    print("AWS App Runner - Update Backend Environment Variables")
    print("=" * 70)
    print()

    try:
        # Initialize App Runner client
        apprunner = boto3.client('apprunner', region_name=CONFIG['aws_region'])

        # Get current service configuration
        print("📋 Fetching current service configuration...")
        response = apprunner.describe_service(ServiceArn=CONFIG['backend_service_arn'])
        service = response['Service']

        print(f"✅ Found service: {service['ServiceName']}")
        print(f"   Status: {service['Status']}")
        print()

        # Prepare the update
        print("🔧 Preparing environment variable update...")
        env_vars = [{"Name": k, "Value": v} for k, v in ENVIRONMENT_VARIABLES.items()]

        print("   Environment variables to set:")
        for env_var in env_vars:
            # Mask sensitive values
            value = env_var['Value']
            if len(value) > 50:
                value = value[:47] + "..."
            print(f"     {env_var['Name']}: {value}")
        print()

        # Update the service
        print("🚀 Updating App Runner service...")
        update_response = apprunner.update_service(
            ServiceArn=CONFIG['backend_service_arn'],
            SourceConfiguration={
                'ImageRepository': {
                    'ImageConfiguration': {
                        'RuntimeEnvironmentVariables': ENVIRONMENT_VARIABLES,
                        'Port': '8000',
                    },
                },
            },
        )

        operation_id = update_response['OperationId']
        print(f"✅ Update initiated (Operation ID: {operation_id})")
        print()

        print("⏳ The service will restart with the new configuration.")
        print("   This may take 5-10 minutes to complete.")
        print()
        print(f"   Monitor status with:")
        print(f"   aws apprunner describe-service --service-arn {CONFIG['backend_service_arn']}")
        print()
        print("✅ Environment variables updated successfully!")

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"❌ AWS Error ({error_code}): {error_message}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
