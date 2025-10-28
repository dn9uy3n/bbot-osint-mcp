#!/bin/bash

# BBOT OSINT MCP - Uninstall Script
# Usage: ./uninstall.sh

set -e

echo "=========================================="
echo "BBOT OSINT MCP - Uninstall Script"
echo "=========================================="
echo ""
echo "Select an option:"
echo "1) Complete removal (delete everything)"
echo "2) Uninstall but keep data"
echo "3) Only delete Neo4j data (reset database)"
echo "4) Cancel"
echo ""
read -p "Your choice (1-4): " choice

case $choice in
  1)
    echo ""
    echo "⚠️  WARNING: This will delete ALL data including:"
    echo "   - Docker containers"
    echo "   - Docker images"
    echo "   - Docker volumes (Neo4j data, Caddy certificates)"
    echo "   - Source code"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    
    if [ "$confirm" != "yes" ]; then
      echo "Cancelled."
      exit 0
    fi
    
    echo ""
    echo "Starting complete removal..."
    
    # Stop and remove containers + volumes
    if [ -d /opt/bbot-osint-mcp ]; then
      cd /opt/bbot-osint-mcp
      echo "→ Stopping containers..."
      sudo docker compose down -v || true
    fi
    
    # Remove images
    echo "→ Removing Docker images..."
    sudo docker rmi bbot-osint-mcp-osint:latest || true
    sudo docker rmi neo4j:5.23.1 || true
    sudo docker rmi caddy:2.8-alpine || true
    
    # Remove source code
    echo "→ Removing source code..."
    cd /opt
    rm -rf /opt/bbot-osint-mcp
    
    echo ""
    echo "✅ Complete removal finished!"
    echo ""
    echo "Remaining Docker resources (if any):"
    sudo docker ps -a | grep bbot || echo "  No containers"
    sudo docker images | grep -E "(bbot|neo4j|caddy)" || echo "  No images"
    sudo docker volume ls | grep bbot || echo "  No volumes"
    ;;
    
  2)
    echo ""
    echo "This will:"
    echo "   - Backup credentials and config"
    echo "   - Stop and remove containers"
    echo "   - Remove Docker images"
    echo "   - Remove source code"
    echo "   - Keep Docker volumes (Neo4j data preserved)"
    echo ""
    read -p "Continue? (y/n): " confirm
    
    if [ "$confirm" != "y" ]; then
      echo "Cancelled."
      exit 0
    fi
    
    echo ""
    echo "Starting uninstall with data preservation..."
    
    # Backup configs
    if [ -f /opt/bbot-osint-mcp/init_config.json ]; then
      echo "→ Backing up config..."
      cp /opt/bbot-osint-mcp/init_config.json ~/bbot-config-backup.json
      echo "  Saved to: ~/bbot-config-backup.json"
    fi
    
    if [ -f /opt/bbot-osint-mcp/secrets/credentials.txt ]; then
      echo "→ Backing up credentials..."
      cp /opt/bbot-osint-mcp/secrets/credentials.txt ~/bbot-credentials-backup.txt
      echo "  Saved to: ~/bbot-credentials-backup.txt"
    fi
    
    # Backup Neo4j volume
    echo "→ Backing up Neo4j data..."
    mkdir -p ~/backups
    sudo docker run --rm \
      -v bbot-osint-mcp_neo4j_data:/data \
      -v ~/backups:/backup \
      ubuntu tar czf /backup/neo4j-data-$(date +%Y%m%d-%H%M%S).tar.gz /data 2>/dev/null || true
    
    # Stop containers (without removing volumes)
    if [ -d /opt/bbot-osint-mcp ]; then
      cd /opt/bbot-osint-mcp
      echo "→ Stopping containers..."
      sudo docker compose down
    fi
    
    # Remove images
    echo "→ Removing Docker images..."
    sudo docker rmi bbot-osint-mcp-osint:latest || true
    sudo docker rmi caddy:2.8-alpine || true
    
    # Remove source
    echo "→ Removing source code..."
    cd /opt
    rm -rf /opt/bbot-osint-mcp
    
    echo ""
    echo "✅ Uninstall completed with data preservation!"
    echo ""
    echo "Backups saved:"
    ls -lh ~/bbot-config-backup.json 2>/dev/null || true
    ls -lh ~/bbot-credentials-backup.txt 2>/dev/null || true
    ls -lh ~/backups/neo4j-data-*.tar.gz 2>/dev/null || true
    echo ""
    echo "Docker volumes preserved:"
    sudo docker volume ls | grep bbot
    echo ""
    echo "To reinstall later:"
    echo "  1. git clone https://github.com/dn9uy3n/bbot-osint-mcp.git"
    echo "  2. cp ~/bbot-config-backup.json bbot-osint-mcp/init_config.json"
    echo "  3. mkdir -p bbot-osint-mcp/secrets"
    echo "  4. cp ~/bbot-credentials-backup.txt bbot-osint-mcp/secrets/credentials.txt"
    echo "  5. cd bbot-osint-mcp && sudo docker compose up -d"
    ;;
    
  3)
    echo ""
    echo "⚠️  WARNING: This will DELETE all Neo4j data!"
    echo "   - All hosts, domains, events will be lost"
    echo "   - Containers will remain running"
    echo ""
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    
    if [ "$confirm" != "yes" ]; then
      echo "Cancelled."
      exit 0
    fi
    
    echo ""
    echo "Deleting Neo4j data..."
    
    if [ -d /opt/bbot-osint-mcp ]; then
      cd /opt/bbot-osint-mcp
      
      # Stop Neo4j
      echo "→ Stopping Neo4j..."
      sudo docker compose stop neo4j
      
      # Remove volume
      echo "→ Removing Neo4j volume..."
      sudo docker volume rm bbot-osint-mcp_neo4j_data
      
      # Restart
      echo "→ Starting Neo4j with fresh database..."
      sudo docker compose up -d neo4j
      
      # Wait for Neo4j to start
      echo "→ Waiting for Neo4j to initialize..."
      sleep 10
      
      # Restart osint service
      echo "→ Restarting OSINT service..."
      sudo docker compose restart osint
      
      echo ""
      echo "✅ Neo4j database has been reset!"
      echo ""
      echo "The scanner will start from scratch on next cycle."
    else
      echo "Error: /opt/bbot-osint-mcp directory not found"
      exit 1
    fi
    ;;
    
  4)
    echo "Cancelled."
    exit 0
    ;;
    
  *)
    echo "Invalid choice."
    exit 1
    ;;
esac

echo ""
echo "Done!"

