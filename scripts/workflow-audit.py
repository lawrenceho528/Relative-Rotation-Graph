import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
UPDATE_WORKFLOW = ROOT / ".github" / "workflows" / "update-data.yml"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-pages.yml"


def main():
    update = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    deploy = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    require('cron: "30 22 * * 1-5"' in update, "RRG data update workflow must run after U.S. market close")
    require("workflow_dispatch:" in update, "RRG data update workflow must support manual runs")
    require("contents: write" in update, "RRG data update workflow must be allowed to commit data")
    require("python scripts/update_rrg_data.py --provider stooq" in update, "RRG data update workflow must run updater")
    require("git-auto-commit-action@v5" in update, "RRG data update workflow must commit updated data")
    require("file_pattern: public/data/rrg.json" in update, "RRG data update workflow must only commit generated data")

    require("workflow_dispatch:" in deploy, "deploy workflow must support manual runs")
    require(re.search(r"push:\s+branches:\s+- main", deploy), "deploy workflow must run on pushes to main")
    require("pages: write" in deploy and "id-token: write" in deploy, "deploy workflow must have Pages permissions")
    require("./scripts/prepare-dist.ps1" in deploy, "deploy workflow must prepare dist artifact")
    require("actions/upload-pages-artifact@v3" in deploy and "path: dist" in deploy, "deploy workflow must upload dist")
    require("actions/deploy-pages@v4" in deploy, "deploy workflow must deploy to GitHub Pages")

    print("Workflow audit passed: updateSchedule=22:30UTC weekdays deploysDist=true")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
