``` markdown
# CLERK System - Budget ECS Deployment (No ALB)
**Ultra Low-Cost Configuration** - For low-volume apps  
Last Updated: 2025-10-24

---

## 💰 Cost Comparison
| Component | With ALB (Standard) | Without ALB (Budget) |
|-----------|---------------------|----------------------|
| ALB | $16/month | $0 (eliminated) |
| Fargate (2 services) | ~$10/month | ~$5/month (1 service) |
| EFS | $0.30/month | $0.30/month |
| Secrets Manager | $0.80/month | $0.80/month |
| CloudWatch | <$1/month | <$1/month |
| **TOTAL** | **~$28/month** | **~$7/month** |

**Savings: ~$21/month (75% reduction!)**

---

## Architecture Changes

**Standard (with ALB):**
```

Internet → ALB → ECS Service (API) → Container ↓ → ECS Service (Web) → Container``` 

**Budget (no ALB):**
```

Internet → ECS Service →    →    →   latex_unknown_taglatex_unknown_taglatex_unknown_tag``` 

All 3 containers run in a **single Fargate task** with nginx routing traffic internally.

---

## Trade-offs

✅ **Pros:**
- **75% cost reduction** ($7/month vs $28/month)
- Simpler architecture (fewer moving parts)
- Faster for low traffic (no ALB hop)

❌ **Cons:**
- **No auto-scaling** (fine for 1-2 users)
- **Single point of failure** (task restart = 30-60 sec downtime)
- **Manual SSL certificate management** (Let's Encrypt with certbot)
- No advanced features (WAF, sticky sessions, etc.)

**For a retirement community secretary app with 1-2 users/month: These trade-offs are acceptable.**

---

## Prerequisites Checklist
Before starting, ensure you have:
- ✅ AWS Console access as Administrator
- ✅ Region set to **us-east-1** (N. Virginia)
- ✅ ECR images pushed: `clerk-api:v0.1.9` and `clerk-web:v0.1.9`
- ✅ Clerk API keys ready (publishable key and secret key)
- ✅ A text editor to record ARNs/IDs as we create resources

---

# PHASE 1: CREATE EFS (Elastic File System)
**Purpose**: Persistent storage for API database and uploaded files  
**Cost**: ~$0.30/GB/month (you'll likely use <1GB = ~$0.30/month)

## Step 1.1: Navigate to EFS

1. Sign in to AWS Console: https://console.aws.amazon.com/
2. Ensure top-right shows **N. Virginia** (us-east-1)
3. In the search bar at top, type **`EFS`**
4. Click **"EFS"** under Services

## Step 1.2: Create File System

1. Click the orange **"Create file system"** button
2. You'll see two options: **Quick create** or **Customize**
3. Click **"Customize"** (we need to configure settings)

## Step 1.3: File System Settings (Page 1)

**General Settings:**
- **Name**: `clerk-efs`
- **Automatic backups**: ✅ **Disable** (to save cost - you can backup manually)
- **Lifecycle management**: Leave as default (Transition into IA: 30 days since last access)
- **Performance mode**: ⚪ **General Purpose** (default)
- **Throughput mode**: ⚪ **Bursting** (perfect for low volume)
- **Encryption**: ✅ **Enable encryption** (use default aws/efs key)

Click **"Next"** at bottom-right

## Step 1.4: Network Access (Page 2)

**VPC Selection:**
- **Virtual Private Cloud (VPC)**: Select your **default VPC** 
  - Should look like `vpc-xxxxxx (default)`
  - If you have multiple, choose the one marked "(default)"

**Mount Targets:**
- You'll see a table with **Availability Zones**
- For **cost savings** on a low-volume app, we'll use **only 1 AZ** (cheapest)
- Keep only the **first row** (e.g., us-east-1a)
- For any additional rows (1b, 1c, etc.), click the **X** on the right to remove them

For the remaining row:
- **Subnet ID**: Leave as default (auto-selected)
- **Security groups**: We'll create a custom one next, but for now **leave the default**
  - ⚠️ **Note**: We'll come back and change this after creating our EFS security group

Click **"Next"**

## Step 1.5: File System Policy (Page 3)

- Leave this **blank** (no custom policy needed)
- Click **"Next"**

## Step 1.6: Review and Create (Page 4)

Review your settings:
- Name: `clerk-efs`
- Throughput mode: Bursting
- Encryption: Enabled
- Mount targets: 1 AZ with default security group

Click **"Create"**

## Step 1.7: Record EFS ID

After creation, you'll see your file system in the list:
1. Click on **`clerk-efs`** (the name is a blue link)
2. At the top, you'll see **File system ID**: `fs-xxxxxxxxx`
3. **📝 COPY THIS ID** - you'll need it later

**Save to your notes:**
```

