import argparse
import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth


class Config:
    def __init__(self):
        load_dotenv()
        self.jira_url = os.getenv("JIRA_URL")
        self.email = os.getenv("JIRA_USER_EMAIL")
        self.api_token = os.getenv("JIRA_USER_API_TOKEN")
        self.project = os.getenv("JIRA_PROJECT")

    def validate(self):
        if not all([self.jira_url, self.email, self.api_token, self.project]):
            print(
                "Error: Missing required environment variables. Check your .env file."
            )
            sys.exit(1)


class JiraClient:
    def __init__(self, config):
        self.config = config
        self.auth = HTTPBasicAuth(config.email, config.api_token)
        self.url = f"{config.jira_url}/rest/api/3/search/jql"
        self.headers = {"Accept": "application/json"}

    def search(self, jql, max_results=100, fields="*all", expand="changelog"):
        query = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields,
            "expand": expand,
        }
        response = requests.get(
            self.url, headers=self.headers, params=query, auth=self.auth
        )
        response.raise_for_status()
        return response.json()


def valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: '{date_str}'. {str(e)}")


def parse_args():
    parser = argparse.ArgumentParser(description="Search JIRA issues")
    parser.add_argument(
        "-s", "--start-date", type=valid_date, help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "-e", "--end-date", type=valid_date, help="End date (YYYY-MM-DD)"
    )
    parser.add_argument("--max-results", type=int, default=100, help="Max results")
    parser.add_argument("--expand", default="changelog", help="Expand fields")
    parser.add_argument("--fields", default="*all", help="Fields to return")
    parser.add_argument("-i", "--issue-keys", nargs="*", help="Issue keys")

    args = parser.parse_args()

    if not args.issue_keys and (not args.start_date or not args.end_date):
        parser.error("--start-date and --end-date required when no issue keys provided")

    return args


def build_jql(args, project):
    if args.issue_keys:
        return "key in (" + ",".join(args.issue_keys) + ")"
    return f"project = {project} and updated >= {args.start_date} and updated <= {args.end_date} and status not in ('To Do', 'To Be Prepared', 'Ready for Development', 'In Code Review', 'in progress')"


def save_results(data, filename="search.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, sort_keys=True, indent=4, separators=(",", ": "))


def main():
    config = Config()
    config.validate()

    args = parse_args()
    client = JiraClient(config)

    jql = build_jql(args, config.project)
    print(f"JQL Query: {jql}")

    results = client.search(jql, args.max_results, args.fields, args.expand)

    save_results(results)
    print(f"Saved {len(results.get('issues', []))} issues to search.json")


if __name__ == "__main__":
    main()
