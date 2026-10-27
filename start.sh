# Source this at the start of every terminal session:  source start.sh
cd ~/code/VALID && source .venv/bin/activate
export PYTHONWARNINGS=ignore::FutureWarning
if [ -z "$GEMINI_API_KEY" ]; then read -s "?Gemini key (hidden): " GEMINI_API_KEY; export GEMINI_API_KEY; echo; fi
echo "ready: $(python --version), key ${GEMINI_API_KEY:+set}"