EFS_FILESYSTEM_ID=fs-xxxxxxxxx``` 

✅ **EFS Created!** We'll configure the security group in the next phase.

---

# PHASE 2: CREATE SECURITY GROUPS
**Purpose**: Firewall rules controlling traffic  
**Cost**: Free

We only need **2 security groups** (vs 3 with ALB):
1. **ECS Security Group** - Allows internet traffic to nginx proxy (80, 443)
2. **EFS Security Group** - Allows ECS to reach EFS (port 2049)

## Step 2.1: Navigate to Security Groups

1. In AWS Console search bar, type **`VPC`**
2. Click **"VPC"** under Services
3. In the left sidebar, scroll down and click **"Security Groups"**
4. You'll see a list of existing security groups (probably just "default")

## Step 2.2: Create ECS Security Group

1. Click **"Create security group"** (orange button, top-right)

**Basic details:**
- **Security group name**: `clerk-ecs-sg`
- **Description**: `Allow HTTP/HTTPS traffic to ECS containers`
- **VPC**: Select your **default VPC**

**Inbound rules:**
Click **"Add rule"** twice to create 2 rules:

| Type  | Protocol | Port Range | Source    | Description          |
|-------|----------|------------|-----------|----------------------|
| HTTP  | TCP      | 80         | 0.0.0.0/0 | Allow HTTP from internet |
| HTTPS | TCP      | 443        | 0.0.0.0/0 | Allow HTTPS from internet |

**Outbound rules:**
- Leave the default (All traffic to 0.0.0.0/0)

**Tags:** (optional but helpful)
- Key: `Name`, Value: `clerk-ecs-sg`

Click **"Create security group"**

**📝 Record Security Group ID:**
After creation, you'll see **Security group ID**: `sg-xxxxxxxxxxx`
```

ECS_SECURITY_GROUP_ID=sg-xxxxxxxxxxx``` 

## Step 2.3: Create EFS Security Group

1. Click **"Create security group"** again

**Basic details:**
- **Security group name**: `clerk-efs-sg`
- **Description**: `Allow NFS traffic from ECS containers to EFS`
- **VPC**: Select your **default VPC**

**Inbound rules:**
Click **"Add rule"**:

| Type | Protocol | Port Range | Source                                    | Description          |
|------|----------|------------|-------------------------------------------|----------------------|
| NFS  | TCP      | 2049       | Custom: `sg-xxxxxxxxxxx` (clerk-ecs-sg)  | ECS to EFS mount |

**For the Source column:**
- Start typing `sg-` and select your **clerk-ecs-sg** from the dropdown
- Or paste the ECS_SECURITY_GROUP_ID you recorded above

**Outbound rules:**
- Leave default

**Tags:**
- Key: `Name`, Value: `clerk-efs-sg`

Click **"Create security group"**

**📝 Record Security Group ID:**
```

