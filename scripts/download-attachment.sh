#!/bin/bash
# download-attachment.sh - Download attachment from Grist via MCP proxy
# Usage: ./download-attachment.sh <attachment_id> <output_file> [token]
#
# Examples:
#   ./download-attachment.sh 11 invoice.pdf                    # prompts for token
#   ./download-attachment.sh 11 invoice.pdf sess_abc123...     # with token

set -e

ATTACHMENT_ID="$1"
OUTPUT_FILE="$2"
TOKEN="$3"

if [[ -z "$ATTACHMENT_ID" || -z "$OUTPUT_FILE" ]]; then
    echo "Usage: $0 <attachment_id> <output_file> [token]"
    echo ""
    echo "Arguments:"
    echo "  attachment_id   ID of the attachment to download"
    echo "  output_file     Path to save the downloaded file"
    echo "  token           Session token (optional, will prompt if not provided)"
    echo ""
    echo "Examples:"
    echo "  $0 11 invoice.pdf                    # Download attachment 11"
    echo "  $0 11 invoice.pdf \$TOKEN            # With pre-obtained token"
    echo ""
    echo "To get attachment IDs, query the Bills table:"
    echo "  SELECT id, BillNumber, Invoice FROM Bills"
    exit 1
fi

# Get token if not provided
if [[ -z "$TOKEN" ]]; then
    echo "Paste session token (from request_session_token MCP call with read permission):"
    read -r TOKEN
fi

# Base URL for the grist-mcp proxy
BASE_URL="${GRIST_MCP_URL:-https://grist-mcp.bballou.com}"

# Download attachment
echo "Downloading attachment $ATTACHMENT_ID to $OUTPUT_FILE..."
HTTP_CODE=$(curl -s -w "%{http_code}" -o "$OUTPUT_FILE" \
    -H "Authorization: Bearer $TOKEN" \
    "$BASE_URL/api/v1/attachments/$ATTACHMENT_ID")

if [[ "$HTTP_CODE" -eq 200 ]]; then
    FILE_SIZE=$(stat -f%z "$OUTPUT_FILE" 2>/dev/null || stat -c%s "$OUTPUT_FILE" 2>/dev/null)
    echo "Success! Downloaded $FILE_SIZE bytes to $OUTPUT_FILE"
else
    echo "Download failed with HTTP $HTTP_CODE"
    echo "Response:"
    cat "$OUTPUT_FILE"
    rm -f "$OUTPUT_FILE"
    exit 1
fi
