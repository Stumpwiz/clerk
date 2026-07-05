# Fix CORS for Production

The production backend is missing the CORS configuration for `https://test.mrrc.online`.

## Option 1: AWS Console (Easiest)

1. Go to AWS Console → App Runner → Services
2. Select `clerk-backend` service
3. Click **"Configuration"** tab
4. Click **"Edit"** under "Environment variables"
5. Add this environment variable:
   - **Name**: `CORS_ORIGINS`
   - **Value**: `http://localhost:3000,http://127.0.0.1:3000,https://test.mrrc.online,https://api.mrrc.online`
6. Click **"Deploy"**
7. Wait 5-10 minutes for the service to redeploy

## Option 2: AWS CLI

Run this command to update the environment variable:

```bash
aws apprunner update-service \
  --service-arn "arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d" \
  --source-configuration '{
    "ImageRepository": {
      "ImageConfiguration": {
        "RuntimeEnvironmentVariables": {
          "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,https://test.mrrc.online,https://api.mrrc.online",
          "DEBUG": "False",
          "API_HOST": "0.0.0.0",
          "API_PORT": "8000"
        },
        "Port": "8000"
      }
    }
  }' \
  --region us-east-1
```

## Option 3: Add to deployment script

The deployment script should also set environment variables. Update the `deploy_app_runner_service` function to include environment variable updates.

## Verification

After the service redeploys, verify the CORS headers:

```bash
curl -I -X OPTIONS https://api.mrrc.online/api/bodies/ \
  -H "Origin: https://test.mrrc.online" \
  -H "Access-Control-Request-Method: GET"
```

You should see:
```
Access-Control-Allow-Origin: https://test.mrrc.online
```

## Important Notes

- The service will restart and take 5-10 minutes to come back online
- All environment variables must be set together (you can't update just one)
- Make sure to also include:
  - `DATABASE_URL` (your RDS connection string)
  - `AUTH_SECRET_KEY`
  - `SESSION_COOKIE_NAME`
  - `SESSION_COOKIE_SECURE`
  - `SESSION_COOKIE_SAMESITE`
  - `SESSION_TTL_SECONDS`
