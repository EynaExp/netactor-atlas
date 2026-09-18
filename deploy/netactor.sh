#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${SCRIPT_DIR}/.env"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    if ! docker-compose --version &> /dev/null 2>&1; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
}

check_env() {
    if [ ! -f "$ENV_FILE" ]; then
        log_warn ".env file not found. Creating from .env.example..."
        cp "${SCRIPT_DIR}/.env.example" "$ENV_FILE"
        log_warn "Please edit .env file with your configuration before starting"
        exit 1
    fi

    source "$ENV_FILE"

    if [ -z "$LLM_API_KEY" ] || [ "$LLM_API_KEY" = "your-api-key-here" ]; then
        log_error "Please set LLM_API_KEY in .env file"
        exit 1
    fi

    if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "change-me-in-production" ]; then
        log_warn "Generating random JWT_SECRET..."
        NEW_SECRET=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '\n' | head -c 64)
        sed -i "s/JWT_SECRET=.*/JWT_SECRET=${NEW_SECRET}/" "$ENV_FILE"
        source "$ENV_FILE"
        log_success "JWT_SECRET generated"
    fi
}

cmd_start() {
    log_info "Starting NetActor..."
    check_docker
    check_env

    cd "$PROJECT_ROOT"

    log_info "Building container..."
    docker-compose build --no-cache

    log_info "Starting..."
    docker-compose up -d

    log_success "NetActor started!"
    log_info "URL: http://localhost:${APP_PORT:-8000}"
    log_info "Default login: admin / admin123"
    log_warn "Change default password after first login!"
}

cmd_stop() {
    log_info "Stopping NetActor..."
    check_docker

    cd "$PROJECT_ROOT"
    docker-compose down

    log_success "NetActor stopped"
}

cmd_restart() {
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    check_docker

    cd "$PROJECT_ROOT"

    echo ""
    log_info "NetActor Status:"
    echo "----------------------------------------"
    docker-compose ps
    echo "----------------------------------------"

    if curl -s http://localhost:${APP_PORT:-8000}/health > /dev/null 2>&1; then
        log_success "App is healthy"
    else
        log_warn "App is not responding"
    fi

    if curl -s http://localhost:3001/health > /dev/null 2>&1; then
        log_success "MCP toolbox is healthy"
    else
        log_warn "MCP toolbox is not responding"
    fi
}

cmd_logs() {
    check_docker

    cd "$PROJECT_ROOT"
    docker-compose logs -f --tail=100
}

cmd_build() {
    log_info "Building NetActor container..."
    check_docker
    check_env

    cd "$PROJECT_ROOT"
    docker-compose build --no-cache

    log_success "Build complete!"
}

cmd_clean() {
    log_info "Cleaning up NetActor..."
    check_docker

    cd "$PROJECT_ROOT"
    docker-compose down -v --rmi all

    log_success "Cleanup complete!"
}

show_help() {
    echo ""
    echo "NetActor - AI-Powered Penetration Testing Platform"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start       Build and start the container"
    echo "  stop        Stop the container"
    echo "  restart     Restart the container"
    echo "  status      Show container status"
    echo "  logs        Show logs (follow)"
    echo "  build       Build container without starting"
    echo "  clean       Remove container, volumes, and images"
    echo "  help        Show this help message"
    echo ""
    echo "Configuration:"
    echo "  Edit .env file to configure LLM API key, ports, etc."
    echo ""
}

case "${1:-help}" in
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    restart)    cmd_restart ;;
    status)     cmd_status ;;
    logs)       cmd_logs ;;
    build)      cmd_build ;;
    clean)      cmd_clean ;;
    help|*)     show_help ;;
esac
