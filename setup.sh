#!/bin/bash

# IBKR Portfolio Manager Setup Script
echo "🚀 Setting up IBKR Portfolio Manager..."

# Create project directory structure
echo "📁 Creating project structure..."
mkdir -p ibkr_portfolio_manager/{logs,snapshots,data}
cd ibkr_portfolio_manager

# Create requirements.txt
echo "📋 Creating requirements.txt..."
cat > requirements.txt << EOF
ib-insync>=0.9.86
pandas>=1.3.0
nest-asyncio>=1.5.0
numpy>=1.21.0
python-dotenv>=0.19.0
EOF

# Create .env template
echo "⚙️ Creating .env template..."
cat > .env.template << EOF
# IBKR Connection Settings
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Monitoring Settings
MONITORING_REFRESH_INTERVAL=30
LOG_LEVEL=INFO

# Optional: Email Alert Settings (leave empty to disable)
EMAIL_SMTP_SERVER=
EMAIL_PORT=
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_RECIPIENTS=
EOF

# Create .gitignore
echo "🚫 Creating .gitignore..."
cat > .gitignore << EOF
# Environment files
.env
*.env

# Log files
logs/
*.log

# Snapshots and data
snapshots/
data/
*.json
*.csv
*.xlsx

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
EOF

# Create README.md
echo "📖 Creating README.md..."
cat > README.md << EOF
# IBKR Portfolio Manager

A Python application for monitoring Interactive Brokers portfolios using the TWS API.

## Quick Start

1. **Install dependencies:**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

2. **Configure IBKR TWS/Gateway:**
   - Start TWS or IB Gateway
   - Enable API: Configure → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Set socket port: 7497 (paper) or 7496 (live)

3. **Test connection:**
   \`\`\`bash
   python cli.py test
   \`\`\`

4. **View portfolio:**
   \`\`\`bash
   python cli.py summary
   python cli.py positions
   \`\`\`

5. **Start monitoring:**
   \`\`\`bash
   python cli.py monitor
   \`\`\`

## Commands

- \`python cli.py test\` - Test IBKR connection
- \`python cli.py summary\` - Show account summary  
- \`python cli.py positions\` - Show portfolio positions
- \`python cli.py orders\` - Show open orders
- \`python cli.py snapshot\` - Save portfolio snapshot
- \`python cli.py monitor\` - Start continuous monitoring

## Configuration

Copy \`.env.template\` to \`.env\` and customize settings.

## Ports Reference

| Service | Paper | Live |
|---------|-------|------|
| TWS | 7497 | 7496 |
| Gateway | 4001 | 4000 |

## Safety

⚠️ Always test with paper trading first!
EOF

# Create a simple run script
echo "🏃 Creating run script..."
cat > run.sh << EOF
#!/bin/bash
# Quick start script for IBKR Portfolio Manager

echo "IBKR Portfolio Manager"
echo "====================="
echo ""
echo "Available commands:"
echo "1. Test connection"
echo "2. Show account summary"  
echo "3. Show positions"
echo "4. Show open orders"
echo "5. Save snapshot"
echo "6. Start monitoring"
echo "7. Exit"
echo ""

while true; do
    read -p "Select option (1-7): " choice
    case \$choice in
        1) python cli.py test ;;
        2) python cli.py summary ;;
        3) python cli.py positions ;;
        4) python cli.py orders ;;
        5) python cli.py snapshot ;;
        6) python cli.py monitor ;;
        7) echo "Goodbye!"; break ;;
        *) echo "Invalid option. Please select 1-7." ;;
    esac
    echo ""
done
EOF

chmod +x run.sh

# Check if Python is available
echo "🐍 Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python not found. Please install Python 3.7+ first."
    exit 1
fi

echo "✅ Found Python: $($PYTHON_CMD --version)"

# Install dependencies
echo "📦 Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
    pip3 install -r requirements.txt
elif command -v pip &> /dev/null; then
    pip install -r requirements.txt
else
    echo "❌ pip not found. Please install pip first."
    exit 1
fi

# Create startup instructions
echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Start TWS or IB Gateway"
echo "2. Enable API access in TWS settings"
echo "3. Run: python cli.py test"
echo "4. Run: ./run.sh for interactive menu"
echo ""
echo "Project structure:"
echo "├── main.py           # Main portfolio manager"
echo "├── cli.py            # Command line interface"  
echo "├── config.py         # Configuration settings"
echo "├── run.sh            # Interactive menu script"
echo "├── requirements.txt  # Python dependencies"
echo "├── .env.template     # Environment variables template"
echo "├── logs/             # Log files directory"
echo "└── snapshots/        # Portfolio snapshots directory"
echo ""
echo "Documentation: README.md"
echo ""

# Final check
if [[ ! -f "main.py" ]]; then
    echo "⚠️  Note: You'll need to create the main.py, cli.py, and config.py files"
    echo "    Copy them from the artifacts provided in the setup instructions."
fi
EOF