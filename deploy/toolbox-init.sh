#!/bin/bash
echo "Starting MCP Toolbox server..."
echo "Available tools: nmap, masscan, nuclei, curl, nxc, searchsploit, adscan, adpeas"
exec node /app/mcp-serve.js
