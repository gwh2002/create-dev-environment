# Client Deployment Workflow Guide

This guide provides a comprehensive workflow for deploying contractor deliverables to your production Google Cloud environment.

## 🔄 **Deployment Workflow Overview**

```
Contractor Deliverable → Your Organization → Production Environment
     (GitHub Repo)         (Copy & Setup)      (Cloud Run Service)
```

### **Workflow Phases:**

1. **📥 Receive Deliverable** - Contractor provides completed repository
2. **🔄 Transfer to Your Org** - Copy repository to your GitHub organization  
3. **🔐 Configure Secrets** - Set up production credentials in Secret Manager
4. **🚀 Deploy to Cloud Run** - Automated deployment using provided scripts
5. **✅ Verify & Monitor** - Test deployment and set up monitoring

---

## 📋 **Phase 1: Receive Deliverable**

### What You'll Receive from Contractor

The contractor will provide a **complete, production-ready repository** containing:

- ✅ **Application Code** - Fully tested risk rating calculator
- ✅ **Dockerfile** - Production-ready container configuration
- ✅ **deploy.sh** - Automated deployment script
- ✅ **requirements.txt** - All dependencies with versions
- ✅ **README.md** - Complete documentation and setup instructions
- ✅ **test_deployment.py** - Verification script (contractor has already run this)

### Contractor Verification Checklist

Before accepting the deliverable, confirm the contractor has completed:

- [ ] All tests pass (`python test_deployment.py` shows 5/5 PASS)
- [ ] Code is well-documented with comments
- [ ] README.md includes any custom features or requirements
- [ ] No sensitive data (service account keys) are committed to the repository
- [ ] Docker build works successfully
- [ ] Application runs in their development environment

---

## 📋 **Phase 2: Transfer to Your Organization**

### Step 2.1: Clone Contractor Repository

```bash
# Clone the contractor's repository
git clone https://github.com/CONTRACTOR_ORG/contractor-project-name.git
cd contractor-project-name

# Verify the deliverable contents
ls -la
# Should see: Dockerfile, deploy.sh, requirements.txt, README.md, test_deployment.py, etc.
```

### Step 2.2: Create Repository in Your Organization

```bash
# Option A: Using GitHub CLI (recommended)
gh repo create YOUR_ORG/risk-rating-calculator \
  --private \
  --description "Risk Rating Calculator - Production Deployment"

# Option B: Create manually via GitHub web interface
# Go to github.com/YOUR_ORG → New Repository → risk-rating-calculator
```

### Step 2.3: Transfer Code to Your Repository

```bash
# Update remote to point to your organization
git remote set-url origin https://github.com/YOUR_ORG/risk-rating-calculator.git

# Push to your organization
git push -u origin main

# Verify the transfer
gh repo view YOUR_ORG/risk-rating-calculator
```

---

## 📋 **Phase 3: Configure Production Secrets**

### Step 3.1: Prepare Your Service Account

Ensure you have a service account with the following roles:
- `BigQuery Admin` (for data access)
- `Cloud Run Admin` (for service deployment)
- `Secret Manager Admin` (for credential storage)
- `Storage Admin` (if using Cloud Storage)

```bash
# Create service account (if needed)
gcloud iam service-accounts create risk-calculator-prod \
  --display-name="Risk Calculator Production Service Account" \
  --project=YOUR_PRODUCTION_PROJECT_ID

# Grant required roles
gcloud projects add-iam-policy-binding YOUR_PRODUCTION_PROJECT_ID \
  --member="serviceAccount:risk-calculator-prod@YOUR_PRODUCTION_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

# Create and download key
gcloud iam service-accounts keys create prod-service-account-key.json \
  --iam-account=risk-calculator-prod@YOUR_PRODUCTION_PROJECT_ID.iam.gserviceaccount.com
```

### Step 3.2: Create Secret Manager Secret

```bash
# Set your production project
export GOOGLE_CLOUD_PROJECT=YOUR_PRODUCTION_PROJECT_ID

# Authenticate with your production project
gcloud auth login
gcloud config set project $GOOGLE_CLOUD_PROJECT

# Create the secret (CRITICAL: must be named exactly this)
gcloud secrets create bellaventure_service_account_json \
  --project=$GOOGLE_CLOUD_PROJECT \
  --data-file=prod-service-account-key.json

# Verify secret creation
gcloud secrets list --project=$GOOGLE_CLOUD_PROJECT
```

### Step 3.3: Verify Secret Access

```bash
# Test that the secret can be accessed
gcloud secrets versions access latest \
  --secret="bellaventure_service_account_json" \
  --project=$GOOGLE_CLOUD_PROJECT
```

---

## 📋 **Phase 4: Deploy to Cloud Run**

### Step 4.1: Pre-Deployment Verification

```bash
# Navigate to your repository
cd risk-rating-calculator

# Verify deployment files exist
ls -la Dockerfile deploy.sh .dockerignore requirements.txt

# Check that deploy.sh is executable
ls -la deploy.sh
# Should show: -rwxr-xr-x (executable permissions)
```

### Step 4.2: Configure Deployment

```bash
# Set environment variables
export GOOGLE_CLOUD_PROJECT=YOUR_PRODUCTION_PROJECT_ID

# Optional: Customize deployment settings by editing deploy.sh
# - SERVICE_NAME (default: "risk-rating-calculator")
# - REGION (default: "us-central1") 
# - Memory/CPU settings
```

### Step 4.3: Execute Deployment

```bash
# Run the automated deployment
./deploy.sh
```

