# Backend on Wintermute
# make sure you're in the venv already
cd ~/Projects/Python/clerk/backend

# start FastAPI in reload mode, bound to the network
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


# Frontend on Wintermute
# make sure you're in the venv already
cd ~/Projects/Python/clerk/frontend
rm -rf .next
npm run dev -- --hostname 0.0.0.0 --port 3000