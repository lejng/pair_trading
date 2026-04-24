# Commands (os windows)

### 1. Determinate is it virt env or not
```
where pip
```

### 2. Activate virtual env or create virtual env
activate
``` 
# windows
.venv\Scripts\activate

# macos
source .venv/bin/activate
```
create:
```
python -m venv .venv
```

### 3. Install/remove dependencies
```
pip install -r requirements.txt

pip uninstall -r requirements.txt
```

### 4. Deactivate virtual env
```
deactivate
```

### 5. How to run console app
```
python -m src.main
```

### 6. Docker
```
docker-compose up -d --build

docker-compose up --build

docker-compose up

docker-compose down
```

### 7. Run streamlit app
```
# dev mode
streamlit run main_web_app.py
caffeinate -i python pair_trading_handle_open_position.py

# production mode
streamlit run main_web_app.py --server.runOnSave=false --server.fileWatcherType=none --client.toolbarMode=hidden --server.headless=true
```