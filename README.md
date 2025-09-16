# jira-dev-metrics

A Python CLI tool for analyzing JIRA developer productivity metrics.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your JIRA credentials
```

## Usage

1. Search JIRA issues:
```bash
python search.py -s 2025-09-01 -e 2025-09-30
```

2. View latest search result info:
```bash
python info.py
``` 

3. Generate reports:
```bash
python report.py --report both
```
