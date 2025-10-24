``` markdown
# PHASE 6: Deploy ECS Cluster & Service
**Budget Deployment - Single Fargate Task with Nginx Proxy**

---

## Prerequisites
✅ Completed Phases 1-5  
✅ All ARNs recorded in RESOURCES-BUDGET.txt  
✅ Nginx image pushed to ECR (DONE!)

---

## STEP 6.1: ✅ COMPLETED - Nginx Image Pushed

The nginx image is already in ECR with tag v0.2.0. Skip to Step 6.2!

---

## STEP 6.2: Create ECS Cluster

1. In AWS Console search bar, type **`ECS`**
2. Click **"Elastic Container Service"**
3. Click **"Clusters"** in left sidebar
4. Click **"Create cluster"** (orange button)

### Cluster Configuration:

**Cluster name:** `clerk-main`

**Infrastructure:**
- ⚪ **AWS Fargate (serverless)** (should be selected by default)
- Leave all other defaults

**Tags:** (optional)
- Key: `App`, Value: `clerk`

Click **"Create"**

**📝 Record Cluster ARN:**
After creation, click on `clerk-main` and copy the ARN at the top:
```

ECS_CLUSTER_ARN=arn:aws:ecs:us-east-1:365591166807:cluster/clerk-main``` 

Paste this into your RESOURCES-BUDGET.txt file.

✅ **Cluster Created!**

---

## STEP 6.3: Register Task Definition

Now we'll register the task definition (the blueprint for your containers).

1. In ECS Console, click **"Task definitions"** in left sidebar
2. Look for a button or link that says **"Create new task definition with JSON"** or similar
   - On newer AWS Console: Click "Create new task definition" dropdown → Select "Create from JSON"
   - On older AWS Console: Look for "Create new task definition" → "Create with JSON"

### Use JSON Import:

1. You should see a JSON editor
2. **Delete everything** in the JSON editor (it might have a template)
3. **Open the file**: `deploy/aws/ecs/taskdef-combined-filled.json` in your code editor
4. **Copy the ENTIRE contents** of that file
5. **Paste** into the AWS Console JSON editor
6. Click **"Create"** or **"Register"**

**📝 Record Task Definition ARN:**
After creation, you'll see:
```

ECS_TASK_DEFINITION_ARN=arn:aws:ecs:us-east-1:365591166807:task-definition/clerk-combined:1``` 

Paste this into your RESOURCES-BUDGET.txt file.

✅ **Task Definition Registered!**

---

## STEP 6.4: Find Your VPC and Subnet

Before creating the service, we need to note your VPC and Subnet IDs.

### Find VPC:

1. In AWS Console search bar, type **`VPC`**
2. Click **"VPC"**
3. In left sidebar, click **"Your VPCs"**
4. Find your **default VPC** (should say "Default VPC" = Yes)
5. **Copy the VPC ID** (looks like `vpc-xxxxxxxxx`)

**📝 Record:**
```

VPC_ID=vpc-xxxxxxxxx``` 

### Find a Public Subnet:

1. In left sidebar, click **"Subnets"**
2. Look for subnets in your default VPC
3. Find one with:
   - **"Auto-assign public IPv4"** = **Yes**, OR
   - In the same AZ as your EFS (us-east-1a if you used 1 AZ)
4. **Copy the Subnet ID** (looks like `subnet-xxxxxxxxx`)

**📝 Record:**
```

SUBNET_ID=subnet-xxxxxxxxx``` 

Paste both into your RESOURCES-BUDGET.txt file.

✅ **VPC Info Recorded!**

---

## STEP 6.5: Create ECS Service

Now we'll create the service that runs your containers.

1. In ECS Console, click **"Clusters"** in left sidebar
2. Click on **`clerk-main`**
3. Click the **"Services"** tab
4. Click **"Create"** button

### Compute Configuration:

**Compute options:**
- ⚪ **Launch type**

**Launch type:**
- Select **FARGATE** from dropdown

### Deployment Configuration:

**Application type:**
- ⚪ **Service**

**Task definition:**
- **Family:** Select **`clerk-combined`** from dropdown
- **Revision:** Select **`1 (LATEST)`**

**Service name:** `clerk-combined-service`

**Desired tasks:** `1`

### Networking:

**VPC:** 
- Select your VPC (the one you recorded in Step 6.4)

**Subnets:** 
- Click the dropdown
- **Uncheck all subnets first**
- **Check ONLY the subnet** you recorded in Step 6.4
- (This ensures it's in the same AZ as your EFS mount)

**Security group:**
- Click **"Use an existing security group"**
- **Remove** the default security group (click the X)
- **Select** `clerk-ecs-sg` (sg-0f52c35c77b8ed90e - the one you created in Phase 2)

**Public IP:**
- ⚪ **TURNED ON** ✅ 
- (CRITICAL - this is how you'll access your app!)

### Load Balancing:

**Load balancer type:**
- ⚪ **None** (we're not using ALB)

### Service Auto Scaling:

- Leave **disabled** (not needed for low-volume app)

### Tags (optional):

- Key: `App`, Value: `clerk`

### Review and Create:

Scroll to bottom and click **"Create"**

⏳ **Wait 3-5 minutes for the service to start...**

You'll see a message like "Service created successfully" and be taken to the service details page.

✅ **Service Created!**

---

## STEP 6.6: Get Your Public IP

Now let's get the public IP address of your running task:

1. You should be on the `clerk-combined-service` details page
2. Click the **"Tasks"** tab
3. You'll see a task with **"Last status"** showing:
   - **PROVISIONING** → **PENDING** → **RUNNING** (refresh page to see updates)
4. Wait until **"Last status"** = **RUNNING** (may take 2-4 minutes)
5. Once RUNNING, click on the **Task ID** (it's a blue link like `abc123def456...`)
6. In the task details, scroll to the **"Configuration"** or **"Network"** section
7. Find **"Public IP"** address
8. **Copy this IP address**

**📝 Record:**
```

