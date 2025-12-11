# Portal Integration Guide

This guide shows how to integrate your portal/application with the Bug Deduplication System.

## Table of Contents
- [Quick Start](#quick-start)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Code Examples](#code-examples)
- [Webhook Integration](#webhook-integration)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

## Quick Start

### 1. Get API Credentials

Contact your system administrator to obtain:
- API Key (for service-to-service integration)
- OR JWT token (for user-based authentication)

### 2. Base URL

```
Production: https://api.example.com
Staging: https://api-staging.example.com
```

### 3. Test Connectivity

```bash
curl https://api.example.com/health
```

Response:
```json
{
  "status": "healthy",
  "service": "bug-deduplication-system"
}
```

## Authentication

### Option 1: API Key (Recommended for Portals)

Include API key in request header:

```http
X-API-Key: bgd_live_abc123...
```

Example:
```bash
curl -X POST https://api.example.com/api/bugs/ \
  -H "X-API-Key: bgd_live_abc123..." \
  -H "Content-Type: application/json" \
  -d @bug.json
```

### Option 2: JWT Token

1. Get token:
```bash
curl -X POST https://api.example.com/api/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password123"
  }'
```

Response:
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

2. Use token:
```bash
curl -X POST https://api.example.com/api/bugs/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..." \
  -H "Content-Type: application/json" \
  -d @bug.json
```

## API Endpoints

### Submit Bug Report

**POST /api/bugs/**

Submit a new bug for duplicate detection and quality validation.

**Request Headers:**
```http
Content-Type: application/json
X-API-Key: bgd_live_abc123...
X-Environment: production
X-Client-Version: 1.0.0
```

**Request Body:**
```json
{
  "title": "Login button not responding on mobile",
  "description": "When user clicks login button on iOS Safari 16.1, nothing happens. Expected behavior: user should be redirected to dashboard after successful login.",
  "product": "Mobile App",
  "component": "Authentication",
  "version": "2.1.0",
  "severity": "major",
  "environment": "production",
  "reporter_email": "qa-team@example.com",
  "steps_to_reproduce": [
    "Open mobile app on iOS device",
    "Navigate to login page",
    "Enter valid credentials",
    "Click 'Login' button",
    "Observe: Button does not respond"
  ],
  "expected_result": "User is authenticated and redirected to dashboard",
  "actual_result": "Button click has no effect, user remains on login page",
  "attachments": [
    "screenshot_login_page.png",
    "console_logs.txt"
  ],
  "tags": ["mobile", "ios", "authentication", "regression"]
}
```

**Success Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Login button not responding on mobile",
  "status": "approved",
  "quality_score": 0.92,
  "is_duplicate": false,
  "similarity_score": null,
  "duplicate_of_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "is_automated_submission": false
}
```

**Duplicate Blocked Response (409):**
```json
{
  "error": {
    "code": "DUPLICATE_RESOURCE",
    "message": "This bug is a duplicate of an existing issue",
    "details": {
      "is_duplicate": true,
      "original_bug": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "title": "Login button unresponsive on iOS Safari",
        "jira_key": "BUGS-1234"
      },
      "similarity_score": 0.92,
      "reason": "Similarity score above blocking threshold (85%)"
    }
  },
  "status": 409,
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_abc123"
}
```

**Low Quality Response (400):**
```json
{
  "message": "Bug submission has quality issues and requires QA review",
  "quality_score": 0.45,
  "issues": [
    "Description too short (minimum 20 characters)",
    "Missing reproduction steps",
    "Missing expected vs actual results"
  ],
  "bug_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "low_quality"
}
```

### Get Bug Details

**GET /api/bugs/{bug_id}**

```bash
curl -X GET https://api.example.com/api/bugs/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: bgd_live_abc123..."
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Login button not responding on mobile",
  "description": "...",
  "product": "Mobile App",
  "component": "Authentication",
  "version": "2.1.0",
  "severity": "major",
  "environment": "production",
  "status": "approved",
  "quality_score": 0.92,
  "is_duplicate": false,
  "jira_key": "BUGS-1234",
  "tp_defect_id": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Search Bugs

**GET /api/bugs/search**

```bash
curl -X GET "https://api.example.com/api/bugs/search?q=login&product=Mobile%20App&status=approved&limit=10" \
  -H "X-API-Key: bgd_live_abc123..."
```

**Response:**
```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Login button not responding on mobile",
      "product": "Mobile App",
      "status": "approved",
      "severity": "major",
      "is_duplicate": false,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Get Statistics

**GET /api/monitoring/stats**

```bash
curl -X GET https://api.example.com/api/monitoring/stats \
  -H "X-API-Key: bgd_live_abc123..."
```

**Response:**
```json
{
  "total_bugs": 1523,
  "duplicates_detected": 234,
  "duplicates_blocked": 156,
  "low_quality_bugs": 89,
  "avg_quality_score": 0.82,
  "avg_similarity_score": 0.73,
  "bugs_by_status": {
    "approved": 1200,
    "pending_review": 45,
    "rejected": 12,
    "duplicate": 234
  },
  "bugs_by_severity": {
    "critical": 23,
    "major": 456,
    "minor": 789,
    "trivial": 255
  }
}
```

## Code Examples

### Python

```python
import requests
from typing import Dict, Any, Optional

class BugDeduplicationClient:
    """Client for Bug Deduplication System API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'Content-Type': 'application/json',
            'X-Client-Version': '1.0.0'
        })
    
    def submit_bug(self, bug_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a bug for duplicate detection.
        
        Args:
            bug_data: Bug information
            
        Returns:
            API response
            
        Raises:
            requests.HTTPError: If request fails
        """
        response = self.session.post(
            f'{self.base_url}/api/bugs/',
            json=bug_data,
            timeout=30
        )
        
        if response.status_code == 201:
            # Success - bug created
            return response.json()
        elif response.status_code == 409:
            # Duplicate detected and blocked
            error = response.json()
            print(f"Duplicate detected: {error['error']['details']}")
            raise DuplicateBugError(error)
        elif response.status_code == 400:
            # Low quality
            error = response.json()
            print(f"Low quality: {error['issues']}")
            raise LowQualityBugError(error)
        else:
            response.raise_for_status()
    
    def get_bug(self, bug_id: str) -> Dict[str, Any]:
        """Get bug details by ID"""
        response = self.session.get(
            f'{self.base_url}/api/bugs/{bug_id}',
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    def search_bugs(
        self,
        query: Optional[str] = None,
        product: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Search bugs"""
        params = {'limit': limit}
        if query:
            params['q'] = query
        if product:
            params['product'] = product
        if status:
            params['status'] = status
        
        response = self.session.get(
            f'{self.base_url}/api/bugs/search',
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()


class DuplicateBugError(Exception):
    """Raised when duplicate bug is detected"""
    pass


class LowQualityBugError(Exception):
    """Raised when bug quality is too low"""
    pass


# Usage
client = BugDeduplicationClient(
    base_url='https://api.example.com',
    api_key='bgd_live_abc123...'
)

try:
    result = client.submit_bug({
        'title': 'Login button not responding',
        'description': 'Detailed description...',
        'product': 'Mobile App',
        'severity': 'major'
    })
    print(f"Bug created: {result['id']}")
except DuplicateBugError as e:
    print(f"Duplicate detected: {e}")
except LowQualityBugError as e:
    print(f"Quality issues: {e}")
```

### JavaScript/TypeScript

```typescript
interface BugSubmission {
  title: string;
  description: string;
  product: string;
  component?: string;
  version?: string;
  severity?: 'critical' | 'major' | 'minor' | 'trivial';
  environment?: 'production' | 'staging' | 'development' | 'qa';
  reporter_email?: string;
  steps_to_reproduce?: string[];
  expected_result?: string;
  actual_result?: string;
  attachments?: string[];
  tags?: string[];
}

interface BugResponse {
  id: string;
  title: string;
  status: string;
  quality_score: number;
  is_duplicate: boolean;
  similarity_score?: number;
  duplicate_of_id?: string;
  created_at: string;
}

class BugDeduplicationClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(baseUrl: string, apiKey: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
  }

  async submitBug(bug: BugSubmission): Promise<BugResponse> {
    const response = await fetch(`${this.baseUrl}/api/bugs/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': this.apiKey,
        'X-Client-Version': '1.0.0',
      },
      body: JSON.stringify(bug),
    });

    if (!response.ok) {
      const error = await response.json();
      
      if (response.status === 409) {
        throw new DuplicateBugError(
          error.error.message,
          error.error.details
        );
      } else if (response.status === 400) {
        throw new LowQualityBugError(
          error.message,
          error.issues
        );
      }
      
      throw new Error(`API Error: ${error.error?.message || response.statusText}`);
    }

    return response.json();
  }

  async getBug(bugId: string): Promise<BugResponse> {
    const response = await fetch(`${this.baseUrl}/api/bugs/${bugId}`, {
      headers: {
        'X-API-Key': this.apiKey,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to get bug: ${response.statusText}`);
    }

    return response.json();
  }
}

class DuplicateBugError extends Error {
  constructor(message: string, public details: any) {
    super(message);
    this.name = 'DuplicateBugError';
  }
}

class LowQualityBugError extends Error {
  constructor(message: string, public issues: string[]) {
    super(message);
    this.name = 'LowQualityBugError';
  }
}

// Usage
const client = new BugDeduplicationClient(
  'https://api.example.com',
  'bgd_live_abc123...'
);

try {
  const result = await client.submitBug({
    title: 'Login button not responding',
    description: 'Detailed description...',
    product: 'Mobile App',
    severity: 'major',
  });
  
  console.log(`Bug created: ${result.id}`);
} catch (error) {
  if (error instanceof DuplicateBugError) {
    console.log('Duplicate detected:', error.details);
  } else if (error instanceof LowQualityBugError) {
    console.log('Quality issues:', error.issues);
  } else {
    console.error('Error:', error);
  }
}
```

## Webhook Integration

### Configure Webhook URL

Provide your webhook endpoint to receive notifications:

```
https://your-portal.com/api/webhooks/bug-deduplication
```

### Webhook Payload

```json
{
  "event": "duplicate.detected",
  "timestamp": "2024-01-15T10:30:00Z",
  "bug": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Login button not responding on mobile",
    "product": "Mobile App",
    "severity": "major",
    "status": "flagged_duplicate",
    "quality_score": 0.92,
    "is_duplicate": true,
    "jira_key": null,
    "created_at": "2024-01-15T10:30:00Z"
  },
  "duplicate_of": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "title": "Login button unresponsive on iOS Safari",
    "jira_key": "BUGS-1234"
  },
  "similarity_score": 0.87,
  "action_taken": "flagged"
}
```

### Verify Webhook Signature

```python
import hmac
import hashlib
import json

def verify_webhook_signature(payload: dict, signature: str, secret: str) -> bool:
    """Verify webhook signature"""
    message = json.dumps(payload, sort_keys=True).encode()
    expected_signature = hmac.new(
        secret.encode(),
        message,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(
        signature.split('=')[1],  # Remove 'sha256=' prefix
        expected_signature
    )


# In your webhook handler
@app.route('/api/webhooks/bug-deduplication', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.json
    
    if not verify_webhook_signature(payload, signature, WEBHOOK_SECRET):
        return {'error': 'Invalid signature'}, 401
    
    # Process event
    event_type = payload['event']
    if event_type == 'duplicate.detected':
        handle_duplicate_detected(payload)
    elif event_type == 'duplicate.blocked':
        handle_duplicate_blocked(payload)
    
    return {'status': 'ok'}, 200
```

## Error Handling

### HTTP Status Codes

- `200 OK` - Request successful
- `201 Created` - Bug created successfully
- `400 Bad Request` - Low quality or validation error
- `401 Unauthorized` - Invalid or missing authentication
- `403 Forbidden` - Insufficient permissions
- `409 Conflict` - Duplicate bug blocked
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Rate Limits

- **Bug Submission**: 100 requests/hour
- **Read Operations**: 1000 requests/hour
- **Search**: 200 requests/hour

Rate limit headers:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1610712000
```

### Retry Strategy

```python
import time
from requests.exceptions import RequestException

def submit_with_retry(client, bug_data, max_retries=3):
    """Submit bug with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return client.submit_bug(bug_data)
        except RequestException as e:
            if e.response and e.response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(e.response.headers.get('Retry-After', 60))
                time.sleep(retry_after)
            elif attempt == max_retries - 1:
                raise
            else:
                # Exponential backoff
                time.sleep(2 ** attempt)
```

## Best Practices

### 1. Provide Complete Information

Always include:
- Clear, descriptive title
- Detailed description (min 20 characters)
- Steps to reproduce
- Expected vs actual results
- Environment details

### 2. Set Environment Context

Include environment headers:
```http
X-Environment: production
X-Client-Version: 1.0.0
```

### 3. Handle All Response Types

Account for:
- Success (201)
- Duplicate (409)
- Low quality (400)
- Rate limiting (429)

### 4. Implement Retries

Use exponential backoff for transient errors.

### 5. Monitor Integration

Track:
- Submission success rate
- Duplicate detection rate
- Quality scores
- API response times

### 6. Cache API Keys

Don't fetch API keys on every request.

### 7. Log Request IDs

Include `request_id` from error responses in support tickets.

---

**Need Help?**
- API Documentation: https://api.example.com/api/docs
- Support: support@example.com
- GitHub Issues: https://github.com/zaidku/ai-bug-deduplication/issues
