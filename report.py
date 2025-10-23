import argparse
import json
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from dateutils import strptime, datetime_compare


def find_at_time(changelog, date, issue_id, timeline_key, inclusive=False):
    previous = None
    items = changelog[issue_id][timeline_key]

    for item in items:
        diff = datetime_compare(item["date"], date)
        if diff < 0 or (inclusive and diff == 0):
            previous = item.copy()
        else:
            break

    return previous or items[0]


def map_issues(response):
    issue_map = {}
    for issue in response["issues"]:
        issue_map[issue["id"]] = (
            # Use first occurrence since issues are sorted by creation date desc
            {
                "key": issue["key"],
                "title": issue["fields"]["summary"],
                "timeestimate": issue["fields"]["timeestimate"],
            }
            if issue["id"] not in issue_map
            else issue_map[issue["id"]]
        )

    return issue_map


def map_assignees(response):
    assignee_map = {}
    for issue in response["issues"]:
        for history in issue["changelog"]["histories"]:
            for item in history["items"]:
                if (
                    item["field"] == "assignee"
                    and item["fieldtype"] == "jira"
                    and item["to"] is not None
                ):
                    assignee_map[item["to"]] = (
                        {
                            "name": item["toString"],
                            "created": history["created"],
                        }
                        if item["to"] not in assignee_map
                        or strptime(history["created"])
                        > strptime(assignee_map[item["to"]]["created"])
                        else assignee_map[item["to"]]
                    )
    return assignee_map


def build_changelog(response):
    """
    Example:
        {
            "12345": {
                "statuses": [
                    {"date": "2023-01-01T10:00:00.000+0000", "from": None, "to": "10001"},
                    {"date": "2023-01-02T14:30:00.000+0000", "from": "10001", "to": "10111"}
                ],
                "assignees": [
                    {"date": "2023-01-01T10:00:00.000+0000", "from": None, "to": "user123"},
                    {"date": "2023-01-03T09:15:00.000+0000", "from": "user123", "to": "user456"}
                ]
            }
        }
    """

    changelog = {}

    for issue in response["issues"]:
        status_changes = []
        assignee_changes = []

        for history in issue["changelog"]["histories"]:
            for item in history["items"]:
                if item["field"] == "status" and item["fieldtype"] == "jira":
                    status_changes.append(
                        {
                            "date": history["created"],
                            "from": item["from"],
                            "to": item["to"],
                        }
                    )
                elif item["field"] == "assignee" and item["fieldtype"] == "jira":
                    assignee_changes.append(
                        {
                            "date": history["created"],
                            "from": item["from"],
                            "to": item["to"],
                        }
                    )

        initial_status = {
            "date": issue["fields"]["created"],
            "from": None,
            "to": (
                status_changes[-1]["from"]
                if len(status_changes) > 0
                else issue["fields"]["status"]["id"]
            ),
        }

        initial_assignee = {
            "date": issue["fields"]["created"],
            "from": None,
            "to": (
                assignee_changes[-1]["from"]
                if len(assignee_changes) > 0
                else issue["fields"]["assignee"]["accountId"]
                if issue["fields"]["assignee"] is not None
                else None
            ),
        }

        changelog[issue["id"]] = {
            "statuses": (status_changes + [initial_status])[::-1],
            "assignees": (assignee_changes + [initial_assignee])[::-1],
        }

    return changelog


def calculate_workload(changelog, target_status):
    """
    Example:
        {
            "issue-id-1": {
                "assignee-id-2": 2.0,
                "assignee-id-1": 1.0
            }
        }
    """

    per_issue = {}
    for issue_id, fields in changelog.items():
        target_status_idx = [
            i
            for i, log in enumerate(fields["statuses"])
            if log["from"] == target_status
        ]
        assignee_idx = 0

        for i in target_status_idx:
            start = strptime(fields["statuses"][i - 1]["date"])
            end = strptime(fields["statuses"][i]["date"])

            while assignee_idx < len(fields["assignees"]):
                date = strptime(fields["assignees"][assignee_idx]["date"])
                assignee = fields["assignees"][assignee_idx]["from"]

                if date < start:
                    assignee_idx += 1
                    continue

                per_issue.setdefault(issue_id, {}).setdefault(assignee, 0)

                if date < end:
                    per_issue[issue_id][assignee] += datetime_compare(date, start)
                    start = date
                    assignee_idx += 1
                    continue

                per_issue[issue_id][assignee] += datetime_compare(end, start)
                break

    return per_issue


