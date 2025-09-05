# Gemini GCP Auto-Configuration for YMERA Platform

## EXECUTE THESE COMMANDS IN GOOGLE CLOUD SHELL

**Goal**: Fix all YMERA platform errors by auto-configuring GCP services

### Step 1: Project Setup
```bash
export PROJECT_ID="ymera-467423"
export REGION="us-central1"

# Configure existing project
gcloud config set project $PROJECT_ID

# Enable required APIs (if not already enabled)
gcloud services enable sqladmin.googleapis.com storage.googleapis.com secretmanager.googleapis.com iam.googleapis.com run.googleapis.com monitoring.googleapis.com logging.googleapis.com pubsub.googleapis.com firestore.googleapis.com
```

### Step 2: Fix Database Issues
```bash
# Create PostgreSQL instance
gcloud sql instances create ymera-db --database-version=POSTGRES_15 --tier=db-f1-micro --region=$REGION --authorized-networks=0.0.0.0/0 --assign-ip

# Set password and create database
gcloud sql users set-password postgres --instance=ymera-db --password="YmeraDB2025!"
gcloud sql databases create ymera_platform --instance=ymera-db
gcloud sql users create app_user --instance=ymera-db --password="AppUser2025!"

# Get connection string
export DB_IP=$(gcloud sql instances describe ymera-db --format="value(ipAddresses.ipAddress)")
export DB_URL="postgresql://app_user:AppUser2025!@$DB_IP:5432/ymera_platform"
```

### Step 3: Storage & Service Account
```bash
# Create storage buckets
gsutil mb gs://ymera-467423-storage
gsutil mb gs://ymera-467423-backups

# Create service account with all permissions
gcloud iam service-accounts create ymera-service
export SA_EMAIL="ymera-service@ymera-467423.iam.gserviceaccount.com"

# Add required roles
gcloud projects add-iam-policy-binding ymera-467423 --member="serviceAccount:$SA_EMAIL" --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding ymera-467423 --member="serviceAccount:$SA_EMAIL" --role="roles/storage.admin"
gcloud projects add-iam-policy-binding ymera-467423 --member="serviceAccount:$SA_EMAIL" --role="roles/secretmanager.secretAccessor"

# Generate service account key
gcloud iam service-accounts keys create sa-key.json --iam-account=$SA_EMAIL
```

### Step 4: Create Secrets
```bash
# Store database connection
echo $DB_URL | gcloud secrets create db-connection-string --data-file=-

# Store service account key
gcloud secrets create service-account-key --data-file=sa-key.json

# Create API key
echo "ymera-api-key-$(openssl rand -hex 16)" | gcloud secrets create api-key --data-file=-
```

### Step 5: Output Configuration
```bash
echo "=== REPLIT ENVIRONMENT VARIABLES ==="
echo "GCP_PROJECT_ID=ymera-467423"
echo "DATABASE_URL=$DB_URL"
echo "DB_HOST=$DB_IP"
echo "GCS_BUCKET=ymera-467423-storage"
echo "SERVICE_ACCOUNT_EMAIL=$SA_EMAIL"
echo ""
echo "✅ All services configured - Copy these to Replit Secrets"
```

## CRITICAL: Copy the output environment variables to your Replit project secrets to fix all platform errors.