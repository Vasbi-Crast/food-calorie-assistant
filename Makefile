STREAMLIT_APP = main_page.py
FASTAPI_APP = service

.PHONY: run_app stop attach_backend attach_frontend peek

run_app:
	@echo "🚀 Starting Backend..."
	@tmux kill-session -t backend 2>/dev/null || true
	@tmux new-session -d -s backend "cd backend && uvicorn $(FASTAPI_APP):app --reload"
	
	@echo "🚀 Starting Frontend..."
	@tmux kill-session -t frontend 2>/dev/null || true
	@tmux new-session -d -s frontend "cd frontend && streamlit run $(STREAMLIT_APP)"
	
	@sleep 1
	@echo "✅ Both apps running in tmux (detached)"
	@echo "👀 Quick peek: make peek"
	@echo "🛑 Stop: make stop"

peek:
	@echo "📦 Backend output:"
	@tmux capture-pane -t backend -p 2>/dev/null || echo "  (not running)"
	@echo "------------------------"
	@echo "🎨 Frontend output:"
	@tmux capture-pane -t frontend -p 2>/dev/null || echo "  (not running)"

stop:
	@echo "🛑 Stopping sessions..."
	@tmux kill-session -t backend 2>/dev/null || true
	@tmux kill-session -t frontend 2>/dev/null || true
	@echo "Stopped."