def group_by_lead(workloads):
    per_leads = {}

    for issue_id, assignee_scores in workloads.items():
        if assignee_scores:
            lead_assignee = max(assignee_scores, key=assignee_scores.get)
            lead_score = assignee_scores[lead_assignee]

            per_leads.setdefault(lead_assignee, {})
            per_leads[lead_assignee][issue_id] = lead_score

    return per_leads


def issue_report(workloads, issues, assignee_map):
    print("=== Issues Report ===")

    for issue_id in workloads:
        issue_info = issues.get(issue_id, {"key": "UNKNOWN", "title": "Unknown Issue"})
        print(f"\n{issue_info['key']} [{issue_id}]: {issue_info['title']} ===")

        # Get assignees for this issue and sort by score (descending)
        assignees_scores = workloads[issue_id]
        sorted_assignees = sorted(
            assignees_scores.items(), key=lambda x: x[1], reverse=True
        )

        if not sorted_assignees:
            print("  No assignees found")
            continue

        for assignee_id, score in sorted_assignees:
            assignee_name = assignee_map.get(assignee_id, {}).get(
                "name", f"Unknown ({assignee_id})"
            )
            print(f"  {assignee_name}: {score:.2f}")
    print("\n")


def assignee_report(workloads, issues, assignee_map):
    print("=== Assignees Report ===")

    groupped = group_by_lead(workloads)

    for assignee_id in groupped:
        assignee_name = assignee_map.get(assignee_id, {}).get("name", "Unknown")

        issues_scores = groupped[assignee_id]

        total_timeestimate = sum(
            issues.get(issue_id, {}).get("timeestimate", None) or 0
            for issue_id in issues_scores
        )

        print(
            f"\n{assignee_name} [{assignee_id}]: {total_timeestimate / 3600:.2f} hours ==="
        )

        sorted_issues = sorted(issues_scores.items(), key=lambda x: x[1], reverse=True)

        if not sorted_issues:
            print("  No issues found")
            continue

        for issue_id, _ in sorted_issues:
            issue_info = issues.get(
                issue_id,
                {"key": "UNKNOWN", "title": "Unknown Issue", "timeestimate": 0},
            )
            timeestimate = issue_info["timeestimate"] or 0
            print(
                f"  {issue_info['key']} [{issue_id}]: {issue_info['title']} - {timeestimate / 3600:.2f} hours"
            )
    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate JIRA development metrics reports"
    )
    parser.add_argument(
        "--status",
        choices=["development", "review"],
        default="development",
        help="Issue status to report on (default: development)",
    )
    parser.add_argument(
        "--report",
        choices=["issue", "assignee", "both", "none"],
        default="assignee",
        help="Type of report to generate (default: assignee)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug output (shows changelog, workload, and maps)",
    )

    args = parser.parse_args()

    status_map = {
        "development": "10111",  # In progress
        "review": "10359",  # In code review
    }

    load_dotenv()
    status_id = status_map[args.status]

    with open("search.json", "r", encoding="utf-8") as f:
        response = json.load(f)

    issue_map = map_issues(response)
    assignee_map = map_assignees(response)

    changelog = build_changelog(response)
    workload = calculate_workload(changelog, status_id)

    # Debug output when verbose is enabled
    if args.verbose:
        print("=== DEBUG: Issue Map ===")
        print(json.dumps(issue_map, indent=2))
        print("\n=== DEBUG: Assignee Map ===")
        print(json.dumps(assignee_map, indent=2))
        print("\n=== DEBUG: Changelog ===")
        print(json.dumps(changelog, indent=2))
        print("\n=== DEBUG: Workload ===")
        print(json.dumps(workload, indent=2))
        print("\n")

    # Generate reports based on user selection
    if args.report == "issue" or args.report == "both":
        issue_report(workload, issue_map, assignee_map)
    if args.report == "assignee" or args.report == "both":
        assignee_report(workload, issue_map, assignee_map)


if __name__ == "__main__":
    main()
