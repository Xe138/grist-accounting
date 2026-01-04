#!/bin/bash
# upload-attachment.sh - Upload file and link to Grist record
# Usage: ./upload-attachment.sh <file> <table> <record_id> [token]
#
# Examples:
#   ./upload-attachment.sh invoice.pdf Bills 13
#   ./upload-attachment.sh receipt.jpg Bills 13 sess_abc123...

set -e

FILE="$1"
TABLE="$2"
RECORD_ID="$3"
TOKEN="$4"

if [[ -z "$FILE" || -z "$TABLE" || -z "$RECORD_ID" ]]; then
    echo "Usage: $0 <file> <table> <record_id> [token]"
    echo ""
    echo "Arguments:"
    echo "  file       Path to file to upload"
    echo "  table      Grist table name (e.g., Bills)"
    echo "  record_id  Record ID to attach file to"
    echo "  token      Session token (optional, will prompt if not provided)"
    echo ""
    echo "Example: $0 invoice.pdf Bills 13"
    exit 1
fi

# Get token if not provided
if [[ -z "$TOKEN" ]]; then
    echo "Paste session token (from request_session_token MCP call):"
    read -r TOKEN
fi

# Base URL for the grist-mcp proxy
BASE_URL="${GRIST_MCP_URL:-https://grist-mcp.bballou.com}"

# Upload attachment
echo "Uploading $FILE..."
RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$FILE" \
    "$BASE_URL/api/v1/attachments")

# Extract attachment ID
ATTACHMENT_ID=$(echo "$RESPONSE" | jq -r '.data.attachment_id')

if [[ "$ATTACHMENT_ID" == "null" || -z "$ATTACHMENT_ID" ]]; then
    echo "Upload failed: $RESPONSE"
    exit 1
fi

echo "Uploaded: attachment_id=$ATTACHMENT_ID"

# Link to record via proxy
echo "Linking to $TABLE id=$RECORD_ID..."
LINK_RESPONSE=$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"method\": \"update_records\", \"table\": \"$TABLE\", \"records\": [{\"id\": $RECORD_ID, \"fields\": {\"Attachment\": [\"L\", $ATTACHMENT_ID]}}]}" \
    "$BASE_URL/api/v1/proxy")

echo "$LINK_RESPONSE" | jq .
echo "Done! Attachment $ATTACHMENT_ID linked to $TABLE record $RECORD_ID"
