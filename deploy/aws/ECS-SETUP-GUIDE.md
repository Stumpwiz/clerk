# CLERK System - ECS Deployment Guide (AWS Console)
**Low-Volume App Configuration** - Optimized for minimal cost  
Last Updated: 2025-10-24

---

## Cost Optimization Notes 🔥
Since this is a low-volume app (1-2 users, few times per month):
- **Fargate Tasks**: 0.25 vCPU / 0.5GB RAM (smallest size)
- **EFS**: Bursting mode (pay per GB stored, ~$0.30/GB/month)
- **ALB**: ~$16/month fixed cost (unavoidable for path-based routing)
- **Estimated Monthly Cost**: $20-30 for light usage

**Alternative to Consider**: If cost is critical, we could use a single container with nginx routing instead of ALB, saving $16/month. But ALB is more robust.

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
- For **cost savings** on a low-volume app, we'll use **only 2 AZs** (not 3+)
- Keep the first **2 rows** (e.g., us-east-1a and us-east-1b)
- For any additional rows (1c, 1d, etc.), click the **X** on the right to remove them

For each remaining row:
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
- Mount targets: 2 AZs with default security group

Click **"Create"**

## Step 1.7: Record EFS ID

After creation, you'll see your file system in the list:
1. Click on **`clerk-efs`** (the name is a blue link)
2. At the top, you'll see **File system ID**: `fs-xxxxxxxxx`
3. **📝 COPY THIS ID** - you'll need it later

**Save to your notes:**