EFS_SECURITY_GROUP_ID=sg-yyyyyyyyyyy``` 

## Step 2.4: Update EFS Mount Target to Use New Security Group

Now we need to update EFS to use our new `clerk-efs-sg`:

1. Go back to **EFS** (search for EFS in top search bar)
2. Click on **`clerk-efs`**
3. Click the **"Network"** tab
4. You'll see your mount target (1 row for 1 AZ)
5. Click **"Manage"** button
6. In the **Security groups** column, **remove** the default security group
7. **Add** your `clerk-efs-sg` (sg-yyyyyyyyyyy)
8. Click **"Save"**

✅ **Security Groups Complete!**

---

# PHASE 3: CREATE CLOUDWATCH LOG GROUPS
**Purpose**: Store container logs for debugging  
**Cost**: ~$0.50/GB ingested + $0.03/GB stored (you'll likely use <100MB/month = pennies)

## Step 3.1: Navigate to CloudWatch

1. In search bar, type **`CloudWatch`**
2. Click **"CloudWatch"**
3. In left sidebar, under **Logs**, click **"Log groups"**

## Step 3.2: Create Combined Log Group

Since all containers run in one task, we'll use one log group:

1. Click **"Create log group"** (top-right)
2. **Log group name**: `/ecs/clerk-combined`
3. **Retention setting**: Select **1 week** (to minimize costs)
4. Leave **KMS key ARN** blank
5. Click **"Create"**

✅ **CloudWatch Log Group Created!**

---

# PHASE 4: CREATE SECRETS IN SECRETS MANAGER
**Purpose**: Securely store Clerk API keys  
**Cost**: $0.40/secret/month = $0.80/month for 2 secrets

## Step 4.1: Navigate to Secrets Manager

1. In search bar, type **`Secrets Manager`**
2. Click **"AWS Secrets Manager"**
3. Click **"Store a new secret"** (orange button)

## Step 4.2: Create Clerk Publishable Key Secret

**Step 1: Secret type**
- **Secret type**: ⚪ **Other type of secret**
- **Key/value pairs**: 
  - Click **"Plaintext"** tab
  - Delete everything in the box
  - Paste your Clerk publishable key (starts with `pk_test_` or `pk_live_`)
- **Encryption key**: Leave as **aws/secretsmanager**
- Click **"Next"**

**Step 2: Secret name and description**
- **Secret name**: `clerk/publishable-key`
- **Description**: `Clerk publishable key for authentication`
- Click **"Next"**

**Step 3: Configure rotation**
- **Automatic rotation**: ❌ **Disable**
- Click **"Next"**

**Step 4: Review**
- Click **"Store"**

**📝 Record Secret ARN:**
After creation, click on `clerk/publishable-key`, you'll see:
```

SECRET_ARN_CLERK_PUBLISHABLE_KEY=arn:aws:secretsmanager:us-east-1:365591166807:secret:clerk/publishable-key-xxxxxx``` 

## Step 4.3: Create Clerk Secret Key Secret

1. Go back to Secrets Manager main page
2. Click **"Store a new secret"**
3. Follow the same steps as above, but:
   - **Plaintext value**: Your Clerk secret key (starts with `sk_test_` or `sk_live_`)
   - **Secret name**: `clerk/secret-key`
   - **Description**: `Clerk secret key for API authentication`

**📝 Record Secret ARN:**
```

