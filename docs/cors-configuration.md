# CORS Configuration Guide

## Current Allowed Origins

The backend API currently allows requests from these origins:

- `http://localhost:3000` - Local development
- `http://127.0.0.1:3000` - Local development (alternate)
- `https://test.mrrc.online` - Production frontend (current)
- `https://clerk.mrrc.online` - Production frontend (future CNAME)
- `https://api.mrrc.online` - Production API (self)

## Updating CORS Origins

### Method 1: AWS CLI (Recommended for immediate changes)

Use this command to update the CORS origins on the running backend service:

```bash
aws apprunner update-service \
  --service-arn "arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d" \
  --region us-east-1 \
  --source-configuration file:///dev/stdin <<'EOF'
{
  "ImageRepository": {
    "ImageIdentifier": "365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend:latest",
    "ImageRepositoryType": "ECR",
    "ImageConfiguration": {
      "RuntimeEnvironmentVariables": {
        "CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,https://test.mrrc.online,https://api.mrrc.online,https://clerk.mrrc.online",
        [... other environment variables ...]
      },
      "StartCommand": "uvicorn app.main:app --host 0.0.0.0 --port 8000",
      "Port": "8000"
    }
  }
}
EOF
```

**Important**: When updating via CLI, you must include ALL environment variables, not just CORS_ORIGINS. Get the current config first:

```bash
aws apprunner describe-service \
  --service-arn "arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d" \
  --region us-east-1 \
  --query 'Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables' \
  --output json
```

### Method 2: Update Code and Redeploy

1. Update `backend/app/config.py`:
   ```python
   cors_origins: Union[List[str], str] = [
       "http://localhost:3000",
       "http://127.0.0.1:3000",
       "https://test.mrrc.online",
       "https://api.mrrc.online",
       "https://clerk.mrrc.online",
       "https://your-new-domain.com",  # Add new domain here
   ]
   ```

2. Commit and push changes:
   ```bash
   git add backend/app/config.py
   git commit -m "Add new CORS origin"
   git push
   ```

3. Deploy using the deployment script:
   ```bash
   python scripts/deploy_to_aws.py --target backend
   ```

### Method 3: AWS Console

1. Go to AWS Console → App Runner → Services
2. Select `clerk-backend`
3. Click **Configuration** tab
4. Click **Edit** under "Environment variables"
5. Update `CORS_ORIGINS` value to include new domain:
   ```
   http://localhost:3000,http://127.0.0.1:3000,https://test.mrrc.online,https://api.mrrc.online,https://clerk.mrrc.online,https://your-new-domain.com
   ```
6. Click **Deploy**

## Testing CORS Configuration

Test if CORS is properly configured for a specific origin:

```bash
curl -I -X OPTIONS https://api.mrrc.online/api/bodies/ \
  -H "Origin: https://clerk.mrrc.online" \
  -H "Access-Control-Request-Method: GET"
```

Look for this header in the response:
```
access-control-allow-origin: https://clerk.mrrc.online
```

## Common Issues

### CORS Error After Adding New Domain

**Symptom**: Browser shows `No 'Access-Control-Allow-Origin' header is present`

**Solution**:
1. Verify the domain is added to `CORS_ORIGINS` environment variable
2. Check that the service has been redeployed (takes 5-10 minutes)
3. Clear browser cache or try in incognito mode

### Wrong Protocol (HTTP vs HTTPS)

**Issue**: CORS origin must exactly match the protocol, domain, and port

**Example**:
- ❌ `http://clerk.mrrc.online` (wrong protocol)
- ✅ `https://clerk.mrrc.online` (correct)

### Wildcard Not Supported with Credentials

The backend uses `allow_credentials=True`, which means wildcard origins (`*`) are not allowed. Each domain must be explicitly listed.

## When to Update CORS

Update CORS origins when:
- Adding a new frontend domain
- Changing from HTTP to HTTPS
- Adding a new subdomain
- Moving to a new hosting provider

## Security Notes

- Only add trusted domains to CORS origins
- Production domains should always use HTTPS
- Remove unused domains from the list
- Never use wildcard (`*`) in production
