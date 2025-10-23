import json
import sys
from collections import Counter


def load_search_data(filename="search.json"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: {filename} not found. Run search.py first.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {filename}")
        sys.exit(1)


def analyze_issues(response):
    issues = response.get("issues", [])

    total_issues = len(issues)
    is_last_page = response.get("isLast", True)

    statuses = [issue["fields"]["status"] for issue in issues]
    status_counts = Counter((status["id"], status["name"]) for status in statuses)

    assignees = []
    for issue in issues:
        assignee = issue["fields"].get("assignee")
        if assignee:
            assignees.append(assignee["displayName"])
        else:
            assignees.append("Unassigned")

    assignee_counts = Counter(assignees)

    return {
        "total_issues": total_issues,
        "is_last_page": is_last_page,
        "status_counts": status_counts,
        "assignee_counts": assignee_counts,
    }


def print_summary(analysis):
    print(f"Total issues: {analysis['total_issues']}")
    print(f"Last page: {analysis['is_last_page']}")

    print("\nStatus distribution:")
    for status, count in analysis["status_counts"].most_common():
        print(f"  [{status[0]}] {status[1]}: {count}")

    print("\nAssignee distribution:")
    for assignee, count in analysis["assignee_counts"].most_common():
        print(f"  {assignee}: {count}")


def main():
    response = load_search_data()
    analysis = analyze_issues(response)
    print_summary(analysis)


if __name__ == "__main__":
    main()