SECRET_ARN_CLERK_SECRET_KEY=arn:aws:secretsmanager:us-east-1:365591166807:secret:clerk/secret-key-xxxxxx``` 

✅ **Secrets Created!**

---

# PHASE 5: CREATE IAM ROLES FOR ECS
**Purpose**: Give ECS permission to pull images, write logs, and access secrets  
**Cost**: Free

We need 2 IAM roles:
1. **ECS Execution Role** - Used by ECS service to pull images and access secrets
2. **ECS Task Role** - Used by your containers to access AWS services (if needed)

## Step 5.1: Navigate to IAM

1. Search for **`IAM`**
2. Click **"IAM"**
3. In left sidebar, click **"Roles"**

## Step 5.2: Create ECS Execution Role

1. Click **"Create role"** (orange button)

**Step 1: Select trusted entity**
- **Trusted entity type**: ⚪ **AWS service**
- **Use case**: Find and select **"Elastic Container Service"**
- Then select **"Elastic Container Service Task"**
- Click **"Next"**

**Step 2: Add permissions**
Search for and select:
- ✅ `AmazonECSTaskExecutionRolePolicy`
- Click **"Next"**

**Step 3: Name, review, and create**
- **Role name**: `clerk-ecs-execution-role`
- **Description**: `Execution role for CLERK ECS tasks`
- Click **"Create role"**

**Step 3b: Add Secrets Manager Permission**
1. After creation, click on **`clerk-ecs-execution-role`**
2. Click **"Add permissions"** → **"Create inline policy"**
3. Click the **"JSON"** tab
4. Replace everything with:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:365591166807:secret:clerk/*"
      ]
    }
  ]
}
```
```

Click "Next"
Policy name: SecretsManagerReadClerk
Click "Create policy"
📝 Record Role ARN: Go back to the role details, at the top you'll see:``` 
ECS_EXECUTION_ROLE_ARN=arn:aws:iam::365591166807:role/clerk-ecs-execution-role
```

Step 5.3: Create ECS Task Role
Click "Create role" again
Trusted entity: ⚪ AWS service → Elastic Container Service → Elastic Container Service Task
Click "Next"
Don't add any policies yet
Click "Next"
Role name: clerk-ecs-task-role
Description: Task role for CLERK containers
Click "Create role"
📝 Record Role ARN:``` 
ECS_TASK_ROLE_ARN=arn:aws:iam::365591166807:role/clerk-ecs-task-role
```

✅ IAM Roles Created!
 
🎉 PHASE 1-5 COMPLETE!
You've now created all prerequisites:
✅ EFS for persistent storage (1 AZ)
✅ Security Groups (ECS, EFS - no ALB needed!)
✅ CloudWatch Log Group
✅ Secrets Manager for Clerk keys
✅ IAM Roles for ECS
What's NOT needed (vs ALB approach):
❌ Application Load Balancer ($16/month saved!)
❌ Target Groups
❌ ALB Security Group
 
Your Resource IDs Checklist:``` 
EFS_FILESYSTEM_ID=fs-xxxxxxxxx
ECS_SECURITY_GROUP_ID=sg-xxxxxxxxxxx
EFS_SECURITY_GROUP_ID=sg-yyyyyyyyyyy
SECRET_ARN_CLERK_PUBLISHABLE_KEY=arn:aws:secretsmanager:us-east-1:365591166807:secret:clerk/publishable-key-xxxxxx
SECRET_ARN_CLERK_SECRET_KEY=arn:aws:secretsmanager:us-east-1:365591166807:secret:clerk/secret-key-xxxxxx
ECS_EXECUTION_ROLE_ARN=arn:aws:iam::365591166807:role/clerk-ecs-execution-role
ECS_TASK_ROLE_ARN=arn:aws:iam::365591166807:role/clerk-ecs-task-role
```

 
NEXT: Phase 6 - Deploy ECS Cluster & Multi-Container Service
Before we continue, we need to:
Build and push the nginx proxy image to ECR
Create the ECS cluster
Register the task definition (3 containers in 1 task)
Create the ECS service with public IP
Ready for Phase 6? Let me know when you've completed Phase 1-5 and recorded your ARNs!
 
Estimated Monthly Cost Breakdown:
EFS (Bursting, <1GB, 1 AZ): $0.30
Secrets Manager (2 secrets): $0.80
Fargate (0.5 vCPU, 1GB, ~720 hrs): $5.18
CloudWatch Logs (<100MB): $0.05
TOTAL: ~$6.33/month 🎉
Compare to ALB approach: 28/month - you're saving **21.67/month (77% reduction)**!
 
Notes
Why 1 AZ instead of 2?
ALB requires 2+ AZs for high availability
Without ALB, we can use 1 AZ to save on data transfer costs
For a low-volume app, the minor availability trade-off is acceptable
About the public IP:
The ECS service will get a public IP address (free)
You'll point your DNS (clerk.mrrc.online) directly to this IP
No ALB = no fancy load balancer DNS name, just a simple IP
SSL/HTTPS:
We'll set up Let's Encrypt certificates inside the nginx container
This requires a bit more setup than ALB (which handles SSL automatically)
But it's free and works great for low-volume apps