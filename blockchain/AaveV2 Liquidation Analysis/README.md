# AAVEv2 Liquidations

Code for AAVEv2 Liquidation report.

### How to use

1. Create venv and install packages
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. Put api key in .env
```
echo "API_KEY=your_api_key_here" > .env
```

1. Fetch data using `get_data.py`. This will put some files in `data/`
```
mkdir data
python -m get_data
```

1. Run analysis in `main.py`. Graphs will open in Chrome and statistics will be
   printed to stdout.
```
python -m main
```
