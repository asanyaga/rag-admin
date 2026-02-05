#!/bin/bash
# Test script to verify backend authorization

echo "Testing backend authorization..."
echo ""

# Create user 1
echo "1. Creating User 1..."
USER1_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user1@test.com",
    "password": "TestPassword123!",
    "full_name": "User One"
  }')

USER1_TOKEN=$(echo $USER1_RESPONSE | jq -r '.access_token')
echo "User 1 token: ${USER1_TOKEN:0:20}..."

# Get User 1's projects
echo ""
echo "2. Getting User 1's projects..."
USER1_PROJECTS=$(curl -s -X GET http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $USER1_TOKEN")
echo "User 1 projects:"
echo $USER1_PROJECTS | jq '.[] | {id: .id, name: .name}'

# Create user 2
echo ""
echo "3. Creating User 2..."
USER2_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user2@test.com",
    "password": "TestPassword123!",
    "full_name": "User Two"
  }')

USER2_TOKEN=$(echo $USER2_RESPONSE | jq -r '.access_token')
echo "User 2 token: ${USER2_TOKEN:0:20}..."

# Get User 2's projects with User 2's token
echo ""
echo "4. Getting User 2's projects with User 2's token..."
USER2_PROJECTS=$(curl -s -X GET http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $USER2_TOKEN")
echo "User 2 projects:"
echo $USER2_PROJECTS | jq '.[] | {id: .id, name: .name}'

# Try to get User 1's projects with User 2's token (should fail/be empty)
echo ""
echo "5. Getting projects with User 2's token (should NOT include User 1's projects)..."
CROSS_CHECK=$(curl -s -X GET http://localhost:8000/api/v1/projects \
  -H "Authorization: Bearer $USER2_TOKEN")
echo "Projects visible to User 2:"
echo $CROSS_CHECK | jq '.[] | {id: .id, name: .name}'

# Try to access User 1's specific project with User 2's token
USER1_PROJECT_ID=$(echo $USER1_PROJECTS | jq -r '.[0].id')
echo ""
echo "6. Trying to access User 1's project ($USER1_PROJECT_ID) with User 2's token..."
UNAUTHORIZED_ACCESS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET \
  "http://localhost:8000/api/v1/projects/$USER1_PROJECT_ID" \
  -H "Authorization: Bearer $USER2_TOKEN")
echo "Response:"
echo $UNAUTHORIZED_ACCESS