**What the deployment script does:**
1. ✅ Verifies gcloud authentication
2. ✅ Sets the correct project
3. ✅ Enables required APIs (Cloud Build, Cloud Run, Secret Manager)
4. ✅ Verifies Secret Manager secret exists
5. ✅ Builds container image using Cloud Build
6. ✅ Deploys to Cloud Run with proper configuration
7. ✅ Sets environment variables and scaling parameters
8. ✅ Outputs the service URL

### Step 4.4: Deployment Output

Successful deployment will show:
```
🚀 Deploying Risk Rating Calculator to Cloud Run
Project: YOUR_PRODUCTION_PROJECT_ID
Service: risk-rating-calculator
Region: us-central1

📋 Enabling required APIs...
✅ APIs enabled

🔐 Checking Secret Manager configuration...
✅ Secret found: bellaventure_service_account_json

🏗️ Building and deploying to Cloud Run...
✅ Container built successfully
✅ Service deployed successfully

✅ Deployment completed successfully!
🌐 Service URL: https://risk-rating-calculator-xxx-uc.a.run.app

To test the deployment:
curl https://risk-rating-calculator-xxx-uc.a.run.app/health
```

---

## 📋 **Phase 5: Verify & Monitor**

### Step 5.1: Test the Deployment

```bash
# Get the service URL from deployment output
SERVICE_URL="https://risk-rating-calculator-xxx-uc.a.run.app"

# Test health endpoint
curl $SERVICE_URL/health
# Expected response: {"status": "healthy"}

# Test processing endpoint (if applicable)
curl -X POST $SERVICE_URL/process
# Should trigger the risk rating calculation
```

### Step 5.2: Verify BigQuery Integration

```bash
# Check that the service can access your BigQuery data
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=risk-rating-calculator" \
  --project=$GOOGLE_CLOUD_PROJECT \
  --limit=10

# Look for successful BigQuery connections in the logs
```

### Step 5.3: Set Up Monitoring

```bash
# Create uptime check (optional)
gcloud monitoring uptime create \
  --display-name="Risk Calculator Health Check" \
  --http-check-path="/health" \
  --hostname="risk-rating-calculator-xxx-uc.a.run.app"

# Set up log-based alerts (optional)
gcloud logging sinks create risk-calculator-errors \
  bigquery.googleapis.com/projects/$GOOGLE_CLOUD_PROJECT/datasets/logs \
  --log-filter='resource.type="cloud_run_revision" AND severity>=ERROR'
```

---

## 🔧 **Troubleshooting Common Issues**

### Issue: "Secret not found"
```bash
# Verify secret exists
gcloud secrets list --project=$GOOGLE_CLOUD_PROJECT | grep bellaventure

# Check secret name exactly matches
gcloud secrets describe bellaventure_service_account_json --project=$GOOGLE_CLOUD_PROJECT
```

### Issue: "Permission denied" 
```bash
# Check service account permissions
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:risk-calculator-prod@*"

# Verify BigQuery dataset access
bq ls --project_id=$GOOGLE_CLOUD_PROJECT
```

### Issue: "Container failed to start"
```bash
# Check detailed logs
gcloud logs read "resource.type=cloud_run_revision" \
  --project=$GOOGLE_CLOUD_PROJECT \
  --limit=20 \
  --format="table(timestamp,textPayload)"

# Common fixes:
# 1. Verify all dependencies in requirements.txt
# 2. Check that gunicorn is included
# 3. Ensure Flask app is properly configured
```

### Issue: "BigQuery table not found"
```bash
# Verify your production tables exist and match expected names
bq ls $GOOGLE_CLOUD_PROJECT:warehouse

# Check table schemas match contractor's development environment
bq show $GOOGLE_CLOUD_PROJECT:warehouse.ifms
```

---

## 📊 **Post-Deployment Checklist**

### Immediate Verification (Day 1)
- [ ] Health endpoint responds successfully
- [ ] Service can access BigQuery data
- [ ] No error logs in Cloud Run
- [ ] Secret Manager integration working
- [ ] Processing endpoint functions correctly

### Ongoing Monitoring (Weekly)
- [ ] Review Cloud Run metrics for performance
- [ ] Check BigQuery usage and costs
- [ ] Monitor error rates and response times
- [ ] Verify log retention and alerting
- [ ] Review security audit logs

### Maintenance Tasks (Monthly)
- [ ] Update container image with latest dependencies
- [ ] Rotate service account keys
- [ ] Review and optimize resource allocation
- [ ] Update documentation with any changes
- [ ] Test disaster recovery procedures

---

## 💰 **Cost Optimization**

### Cloud Run Optimization
```bash
# Monitor current resource usage
gcloud run services describe risk-rating-calculator \
  --region=us-central1 \
  --project=$GOOGLE_CLOUD_PROJECT

# Adjust resources based on actual usage
gcloud run services update risk-rating-calculator \
  --memory=512Mi \
  --cpu=0.5 \
  --region=us-central1 \
  --project=$GOOGLE_CLOUD_PROJECT
```

### BigQuery Cost Management
- Set up query cost alerts
- Use partitioned tables for large datasets
- Monitor slot usage during peak processing
- Consider BigQuery reservations for predictable workloads

---

## 🔒 **Security Best Practices**

### Access Control
- Use least privilege IAM roles
- Regularly audit service account permissions
- Enable audit logging for all services
- Implement network security policies

### Credential Management
- Rotate service account keys quarterly
- Use Secret Manager for all sensitive data
- Never commit credentials to repositories
- Monitor secret access patterns

### Container Security
- Regularly update base images
- Scan containers for vulnerabilities
- Use non-root users in containers
- Implement resource limits

---

**🎯 Summary**: This workflow transforms the contractor's deliverable into a production-ready service with minimal effort while maintaining security and operational best practices. 