ECS_PUBLIC_IP=X.X.X.X``` 

Paste this into your RESOURCES-BUDGET.txt file.

✅ **Service Running with Public IP!**

---

## STEP 6.7: Test Your Deployment

### Test 1: API Health Endpoint

Open your browser to:
```

http://YOUR_PUBLIC_IP/health``` 

**Expected result:**
```

json {"status": "ok"}``` 

If you see this, your API container is working! ✅

### Test 2: Web Application

Open your browser to:
```

http://YOUR_PUBLIC_IP/``` 

**Expected result:**
- You should see your CLERK web application login page or home page

If you see this, your Web container is working! ✅

### Test 3: Nginx Health

Open your browser to:
```

http://YOUR_PUBLIC_IP/nginx-health``` 

**Expected result:**
```

healthy``` 

If all three tests pass: 🎉 **YOUR DEPLOYMENT IS SUCCESSFUL!**

---

## Troubleshooting

### If the task fails to start:

1. Go to **ECS** → **Clusters** → **clerk-main** → **Services** → **clerk-combined-service** → **Tasks**
2. Click on the failed task
3. Click **"Logs"** tab
4. Look for error messages

Common issues:
- **EFS mount fails**: Check EFS security group (sg-0643c747711f69285) allows NFS port 2049 from ECS SG (sg-0f52c35c77b8ed90e)
- **Image pull fails**: Verify all 3 images exist in ECR (clerk-api, clerk-web, clerk-nginx) with tag v0.2.0
- **Secrets fail**: Check IAM execution role has secretsmanager:GetSecretValue permission
- **Container unhealthy**: Check CloudWatch logs at /ecs/clerk-combined for specific errors

### If task is RUNNING but you can't access it:

1. **Check Security Group**: 
   - Go to VPC → Security Groups → clerk-ecs-sg (sg-0f52c35c77b8ed90e)
   - Verify inbound rules allow port 80 from 0.0.0.0/0

2. **Check Public IP is assigned**:
   - Task details should show a public IP (not just "Public IP: Enabled")

3. **Use HTTP not HTTPS**:
   - Try `http://` not `https://` (SSL not configured yet)

4. **Wait a bit longer**:
   - Containers need 30-60 seconds to become healthy after task shows RUNNING

### Check CloudWatch Logs:

1. Go to **CloudWatch** → **Log groups** → **/ecs/clerk-combined**
2. You'll see 3 log streams (one per container):
   - `/ecs/clerk-combined/nginx/...`
   - `/ecs/clerk-combined/api/...`
   - `/ecs/clerk-combined/web/...`
3. Click on each to see container logs

---

## 🎉 SUCCESS! What You've Accomplished

If all tests pass, you now have:
- ✅ A running Fargate task with 3 containers (nginx, API, web)
- ✅ Public IP address accessible from anywhere
- ✅ API responding at `/health` and `/api/*`
- ✅ Web application responding at `/`
- ✅ All for ~$6/month!

---

## Next Steps (Optional)

### Phase 7: DNS Setup
Point your domain `clerk.mrrc.online` to the public IP:
1. Log in to IONOS (or your DNS provider)
2. Create an **A record**:
   - Name: `clerk`
   - Type: `A`
   - Value: `YOUR_PUBLIC_IP`
   - TTL: 3600
3. Wait 5-60 minutes for DNS propagation
4. Access your app at: `http://clerk.mrrc.online`

### Phase 8: SSL/HTTPS (Optional)
To add HTTPS with Let's Encrypt:
1. Update nginx container to include certbot
2. Run certbot to get SSL certificate
3. Update nginx config to listen on port 443
4. Update security group to allow port 443

(This is more advanced - let me know if you want detailed instructions)

---

## Cost Reminder

**Your monthly costs:**
- EFS (1 AZ, <1GB): $0.30
- Secrets Manager (2): $0.80
- Fargate (0.5 vCPU, 1GB, 720 hrs): $5.18
- CloudWatch Logs: $0.05
- Data transfer: $0.10
- **Total: ~$6.43/month** 💰

**You're saving $21.57/month (77%) vs ALB deployment!**

---

## Important Notes

**About the Public IP:**
- This IP is semi-permanent (stays the same unless you stop/restart the service)
- If you stop the service and restart it, you'll get a new IP
- For a production app, you'd use an Elastic IP or load balancer
- For your low-volume app, the public IP approach is fine

**Monitoring:**
- Check CloudWatch logs occasionally for errors
- AWS will email you if monthly costs exceed your billing alarms
- Task will automatically restart if it crashes

**Stopping the Service (to save money):**
If you want to temporarily stop paying:
1. Go to ECS → Clusters → clerk-main → Services → clerk-combined-service
2. Click "Update service"
3. Set "Desired tasks" to `0`
4. Click "Update"
5. (To restart, set back to `1`)

---

**Congratulations! Your CLERK app is now live on AWS!** 🚀🎉
```
