#!/bin/bash

# Setup script for Cloudflare Email Worker

set -e

echo "╔════════════════════════════════════════════╗"
echo "║  Cloudflare Email Worker Setup Script     ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Check Node.js
if command -v node >/dev/null 2>&1; then
    NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
    echo "✓ Node.js found: $(node --version)"
    if [ "$NODE_VERSION" -lt 22 ]; then
        echo "⚠ Node.js 22+ recommended (you have version $NODE_VERSION)"
        read -p "Upgrade to Node.js 22? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
            sudo apt-get install -y nodejs
        fi
    fi
else
    echo "⚠ Node.js not found"
    read -p "Install Node.js 22? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
        sudo apt-get install -y nodejs
        echo "✓ Node.js installed"
    fi
fi

# Check Wrangler
if command -v wrangler >/dev/null 2>&1; then
    echo "✓ Wrangler found: $(wrangler --version)"
else
    echo "⚠ Wrangler not found"
    read -p "Install Wrangler? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        npm install -g wrangler
        echo "✓ Wrangler installed"
    fi
fi

# Check Python
if command -v python3 >/dev/null 2>&1; then
    echo "✓ Python found: $(python3 --version)"
else
    echo "⚠ Python 3 not found (needed for viewing emails)"
fi

# Authenticate
echo ""
echo "Checking authentication..."
if wrangler whoami >/dev/null 2>&1; then
    echo "✓ Already authenticated"
else
    read -p "Authenticate with Cloudflare? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        wrangler login
    fi
fi

# Check R2 bucket
echo ""
echo "Checking R2 bucket..."
if wrangler r2 bucket list 2>/dev/null | grep -q "failed-emails"; then
    echo "✓ R2 bucket exists"
else
    echo "⚠ R2 bucket not found"
    read -p "Create bucket 'failed-emails'? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        wrangler r2 bucket create failed-emails
        echo "✓ R2 bucket created"
    fi
fi

# Check .env file
echo ""
if [ -f ".env" ]; then
    echo "✓ .env file exists"
else
    echo "⚠ .env file not found"
    echo "  You'll need to create it from .env.example"
    echo "  See .env.example for R2 API token setup instructions"
fi

# Setup Python venv
echo ""
read -p "Set up Python virtual environment? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    echo "✓ Python virtual environment created and boto3 installed"
    echo ""
    echo "To activate: source .venv/bin/activate"
fi

# Deploy
echo ""
read -p "Deploy worker now? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    wrangler deploy
    echo ""
    echo "✓ Worker deployed!"
fi

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║         Setup Complete! 🎉                 ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. If not done already: cp .env.example .env"
echo "2. Edit .env with your R2 API credentials"
echo "3. Test: source .venv/bin/activate && set -a && source .env && set +a"
echo "4. Run: python3 view_failed_emails.py --stats"
echo "5. Configure email routing in Cloudflare Dashboard"
echo "6. See TESTING.md for testing procedures"
