#!/bin/bash
# Run the stock signal bot in the background on your local Mac/Linux machine.
# Logs go to logs/main.log. PID stored in .pid file.
# Usage: ./run_background.sh start | stop | status | restart

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.pid"
LOG_FILE="$SCRIPT_DIR/logs/main.log"
PYTHON="$SCRIPT_DIR/venv/bin/python"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Already running (PID $(cat "$PID_FILE"))"
        return
    fi
    mkdir -p "$SCRIPT_DIR/logs"
    cd "$SCRIPT_DIR"
    nohup "$PYTHON" main.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started (PID $!). Dashboard → http://localhost:8501"
    echo "Logs → tail -f $LOG_FILE"
}

stop() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null && echo "Stopped (PID $PID)" || echo "Process not found"
        rm -f "$PID_FILE"
    else
        echo "Not running"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Running (PID $(cat "$PID_FILE"))"
        echo "Last health ping: $(tail -1 "$SCRIPT_DIR/logs/health.log" 2>/dev/null || echo 'none')"
    else
        echo "Not running"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 2; start ;;
    status)  status ;;
    *)       echo "Usage: $0 start|stop|restart|status" ;;
esac
